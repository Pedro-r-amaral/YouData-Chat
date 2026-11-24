"""Camada determinística de segurança: a LLM propõe, este módulo decide.

Nada que a LLM escreve chega ao banco sem passar por validate_sql().
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .schema import ALLOWED_RELATIONS


class UnsafeQueryError(ValueError):
    """Consulta rejeitada. retryable=False => tentativa de escrita/ataque: não pedir nova tentativa."""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


FORBIDDEN_KEYWORDS = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "ATTACH", "DETACH",
    "PRAGMA", "VACUUM", "REINDEX", "LOAD_EXTENSION", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "MERGE", "CALL", "COPY", "UPSERT", "SAVEPOINT", "BEGIN", "COMMIT", "ROLLBACK",
})

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_LITERAL = re.compile(r"'(?:[^']|'')*'")
_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_REPLACE_INTO = re.compile(r"\breplace\s+into\b", re.IGNORECASE)
_COMMA_JOIN = re.compile(r"\bfrom\s+[a-z_]\w*(?:\s+(?:as\s+)?[a-z_]\w*)?\s*,", re.IGNORECASE)
_RELATION = re.compile(r"\b(?:from|join)\s+([a-z_]\w*)", re.IGNORECASE)
_CTE_NAME = re.compile(r"\b([a-z_]\w*)\s+as\s*\(", re.IGNORECASE)
_HAS_FINAL_LIMIT = re.compile(r"\blimit\s+\d+(\s+offset\s+\d+)?\s*$", re.IGNORECASE)


@dataclass(frozen=True)
class ValidatedQuery:
    sql: str
    relations: frozenset[str]
    limit_injected: bool


def extract_sql(raw: str) -> str:
    """Remove cercas de markdown (```sql) e o ';' final que LLMs costumam adicionar."""
    match = _FENCE.search(raw)
    sql = match.group(1) if match else raw
    return sql.strip().rstrip(";").strip()


def validate_sql(sql: str, allowed_relations: frozenset[str] = ALLOWED_RELATIONS,
                 row_limit: int = 100) -> ValidatedQuery:
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise UnsafeQueryError("Consulta vazia.")

    # Literais de texto não podem esconder palavras proibidas nem ';' / comentários.
    masked = _LITERAL.sub(" __lit__ ", sql)
    if "'" in masked:
        raise UnsafeQueryError("Aspas simples desbalanceadas.")
    if any(ch in masked for ch in ('"', "`", "[")):
        raise UnsafeQueryError("Identificadores entre aspas/colchetes não são permitidos.")
    if "--" in masked or "/*" in masked:
        raise UnsafeQueryError("Comentários SQL não são permitidos.")
    # Tentativas de escrita são verificadas PRIMEIRO e nunca geram nova tentativa ao modelo.
    tokens = set(re.findall(r"[A-Za-z_]+", masked.upper()))
    bad = sorted(tokens & FORBIDDEN_KEYWORDS)
    if bad or _REPLACE_INTO.search(masked):
        raise UnsafeQueryError(
            f"Operação não permitida (somente leitura): {', '.join(bad) or 'REPLACE INTO'}.",
            retryable=False)

    if ";" in masked:
        raise UnsafeQueryError("Apenas uma instrução por consulta.")
    if not _START.match(masked):
        raise UnsafeQueryError("A consulta deve começar com SELECT ou WITH.")

    if _COMMA_JOIN.search(masked):
        raise UnsafeQueryError("Use JOIN explícito em vez de vírgula no FROM.")

    ctes = {m.lower() for m in _CTE_NAME.findall(masked)}
    relations = {m.lower() for m in _RELATION.findall(masked)}
    unknown = sorted(relations - allowed_relations - ctes)
    if unknown:
        raise UnsafeQueryError(f"Relações fora da camada semântica: {', '.join(unknown)}.")

    limit_injected = False
    if not _HAS_FINAL_LIMIT.search(masked):
        sql = f"{sql}\nLIMIT {row_limit}"
        limit_injected = True
    return ValidatedQuery(sql=sql, relations=frozenset(relations - ctes), limit_injected=limit_injected)
