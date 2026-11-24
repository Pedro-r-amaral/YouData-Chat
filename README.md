# YouData Chat — BI conversacional seguro (protótipo)

Protótipo do **Desafio de Inovação · Programa de Estágio YouShop 2027**.
Pergunta em português → IA gera SQL → trava determinística valida → execução somente leitura → IA explica.
Todos os dados são **sintéticos**.

## Como funciona (3 camadas)

| Camada | Arquivo | O que faz |
|---|---|---|
| 1. Texto → SQL | `youdata/llm.py`, `prompts.py` | LLM recebe só as *views* (camada semântica) e as regras de negócio |
| 2. Segurança + execução | `youdata/security.py`, `db.py` | valida (SELECT/WITH, 1 instrução, sem comentários, só views permitidas, LIMIT automático) e executa com 3 travas: arquivo `mode=ro`, `PRAGMA query_only`, `authorizer` |
| 3. Dados → texto | `youdata/pipeline.py` | LLM resume o resultado usando só os números da tabela; o SQL e os dados ficam visíveis para auditoria |

Se a consulta falha, há **uma** nova tentativa com a mensagem de erro. Tentativas de escrita (`DROP`, `DELETE`…) **não** geram nova tentativa.

## Estrutura

```
youdata-chat/
├── app.py                   # interface Streamlit
├── youdata/
│   ├── config.py            # settings (env vars / st.secrets)
│   ├── schema.py            # tabelas, views, regras de negócio
│   ├── seed.py              # dados sintéticos + padrão oculto (FitPlus)
│   ├── security.py          # validador de SQL
│   ├── db.py                # conexão somente leitura
│   ├── llm.py               # Ollama ou Anthropic
│   ├── prompts.py           # prompts de SQL e de explicação
│   ├── suggestions.py       # perguntas sugeridas + SQL pré-validado (modo demo)
│   └── pipeline.py          # orquestra as 3 camadas
├── tests/                   # 35 testes (segurança, pipeline, padrão oculto)
├── .streamlit/              # tema (azul/lima) e exemplo de secrets
└── requirements.txt
```

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q                                            # deve passar tudo
streamlit run app.py
```

Sem nenhuma chave, o app abre em **modo demonstração** (4 perguntas sugeridas funcionam).
Para perguntas livres:

- **Anthropic:** `cp .streamlit/secrets.toml.example .streamlit/secrets.toml` e coloque sua chave.
- **Local (Ollama):** `ollama pull qwen2.5-coder:7b` e rode com `LLM_PROVIDER=ollama streamlit run app.py`
  (modelos de 3B erram JOINs complexos; prefira 7B ou maior).

## Publicar para o avaliador (Streamlit Community Cloud)

1. Suba esta pasta para um repositório **público** no GitHub (o `.gitignore` já exclui `secrets.toml` e `*.db`).
2. Em share.streamlit.io: *New app* → escolha o repositório, branch e `app.py`.
3. *Advanced settings → Secrets*: cole `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` e `MAX_QUESTIONS = "15"`.
4. Defina um **limite de gasto** no painel da Anthropic para a chave (qualquer pessoa com o link consome sua cota).
5. Abra o link em aba anônima e teste as 4 perguntas sugeridas **e** uma pergunta livre antes de enviar.
6. Coloque o link no formulário e 2 prints no slide do protótipo.

## Limites conhecidos

- O banco é SQLite com dados fictícios; em produção use réplica de leitura com um usuário que tenha `GRANT SELECT` só nas views.
- A IA pode errar o SQL: por isso o SQL e os dados brutos ficam visíveis em cada resposta.
- No modo demonstração a resposta é um resumo mecânico, sem IA.
