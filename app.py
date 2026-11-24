"""YouData Chat — BI conversacional seguro para Controladoria e Diretoria (protótipo)."""
from __future__ import annotations

import streamlit as st

from youdata.config import load_settings
from youdata.llm import build_client
from youdata.pipeline import QueryResult, answer_demo, answer_with_llm
from youdata.schema import ALLOWED_RELATIONS
from youdata.seed import build_database
from youdata.suggestions import SUGGESTED, SUGGESTED_BY_ID

st.set_page_config(page_title="YouData Chat · YouShop", page_icon="💬", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1100px;}
section[data-testid="stSidebar"] {border-right: 4px solid #8CE000;}
.badge {display:inline-block; padding:2px 10px; border-radius:12px; background:#8CE000;
        color:#0B2545; font-weight:700; font-size:0.8rem;}
</style>
""", unsafe_allow_html=True)


@st.cache_resource(ttl=6 * 3600, show_spinner="Preparando o banco de demonstração…")
def prepare_database(path: str) -> str:
    build_database(path)       # dados sintéticos, sempre relativos à data de hoje
    return path


settings = load_settings()
prepare_database(str(settings.db_path))
llm = build_client(settings)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("llm_calls", 0)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 💬 YouData Chat")
    st.markdown('<span class="badge">🔒 Modo: somente leitura ativo</span>', unsafe_allow_html=True)
    st.caption("Qualquer INSERT, UPDATE, DELETE, DROP ou ALTER é bloqueado antes de chegar ao banco.")

    if llm:
        st.success(f"IA ativa: {llm.name}", icon="🤖")
        st.caption(f"Perguntas livres nesta sessão: {st.session_state.llm_calls}/{settings.max_questions}")
    else:
        st.info("Modo demonstração: use as perguntas sugeridas abaixo. "
                "Perguntas livres exigem uma chave de LLM configurada.", icon="🧪")

    st.markdown("**Perguntas sugeridas da Diretoria**")
    for s in SUGGESTED:
        if st.button(s.label, key=f"btn_{s.id}", width="stretch"):
            st.session_state.pending = s.id

    st.markdown("**Dados conectados (views)**")
    st.write(" · ".join(f"`{v}`" for v in sorted(ALLOWED_RELATIONS)))
    st.caption("Dados 100% sintéticos, gerados para esta demonstração.")
    if st.button("🗑️ Limpar conversa", width="stretch"):
        st.session_state.messages = []
        st.rerun()

# ---------------------------------------------------------------- main
st.title("YouData Chat")
st.caption("Pergunte em português. A IA gera o SQL, a trava de segurança valida, "
           "e você audita a consulta e os dados brutos.")


def render_result(res: QueryResult) -> None:
    if res.error:
        st.error(res.error, icon="🚫")
    else:
        st.markdown(res.answer)
    if res.sql:
        with st.expander("🔍 Auditar SQL gerado e dados brutos"):
            st.code(res.sql, language="sql")
            if res.limit_injected:
                st.caption("LIMIT injetado automaticamente pela camada de segurança.")
            if res.df is not None:
                st.dataframe(res.df, width="stretch", hide_index=True)
                if res.df.attrs.get("truncated"):
                    st.caption("Resultado truncado no teto de linhas.")
    if res.attempts:
        st.caption(f"⏱ {res.elapsed_s:.1f}s · tentativas de SQL: {res.attempts} · modo: {res.mode}")


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            render_result(msg["result"])

typed = st.chat_input("Ex.: Quais marcas tiveram mais de 5% de estorno via creators?")
pending_id = st.session_state.pop("pending", None)
suggestion = SUGGESTED_BY_ID.get(pending_id) if pending_id else None
question = typed or (suggestion.question if suggestion else None)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        result: QueryResult | None = None
        if llm is None:
            if suggestion:
                result = answer_demo(suggestion, settings)
            else:
                st.info("Modo demonstração: escolha uma das perguntas sugeridas na barra lateral. "
                        "Para perguntas livres, configure ANTHROPIC_API_KEY (ou um Ollama local).")
        elif st.session_state.llm_calls >= settings.max_questions:
            st.warning("Limite de perguntas desta sessão atingido. Recarregue a página para recomeçar.")
        else:
            with st.spinner("Gerando e validando a consulta…"):
                st.session_state.llm_calls += 1
                result = answer_with_llm(question, llm, settings)
        if result:
            render_result(result)
            st.session_state.messages.append({"role": "assistant", "result": result})
