#!/usr/bin/env python3
"""Modelo académico reproducible del taller ISA: pronóstico, escenarios y políticas.

Montos en miles de millones de COP. Los shocks son supuestos ilustrativos editables,
no pronósticos oficiales de ISA. No calcula un precio objetivo ni sustituye el DCF
principal de la aplicación.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "datos_curados.json"
DEFAULT_OUT = ROOT / "salidas_taller_isa"

SCENARIOS = {
    "Pesimista": {
        "growth": 0.02,
        "ebit_margin_delta": -0.02,
        "capex_ratio_delta": 0.03,
        "nwc_ratio_delta": 0.02,
    },
    "Base": {
        "growth": 0.0635,
        "ebit_margin_delta": 0.0,
        "capex_ratio_delta": 0.0,
        "nwc_ratio_delta": 0.0,
    },
    "Optimista": {
        "growth": 0.09,
        "ebit_margin_delta": 0.01,
        "capex_ratio_delta": -0.03,
        "nwc_ratio_delta": -0.01,
    },
}

POLICIES = {
    "Sin política": {"capex_saving": 0.0, "ebit_margin_uplift": 0.0},
    # Se asume que 30% del CAPEX es expansión; se reduce 15% de ese componente.
    "Priorizar CAPEX": {"capex_saving": 0.30 * 0.15, "ebit_margin_uplift": 0.0},
    # Mejora hipotética de 50 puntos básicos en margen EBIT, sin atribuirla a datos observados.
    "Eficiencia operativa": {"capex_saving": 0.0, "ebit_margin_uplift": 0.005},
}

WACC_ILLUSTRATIVE = 0.105  # Solo para descuento de comparación; validar contra pestaña DCF.
TAX_RATE = 0.22
FORECAST_YEARS = range(2026, 2031)


def load_isa(data_path: Path = DEFAULT_DATA) -> dict:
    data = json.loads(data_path.read_text(encoding="utf-8"))
    company = data["empresas"]["ISA — Interconexión Eléctrica"]
    h = company["historico"]
    rows = []
    for i, year in enumerate(h["Año"]):
        rows.append({k: float(h[k][i]) for k in ("Ingresos", "EBIT", "Depreciacion", "CAPEX", "NWC")})
        rows[-1]["Año"] = int(year)
    return {
        "history": rows,
        "tax": float(company["supuestos"]["tax"]),
        "data_as_of": data.get("as_of"),
        "verification": company.get("verificacion", ""),
        "source": company.get("fuente_historico", ""),
        "currency": data.get("moneda", "COP"),
        "unit": data.get("unidad", "miles de millones"),
    }


def build_projection(scenario_name: str, policy_name: str, isa: dict) -> list[dict]:
    h = isa["history"]
    last = h[-1]
    scenario = SCENARIOS[scenario_name]
    policy = POLICIES[policy_name]
    revenue = last["Ingresos"]
    previous_nwc = last["NWC"]
    base_ebit_margin = last["EBIT"] / last["Ingresos"]
    da_ratio = last["Depreciacion"] / last["Ingresos"]
    capex_ratio = last["CAPEX"] / last["Ingresos"]
    nwc_ratio = last["NWC"] / last["Ingresos"]
    tax = isa["tax"]
    result = []
    for year in FORECAST_YEARS:
        revenue *= 1 + scenario["growth"]
        ebit_margin = base_ebit_margin + scenario["ebit_margin_delta"] + policy["ebit_margin_uplift"]
        depreciation = revenue * da_ratio
        ebit = revenue * ebit_margin
        # Se aplica el shock a la ratio histórica y luego el ahorro incremental de política.
        capex = revenue * capex_ratio * (1 + scenario["capex_ratio_delta"]) * (1 - policy["capex_saving"])
        nwc = revenue * nwc_ratio * (1 + scenario["nwc_ratio_delta"])
        delta_nwc = nwc - previous_nwc
        nopat = ebit * (1 - tax)
        fcff = nopat + depreciation - capex - delta_nwc
        discount_factor = 1 / ((1 + WACC_ILLUSTRATIVE) ** (year - 2025))
        result.append({
            "escenario": scenario_name,
            "politica": policy_name,
            "año": year,
            "ingresos": revenue,
            "crecimiento_ingresos": scenario["growth"],
            "margen_ebit": ebit_margin,
            "ebit": ebit,
            "impuestos_sobre_ebit": ebit * tax,
            "nopat": nopat,
            "depreciacion": depreciation,
            "capex": capex,
            "nwc": nwc,
            "delta_nwc": delta_nwc,
            "fcff": fcff,
            "factor_descuento_wacc_ilustrativo": discount_factor,
            "valor_presente_fcff_explicito": fcff * discount_factor,
        })
        previous_nwc = nwc
    return result


def run_model(data_path: Path = DEFAULT_DATA, output_dir: Path = DEFAULT_OUT) -> dict:
    isa = load_isa(data_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    detail = []
    summary = []
    for scenario_name in SCENARIOS:
        for policy_name in POLICIES:
            rows = build_projection(scenario_name, policy_name, isa)
            detail.extend(rows)
            summary.append({
                "escenario": scenario_name,
                "politica": policy_name,
                "fcff_acumulado_2026_2030": sum(r["fcff"] for r in rows),
                "vp_fcff_explicito_wacc_ilustrativo": sum(r["valor_presente_fcff_explicito"] for r in rows),
                "fcff_2030": rows[-1]["fcff"],
                "supuestos_no_observados": "Sí: shocks de escenario y políticas",
                "wacc_usado_solo_para_descuento": WACC_ILLUSTRATIVE,
                "tasa_impuestos": isa["tax"],
            })
    for name, rows in (("detalle_escenarios_politicas.csv", detail), ("resumen_escenarios_politicas.csv", summary)):
        with (output_dir / name).open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    metadata = {
        "empresa": "ISA — Interconexión Eléctrica",
        "datos_a_corte": isa["data_as_of"],
        "moneda": isa["currency"],
        "unidad": isa["unit"],
        "historia": [r["Año"] for r in isa["history"]],
        "horizonte": [min(FORECAST_YEARS), max(FORECAST_YEARS)],
        "drivers": ["crecimiento de ingresos", "margen EBIT", "ratio CAPEX/ingresos", "ratio NWC/ingresos", "depreciación/ingresos"],
        "escenarios": SCENARIOS,
        "politicas": POLICIES,
        "wacc_ilustrativo": WACC_ILLUSTRATIVE,
        "advertencias": [
            "Los shocks de escenarios y políticas son hipótesis editables, no datos observados ni metas oficiales de ISA.",
            "La ratio CAPEX/ingresos de 2025 es elevada; debe verificarse clasificación, perímetro y unidad antes de usar el FCFF como valoración.",
            "El valor presente reportado es solo el de los FCFF explícitos; no incluye valor terminal ni es un VPN de proyecto porque no hay inversión inicial incremental definida.",
            "El WACC de 10,5% es ilustrativo para comparación y debe sustituirse por el WACC validado de la pestaña de valoración.",
            "NWC está estimado en la fuente curada y requiere conciliación con balances detallados.",
        ],
        "fuente_historico": isa["source"],
        "verificacion_historico": isa["verification"],
    }
    (output_dir / "metadatos_modelo.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"detail": detail, "summary": summary, "metadata": metadata}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Ruta a datos_curados.json")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Directorio de salida")
    args = parser.parse_args()
    result = run_model(args.data, args.out)
    print(f"Empresa: {result['metadata']['empresa']}")
    print(f"Histórico: {result['metadata']['historia']} | proyección: 2026–2030")
    print(f"Escenarios: {len(SCENARIOS)} | políticas: {len(POLICIES)} | filas de detalle: {len(result['detail'])}")
    print(f"Archivos generados en: {args.out}")
    print("ADVERTENCIA: supuestos ilustrativos; validar CAPEX, NWC y WACC antes de interpretar la valoración.")


if __name__ == "__main__":
    main()
