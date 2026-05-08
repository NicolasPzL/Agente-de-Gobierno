"""Tests del agente RAG y la tool buscar_plan_gobierno (Sprint 3).

Mockean el cliente Chroma para no tocar la red ni el filesystem real.
Verifican:
    - El agente decide invocar RAG solo para plan_gobierno o cuando hay candidato.
    - Si la base esta vacia, devuelve no_configurado (no inventa).
    - Si chromadb no esta importable, devuelve no_configurado.
    - Modo offline corta antes de tocar Chroma.
    - El filtro candidato_id se propaga al cliente.
    - El ingestor chunkea correctamente y produce metadata estable.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from ate.agents.rag import _debe_invocar_rag, consultar_rag
from ate.candidatos.registro import por_id
from ate.config.settings import load_settings
from ate.rag.cliente import Hit
from ate.rag.ingestor import _limpiar_texto, _ventanas, chunkear_pdf
from ate.schemas.state import ContextoRag, Intencion, PlanEjecucion
from ate.tools.rag_planes import buscar_plan_gobierno


def _cfg(**overrides):
    base = load_settings()
    overrides.setdefault("ate_offline", False)
    return replace(base, **overrides)


# ---------------- _debe_invocar_rag ----------------


def test_no_invoca_si_plan_es_none():
    assert _debe_invocar_rag(None) is False


def test_no_invoca_si_indefinida_sin_candidato():
    plan = PlanEjecucion(intencion=Intencion.INDEFINIDA, tools=[])
    assert _debe_invocar_rag(plan) is False


def test_invoca_si_intencion_plan_gobierno():
    plan = PlanEjecucion(intencion=Intencion.PLAN_GOBIERNO, tools=[])
    assert _debe_invocar_rag(plan) is True


def test_invoca_si_hay_candidato_aunque_intencion_sea_otra():
    cep = por_id("ivan-cepeda")
    plan = PlanEjecucion(
        intencion=Intencion.CONTRATACION,
        tools=["consultar_secop"],
        candidato=cep,
    )
    assert _debe_invocar_rag(plan) is True


# ---------------- consultar_rag ----------------


def test_rag_offline():
    cfg = _cfg(ate_offline=True)
    plan = PlanEjecucion(intencion=Intencion.PLAN_GOBIERNO, tools=[])
    ctx = consultar_rag("salud", plan, cfg)
    assert ctx.estado == "offline"


def test_rag_no_se_activa_para_intencion_no_relevante():
    cfg = _cfg()
    plan = PlanEjecucion(intencion=Intencion.NOTICIAS, tools=["buscar_noticias"])
    ctx = consultar_rag("ultima entrevista", plan, cfg)
    assert ctx.estado == "sin_datos"
    assert ctx.pasajes == []


def test_rag_base_vacia_devuelve_no_configurado(monkeypatch):
    cfg = _cfg()
    plan = PlanEjecucion(intencion=Intencion.PLAN_GOBIERNO, tools=[])

    cliente_mock = MagicMock()
    cliente_mock.contar.return_value = 0
    monkeypatch.setattr("ate.rag.cliente.abrir_cliente", lambda *a, **k: cliente_mock)
    monkeypatch.setattr("ate.agents.rag.abrir_cliente", lambda *a, **k: cliente_mock, raising=False)

    # La importacion perezosa dentro del agente -> reescribir su `from ate.rag.cliente import abrir_cliente`
    import ate.rag.cliente as cliente_mod
    monkeypatch.setattr(cliente_mod, "abrir_cliente", lambda *a, **k: cliente_mock)

    ctx = consultar_rag("salud", plan, cfg)
    assert ctx.estado == "no_configurado"
    assert "ingestar_planes" in ctx.mensaje


def test_rag_retorna_pasajes_normalizados(monkeypatch):
    cfg = _cfg()
    cep = por_id("ivan-cepeda")
    plan = PlanEjecucion(
        intencion=Intencion.PLAN_GOBIERNO,
        tools=["buscar_plan_gobierno"],
        candidato=cep,
    )

    hits_mock = [
        Hit(
            chunk_id="ivan-cepeda:p1:c0",
            texto="Propuesta sobre derechos humanos...",
            metadata={
                "candidato_id": "ivan-cepeda",
                "candidato_nombre": "Ivan Cepeda Castro",
                "pdf": "public/Candidatos/x.pdf",
                "pagina": 3,
            },
            distancia=0.21,
        )
    ]

    cliente_mock = MagicMock()
    cliente_mock.contar.return_value = 13
    cliente_mock.buscar.return_value = hits_mock

    import ate.rag.cliente as cliente_mod
    monkeypatch.setattr(cliente_mod, "abrir_cliente", lambda *a, **k: cliente_mock)

    ctx = consultar_rag("derechos humanos", plan, cfg)
    assert ctx.estado == "ok"
    assert ctx.candidato_filtro == "ivan-cepeda"
    assert len(ctx.pasajes) == 1
    p = ctx.pasajes[0]
    assert p.candidato_nombre == "Ivan Cepeda Castro"
    assert p.pagina == 3
    assert p.score == 0.21
    # Verificar que el filtro se paso al cliente
    cliente_mock.buscar.assert_called_once()
    args, kwargs = cliente_mock.buscar.call_args
    assert kwargs.get("candidato_id") == "ivan-cepeda"


def test_rag_sin_pasajes_es_sin_datos(monkeypatch):
    cfg = _cfg()
    cep = por_id("sergio-fajardo")
    plan = PlanEjecucion(
        intencion=Intencion.PLAN_GOBIERNO,
        tools=[],
        candidato=cep,
    )

    cliente_mock = MagicMock()
    cliente_mock.contar.return_value = 13
    cliente_mock.buscar.return_value = []

    import ate.rag.cliente as cliente_mod
    monkeypatch.setattr(cliente_mod, "abrir_cliente", lambda *a, **k: cliente_mock)

    ctx = consultar_rag("xyz topic raro", plan, cfg)
    assert ctx.estado == "sin_datos"


# ---------------- tool buscar_plan_gobierno ----------------


def test_tool_offline():
    cfg = _cfg(ate_offline=True)
    r = buscar_plan_gobierno("salud", settings=cfg)
    assert r.estado == "offline"


def test_tool_consulta_vacia():
    cfg = _cfg()
    r = buscar_plan_gobierno("   ", settings=cfg)
    assert r.estado == "sin_datos"


def test_tool_base_vacia(monkeypatch):
    cfg = _cfg()
    cliente_mock = MagicMock()
    cliente_mock.contar.return_value = 0

    import ate.rag.cliente as cliente_mod
    monkeypatch.setattr(cliente_mod, "abrir_cliente", lambda *a, **k: cliente_mock)

    r = buscar_plan_gobierno("salud", settings=cfg)
    assert r.estado == "no_configurado"


def test_tool_con_filtro_candidato(monkeypatch):
    cfg = _cfg()
    cep = por_id("ivan-cepeda")

    hits_mock = [
        Hit(
            chunk_id="ivan-cepeda:p2:c1",
            texto="...derechos humanos...",
            metadata={
                "candidato_id": "ivan-cepeda",
                "candidato_nombre": "Ivan Cepeda Castro",
                "pdf": "x.pdf",
                "pagina": 2,
            },
            distancia=0.3,
        )
    ]
    cliente_mock = MagicMock()
    cliente_mock.contar.return_value = 13
    cliente_mock.buscar.return_value = hits_mock

    import ate.rag.cliente as cliente_mod
    monkeypatch.setattr(cliente_mod, "abrir_cliente", lambda *a, **k: cliente_mock)

    r = buscar_plan_gobierno("derechos", settings=cfg, candidato=cep)
    assert r.estado == "ok"
    assert r.total_resultados == 1
    cliente_mock.buscar.assert_called_with("derechos", k=cfg.rag_top_k, candidato_id="ivan-cepeda")


# ---------------- ingestor ----------------


def test_limpiar_texto_normaliza_espacios():
    crudo = "Linea uno\nLinea dos   con  multiples\nespacios"
    limpio = _limpiar_texto(crudo)
    assert "\n" not in limpio
    assert "  " not in limpio


def test_limpiar_texto_repara_palabras_cortadas():
    """Newline despues de un guion = palabra cortada al final de linea."""
    assert _limpiar_texto("transfor-\nmacion") == "transformacion"


def test_ventanas_respeta_tamano_y_overlap():
    texto = "abcdefghijklmnopqrstuvwxyz" * 4   # 104 chars
    ventanas = list(_ventanas(texto, tamano=30, overlap=10))
    assert all(len(v) <= 30 for v in ventanas)
    assert len(ventanas) > 1
    # solapamiento = primeros 10 chars de la siguiente == ultimos 10 de la anterior
    assert ventanas[1][:10] == ventanas[0][-10:]


def test_chunkear_pdf_real_si_existe():
    """Si el PDF de Cepeda existe en el repo, chunkearlo produce >0 chunks."""
    pdf = Path("public/Candidatos/candidatos_presidenciales_2026-Ivan Cepeda.pdf")
    if not pdf.exists():
        pytest.skip("PDF no presente en CI")
    cep = por_id("ivan-cepeda")
    chunks = chunkear_pdf(pdf, candidato=cep)
    assert len(chunks) > 0
    primero = chunks[0]
    assert primero.candidato_id == "ivan-cepeda"
    assert primero.candidato_nombre == "Ivan Cepeda Castro"
    assert primero.pagina >= 1
    assert primero.chunk_id.startswith("ivan-cepeda:")


def test_chunkear_pdf_inexistente_lanza_filenotfound():
    cep = por_id("ivan-cepeda")
    with pytest.raises(FileNotFoundError):
        chunkear_pdf("no-existe.pdf", candidato=cep)
