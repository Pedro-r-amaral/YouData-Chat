"""Esquema do banco de demonstração da YouShop (SQLite).

O LLM NUNCA enxerga as tabelas brutas: só as views abaixo (camada semântica).
Em produção, isto equivale a um usuário de banco com GRANT SELECT apenas nas views.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

TABLES_DDL = """
CREATE TABLE marcas_produtores (
    id INTEGER PRIMARY KEY, nome TEXT NOT NULL, segmento TEXT NOT NULL, data_entrada DATE NOT NULL
);
CREATE TABLE produtos (
    id INTEGER PRIMARY KEY,
    marca_id INTEGER NOT NULL REFERENCES marcas_produtores(id),
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('Físico','Digital')),
    categoria TEXT NOT NULL,
    preco REAL NOT NULL,
    comissao_pct REAL NOT NULL
);
CREATE TABLE creators (
    id INTEGER PRIMARY KEY, nome TEXT NOT NULL, nicho TEXT NOT NULL,
    nivel TEXT NOT NULL CHECK (nivel IN ('Micro','Médio','Top'))
);
CREATE TABLE vendas (
    id INTEGER PRIMARY KEY,
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    creator_id INTEGER REFERENCES creators(id),
    valor_total REAL NOT NULL,
    valor_comissao REAL NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('Aprovada','Reembolsada','Chargeback')),
    data_venda DATE NOT NULL
);
CREATE TABLE tickets_suporte (
    id INTEGER PRIMARY KEY,
    venda_id INTEGER NOT NULL REFERENCES vendas(id),
    motivo TEXT NOT NULL CHECK (motivo IN ('Atraso Entrega','Acesso Curso','Dúvida Comissão')),
    data_abertura DATE NOT NULL
);
"""

VIEWS_DDL = """
CREATE VIEW v_marcas AS
    SELECT id AS marca_id, nome AS marca, segmento, data_entrada FROM marcas_produtores;

CREATE VIEW v_produtos AS
    SELECT p.id AS produto_id, p.nome AS produto, p.tipo AS tipo_produto, p.categoria,
           p.preco, p.comissao_pct, m.id AS marca_id, m.nome AS marca
    FROM produtos p JOIN marcas_produtores m ON m.id = p.marca_id;

CREATE VIEW v_creators AS
    SELECT id AS creator_id, nome AS creator, nicho, nivel AS nivel_creator FROM creators;

CREATE VIEW v_vendas AS
    SELECT v.id AS venda_id, v.data_venda, strftime('%Y-%m', v.data_venda) AS mes,
           v.status, v.valor_total, v.valor_comissao,
           CASE WHEN v.status = 'Aprovada' THEN v.valor_total ELSE 0 END AS receita_liquida,
           p.id AS produto_id, p.nome AS produto, p.tipo AS tipo_produto, p.categoria,
           m.id AS marca_id, m.nome AS marca,
           v.creator_id, c.nome AS creator, c.nivel AS nivel_creator,
           CASE WHEN v.creator_id IS NULL THEN 'direta' ELSE 'creator' END AS canal
    FROM vendas v
    JOIN produtos p ON p.id = v.produto_id
    JOIN marcas_produtores m ON m.id = p.marca_id
    LEFT JOIN creators c ON c.id = v.creator_id;

CREATE VIEW v_tickets AS
    SELECT id AS ticket_id, venda_id, motivo, data_abertura FROM tickets_suporte;
"""

ALLOWED_RELATIONS = frozenset({"v_vendas", "v_produtos", "v_marcas", "v_creators", "v_tickets"})

VIEW_DESCRIPTIONS = {
    "v_vendas": "uma linha por venda, já com produto, marca e creator (visão principal)",
    "v_produtos": "catálogo de produtos com a marca",
    "v_marcas": "marcas/produtores cadastrados",
    "v_creators": "creators (afiliados) e seu nível: Micro, Médio ou Top",
    "v_tickets": "tickets de suporte ligados a uma venda",
}

BUSINESS_RULES = """\
- status da venda: 'Aprovada', 'Reembolsada' ou 'Chargeback'.
- Receita líquida = SUM(receita_liquida) (a coluna já vale valor_total só quando status = 'Aprovada').
- Estorno = status IN ('Reembolsada','Chargeback'). Chargeback = status = 'Chargeback'.
- Taxa em % = ROUND(100.0 * SUM(<condição>) / COUNT(*), 1). Ao calcular taxas por grupo, inclua sempre a coluna total_vendas.
- canal = 'creator' quando a venda veio de um creator, 'direta' caso contrário.
- nivel_creator: 'Micro', 'Médio', 'Top'. tipo_produto: 'Físico' ou 'Digital'.
- "últimos N dias": data_venda >= date('now','-N day'). "este mês": mes = strftime('%Y-%m','now').
- Categorias: 'Suplementos', 'Cosméticos', 'Cursos', 'Mentorias', 'Software'.
- Use sempre JOIN explícito (nunca vírgula no FROM) e dê nomes claros às colunas calculadas.
"""


def describe_views(db_path: str | Path) -> str:
    """Gera o trecho de esquema para o prompt a partir do próprio banco (sem desatualizar)."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        parts = []
        for view in sorted(ALLOWED_RELATIONS):
            cols = [f"{r[1]} {r[2]}".strip() for r in conn.execute(f"PRAGMA table_info({view})")]
            parts.append(f"{view} -- {VIEW_DESCRIPTIONS[view]}\n  ({', '.join(cols)})")
        return "\n".join(parts)
    finally:
        conn.close()
