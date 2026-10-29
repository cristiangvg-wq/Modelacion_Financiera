"""Regresión funcional de los cálculos que alimentan la pestaña 10 para ISA.

La proyección usa el cierre 2025 y los supuestos documentados del caso ISA:
crecimiento de ventas 6,3 %, margen EBITDA 57,8 %, D&A/ventas 7,178 %,
CAPEX/ventas 13,723 %, KTNO/ventas 27,35 % e impuesto 35 %.
Los tests validan la capa financiera; no sustituyen una prueba end-to-end de la UI.
"""
import numpy as np
import pandas as pd

import modelacion_logic as L


TAX = 0.35
WACC = 0.122
G_TERMINAL = 0.035
G_MAX_MACRO = 0.0609


def isa_projection():
    """Proyección 2026–2030 en COP billones, a partir de las hipótesis del caso."""
    revenue_2025 = 15.918005563
    growth = 0.063
    margin_ebitda = 0.577582
    da_ratio = 0.071780
    capex_ratio = 0.137233
    nwc_ratio = 0.273501

    revenues = [revenue_2025 * (1 + growth) ** year for year in range(1, 6)]
    nwc = [revenue * nwc_ratio for revenue in revenues]
    df = pd.DataFrame({
        "Año": [2026, 2027, 2028, 2029, 2030],
        "Ingresos": revenues,
        "EBITDA": [revenue * margin_ebitda for revenue in revenues],
        "Depreciacion": [revenue * da_ratio for revenue in revenues],
        "CAPEX": [revenue * capex_ratio for revenue in revenues],
        "NWC": nwc,
        "Delta_NWC": [nwc[0] - revenue_2025 * nwc_ratio] + [
            nwc[i] - nwc[i - 1] for i in range(1, len(nwc))
        ],
    })
    # EBIT histórico/operativo se mantiene separado de EBITDA y D&A en el modelo.
    df["EBIT"] = df["EBITDA"] - df["Depreciacion"]
    return L.recalcular_fcff(df, tax=TAX, capex_extra=0.0)


def value_projection(df):
    fcff = pd.to_numeric(df["FCFF"], errors="raise").astype(float).tolist()
    bridge = {
        # Deuda neta 2025 = deuda financiera 34,68 − caja 4,47; caja no se suma dos veces.
        "deuda_neta": 30.21,
        "caja": 0.0,
        "nci": 0.0,
        "otros_claims": 0.0,
        "asociados": 0.0,
    }
    return L.valorar_con_bridge(
        fcff, WACC, G_TERMINAL, bridge,
        ebitda_salida=float(df["EBITDA"].iloc[-1]),
        mid_year=True, g_max_macro=G_MAX_MACRO,
        nopat_final=float(df["NOPAT"].iloc[-1]),
    )


def test_isa_base_projection_has_finite_fcff_and_accounting_identity():
    df = isa_projection()
    assert len(df) == 5
    for column in ("Ingresos", "EBITDA", "EBIT", "NOPAT", "CAPEX", "Delta_NWC", "FCFF"):
        assert np.isfinite(df[column].to_numpy(dtype=float)).all()

    expected_fcff = df["NOPAT"] + df["Depreciacion"] - df["CAPEX"] - df["Delta_NWC"]
    np.testing.assert_allclose(df["FCFF"], expected_fcff, rtol=1e-10, atol=1e-10)
    assert (df["Ingresos"] > 0).all()


def test_isa_base_scenario_is_identity_and_operating_shocks_change_drivers():
    base = isa_projection()
    base_shock = L.aplicar_shocks_drivers_proyeccion(
        base, tax=TAX, shock=L.SHOCKS_ESCENARIOS["Base"]
    )
    pd.testing.assert_series_equal(base_shock["Ingresos"], base["Ingresos"], check_names=False)
    pd.testing.assert_series_equal(base_shock["CAPEX"], base["CAPEX"], check_names=False)
    pd.testing.assert_series_equal(base_shock["Delta_NWC"], base["Delta_NWC"], check_names=False)

    optimistic = L.aplicar_shocks_drivers_proyeccion(
        base, tax=TAX, shock=L.SHOCKS_ESCENARIOS["Optimista"]
    )
    pessimistic = L.aplicar_shocks_drivers_proyeccion(
        base, tax=TAX, shock=L.SHOCKS_ESCENARIOS["Pesimista"]
    )
    assert (optimistic["Ingresos"] > base["Ingresos"]).all()
    assert (pessimistic["Ingresos"] < base["Ingresos"]).all()
    assert not np.allclose(optimistic["FCFF"], base["FCFF"])
    assert not np.allclose(pessimistic["FCFF"], base["FCFF"])


def test_policy_valuation_uses_same_bridge_and_reports_delta_ev_not_project_npv():
    base = isa_projection()
    base_value = value_projection(base)
    assert np.isfinite(float(base_value["EV"]))
    assert np.isfinite(float(base_value["Equity_Value"]))
    assert float(base_value["EV"]) > 0
    assert float(base_value["Equity_Value"]) > 0

    # Política CAPEX: reducción de 10 %, con piso explícito de 10 % de ventas.
    capex_policy = base.copy()
    capex_policy["CAPEX"] = np.maximum(
        capex_policy["Ingresos"] * 0.10,
        capex_policy["CAPEX"] * 0.90,
    )
    capex_policy = L.recalcular_fcff(capex_policy, tax=TAX, capex_extra=0.0)
    capex_value = value_projection(capex_policy)

    delta_ev = float(capex_value["EV"]) - float(base_value["EV"])
    delta_equity = float(capex_value["Equity_Value"]) - float(base_value["Equity_Value"])
    assert np.isfinite(delta_ev) and np.isfinite(delta_equity)
    # Como se mantiene el mismo bridge de deuda/claims, el delta de Equity
    # debe coincidir con el delta EV (salvo tolerancia numérica).
    np.testing.assert_allclose(delta_equity, delta_ev, rtol=1e-9, atol=1e-9)
    # El indicador es delta de valoración empresarial con TV, no una TIR ni VPN
    # de inversión aislada; no se calcula TIR con FCFF corporativo.
