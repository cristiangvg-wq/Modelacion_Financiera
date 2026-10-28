"""Gemini: una cuota agotada (HTTP 429) se informa como tal, y no se prueban modelos retirados."""
import io
import urllib.error
import urllib.request

import modelacion_logic as L


def _falso_429(req, timeout=None):
    raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b'{"error":{"code":429}}'))


def test_cuota_agotada_en_busqueda_web(monkeypatch):
    L.vincular_estado_sesion({})
    monkeypatch.setattr(urllib.request, "urlopen", _falso_429)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    try:
        r = L._llamar_ia_redaccion("s", "u", api_key="clave-falsa", proveedor="gemini", buscar_web=True)
        assert r is None
        err = L._get_ia_error()
        assert "Cuota de Gemini agotada" in err and "búsqueda web" in err
        assert "clave-falsa" not in err
    finally:
        L.desvincular_estado_sesion()


def test_sin_modelos_retirados():
    assert "gemini-2.5-flash" not in L.GEMINI_MODELOS_PREFERIDOS
