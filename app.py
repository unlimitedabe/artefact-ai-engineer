"""Streamlit customer-service chat. Run from the repository root."""

import streamlit as st

from emporio.bootstrap import create_agent, resources
from emporio.config import Settings
from emporio.ingest import DataError
from emporio.provider import ProviderError
from emporio.session import Verification

st.set_page_config(page_title="Empório da Música", page_icon="🎸", layout="centered")
st.title("Empório da Música 🎸")
st.caption("Sua música começa aqui. Assistente virtual • Campo Grande/MS")


@st.cache_resource
def load_resources(data_dir, policy_pdf, database_path):
    return resources(
        Settings(data_dir=data_dir, policy_pdf=policy_pdf, database_path=database_path)
    )


try:
    settings = Settings.from_env()
    store, policies = load_resources(settings.data_dir, settings.policy_pdf, settings.database_path)
except (DataError, ValueError, OSError):
    st.error("Não consegui carregar os dados. Confira os caminhos e execute: emporio load")
    st.stop()

if "verification" not in st.session_state:
    st.session_state.verification = Verification()
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("Seu atendimento")
    mode = st.selectbox(
        "Modo",
        ["openai", "demo"],
        index=0 if settings.mode == "openai" else 1,
        format_func=lambda x: "IA via API" if x == "openai" else "Demonstração offline",
    )
    st.caption(
        "Dados de demonstração: arquivos fornecidos no desafio, sem conexão com sistema ao vivo."
    )
    verification = st.session_state.verification
    if verification.customer_id is None:
        st.write("Para consultar um pedido, confirme seus dados fora do chat.")
        with st.form("identity", clear_on_submit=True):
            email = st.text_input("E-mail cadastrado", max_chars=254)
            phone = st.text_input("Telefone cadastrado", type="password", max_chars=30)
            submitted = st.form_submit_button("Verificar dados")
        if submitted:
            verified = verification.verify(store, email, phone)
            # Every identity attempt invalidates conversation state to prevent cross-account memory.
            st.session_state.pop("agent", None)
            st.session_state.messages = []
            if verified:
                st.rerun()
            st.error("Não foi possível verificar os dados. Confira-os ou procure a equipe.")
        if verification.failures >= 5:
            st.warning("Limite de tentativas desta sessão atingido. Procure atendimento humano.")
    else:
        st.success("Cliente verificado nesta sessão")
        if st.button("Sair da consulta de pedidos"):
            verification.customer_id = None
            st.session_state.pop("agent", None)
            st.session_state.messages = []
            st.rerun()
    if st.button("Limpar conversa"):
        st.session_state.pop("agent", None)
        st.session_state.messages = []
        st.rerun()
    show_sources = st.checkbox("Mostrar fontes consultadas", value=True)
    st.caption(
        "Verificação por dados conhecidos é apenas um protótipo; não use dados reais neste chat."
    )

settings = settings.model_copy(update={"mode": mode})
if st.session_state.get("agent_mode") != mode:
    st.session_state.pop("agent", None)
    st.session_state.messages = []
    st.session_state.agent_mode = mode
if mode == "demo":
    st.info(
        "Demonstração offline com cenários limitados. Nenhum modelo de IA é chamado neste modo."
    )
elif not settings.api_key:
    st.warning("Configure OPENAI_API_KEY no arquivo .env ou selecione Demonstração offline.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input(
    "Como podemos ajudar?", max_chars=4000, disabled=(mode == "openai" and not settings.api_key)
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    try:
        if "agent" not in st.session_state:
            st.session_state.agent = create_agent(
                settings, store, policies, verification.customer_id
            )
        with st.chat_message("assistant"), st.spinner("Consultando as informações…"):
            result = st.session_state.agent.reply(prompt)
            st.markdown(result.answer)
            if show_sources and result.trace:
                with st.expander("Fontes consultadas neste turno"):
                    for entry in result.trace:
                        data = entry["result"]
                        st.write(f"{entry['evidence_id']} · {entry['tool']}")
                        for match in data.get("matches", data.get("policy", {}).get("matches", [])):
                            st.caption(f"Seção {match['section']} · {match['source']}")
                        if "matches" not in data and "policy" not in data:
                            st.caption("Base CSV fornecida no desafio")
        st.session_state.messages.append({"role": "assistant", "content": result.answer})
    except ProviderError:
        st.error("Não consegui iniciar o modelo. Confira a configuração da API.")
