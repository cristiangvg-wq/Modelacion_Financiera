"""Centro de Agentes IA — auditoría financiera inicial (snapshot JSON)."""
from __future__ import annotations

import json
import streamlit as st

from agents.service import audit_snapshot

st.set_page_config(page_title="Centro de Agentes IA", page_icon="🧠", layout="wide")
st.title("🧠 Centro de Agentes IA")
st.caption("Versión inicial · auditoría financiera de solo lectura · no modifica el modelo")

st.info(
    "Esta primera versión audita un snapshot JSON que tú proporcionas. "
    "Todavía no extrae automáticamente los parámetros de la sesión de valoración. "
    "Las tasas deben expresarse como decimales: 0.10 equivale a 10%."
)

example = {
    "task": "Auditoría financiera de ejemplo",
    "company": "ISA",
    "ticker": "ISA",
    "currency": "COP",
    "repository_ref": "main",
    "model_inputs": {
        "debt_weight": 0.4,
        "equity_weight": 0.6,
        "kd": 0.08,
        "ke": 0.12,
        "tax_rate": 0.25,
        "nopat": 100.0,
        "depreciation": 20.0,
        "capex": 30.0,
        "change_nwc": 10.0,
        "wacc": 0.096,
        "terminal_growth": 0.035,
        "fcff_next": 80.0
    },
    "model_outputs": {"wacc": 0.096, "fcff": 80.0, "terminal_value": 1311.475409836},
    "data_provenance": [],
    "quality_flags": []
}

left, right = st.columns([1.15, 0.85], gap="large")
with left:
    st.subheader("Snapshot del modelo")
    raw = st.text_area(
        "Pega o edita el JSON con los datos que quieres auditar",
        value=json.dumps(example, ensure_ascii=False, indent=2),
        height=540,
        help="No incluyas claves API, credenciales ni información personal sensible.",
    )
    run = st.button("Ejecutar auditoría", type="primary", use_container_width=True)
with right:
    st.subheader("Comprobaciones disponibles")
    st.markdown(
        "- Pesos de deuda y patrimonio en WACC.\n"
        "- Reconciliación de WACC con kd, ke e impuestos.\n"
        "- Identidad FCFF = NOPAT + D&A − CAPEX − variación de NWC.\n"
        "- Condición WACC > g y fórmula de Gordon-Shapiro.\n"
        "- Alertas de calidad entregadas en el snapshot."
    )
    st.warning("No cambia supuestos, fórmulas, archivos ni datos del modelo. No reemplaza una revisión profesional.")

if run:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("El JSON debe contener un objeto en el nivel superior.")
        report = audit_snapshot(payload)
        st.session_state["agent_audit_last_report"] = report
    except json.JSONDecodeError as exc:
        st.error(f"JSON inválido: {exc}")
    except (TypeError, ValueError) as exc:
        st.error(str(exc))
    except Exception as exc:  # la interfaz no debe ocultar fallos inesperados
        st.exception(exc)

report = st.session_state.get("agent_audit_last_report")
if report:
    st.divider()
    st.subheader("Resultado de la auditoría")
    status = report.get("status", "SIN ESTADO")
    if status == "BLOQUEADO":
        st.error(status)
    elif status == "ADVERTENCIAS":
        st.warning(status)
    else:
        st.success(status)
    st.caption(
        f"Empresa: {report.get('company') or 'No especificada'} · "
        f"Ejecución: {report.get('run_id')} · Snapshot SHA-256: {report.get('snapshot_hash')}"
    )
    st.write("Aprobación humana requerida: **Sí** · Cambios aplicados: **No**")
    for agent in report.get("agent_results", []):
        st.markdown(f"**{agent.get('agent')}** — {agent.get('summary')}")
        findings = agent.get("findings", [])
        if findings:
            st.dataframe(findings, use_container_width=True, hide_index=True)
        else:
            st.success("No se detectaron inconsistencias en las comprobaciones ejecutadas.")
        if agent.get("limitations"):
            with st.expander("Limitaciones y comprobaciones no ejecutadas"):
                for item in agent["limitations"]:
                    st.write(f"- {item}")
    with st.expander("Ver informe JSON completo"):
        st.json(report)
