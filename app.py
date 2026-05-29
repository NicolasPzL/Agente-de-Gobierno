"""Interfaz web del Agente de Transparencia Electoral (ATE) - Sprint 5.

Interfaz de chat en Streamlit sobre el grafo multiagente completo
(planificador -> extraccion -> rag -> contraste -> validador -> generador).

Caracteristicas:
    - Diseno limpio (tema nativo en `.streamlit/config.toml` + CSS propio).
    - Interruptor "Mostrar flujo de analisis": alterna entre ver solo la
      respuesta final o ver toda la cadena de evidencia (planificacion,
      extraccion, RAG, contraste, validacion).
    - Citacion verificable: muestra las fuentes oficiales validadas.

Ejecutar:
    pip install -e ".[ui]"
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Red de seguridad: permite `streamlit run app.py` aunque el paquete no se
# haya instalado en modo editable (espeja lo que hace tests/conftest.py).
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import langchain
import streamlit as st

# Algunas versiones de langchain no exponen `debug`; evitamos el AttributeError.
if not hasattr(langchain, "debug"):
    langchain.debug = False

from ate.candidatos.registro import CANDIDATOS_2026
from ate.config.settings import load_settings
from ate.graph.builder import construir_grafo
from ate.rag.cliente import abrir_cliente
from ate.rag.ingestor import ingestar_todos


st.set_page_config(
    page_title="ATE — Transparencia Electoral 2026",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

_CSS = """
<style>
:root {
    --ate-primary: #2563EB;
    --ate-ink: #0F172A;
    --ate-muted: #64748B;
    --ate-border: #E2E8F0;
    --ate-ok: #16A34A;
    --ate-warn: #D97706;
    --ate-error: #DC2626;
    --ate-neutral: #94A3B8;
}

/* Limpieza del chrome de Streamlit */
#MainMenu, footer, header [data-testid="stToolbar"] { visibility: hidden; }
.block-container { padding-top: 2.2rem; padding-bottom: 6rem; max-width: 1100px; }

/* Hero */
.ate-hero {
    background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 55%, #3B82F6 100%);
    color: #FFFFFF;
    border-radius: 20px;
    padding: 26px 30px;
    margin-bottom: 18px;
    box-shadow: 0 12px 30px rgba(37, 99, 235, 0.22);
}
.ate-hero h1 { color: #FFFFFF; font-size: 1.7rem; font-weight: 750; margin: 0 0 6px 0; letter-spacing: -0.01em; }
.ate-hero p { color: rgba(255,255,255,0.92); font-size: 0.97rem; margin: 0; max-width: 720px; line-height: 1.55; }
.ate-hero .ate-kicker {
    display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.14em;
    text-transform: uppercase; color: rgba(255,255,255,0.85);
    background: rgba(255,255,255,0.14); padding: 4px 10px; border-radius: 999px; margin-bottom: 12px;
}

/* Etiqueta de seccion */
.ate-step-label {
    font-size: 0.74rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--ate-muted); margin: 4px 0 8px 0;
}

/* Pills de estado */
.ate-pill {
    display: inline-block; font-size: 0.72rem; font-weight: 650; padding: 2px 10px;
    border-radius: 999px; border: 1px solid transparent; white-space: nowrap;
}
.ate-pill--ok      { color: #14532D; background: #DCFCE7; border-color: #BBF7D0; }
.ate-pill--warn    { color: #7C2D12; background: #FEF3C7; border-color: #FDE68A; }
.ate-pill--error   { color: #7F1D1D; background: #FEE2E2; border-color: #FECACA; }
.ate-pill--neutral { color: #334155; background: #F1F5F9; border-color: #E2E8F0; }

/* Chips de metricas */
.ate-stats { display: flex; gap: 10px; flex-wrap: wrap; margin: 8px 0 4px 0; }
.ate-stat {
    background: #F8FAFC; border: 1px solid var(--ate-border); border-radius: 12px;
    padding: 8px 14px; min-width: 92px;
}
.ate-stat .v { font-size: 1.25rem; font-weight: 750; color: var(--ate-ink); line-height: 1.1; }
.ate-stat .k { font-size: 0.72rem; color: var(--ate-muted); text-transform: uppercase; letter-spacing: 0.05em; }

/* Respuesta final */
.ate-answer-label {
    font-size: 0.74rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase;
    color: var(--ate-primary); margin-bottom: 6px;
}
[data-testid="stChatMessage"] { background: transparent; }

/* Expanders mas suaves */
[data-testid="stExpander"] details {
    border: 1px solid var(--ate-border); border-radius: 14px; background: #FFFFFF;
}
[data-testid="stExpander"] summary { font-weight: 600; }

/* Tarjeta de evidencia interna */
.ate-evi { color: var(--ate-ink); }
.ate-evi blockquote {
    border-left: 3px solid var(--ate-primary); background: #F8FAFC;
    margin: 6px 0; padding: 6px 12px; border-radius: 0 8px 8px 0; color: #334155;
}
.ate-cap { color: var(--ate-muted); font-size: 0.82rem; }

/* Lista de candidatos en sidebar */
.ate-cand { font-size: 0.84rem; color: var(--ate-ink); padding: 3px 0; }
.ate-cand small { color: var(--ate-muted); }
</style>
"""


_ESTADO_META = {
    "ok": ("ok", "ok"),
    "sin_datos": ("neutral", "sin datos"),
    "sin_candidato": ("neutral", "sin candidato"),
    "sin_fuentes": ("neutral", "sin fuentes"),
    "no_configurado": ("warn", "no configurado"),
    "offline": ("neutral", "offline"),
    "error": ("error", "error"),
    "error_red": ("error", "error de red"),
    "error_http": ("error", "error http"),
    "error_parseo": ("error", "error de parseo"),
}


def pill(estado: str) -> str:
    cls, label = _ESTADO_META.get(estado, ("neutral", estado))
    return f'<span class="ate-pill ate-pill--{cls}">{label}</span>'


def stats_chips(items: list[tuple[str, object]]) -> str:
    chips = "".join(
        f'<div class="ate-stat"><div class="v">{v}</div><div class="k">{k}</div></div>'
        for k, v in items
    )
    return f'<div class="ate-stats">{chips}</div>'


# ---------------------------------------------------------------------------
# Grafo + RAG
# ---------------------------------------------------------------------------


@st.cache_resource
def obtener_grafo():
    """Compila el grafo una sola vez por sesion del servidor (no por mensaje)."""
    return construir_grafo()


def inicializar_rag(cfg) -> None:
    """Ingesta los PDFs la primera vez si la base vectorial esta vacia.

    Se omite en modo offline porque la primera ingesta descarga el modelo
    de embeddings ONNX (requiere red). En offline el RAG no se consulta.
    """
    if cfg.ate_offline:
        return
    try:
        cliente_rag = abrir_cliente(cfg.rag_dir)
        if cliente_rag.contar() == 0:
            with st.status("Inicializando base de conocimientos (RAG)…", expanded=False) as status:
                st.write("Indexando los planes de gobierno de los candidatos…")
                ingestar_todos(cliente=cliente_rag, repo_root=Path(__file__).resolve().parent)
                status.update(label="Base de conocimientos lista", state="complete")
    except Exception as exc:  # noqa: BLE001 - la app no debe caerse por el RAG
        st.warning(f"No se pudo inicializar el RAG automaticamente: {exc}")


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_sidebar(cfg) -> bool:
    """Dibuja la barra lateral y devuelve el estado del interruptor de analisis."""
    with st.sidebar:
        st.markdown("### 🗳️ ATE")
        st.caption("Agente de Transparencia Electoral — Colombia 2026")

        st.divider()
        st.markdown("#### Modo de respuesta")
        mostrar_analisis = st.toggle(
            "Mostrar flujo de análisis",
            value=st.session_state.get("mostrar_analisis", True),
            key="mostrar_analisis",
            help="Activado: muestra toda la cadena de evidencia (planificación, "
            "extracción, RAG, contraste y validación). Desactivado: solo la "
            "respuesta final.",
        )
        st.caption(
            "🔍 Análisis completo" if mostrar_analisis else "💬 Solo respuesta final"
        )

        st.divider()
        st.markdown("#### Configuración")
        st.write("**Red:** " + ("🔌 Offline" if cfg.ate_offline else "🌐 Online"))
        proveedor = cfg.llm_provider if cfg.llm_available else f"{cfg.llm_provider} (sin credencial)"
        st.write(f"**LLM:** {proveedor}")
        if not cfg.llm_available:
            st.caption("Sin LLM: el generador usa su modo determinista (sin alucinaciones).")

        st.divider()
        st.markdown("#### Candidatos 2026")
        for c in CANDIDATOS_2026:
            st.markdown(
                f'<div class="ate-cand">{c.nombre_corto}<br><small>{c.partido}</small></div>',
                unsafe_allow_html=True,
            )

        if st.button("🗑️ Limpiar conversación", use_container_width=True):
            st.session_state.history = []
            st.rerun()

    return mostrar_analisis


def render_evidencia(estado: dict) -> None:
    """Renderiza la cadena de evidencia (el 'flujo de pensamiento') por pasos."""
    st.markdown('<div class="ate-step-label">Flujo de análisis</div>', unsafe_allow_html=True)

    # 1. Planificacion
    plan = estado.get("plan")
    if plan is not None:
        candidato = plan.candidato.nombre_canonico if plan.candidato else "No detectado"
        with st.expander("① Planificación — intención y candidato", expanded=False):
            st.markdown(
                f'<div class="ate-evi"><b>Intención:</b> {plan.intencion.value} &nbsp;·&nbsp; '
                f"<b>Candidato:</b> {candidato}</div>",
                unsafe_allow_html=True,
            )
            st.markdown("**Tools planificadas:** " + (", ".join(plan.tools) or "ninguna"))
            st.markdown(f'<div class="ate-cap">{plan.razonamiento}</div>', unsafe_allow_html=True)

    # 2. Extraccion
    ext = estado.get("contexto_extraido")
    if ext is not None:
        n = len(ext.resultados)
        with st.expander(f"② Extracción — fuentes oficiales consultadas ({n})", expanded=False):
            if not ext.resultados:
                st.markdown('<div class="ate-cap">No se invocaron tools para esta pregunta.</div>', unsafe_allow_html=True)
            for r in ext.resultados:
                st.markdown(
                    f"**{r.fuente}** &nbsp; {pill(r.estado)} &nbsp; "
                    f'<span class="ate-cap">{r.total_resultados} resultado(s)</span>',
                    unsafe_allow_html=True,
                )
                if r.mensaje:
                    st.markdown(f'<div class="ate-cap">{r.mensaje}</div>', unsafe_allow_html=True)
                for url in r.urls_oficiales:
                    st.markdown(f"- [{url}]({url})")

    # 3. RAG
    rag = estado.get("contexto_rag")
    if rag is not None:
        with st.expander(f"③ Planes de gobierno (RAG) — {rag.estado}", expanded=False):
            st.markdown(pill(rag.estado), unsafe_allow_html=True)
            if rag.mensaje:
                st.markdown(f'<div class="ate-cap">{rag.mensaje}</div>', unsafe_allow_html=True)
            for p in rag.pasajes:
                st.markdown(f'<div class="ate-evi"><blockquote>{p.texto}</blockquote></div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="ate-cap">— {p.candidato_nombre}, pág. {p.pagina} '
                    f"(score {p.score:.4f})</div>",
                    unsafe_allow_html=True,
                )

    # 4. Contraste
    con = estado.get("contraste")
    if con is not None:
        with st.expander(f"④ Contraste — propuesta vs. datos reales", expanded=True):
            st.markdown(pill(con.estado), unsafe_allow_html=True)
            if con.mensaje:
                st.markdown(f'<div class="ate-cap">{con.mensaje}</div>', unsafe_allow_html=True)
            st.markdown(
                stats_chips(
                    [
                        ("Propuestas", con.n_propuestas_analizadas),
                        ("Contratos", con.n_contratos_analizados),
                        ("Sanciones", con.n_sanciones_analizadas),
                        ("Inconsistencias", len(con.inconsistencias)),
                    ]
                ),
                unsafe_allow_html=True,
            )
            for inc in con.inconsistencias:
                st.warning(f"**{inc.tipo}** — {inc.descripcion}")
                if inc.evidencia_dato:
                    st.markdown(f'<div class="ate-cap">Dato: {inc.evidencia_dato}</div>', unsafe_allow_html=True)
                if inc.fuentes:
                    st.markdown(f'<div class="ate-cap">Fuentes: {", ".join(inc.fuentes)}</div>', unsafe_allow_html=True)
            if con.estado == "ok" and not con.inconsistencias:
                st.success("Sin inconsistencias entre propuestas y datos reales.")

    # 5. Validacion
    val = estado.get("validacion")
    if val is not None:
        with st.expander(f"⑤ Validación de fuentes — {val.estado}", expanded=False):
            st.markdown(
                stats_chips(
                    [
                        ("Oficiales", val.fuentes_oficiales),
                        ("No oficiales", val.fuentes_no_oficiales),
                        ("Inaccesibles", val.fuentes_inaccesibles),
                    ]
                ),
                unsafe_allow_html=True,
            )
            for f in val.fuentes_validadas:
                icono = "✅" if f.es_oficial else "⚠️"
                st.markdown(f"{icono} [{f.url}]({f.url}) — `{f.dominio_detectado}`")


def render_respuesta(content: str, llm_info: dict, mostrar_analisis: bool) -> None:
    st.markdown('<div class="ate-answer-label">Respuesta del agente</div>', unsafe_allow_html=True)
    st.markdown(content)
    if mostrar_analisis and (llm_info or {}).get("used_fallback"):
        st.caption("ℹ️ Generada en modo determinista (sin LLM).")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


def main() -> None:
    cfg = load_settings()
    st.markdown(_CSS, unsafe_allow_html=True)
    mostrar_analisis = render_sidebar(cfg)

    st.markdown(
        """
        <div class="ate-hero">
            <span class="ate-kicker">Auditoría ciudadana basada en evidencia</span>
            <h1>Agente de Transparencia Electoral</h1>
            <p>Pregunta sobre un candidato presidencial de Colombia 2026 y obtén un
            análisis que cruza sus propuestas con datos oficiales de contratación,
            sanciones y financiación — con citación verificable y sin juicios de valor.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    inicializar_rag(cfg)

    if "history" not in st.session_state:
        st.session_state.history = []

    # Estado vacio: sugerencias clicables.
    if not st.session_state.history:
        st.markdown('<div class="ate-step-label">Prueba con una pregunta</div>', unsafe_allow_html=True)
        ejemplos = [
            "¿Qué propone Iván Cepeda sobre derechos humanos?",
            "¿Qué contratos tiene Sergio Fajardo en SECOP?",
            "Sanciones de Claudia López en la Procuraduría",
            "Financiación de campaña de Paloma Valencia",
        ]
        cols = st.columns(2)
        for i, ej in enumerate(ejemplos):
            if cols[i % 2].button(ej, use_container_width=True, key=f"ej_{i}"):
                st.session_state.pendiente = ej
                st.rerun()

    # Historial.
    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                render_respuesta(msg["content"], msg.get("llm_info", {}), mostrar_analisis)
                if mostrar_analisis and msg.get("estado") is not None:
                    render_evidencia(msg["estado"])

    pregunta = st.chat_input("Haz una pregunta sobre la transparencia de un candidato…")
    if not pregunta:
        pregunta = st.session_state.pop("pendiente", None)
    if not pregunta:
        return

    st.session_state.history.append({"role": "user", "content": pregunta})
    with st.chat_message("user"):
        st.markdown(pregunta)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Ejecutando el grafo multiagente…"):
                estado_final = obtener_grafo().invoke({"pregunta": pregunta})
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Ocurrió un error al consultar el agente: {exc}"
            st.error(error_msg)
            st.session_state.history.append({"role": "assistant", "content": error_msg})
            return

        respuesta = estado_final.get("respuesta_final") or (
            "No se pudo generar una respuesta final. Activa el flujo de análisis "
            "para ver dónde se detuvo el proceso."
        )
        llm_info = estado_final.get("llm_info") or {}
        render_respuesta(respuesta, llm_info, mostrar_analisis)
        if mostrar_analisis:
            render_evidencia(estado_final)

    st.session_state.history.append(
        {"role": "assistant", "content": respuesta, "llm_info": llm_info, "estado": estado_final}
    )


if __name__ == "__main__":
    main()
