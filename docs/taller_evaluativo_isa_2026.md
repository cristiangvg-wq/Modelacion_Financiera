# Taller evaluativo 2026 — ISA
## Pronóstico, escenarios, políticas y decisión (camino: Evaluación empresarial)

**Empresa:** ISA — Interconexión Eléctrica · **Unidades:** miles de millones de COP (valor por acción en COP).
**Informe para entregar:** [`docs/Informe_Taller_ISA_2026.pdf`](Informe_Taller_ISA_2026.pdf) (7 páginas de cuerpo + anexos).

> Este documento describe el método. **No copia cifras de resultados**: todas salen del código y se regeneran con él, para evitar que el texto quede desactualizado cuando cambian los datos (problema detectado en la auditoría del 29-oct-2026, ver Anexo A del informe).

## 1. Cómo se responde cada bloque del taller

| Bloque / criterio | Dónde está | Qué produce |
|---|---|---|
| A. Pronóstico (20 %) | `historical_drivers`, `project`, `value`, `implied_irr` | Drivers calibrados con 2023–2025, FCFF 2026–2030 + año terminal, EV, patrimonio, VPN del inversionista y TIR implícita |
| B. Escenarios (20 %) | `SCENARIOS`, `tornado`, `wacc_g_matrix` | 4 escenarios × 6 drivers, tabla comparativa, tornado de 7 drivers y matriz WACC × g |
| C. Políticas (20 %) | `POLICIES`, `policy_triggered`, `policy_impact`, `policy_recommendation` | 3 políticas con regla SI–ENTONCES, ΔVPN, TIR incremental, efecto en covenant; adoptar / condicionar / descartar |
| D. Decisión (15 %) | `DECISION_THRESHOLDS`, `investment_decision` | Umbrales explícitos, decisión sobre la acción y recomendación condicionada |
| E. Prompts (15 %) | [`ingenieria_prompts_taller_isa.md`](ingenieria_prompts_taller_isa.md) | Prompt maestro v2 parametrizable, versionado y 4 interacciones |
| Código e informe (10 %) | `scripts/taller_isa.py`, `tests/test_taller_isa.py`, `scripts/generar_informe_taller_isa.py` | Ejecución reproducible, 28 pruebas, informe PDF regenerable |
| Bono +5 | `monte_carlo`, `scripts/dashboard_taller_isa.py` | Monte Carlo (5.000 simulaciones, semilla fija) y dashboard Streamlit |

## 2. Datos
`datos_taller_isa_2026.json` es una instantánea propia del taller (histórico 2023–2025, puente EV→patrimonio, precio de referencia, parámetros de costo de capital con fuente). Así el taller no depende del catálogo de la app. Para actualizarla desde `datos_curados.json`: `python scripts/taller_isa.py --refrescar-instantanea`.

Calidad: ingresos, EBIT y D&A 2024–2025 conciliados con EEFF oficiales; CAPEX 2024–2025 = PP&E + intangibles pagados en caja; NWC preliminar; 2023 no comparable en CAPEX/NWC.

## 3. Método
```
Ingresos_t   = Ingresos_(t-1) × (1 + g_t)                  g base = CAGR 2023–2025 calculado en código
EBIT_t       = Ingresos_t × margen − costo de política        margen base = EBIT/ingresos 2025
CAPEX_t      = Ingresos_t × m_mant + k × ΔIngresos_t          m_mant ≈ D&A/ingresos; k = (CAPEX − D&A)/ΔIngresos, prom. 2024–2025
ΔNWC_t       = NWC/Ingresos × Ingresos_t − NWC_(t-1)
FCFF_t       = EBIT_t(1 − t) + D&A_t − CAPEX_t − ΔNWC_t
VT           = FCFF_2031 / (WACC − g)                         año terminal proyectado con g terminal
EV           = Σ FCFF_t/(1+WACC)^t + VT/(1+WACC)^5
Patrimonio   = EV − deuda neta − minoritarios + asociadas
VPN inv.     = Patrimonio − capitalización de mercado
TIR implícita: tasa r tal que EV(r) = EV de mercado
WACC         = E/V·[rf + β_L·ERP] + D/V·Kd(1 − t); rf = TES − spread de default; Kd = TES + spread
```
Enlazar el CAPEX de expansión con ΔIngresos garantiza la coherencia pedida en el Bloque B: si las ventas suben, suben también la inversión y el capital de trabajo.

## 4. Escenarios, políticas y umbrales
Los valores exactos están en los diccionarios del código (editables). Resumen:
- **Escenarios:** Estrés, Pesimista, Base, Optimista; mueven crecimiento, margen EBIT, intensidad de CAPEX, NWC/ingresos, WACC y g terminal.
- **P1 Diferir CAPEX de expansión** (política de inversión), **P2 Programa de eficiencia operativa** (márgenes, con costo inicial y recurrente), **P3 Dividendos condicionados al apalancamiento** (política financiera / liquidez).
- **Umbrales:** covenant deuda neta/EBITDA, probabilidad mínima en Monte Carlo para adoptar una política, margen de seguridad de compra y banda de "mantener". Son criterios de diseño del equipo, no datos.

## 5. Reproducción
```bash
python scripts/taller_isa.py                       # CSV/JSON en salidas_taller_isa/
python -m pytest -q tests/test_taller_isa.py       # 28 pruebas
python scripts/generar_informe_taller_isa.py --equipo "Nombre 1; Nombre 2; Nombre 3" --fecha "AAAA-MM-DD"
streamlit run scripts/dashboard_taller_isa.py      # dashboard (bonificación)
```

## 6. Limitaciones
Las advertencias completas están en `salidas_taller_isa/metadatos_modelo.json` y en la sección 9 del informe. La principal: el CAPEX de caja puede no incluir inversiones en concesiones registradas como activos financieros/contractuales (CINIIF 12), lo que sobrestimaría el FCFF. El resultado es académico y no constituye recomendación de inversión profesional.
