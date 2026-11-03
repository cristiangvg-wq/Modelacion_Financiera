"""Despliegue en Streamlit Cloud: el script se re-ejecuta sin reiniciar el proceso y los módulos importados
quedan con su versión anterior. La pestaña 10 falló con «no attribute 'datos_taller_modelo'» tras el PR #80."""
import ast
import importlib
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cargar_funcion_recarga():
    """Extrae _recargar_si_cambio de streamlit_app.py sin ejecutar la app."""
    src = (ROOT / "streamlit_app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_recargar_si_cambio")
    ns = {"os": os, "importlib": importlib}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "streamlit_app.py", "exec"), ns)
    return ns["_recargar_si_cambio"], src


class TestRecargaModulos(unittest.TestCase):
    def test_api_requerida_incluye_lo_que_usa_la_pestana_10(self):
        _, src = _cargar_funcion_recarga()
        for n in ("datos_taller_modelo", "calendario_valoracion", "bridge_con_fechas", "config_ronic_sesion"):
            self.assertIn(f'"{n}"', src)

    def test_recarga_por_cambio_de_archivo(self):
        recargar, _ = _cargar_funcion_recarga()
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / "mod_prueba_recarga.py"
            ruta.write_text("VERSION = 1\n", encoding="utf-8")
            sys.path.insert(0, tmp)
            try:
                mod = importlib.import_module("mod_prueba_recarga")
                mod = recargar(mod)
                self.assertEqual(mod.VERSION, 1)
                ruta.write_text("VERSION = 2\ndef nueva():\n    return 2\n", encoding="utf-8")
                os.utime(ruta, (time.time() + 5, time.time() + 5))
                mod = recargar(mod)
                self.assertEqual(mod.VERSION, 2)
                self.assertEqual(mod.nueva(), 2)
            finally:
                sys.path.remove(tmp)
                sys.modules.pop("mod_prueba_recarga", None)

    def test_recarga_si_falta_la_api(self):
        recargar, _ = _cargar_funcion_recarga()
        import modelacion_logic as L
        guardada = L.datos_taller_modelo
        try:
            del L.datos_taller_modelo
            L2 = recargar(L, ("datos_taller_modelo",))
            self.assertTrue(hasattr(L2, "datos_taller_modelo"))
        finally:
            if not hasattr(L, "datos_taller_modelo"):
                L.datos_taller_modelo = guardada


if __name__ == "__main__":
    unittest.main()
