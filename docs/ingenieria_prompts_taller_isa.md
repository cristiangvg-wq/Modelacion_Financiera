# Ingeniería de prompts — Taller ISA 2026

Este anexo documenta (1) el prompt maestro reutilizable y su versionado, y (2) el registro de interacciones reales con IA que alimentaron el modelo `scripts/taller_isa.py`. Las interacciones 1 y 2 son pedidos reales hechos a Claude Opus 5.5 (Anthropic) el 29-oct-2026; la 3 y la 4 son ejecuciones de la plantilla maestra en la misma sesión. El equipo puede añadir sus propias interacciones con el mismo formato (prompt → salida clave → uso en el modelo).

## 1. Prompt maestro (plantilla parametrizable, v2)

Los campos entre llaves se reemplazan antes de cada uso. El bloque *Tarea* selecciona el módulo: (a) estructurar supuestos, (b) generar escenarios coherentes, (c) simular una política o (d) interpretar resultados para la decisión.

> **Rol:** analista financiero sénior y auditor de modelos de valoración de {sector}.
> **Empresa y datos:** {empresa}; moneda {moneda}; unidad {unidad}; corte {fecha_corte}. Datos: {tabla_historica} con su fuente y calidad por año: {calidad_por_anio}. Parámetros de mercado: {tes}, {primas_riesgo}, {beta_u}, {d_e}, {tasa_impuestos} (estado: {estado_tasa}).
> **Tarea:** {modulo: a | b | c | d} — {instruccion_especifica}.
> **Restricciones:** (1) no inventes datos ni fuentes; etiqueta cada cifra como *observada*, *estimada* o *hipótesis*; (2) no conviertas N/D en cero; (3) unidades, moneda y base nominal consistentes; (4) si un driver se mueve, explica el efecto sobre los drivers enlazados (ventas → CAPEX de expansión → NWC → deuda); (5) todo umbral de decisión debe quedar como **parámetro explícito** con su justificación, nunca implícito; (6) distingue VPN del inversionista, ΔVPN de una política y EV; indica cuándo la TIR no existe o es un costo de financiación; (7) no fuerces un resultado positivo.
> **Formato de salida:** JSON o tabla con: `driver | valor | tipo (observado/estimado/hipótesis) | fuente | efecto enlazado`, seguido de máximo 10 viñetas de interpretación y una lista de *pendientes de validar*.
> **Criterios de calidad:** cada cifra trazable a dato, fórmula o supuesto; coherencia entre escenarios (orden monotónico del valor); reglas de política con forma SI–ENTONCES ejecutable en código.

### Versionado

| Versión | Cambio | Motivo (detectado en la interacción) |
|---|---|---|
| v1 (oct-2026, versión previa del repo) | Rol, restricciones de no inventar datos, salida en 6 secciones. | Primer borrador; los umbrales se dejaban "para el equipo" y el CAPEX era un % fijo de ingresos. |
| v2 (29-oct-2026) | Se añaden las restricciones 4, 5 y 6, el formato tabular con columna *tipo* y los criterios de calidad. | Interacción 1: el modelo v1 no enlazaba CAPEX con crecimiento, no tenía umbrales y el texto conservaba cifras desactualizadas (CAPEX/ingresos 39 %). |

## 2. Registro de interacciones

### Interacción 1 — Auditoría de cobertura del taller (módulo d, interpretación)
**Prompt (usuario → Claude Opus 5.5, 29-oct-2026):** "Usando este repositorio [cristiangvg-wq/Modelacion_Financiera], verifica si se puede dar respuesta al taller" (adjunto: enunciado del taller en PDF).

**Salida clave:** tabla criterio por criterio de la rúbrica. Hallazgos: (i) faltaban VPN y TIR del escenario base (solo había VP de flujos explícitos sin valor terminal); (ii) solo 4 drivers se movían (D&A fijo); (iii) faltaba tornado; (iv) las políticas no tenían costo y la regla SI–ENTONCES no estaba programada; (v) no había umbrales de decisión; (vi) el registro de prompts era una plantilla, no interacciones reales; (vii) faltaba el informe PDF. Además detectó dos cifras desactualizadas al recalcular con los datos vigentes: CAPEX/ingresos 2025 = 10,7 % (el texto decía 39,15 %) y CAGR de ingresos 2023–2025 = 6,0 % (el código fijaba 6,35 %).

**Uso en el modelo:** el crecimiento base pasa a calcularse en código (`historical_drivers`) y se agrega una prueba que lo verifica (`test_growth_is_computed_from_data_not_hardcoded`); se agrega prueba de la ratio CAPEX vigente; se reescribe el informe sin las cifras antiguas.

### Interacción 2 — Rediseño del modelo (módulos a, b y c)
**Prompt (usuario → Claude Opus 5.5, 29-oct-2026):** "Haz todos los ajustes para que se pueda dar una respuesta total al taller."

**Salida clave:** rediseño aplicado al código: (1) CAPEX = mantenimiento (≈ D&A) + intensidad × ΔIngresos, con intensidad calibrada con 2024–2025 (0,68) porque 2023 no es comparable; (2) WACC por CAPM con el método de la app (TES − spread de default + β apalancada × ERP de Damodaran para Colombia) = 13,8 %; (3) valor terminal de Gordon, puente EV → patrimonio, VPN del inversionista y TIR implícita al precio de mercado; (4) cuatro escenarios con seis drivers; (5) tres políticas con regla SI–ENTONCES y costos; (6) umbrales de decisión parametrizados; (7) tornado, matriz WACC × g y Monte Carlo; (8) instantánea de datos propia del taller para no depender del catálogo de la app.

**Uso en el modelo:** todo lo anterior quedó en `scripts/taller_isa.py`, con 20 pruebas en `tests/test_taller_isa.py`. Corrección hecha al revisar la salida: la primera versión de la recomendación de P3 medía solo el apalancamiento *máximo*, que en Estrés ocurre en 2026 (antes de que la regla pueda actuar); se cambió a *años sobre el covenant* y *deuda neta 2030*.

### Interacción 3 — Escenarios coherentes (plantilla maestra v2, módulo b)
**Prompt (plantilla v2 con parámetros de ISA):** "{módulo b}: construye escenarios Estrés, Pesimista, Base y Optimista para ISA 2026–2030 moviendo al menos cinco drivers a la vez. Explica el efecto enlazado de cada choque y verifica que el valor por acción sea monotónico entre escenarios y que WACC − g ≥ 2 pp."

**Salida clave:** matriz de seis drivers (crecimiento, margen EBIT, intensidad de CAPEX, NWC/ingresos, WACC, g terminal), todos etiquetados como hipótesis; enlaces explícitos (más crecimiento → más CAPEX de expansión y más ΔNWC por construcción del modelo; tasas altas → WACC y menor g). Verificación: el valor por acción crece de Estrés a Optimista y el diferencial WACC − g es ≥ 6 pp en todos los escenarios.

**Uso en el modelo:** diccionario `SCENARIOS` y prueba `test_scenarios_move_at_least_five_drivers_and_are_ordered`.

### Interacción 4 — Interpretación para la decisión (plantilla maestra v2, módulo d)
**Prompt (plantilla v2):** "{módulo d}: con `salidas_taller_isa/metadatos_modelo.json` e `impacto_politicas.csv`, emite una recomendación sobre la acción y sobre cada política aplicando solo los umbrales de `DECISION_THRESHOLDS`. Indica qué driver domina la dispersión y qué pasa si la TIR incremental es de tipo financiación."

**Salida clave:** (1) al precio de referencia, la TIR implícita (≈ 12,5 %) es inferior al WACC (13,8 %) y el valor Base queda por debajo del precio: *no comprar / subponderar*; el precio solo se justificaría con WACC cercano a 12,5 % o con el escenario Optimista. (2) El WACC domina el tornado, seguido por g y el crecimiento. (3) P1 (diferir CAPEX) tiene flujos tipo financiación con costo implícito ≈ 25 % > WACC: libera caja hoy pero cuesta más de lo que vale → *descartar* aunque la regla se active en Pesimista. (4) P2 (eficiencia) tiene ΔVPN > 0 en todos los escenarios y P(ΔVPN > 0) ≈ 79 % en Monte Carlo → *adoptar*. (5) P3 (dividendos) no cambia el EV pero reduce años sobre el covenant en Estrés → *regla contingente*.

**Uso en el modelo:** función `_irr_reading` (lectura de TIR según tipo de flujo) y sección 6 del informe. Revisión crítica: la conclusión sobre la acción es sensible al WACC (±1 pp mueve el valor por acción ≈ ±6.000 COP) y a la clasificación del CAPEX de concesiones; por eso la decisión se presenta como condicionada, no como precio objetivo.

## 3. Técnicas nombradas y dónde están

| Técnica | Implementación |
|---|---|
| T1 Pronóstico por drivers | `historical_drivers`, `scenario_params`, `project` |
| T2 Parametrización de escenarios | diccionario `SCENARIOS` (6 drivers × 4 escenarios) |
| T3 Sensibilidad | `tornado` (7 drivers) y `wacc_g_matrix` |
| T4 Simulación de políticas | diccionario `POLICIES`, `policy_triggered`, `policy_impact`, `policy_recommendation` |
| T5 Monte Carlo | `monte_carlo` (semilla fija, 5.000 simulaciones) |
| T6 Ingeniería de prompts | este anexo (plantilla v2 + versionado + 4 interacciones) |
| Validación | `tests/test_taller_isa.py` (20 pruebas) |
