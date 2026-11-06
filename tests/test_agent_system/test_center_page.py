from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_agent_center_page_renders_without_existing_model_session():
    page = Path(__file__).resolve().parents[2] / "pages" / "12_Centro_Agentes.py"
    app = AppTest.from_file(str(page), default_timeout=30).run()

    assert not app.exception
    assert any("Selecciona una empresa" in item.value for item in app.warning)
