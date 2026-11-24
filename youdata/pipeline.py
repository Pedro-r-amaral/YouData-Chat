"""Pipeline de 3 camadas: (1) texto → SQL, (2) validação + execução somente leitura, (3) dados → texto."""
from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

from . import prompts
from .config import Settings
from .db import QueryExecutionError, connect_readonly, execute_readonly
from .llm import LLMClient, LLMError
from .schema import ALLOWED_RELATIONS, describe_views
from .security import UnsafeQueryError, extract_sql, validate_sql
from .suggestions import Suggestion


@dataclass
class QueryResult:
    question: str
    sql: str | None = None
    df: pd.DataFrame | None = None
    answer: str = ""
    error: str | None = None
    attempts: int = 0
    mode: str = "llm"            # "llm" | "demo"
    elapsed_s: float = 0.0
    limit_injected: bool = False


def fallback_summary(df: pd.DataFrame) -> str:
    """Resumo mecânico (sem IA) usado no modo demonstração ou se a explicação falhar."""
    if df.empty:
        return "Nenhum registro atendeu ao filtro."
    first = ", ".join(f"{c} = {v}" for c, v in df.iloc[0].items())
    return f"A consulta retornou {len(df)} linha(s). Primeira linha: {first}."


def _run_sql(sql_raw: str, settings: Settings):
    vq = validate_sql(sql_raw, ALLOWED_RELATIONS, settings.row_limit)
    conn = connect_readonly(settings.db_path)
    try:
        df = execute_readonly(conn, vq.sql, settings.max_fetch_rows, settings.query_timeout_s)
    finally:
        conn.close()
    return vq, df


def answer_demo(suggestion: Suggestion, settings: Settings) -> QueryResult:
    """Modo demonstração: usa o SQL pré-escrito, mas passa pela MESMA validação e execução."""
    t0 = time.monotonic()
    res = QueryResult(question=suggestion.question, mode="demo", attempts=1)
    try:
        vq, df = _run_sql(suggestion.sql, settings)
    except (UnsafeQueryError, QueryExecutionError) as exc:
        res.error = str(exc)
    else:
        res.sql, res.df, res.limit_injected = vq.sql, df, vq.limit_injected
        res.answer = "🛈 Resumo automático (modo demonstração, sem IA): " + fallback_summary(df)
    res.elapsed_s = time.monotonic() - t0
    return res


def answer_with_llm(question: str, llm: LLMClient, settings: Settings) -> QueryResult:
    t0 = time.monotonic()
    res = QueryResult(question=question, mode="llm")
    schema_text = describe_views(settings.db_path)
    system = prompts.build_sql_system(schema_text)
    user_prompt = prompts.build_sql_user(question)
    sql_raw = ""

    for attempt in range(1, settings.max_attempts + 1):
        res.attempts = attempt
        try:
            sql_raw = extract_sql(llm.complete(system, user_prompt))
            if sql_raw == prompts.OUT_OF_SCOPE_SQL:
                res.error = "Essa pergunta não pode ser respondida com os dados disponíveis."
                break
            vq, df = _run_sql(sql_raw, settings)
        except LLMError as exc:
            res.error = str(exc)
            break
        except (UnsafeQueryError, QueryExecutionError) as exc:
            res.sql, res.error = sql_raw or None, str(exc)
            if isinstance(exc, UnsafeQueryError) and not exc.retryable:
                break                                   # tentativa de escrita: bloqueia sem reenviar ao modelo
            user_prompt = prompts.build_repair_user(question, sql_raw, str(exc), schema_text)
            continue
        else:
            res.sql, res.df, res.error, res.limit_injected = vq.sql, df, None, vq.limit_injected
            break

    if res.error is None and res.df is not None:
        if res.df.empty:
            res.answer = "Nenhum registro atendeu aos critérios da consulta."
        else:
            try:
                res.answer = llm.complete(prompts.explain_system(),
                                          prompts.build_explain_user(question, res.sql, res.df), 400).strip()
            except LLMError:
                res.answer = "Resumo automático: " + fallback_summary(res.df)
    res.elapsed_s = time.monotonic() - t0
    return res