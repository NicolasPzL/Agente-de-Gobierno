import streamlit as st
import langchain
import os
from pathlib import Path
# Monkey-patch for langchain.debug to avoid "module 'langchain' has no attribute 'debug'" error
if not hasattr(langchain, 'debug'):
    langchain.debug = False

from ate.graph.builder import construir_grafo
from ate.config.settings import load_settings
from ate.rag.cliente import abrir_cliente
from ate.rag.ingestor import ingestar_todos
import time


# Page config
st.set_page_config(
    page_title="ATE - Agente de Transparencia Electoral",
    page_icon="🗳️",
    layout="wide"
)

# Load settings
settings = load_settings()

# --- Automatic Knowledge Base Initialization ---
# Check if the RAG index is populated. If not, ingest PDFs automatically.
try:
    cliente_rag = abrir_cliente(settings.rag_dir)
    if cliente_rag.contar() == 0:
        with st.status("📚 Inicializando Base de Conocimientos (RAG)...", expanded=True) as status:
            st.write("Analizando planes de gobierno de los candidatos...")
            repo_root = Path(__file__).resolve().parent
            ingestar_todos(cliente=cliente_rag, repo_root=repo_root)
            status.update(label="Base de conocimientos lista", state="complete", expanded=False)
except Exception as e:
    st.error(f"Error inicializando RAG: {e}")
# ---------------------------------------------

# CSS for better styling
st.markdown("""
    <style>
    .main {
        background-color: #f5f7f9;
    }
    .stChatMessage {
        border-radius: 15px;
    }
    .respuesta-box {
        background: #ffffff;
        border: 1px solid #d1d9e6;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        padding: 18px;
        border-radius: 18px;
        line-height: 1.7;
        white-space: pre-wrap;
        font-size: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("Agente de Transparencia Electoral (ATE)")
st.markdown("""
    Bienvenido al **ATE**, el sistema de auditoría ciudadana para candidatos presidenciales de Colombia 2026.
    Este agente cruza propuestas de planes de gobierno con datos reales de contratación pública y antecedentes.
""")

# Sidebar configuration
with st.sidebar:
    st.header("Configuración")
    st.info(f"**Provider:** {settings.llm_provider}")
    st.info(f"**Modo Offline:** {'SÍ' if settings.ate_offline else 'NO'}")

    if settings.llm_provider == "anthropic":
        st.write(f"**Modelo:** {settings.anthropic_model}")
    elif settings.llm_provider == "ollama":
        st.write(f"**Modelo:** {settings.ollama_model}")

    if not settings.llm_available:
        st.warning(
            "LLM no disponible: configure `ATE_LLM_PROVIDER=ollama` con un servidor Ollama local o `ATE_LLM_PROVIDER=anthropic` y su clave API."
        )

    st.divider()
    st.markdown("### Guía de Consulta")
    st.write("- *¿Qué propone el candidato X sobre salud?*")
    st.write("- *¿Tiene el candidato Y contratos en SECOP?*")
    st.write("- *¿Existen sanciones disciplinarias para el candidato Z?*")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Haz una pregunta sobre la transparencia de un candidato..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Agent response
    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        response_placeholder = st.empty()

        try:
            # Process the query using the ATE agent
            with status_placeholder.status("Analizando la solicitud con ATE...", expanded=False) as status:
                grafo = construir_grafo()
                resultado = grafo.invoke({"pregunta": prompt})
                status.update(label="✅ Análisis completado", state="complete", expanded=False)

            # Display final answer
            final_answer = resultado.get("respuesta_final", "Lo siento, no pude generar una respuesta final.")
            response_placeholder.markdown(
                f"<div class='respuesta-box'>{final_answer}</div>",
                unsafe_allow_html=True,
            )


        except Exception as e:
            status_placeholder.error(f"Error durante el procesamiento: {str(e)}")
            response_placeholder.error("Ocurrió un error inesperado al consultar el agente.")

    # Add assistant message to history
    st.session_state.messages.append({"role": "assistant", "content": final_answer if 'final_answer' in locals() else "Error al generar respuesta."})
