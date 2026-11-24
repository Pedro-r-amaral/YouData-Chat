"""Clientes de LLM intercambiáveis. A lógica de segurança NÃO depende de qual modelo é usado."""
from __future__ import annotations

from typing import Protocol

import requests

from .config import Settings


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str: ...


class OllamaClient:
    """Modelo local (ex.: qwen2.5-coder). Bom para dados que não podem sair da empresa."""

    def __init__(self, url: str, model: str):
        self.url, self.model = url.rstrip("/"), model
        self.name = f"ollama:{model}"

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        try:
            resp = requests.post(
                f"{self.url}/api/chat",
                json={"model": self.model, "stream": False,
                      "options": {"temperature": 0, "num_predict": max_tokens},
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": user}]},
                timeout=120)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as exc:
            raise LLMError(f"Falha ao chamar o Ollama: {exc}") from exc


class AnthropicClient:
    """API da Anthropic (usada no deploy público, onde não há Ollama)."""

    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.name = f"anthropic:{model}"

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}])
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        except Exception as exc:
            raise LLMError(f"Falha ao chamar a API: {exc}") from exc


def build_client(settings: Settings) -> LLMClient | None:
    """None => modo demonstração (sem LLM)."""
    if settings.provider == "ollama":
        return OllamaClient(settings.ollama_url, settings.ollama_model)
    if settings.provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)
    return None
