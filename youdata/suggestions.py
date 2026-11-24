"""Perguntas sugeridas. O SQL pré-validado só é usado no modo demonstração (sem LLM)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Suggestion:
    id: str
    label: str
    question: str
    sql: str


SUGGESTED = [
    Suggestion(
        "estorno_marcas", "📉 Marcas com estorno > 5% via creators",
        "Quais marcas tiveram mais de 5% de estorno nas vendas via creators nos últimos 30 dias?",
        """SELECT marca,
       COUNT(*) AS total_vendas,
       SUM(status IN ('Reembolsada','Chargeback')) AS estornos,
       ROUND(100.0 * SUM(status IN ('Reembolsada','Chargeback')) / COUNT(*), 1) AS taxa_estorno_pct
FROM v_vendas
WHERE canal = 'creator' AND data_venda >= date('now','-30 day')
GROUP BY marca
HAVING 100.0 * SUM(status IN ('Reembolsada','Chargeback')) / COUNT(*) > 5
ORDER BY taxa_estorno_pct DESC"""),
    Suggestion(
        "top_cosmeticos", "💄 Top creators em Cosméticos (receita líquida)",
        "Quais creators geraram maior receita líquida na categoria Cosméticos?",
        """SELECT creator, nivel_creator, COUNT(*) AS total_vendas,
       ROUND(SUM(receita_liquida), 2) AS receita_liquida
FROM v_vendas
WHERE categoria = 'Cosméticos' AND canal = 'creator'
GROUP BY creator, nivel_creator
ORDER BY receita_liquida DESC
LIMIT 5"""),
    Suggestion(
        "chargeback_micro", "📦 Chargeback em físicos via micro-creators",
        "Quais categorias de produtos físicos tiveram a maior taxa de chargeback nas vendas de micro-creators nos últimos 30 dias?",
        """SELECT categoria, COUNT(*) AS total_vendas,
       SUM(status = 'Chargeback') AS chargebacks,
       ROUND(100.0 * SUM(status = 'Chargeback') / COUNT(*), 1) AS taxa_chargeback_pct
FROM v_vendas
WHERE tipo_produto = 'Físico' AND nivel_creator = 'Micro'
  AND data_venda >= date('now','-30 day')
GROUP BY categoria
ORDER BY taxa_chargeback_pct DESC"""),
    Suggestion(
        "fitplus", "🔎 Quem concentra os chargebacks da FitPlus?",
        "Quais creators concentram os chargebacks da marca FitPlus Suplementos?",
        """SELECT creator, nivel_creator, COUNT(*) AS total_vendas,
       SUM(status = 'Chargeback') AS chargebacks,
       ROUND(100.0 * SUM(status = 'Chargeback') / COUNT(*), 1) AS taxa_chargeback_pct
FROM v_vendas
WHERE marca = 'FitPlus Suplementos' AND canal = 'creator'
GROUP BY creator, nivel_creator
ORDER BY taxa_chargeback_pct DESC"""),
]
SUGGESTED_BY_ID = {s.id: s for s in SUGGESTED}
