"""Centro de Agentes IA conectado a la valoración vigente de la sesión."""
from __future__ import annotations

import streamlit as st

import modelacion_logic as L
from agents.session_adapter import build_session_snapshot
from agents.service import audit_snapshot

st.set_page_config(page_title="Centro de Agentes IA", page_icon="🧠", layout="wide")
if hasattr(L, "vincular_estado_sesion"):
    L.vincular_estado_sesion(st.session_state.setdefault("_estado_logica", {}))

st.title("🧠 Centro de Agentes IA")
st.caption("Auditoría financiera conectada · solo lectura · requiere aprobación humana")

st.info(
    "El Centro toma la empresa, los supuestos y la proyección de la sesión actual. "
    "No vuelve a calcular ni modifica el modelo, no consulta proveedores externos y no aplica cambios."
)

snapshot, reason = build_session_snapshot(
    st.session_state,
    L,
    repository_ref="feat/arquitectura-multiagente-v1",
)

if snapshot is None:
    st.warning(reason or "No hay una valoración disponible para auditar.")
    st.markdown(
        "**Para habilitar la auditoría:** vuelve a la página principal, selecciona la empresa, "
        "revisa los supuestos y pulsa **Generar todo**. Después abre nuevamente el Centro de Agentes."
    )
    st.stop()

company_col, ticker_col, currency_col = st.columns(3)
company_col.metric("Empresa", snapshot.get("company") or "—")
ticker_col.metric("Ticker", snapshot.get("ticker") or "—")
currency_col.metric("Moneda", snapshot.get("currency") or "—")

st.subheader("Snapshot de la valoración actual")
inputs = snapshot.get("model_inputs") or {}
outputs = snapshot.get("model_outputs") or {}
c1, c2, c3 = st.columns(3)
c1.metric("WACC", f"{outputs['wacc']:.2%}" if outputs.get("wacc") is not None else "N/D")
c2.metric("g terminal", f"{inputs['terminal_growth']:.2%}" if inputs.get("terminal_growth") is not None else "N/D")
c3.metric("FCFF último año proyectado", f"{outputs['fcff']:,.2f}" if outputs.get("fcff") is not None else "N/D")
with st.expander("Ver datos y procedencia que recibirán los agentes"):
    st.json(snapshot)

st.subheader("Auditoría")
st.caption("Las comprobaciones se ejecutan sobre una copia serializable de los datos de esta sesión.")
if st.button("Ejecutar auditoría de la valoración", type="primary", use_container_width=True):
    try:
        report = audit_snapshot(snapshot)
        st.session_state["agent_audit_last_report"] = report
        st.session_state["agent_audit_last_company"] = snapshot.get("company")
        st.session_state["agent_audit_last_hash"] = report.get("snapshot_hash")
    except (TypeError, ValueError) as exc:
        st.error(str(exc))
    except Exception as exc:
        st.exception(exc)

report = st.session_state.get("agent_audit_last_report")
if (report and st.session_state.get("agent_audit_last_company") == snapshot.get("company")
        and st.session_state.get("agent_audit_last_hash") == report.get("snapshot_hash"))
        and report.get("snapshot_hash") == st.session_state.get("agent_audit_last_hash"):
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
