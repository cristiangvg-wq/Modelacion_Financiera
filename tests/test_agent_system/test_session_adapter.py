import pandas as pd

from agents.session_adapter import build_session_snapshot


class LogicStub:
    def metricas_valoracion_sesion(self, company):
        if company != "ISA":
            return None
        return {
            "empresa": "ISA", "ticker": "ISA.CL", "moneda": "COP",
            "wacc_calc": 0.10, "ke_calc": 0.13, "g_usada": 0.035,
            "nivel_calidad": "MEDIA", "fuente_financiera": "Yahoo Finance",
            "fuente_mercado": "Yahoo Finance", "vetos_calidad": [],
            "alertas_modelo": [],
        }


def valid_session():
    projection = pd.DataFrame([{
        "NOPAT": 100.0, "Depreciacion": 20.0, "CAPEX": 30.0,
        "Delta_NWC": 10.0, "FCFF": 80.0,
    }], index=[2026])
    return {
        "empresa_sel": "ISA",
        "modelo_dirty": False,
        "params": {"de_ratio": 0.5, "kd": 0.08, "tax": 0.25, "g": 0.035, "beta_u": 0.8},
        "rf": 0.09, "erp": 0.06, "crp": 0.0,
        "resultados": {"tab1": ("info", None, None, None, None, "", projection)},
    }


def test_adapter_builds_snapshot_from_current_session_without_mutating_it():
    session = valid_session()
    before = dict(session)
    payload, reason = build_session_snapshot(session, LogicStub())
    assert reason is None
    assert payload["company"] == "ISA"
    assert payload["ticker"] == "ISA.CL"
    assert payload["model_inputs"]["debt_weight"] == 1 / 3
    assert payload["model_inputs"]["equity_weight"] == 2 / 3
    assert payload["model_inputs"]["nopat"] == 100.0
    assert payload["model_inputs"]["depreciation"] == 20.0
    assert payload["model_outputs"]["fcff"] == 80.0
    assert payload["model_outputs"]["wacc"] == 0.10
    assert session == before


def test_adapter_blocks_when_model_is_dirty():
    session = valid_session()
    session["modelo_dirty"] = True
    payload, reason = build_session_snapshot(session, LogicStub())
    assert payload is None
    assert "Generar todo" in reason


def test_adapter_requires_fresh_tab4_metrics():
    session = valid_session()
    payload, reason = build_session_snapshot(session, object())
    assert payload is None
    assert "pestaña 4" in reason


def test_adapter_does_not_mix_company_results():
    session = valid_session()
    session["empresa_sel"] = "GEB"
    payload, reason = build_session_snapshot(session, LogicStub())
    assert payload is None
    assert "pestaña 4" in reason


def test_adapter_handles_missing_fcff_components_as_limitations():
    session = valid_session()
    session["resultados"]["tab1"][6].drop(columns=["CAPEX"], inplace=True)
    payload, reason = build_session_snapshot(session, LogicStub())
    assert reason is None
    assert "capex" not in payload["model_inputs"]
    assert payload["model_outputs"]["fcff"] == 80.0
