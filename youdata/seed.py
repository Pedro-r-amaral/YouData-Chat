"""Gera o banco sintético da YouShop, com um padrão oculto para a demonstração.

PADRÃO OCULTO: a marca 'FitPlus Suplementos' tem ~30% de chargeback nas vendas
trazidas por dois micro-creators (@lia.fit e @bruno.treina) e ~2% no resto.
"""
from __future__ import annotations

import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .schema import TABLES_DDL, VIEWS_DDL

MARCAS = [
    (1, "FitPlus Suplementos", "Suplementos", "2024-03-10"),
    (2, "BelaPele Cosméticos", "Cosméticos", "2024-05-21"),
    (3, "VitaMax Nutrição", "Suplementos", "2024-08-02"),
    (4, "CodeLab Cursos", "Cursos Online", "2023-11-15"),
    (5, "ZenMind Mentorias", "Mentorias", "2025-01-09"),
    (6, "AppFlow Software", "Software", "2024-10-30"),
    (7, "Aura Skincare", "Cosméticos", "2025-02-18"),
]

# id, marca_id, nome, tipo, categoria, preco, comissao_pct, peso de vendas
PRODUTOS = [
    (1, 1, "FitPlus Whey 900g", "Físico", "Suplementos", 129.9, 25, 3),
    (2, 1, "FitPlus Termogênico", "Físico", "Suplementos", 89.9, 30, 2),
    (3, 2, "BelaPele Sérum Vitamina C", "Físico", "Cosméticos", 149.9, 20, 2),
    (4, 2, "BelaPele Protetor Solar", "Físico", "Cosméticos", 79.9, 20, 2),
    (5, 3, "VitaMax Creatina", "Físico", "Suplementos", 99.9, 25, 2),
    (6, 4, "CodeLab Python do Zero", "Digital", "Cursos", 297.0, 40, 2),
    (7, 4, "CodeLab Dados na Prática", "Digital", "Cursos", 397.0, 40, 1),
    (8, 5, "ZenMind Mentoria 90 dias", "Digital", "Mentorias", 997.0, 30, 1),
    (9, 6, "AppFlow Planner Pro", "Digital", "Software", 49.9, 35, 2),
    (10, 7, "Aura Hidratante Facial", "Físico", "Cosméticos", 119.9, 22, 1),
    (11, 7, "Aura Kit Skincare", "Físico", "Cosméticos", 249.9, 22, 1),
]

CREATORS = [
    (1, "@lia.fit", "Fitness", "Micro"),
    (2, "@bruno.treina", "Fitness", "Micro"),
    (3, "@carol.skin", "Beleza", "Micro"),
    (4, "@dani.makeup", "Beleza", "Médio"),
    (5, "@rafa.dev", "Tecnologia", "Micro"),
    (6, "@thi.codando", "Tecnologia", "Médio"),
    (7, "@mari.wellness", "Bem-estar", "Micro"),
    (8, "@gui.invest", "Finanças", "Médio"),
    (9, "@fer.fitpro", "Fitness", "Top"),
    (10, "@julia.glow", "Beleza", "Top"),
    (11, "@leo.tech", "Tecnologia", "Top"),
    (12, "@nina.zen", "Bem-estar", "Micro"),
    (13, "@pedro.fit", "Fitness", "Micro"),
    (14, "@bia.beauty", "Beleza", "Micro"),
]

NICHES = {
    "Suplementos": ["Fitness", "Bem-estar"],
    "Cosméticos": ["Beleza", "Bem-estar"],
    "Cursos": ["Tecnologia", "Finanças"],
    "Mentorias": ["Bem-estar", "Finanças"],
    "Software": ["Tecnologia", "Finanças"],
}
LEVEL_WEIGHT = {"Micro": 1, "Médio": 2, "Top": 3}
PATTERN_PRODUCTS = {1, 2}
PATTERN_CREATORS = [1, 2]


def build_database(path: str | Path, seed: int = 42, today: date | None = None,
                   n_vendas: int = 360, days: int = 75) -> Path:
    rng = random.Random(seed)
    today = today or date.today()
    path = Path(path)
    path.unlink(missing_ok=True)

    conn = sqlite3.connect(path)
    conn.executescript(TABLES_DDL)
    conn.executemany("INSERT INTO marcas_produtores VALUES (?,?,?,?)", MARCAS)
    conn.executemany("INSERT INTO produtos VALUES (?,?,?,?,?,?,?)", [p[:7] for p in PRODUTOS])
    conn.executemany("INSERT INTO creators VALUES (?,?,?,?)", CREATORS)

    prod_weights = [p[7] for p in PRODUTOS]
    sales = []
    for _ in range(n_vendas):
        prod = rng.choices(PRODUTOS, weights=prod_weights)[0]
        pid, _, _, tipo, categoria, preco, comissao = prod[:7]

        creator_id = None
        if rng.random() < 0.8:  # 80% das vendas vêm de creators
            cands = [c for c in CREATORS if c[2] in NICHES[categoria]] or CREATORS
            creator = rng.choices(cands, weights=[LEVEL_WEIGHT[c[3]] for c in cands])[0]
            creator_id = creator[0]
            if pid in PATTERN_PRODUCTS and rng.random() < 0.7:
                creator_id = rng.choice(PATTERN_CREATORS)

        p_chargeback = 0.30 if (pid in PATTERN_PRODUCTS and creator_id in PATTERN_CREATORS) else 0.02
        p_refund = 0.06 if tipo == "Digital" else 0.05
        r = rng.random()
        status = "Chargeback" if r < p_chargeback else "Reembolsada" if r < p_chargeback + p_refund else "Aprovada"

        valor_comissao = round(preco * comissao / 100, 2) if creator_id else 0.0
        data_venda = today - timedelta(days=rng.randint(0, days - 1))
        sales.append((pid, creator_id, preco, valor_comissao, status, data_venda.isoformat()))

    sales.sort(key=lambda s: s[-1])
    conn.executemany(
        "INSERT INTO vendas (produto_id, creator_id, valor_total, valor_comissao, status, data_venda) "
        "VALUES (?,?,?,?,?,?)", sales)

    tickets = []
    for venda_id, (pid, _, _, _, status, data_venda) in enumerate(sales, start=1):
        tipo = next(p[3] for p in PRODUTOS if p[0] == pid)
        prob = 0.6 if status != "Aprovada" else 0.15
        if rng.random() < prob:
            motivo = rng.choice(["Atraso Entrega", "Dúvida Comissão"] if tipo == "Físico"
                                else ["Acesso Curso", "Dúvida Comissão"])
            abertura = date.fromisoformat(data_venda) + timedelta(days=rng.randint(1, 5))
            tickets.append((venda_id, motivo, min(abertura, today).isoformat()))
    conn.executemany("INSERT INTO tickets_suporte (venda_id, motivo, data_abertura) VALUES (?,?,?)", tickets)

    conn.executescript(VIEWS_DDL)
    conn.commit()
    conn.close()
    return path


if __name__ == "__main__":
    from .config import load_settings

    out = build_database(load_settings().db_path)
    print(f"Banco criado em {out}")
