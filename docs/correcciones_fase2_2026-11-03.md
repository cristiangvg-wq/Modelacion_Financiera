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

## Segunda tanda (mismo día): hallazgos medios y bajos

| Hallazgo | Cambio | Archivo |
|---|---|---|
| M-08 Tasas de otros mercados | Bonos a 10 años con fuente y fecha: Brasil 15,4 % (29-oct), México 9,28 % (30-oct), Chile 6,00 % (2-nov), Reino Unido 5,29 % (29-oct), Trading Economics. Antes: 12 %, 9 %, 5,5 % y 4 % sin fecha. Mismo método de Damodaran que Colombia en los cinco mercados: rf = bono − spread de default; ERP = madura + riesgo país. | `modelacion_logic.py` |
| M-03 Múltiplo de salida | Múltiplo de la industria (Damodaran, ajustado por país) en vez del EV/EBITDA actual de la propia empresa (circular); sin dato → N/D (antes 22x/10x fijos). El propio queda como `ev_ebitda_mercado`. | `modelacion_logic.py` |
| M-09 Múltiplos | Nuevos EV/Ventas, P/E y P/VL (`valoracion_por_multiplo`). La sección de múltiplos estaba oculta (`if False`); ahora se ve en la pestaña 6. | `multiples_valuation.py`, `streamlit_app.py` |
| M-02 g recortada | El puente informa «g pedida → g usada» cuando se aplica el techo. | `modelacion_logic.py` |
| M-04 Asociadas | Se conserva el método validado con GEB (mayor entre libros y utilidad capitalizada), pero rotulado como estimado y con el valor en libros para contraste. | `modelacion_logic.py` |
| M-06 ROIC | `capital_base_roic` solo usa capital contable (antes añadía patrimonio de mercado). | `modelacion_logic.py` |
| M-11 Duplicados | La UI calcula WACC solo con el motor; si un insumo es inválido muestra el error (antes recalculaba con fórmulas propias y lo ocultaba). El asistente IA usa las anclas CAPM del mercado (antes rf 9 % y ERP 6 % fijos). | `streamlit_app.py`, `modelacion_logic.py` |
| M-12 Pestaña 5 | Se aclara que el VPN/TIR es de un proyecto ilustrativo; para la acción, VPN del inversionista y TIR implícita (pestaña 10). | `modelacion_logic.py` |
| A-05 Precio | La corrección de escala del precio contrasta precio × acciones con la capitalización (regla general; antes parche fijo para ISA). | `modelacion_logic.py` |
| A-06 Dependencias y pruebas | Topes de versión mayor en `requirements.txt`; las 2 pruebas que necesitan precio de Yahoo se omiten con motivo cuando no hay red. | `requirements.txt`, `test_informe_pdf.py` |
| A-07 Estado por sesión | Si la lógica corre en una sesión de Streamlit sin vínculo, se vincula a su `session_state` en vez de usar el diccionario global del proceso. | `modelacion_logic.py` |
| B-01, B-03, B-04, B-05, B-06, B-07 | Una sola fuente de FX; sin import de Gradio; devcontainer con CORS/XSRF activos; escenarios sin `fillna(0)`; frontera desde la cartera de mínima volatilidad; «beta de mercado (apalancada)» en la ficha. | varios |
| B-02 | Verificado: la UI ya cierra cada figura tras mostrarla; sin cambio. | — |

### Evidencia nueva sobre ISA (no incorporada al FCFF)
Según el resumen de resultados 4T25 ([Quartr](https://quartr.com/events/interconexi-n-el-ctrica-sa-esp-isa-q4-2025_FMNEn0pg)), ISA invirtió **COP 6,3 billones en 2025**, frente a 1,7 billones de CAPEX en el histórico del modelo. Se registró en `datos_curados.json` (`inversion_reportada`) y la pestaña 4 lo muestra como alerta. No se sumó al FCFF porque falta conciliar qué parte es activo de concesión, adquisiciones o expansión con ingresos futuros: hacerlo sin ese detalle bajaría el valor drásticamente sin sustento. El mismo resumen reporta EBITDA ajustado de 9,6 billones (excluye eventos especiales de 2025), lo que respalda tratar el margen de 2025 como atípico.

### Pendiente (requiere decisión o datos)
- **A-02 Tasa fiscal de ISA (22 %):** no se encontró la utilidad por método de participación de 2025 en fuentes verificables; se mantiene como provisional con sensibilidad a 35 %.
- **A-03 RONIC:** el modo por defecto («roic», mitad del exceso del ROIC sobre el WACC) se conserva como supuesto documentado.
- **B-08:** confirmar si el catálogo curado debe seguir como tercera fuente de datos.
- **M-10:** dividir funciones largas y reemplazar `except Exception` genéricos exige una refactorización gradual aparte.

### Pruebas
`pytest -q` local sin red: **459 aprobadas, 2 omitidas (requieren Yahoo), 0 fallidas**. App ejecutada localmente: pestañas 6, 9 y 10 sin excepciones.
