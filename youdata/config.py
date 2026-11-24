"""Configuração central. Lê variáveis de ambiente ou st.secrets (Streamlit Cloud)."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:  # st.secrets só existe quando rodando no Streamlit
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


@dataclass(frozen=True)
class Settings:
    provider: str                 # "demo" | "ollama" | "anthropic"
    ollama_url: str
    ollama_model: str
    anthropic_api_key: str | None
    anthropic_model: str
    db_path: Path
    row_limit: int                # LIMIT injetado automaticamente
    max_fetch_rows: int           # teto duro de linhas lidas do banco
    query_timeout_s: float
    max_questions: int            # perguntas livres (com LLM) por sessão
    max_attempts: int             # tentativas de gerar SQL válido


def load_settings() -> Settings:
    key = get_setting("ANTHROPIC_API_KEY")
    provider = (get_setting("LLM_PROVIDER") or ("anthropic" if key else "demo")).lower()
    return Settings(
        provider=provider,
        ollama_url=get_setting("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=get_setting("OLLAMA_MODEL", "qwen2.5-coder:7b"),
        anthropic_api_key=key,
        anthropic_model=get_setting("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        db_path=Path(tempfile.gettempdir()) / "youdata_demo.db",
        row_limit=100,
        max_fetch_rows=200,
        query_timeout_s=5.0,
        max_questions=int(get_setting("MAX_QUESTIONS", "20")),
        max_attempts=2,
    )
