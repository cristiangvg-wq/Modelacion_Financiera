from __future__ import annotations

import math

import pytest

from scenario_api.main import _projection_for_margin, _snapshot_inputs, calculate_scenario


def sample_metrics():
    rows = [
        {"Año": 2026, "Ingresos": 1000.0, "EBITDA": 500.0, "EBIT": 400.0,
         "Depreciacion": 100.0, "CAPEX": 120.0, "Delta_NWC": 10.0},
        {"Año": 2027, "Ingresos": 1100.0, "EBITDA": 550.0, "EBIT": 440.0,
         "Depreciacion": 110.0, "CAPEX": 130.0, "Delta_NWC": 11.0},
        {"Año": 2028, "Ingresos": 1210.0, "EBITDA": 605.0, "EBIT": 484.0,
         "Depreciacion": 121.0, "CAPEX": 140.0, "Delta_NWC": 12.0},
    ]
    return {
        "ticker": "ISA",
        "moneda": "COP",
        "unidad_modelo": "miles de millones de COP",
        "wacc_calc": 0.12,
        "g_usada": 0.03,
        "val_ev": 5000.0,
        "ronic_terminal": 0.13,
        "precio_mercado": 100.0,
        "supuestos": {"tax": 0.35, "mid_year": True, "g_max_macro": 0.05},
        "bridge": {"deuda_neta": 500.0, "caja": 0.0, "nci": 0.0, "otros_claims": 0.0,
                   "asociados": 0.0, "acciones": 100.0, "exit_multiple": 0.0},
        "proyeccion_sensibilidad": rows,
    }


def test_snapshot_rejects_non_isa():
    with pytest.raises(ValueError, match="ISA"):
        _snapshot_inputs({"ticker": "GEB"})


def test_snapshot_requires_projection():
    with pytest.raises(ValueError, match="proyeccion_sensibilidad"):
        _snapshot_inputs({"ticker": "ISA", "bridge": {}, "supuestos": {}})


def test_margin_change_recalculates_fcff_with_python_engine():
    metrics = sample_metrics()
    rows, bridge, assumptions = _snapshot_inputs(metrics)
    base_margin = 0.5
    fcff_base, _, _, _ = _projection_for_margin(rows, assumptions, base_margin)
    fcff_higher, _, _, _ = _projection_for_margin(rows, assumptions, 0.52)
    assert len(fcff_base) == 3
    assert all(math.isfinite(value) for value in fcff_higher)
    assert fcff_higher != fcff_base


def test_full_scenario_returns_sensitivity_and_three_cases():
    result = calculate_scenario(sample_metrics(), {"wacc": 0.12, "g": 0.03, "ebitda_margin": 0.50})
    assert set(result["scenarios"]) == {"Bear", "Base", "Bull"}
    assert len(result["sensitivity"]) == 5
    assert len(result["tornado"]) == 3
    assert result["diagnostics"]["official_publication_is_unchanged"] is True
    assert result["diagnostics"]["calculation_is_persisted"] is False
    assert result["base"]["EV"] > 0
