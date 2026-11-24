import sqlite3

import pytest

from youdata.db import QueryExecutionError, connect_readonly, execute_readonly
from youdata.pipeline import answer_demo, answer_with_llm
from youdata.security import validate_sql
from youdata.suggestions import SUGGESTED


class FakeLLM:
    name = "fake"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, user, max_tokens=800):
        self.calls.append(user)
        return self.responses.pop(0)


@pytest.mark.parametrize("s", SUGGESTED, ids=lambda s: s.id)
def test_every_suggestion_passes_validator_and_runs(s, settings):
    res = answer_demo(s, settings)
    assert res.error is None and res.df is not None and len(res.df) > 0


def test_hidden_pattern_is_discoverable(settings):
    from youdata.suggestions import SUGGESTED_BY_ID
    df = answer_demo(SUGGESTED_BY_ID["fitplus"], settings).df
    top = df.iloc[0]
    assert top["creator"] in ("@lia.fit", "@bruno.treina") and top["taxa_chargeback_pct"] > 10


def test_database_layer_refuses_writes_even_if_validator_is_bypassed(settings):
    conn = connect_readonly(settings.db_path)
    for sql in ("DELETE FROM vendas", "DROP TABLE vendas", "UPDATE vendas SET status='Aprovada'"):
        with pytest.raises((QueryExecutionError, sqlite3.Error)):
            execute_readonly(conn, sql)
    assert execute_readonly(conn, "SELECT COUNT(*) AS n FROM vendas")["n"][0] > 0


def test_malicious_sql_is_blocked_without_retry(settings):
    llm = FakeLLM("DROP TABLE vendas")
    res = answer_with_llm("apague tudo", llm, settings)
    assert res.error and res.df is None and len(llm.calls) == 1   # nem tentou de novo
    conn = connect_readonly(settings.db_path)
    assert execute_readonly(conn, "SELECT COUNT(*) AS n FROM vendas")["n"][0] > 0


def test_repair_loop_recovers_from_bad_sql(settings):
    llm = FakeLLM("SELECT coluna_inexistente FROM v_vendas",
                  "```sql\nSELECT marca, COUNT(*) AS total_vendas FROM v_vendas GROUP BY marca;\n```",
                  "Resposta executiva.")
    res = answer_with_llm("vendas por marca", llm, settings)
    assert res.error is None and res.attempts == 2 and res.answer == "Resposta executiva."


def test_out_of_scope_question(settings):
    llm = FakeLLM("SELECT 'PERGUNTA_FORA_DO_ESCOPO' AS aviso")
    res = answer_with_llm("qual a previsão do tempo?", llm, settings)
    assert res.error and "dados disponíveis" in res.error
