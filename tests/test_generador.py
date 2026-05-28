import pytest

from ate.agents.generador import _extraer_texto_ollama, _sanitizar_texto


def test_sanitizar_texto_elimina_escape_y_normaliza():
    entrada = 'Respuesta con \\\"comillas\\\" y \\n saltos \\t y \\r retornos'
    esperado = 'Respuesta con "comillas" y saltos y retornos'
    assert _sanitizar_texto(entrada) == esperado


def test_extraer_texto_ollama_usa_response_y_thinking():
    assert _extraer_texto_ollama({"response": "hola"}) == "hola"
    assert _extraer_texto_ollama({"thinking": "pensando"}) == "pensando"


def test_extraer_texto_ollama_usa_output_con_texto():
    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "texto completo"}
                ]
            }
        ]
    }
    assert _extraer_texto_ollama(payload) == "texto completo"


def test_extraer_texto_ollama_lanza_si_no_hay_texto():
    with pytest.raises(RuntimeError, match="no devolvió texto"):
        _extraer_texto_ollama({"output": []})
