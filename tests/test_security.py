import pytest

from youdata.security import UnsafeQueryError, extract_sql, validate_sql

OK = [
    "SELECT marca, COUNT(*) FROM v_vendas GROUP BY marca",
    "WITH t AS (SELECT * FROM v_vendas) SELECT COUNT(*) FROM t",
    "SELECT * FROM v_vendas v JOIN v_creators c ON c.creator_id = v.creator_id",
    "SELECT status FROM v_vendas WHERE marca = 'Delete Me; DROP TABLE x'",   # palavra proibida só dentro de literal
    "SELECT REPLACE(marca, 'a', 'b') FROM v_vendas",                          # REPLACE() é função, não escrita
]

BLOCKED_NOT_RETRYABLE = [
    "DROP TABLE vendas",
    "DELETE FROM v_vendas",
    "UPDATE vendas SET status='Aprovada'",
    "INSERT INTO creators VALUES (99,'x','y','Top')",
    "SELECT 1; DROP TABLE vendas",
    "WITH x AS (SELECT 1) DELETE FROM vendas",
    "PRAGMA table_info(vendas)",
    "ATTACH DATABASE 'x.db' AS x",
    "REPLACE INTO creators VALUES (1,'a','b','Top')",
]

BLOCKED_RETRYABLE = [
    "",
    "Aqui está sua consulta: SELECT 1",
    "SELECT * FROM vendas",                       # tabela bruta, fora da camada semântica
    "SELECT * FROM sqlite_master",
    'SELECT * FROM "vendas"',
    "SELECT * FROM v_vendas, v_creators",
    "SELECT 1 -- comentário",
    "SELECT 1 /* x */",
    "SELECT * FROM json_each('[1]')",
    "SELECT 'abc",
]


@pytest.mark.parametrize("sql", OK)
def test_allows_read_queries(sql):
    assert validate_sql(sql).sql.upper().startswith(("SELECT", "WITH"))


@pytest.mark.parametrize("sql", BLOCKED_NOT_RETRYABLE)
def test_blocks_writes(sql):
    with pytest.raises(UnsafeQueryError) as exc:
        validate_sql(sql)
    assert exc.value.retryable is False


@pytest.mark.parametrize("sql", BLOCKED_RETRYABLE)
def test_blocks_malformed_or_out_of_scope(sql):
    with pytest.raises(UnsafeQueryError):
        validate_sql(sql)


def test_injects_limit_only_when_missing():
    assert validate_sql("SELECT * FROM v_vendas").limit_injected
    assert not validate_sql("SELECT * FROM v_vendas LIMIT 5").limit_injected


def test_extract_sql_removes_markdown_and_semicolon():
    assert extract_sql("```sql\nSELECT 1 FROM v_vendas;\n```") == "SELECT 1 FROM v_vendas"
