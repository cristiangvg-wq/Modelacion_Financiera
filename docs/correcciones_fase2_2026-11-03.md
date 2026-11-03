# Correcciones fase 2 — 3 de noviembre de 2026

Rama `fix/valoracion-mercado-taller-tab10`. Responde a la auditoría de la fase 1 (hallazgos C-01 a C-05, A-01, A-03, A-04, M-01, M-05, M-07).

Principio aplicado: **ningún supuesto se ajustó para acercar el valor al precio**. Se corrigieron errores de método y de datos; la brecha que queda frente al mercado se explica, no se fuerza.

## Cambios en el motor de valoración

| Hallazgo | Cambio | Archivo |
|---|---|---|
| C-03 Fecha de valoración | `valoracion_dcf` acepta `frac_transcurrida` y `t_valoracion`. Los flujos parten del cierre fiscal; del primer año solo cuenta el tramo posterior a la fecha del balance del puente; el valor se expresa a la fecha del precio. `calendario_valoracion` obtiene las fechas (catálogo: `fecha_balance`; Yahoo: `mostRecentQuarter` y `lastFiscalYearEnd`). Valores por defecto = método anterior. | `modelacion_logic.py`, `datos_curados.json` |
| C-04 Margen | Si el margen del último año difiere más de 2 pp del representativo, converge en 3 años (antes: salto inmediato en el año 1). La narrativa puede fijar otra velocidad. | `modelacion_logic.py` (`proyectar_por_drivers`) |
| C-01 Trazabilidad | Sin fuente declarada el estado es «SIN FUENTE» (antes «OBSERVADO»); supuestos y cifras provisionales son ESTIMADO; el catálogo declara la procedencia de deuda, caja, NCI, asociadas, acciones, beta e impuestos; la rf en COP derivada del TES es ESTIMADO. | `modelacion_logic.py` |
| C-02 Datos sustitutos | La descarga de Yahoo registra por año qué partidas se sustituyeron por regla (EBIT, EBITDA, D&A, CAPEX, NWC); aparecen como ESTIMADO y bajan la calidad de datos. | `modelacion_logic.py` |
| C-05 Múltiplos | Patrimonio = EV − deuda neta − NCI − otros + asociadas (mismo puente que el DCF); rango Q1–Q3 en valor por acción; patrimonio negativo → 0 por acción. La UI pide NCI y asociadas. | `multiples_valuation.py`, `streamlit_app.py` |
| A-03 ROIC | Una sola definición: NOPAT histórico mediano / capital operativo (sin asociadas), la misma que usa el RONIC del valor terminal. | `modelacion_logic.py` |
| A-04 Anclas | Los escenarios pesimista y optimista se tratan como par: si uno queda fuera del rango, el otro también. | `comite_ia.py` |
| M-01 WACC optimista | `wacc_optimista`: WACC − 1 pp con margen mínimo sobre g; ya no puede superar al base. | `modelacion_logic.py`, `streamlit_app.py` |
| M-05 Acciones | Yahoo informa acciones en unidades: siempre ÷ 10⁶. | `modelacion_logic.py` |
| M-07 / A-01 Textos | Los escenarios describen los choques reales; la pestaña 1 avisa que ETS/ARIMA no se usan en la valoración. | `modelacion_logic.py`, `streamlit_app.py` |

## Pestaña 10 (taller)

Nuevo tablero `ui_taller.py` sobre el modelo del taller (`scripts/taller_isa.py`), con los bloques del enunciado:

- **A Pronóstico:** drivers con fórmula y fuente, método justificado, FCFF 2026–2030 + año terminal, VPN del inversionista y TIR implícita.
- **B Escenarios:** matriz de 6 drivers × 4 escenarios (editable), tabla de FCFF, EV, valor por acción, VPN y TIR; gráfico de FCFF; tornado; matriz WACC × g.
- **C Políticas:** tres reglas SI–ENTONCES con parámetros editables (el texto de la regla se regenera), impacto por escenario y recomendación.
- **D Decisión:** umbrales editables, decisión sobre la acción y matriz de decisión política × escenario.
- **E Prompts y técnicas:** técnicas T1–T6 con su ubicación en el código, Monte Carlo (bonificación) y anexo de prompts.
- Descargas: JSON de datos y supuestos, CSV de proyecciones, código del modelo. El PDF del taller usa exactamente los datos y supuestos del tablero.
- El análisis anterior de la pestaña 10 se conserva como «Análisis complementario».

`scripts/taller_isa.py`: fecha de valoración (`fechas` en `datos_taller_isa_2026.json`), configuración por corrida sin estado compartido (`escenarios_de`, `politicas_de`, `umbrales_de`), `calcular_modelo` en memoria, Monte Carlo sin TIR por simulación (5.000 simulaciones en ≈ 1 s), valor por acción ≥ 0.

## Efecto en ISA (datos del repositorio, sin conexión a Yahoo)

| Modelo | Antes | Después | Precio ref. 27.500 COP |
|---|---:|---:|---:|
| App (pestañas 2–7), caso base | 20.197 | 23.137 | −16 % |
| Taller (pestaña 10), escenario Base | — (valor al cierre 2025) | 22.108 | −20 % |

Lectura: la brecha restante proviene de supuestos con limitaciones documentadas (tasa fiscal provisional de 22 %, CAPEX de perímetro parcial, NCI y asociadas a valor contable), no de errores de cálculo. Cerrarla exige estados financieros de ISA, no ajustar parámetros.

## Pruebas

- Nuevas: `tests/test_correcciones_fase2.py` (21 pruebas con cálculos independientes).
- Ajustadas (comportamiento corregido): `test_comite_ia_v2.py` (par de escenarios), `tests/test_taller_isa.py` (estructura de la pestaña 10).
- Suite completa: ver la descripción del PR. Las 2 pruebas de `test_informe_pdf.py` que fallan sin red fallaban igual antes de los cambios (necesitan precio de Yahoo).
