"""Execução somente leitura: 3 travas independentes (arquivo ro, query_only e authorizer)."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pandas as pd

# Códigos de ação do SQLite (valores numéricos para funcionar em qualquer versão do Python)
_OK, _DENY = 0, 1
_ALLOWED_ACTIONS = {
    21,  # SQLITE_SELECT
    20,  # SQLITE_READ
    31,  # SQLITE_FUNCTION
    33,  # SQLITE_RECURSIVE
}


class QueryExecutionError(RuntimeError):
    pass


def _authorizer(action, arg1, arg2, dbname, source):
    return _OK if action in _ALLOWED_ACTIONS else _DENY


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"       # trava 1: arquivo aberto como leitura
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON")                    # trava 2: escrita recusada pelo motor
    conn.set_authorizer(_authorizer)                          # trava 3: só SELECT/READ/FUNCTION
    return conn


def execute_readonly(conn: sqlite3.Connection, sql: str, max_rows: int = 200,
                     timeout_s: float = 5.0) -> pd.DataFrame:
    deadline = time.monotonic() + timeout_s
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    try:
        cur = conn.execute(sql)
        columns = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(max_rows + 1)
    except sqlite3.Error as exc:
        raise QueryExecutionError(str(exc)) from exc
    finally:
        conn.set_progress_handler(None, 0)

    df = pd.DataFrame(rows[:max_rows], columns=columns)
    df.attrs["truncated"] = len(rows) > max_rows
    return df
