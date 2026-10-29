# Ingeniería de prompts — Taller ISA 2026

Este anexo documenta una plantilla maestra reutilizable y cuatro interacciones preparadas para la ejecución del taller. Para evitar atribuciones falsas, las salidas resumidas son **resultados calculables del script determinista o criterios de validación**, no transcripciones literales de una API de IA. Si se usa un LLM para entregar, guardar su respuesta real y reemplazar el resumen por la salida efectivamente obtenida.

## 1. Prompt maestro parametrizable

> **Rol:** Actúa como analista financiero sénior y auditor de modelos de valoración de infraestructura regulada.  
> **Empresa:** ISA — Interconexión Eléctrica. **Moneda/unidad:** COP, montos en miles de millones.  
> **Objetivo:** revisar histórico y supuestos; proponer un pronóstico 3–5 años; construir escenarios pesimista, base y optimista con al menos cinco drivers; simular dos políticas con regla si–entonces; cuantificar el efecto en FCFF y valor presente; formular una decisión condicionada.  
> **Datos disponibles:** [pegar datos y fuentes], [fecha de corte], [moneda], [unidad], [WACC validado], [g terminal], [presupuesto CAPEX mantenimiento/expansión].  
> **Restricciones:** no inventes datos ni fuentes; etiqueta cada dato como observado, estimado o hipotético; no conviertas N/D en cero; mantén consistentes unidades, moneda y base nominal; no calcules un precio objetivo si faltan datos materiales; separa hechos, supuestos, cálculos e inferencias.  
> **Técnicas obligatorias:** parametrización de escenarios, pronóstico explícito, sensibilidad, simulación contrafactual y validación cruzada con pruebas.  
> **Salida:** (1) tabla de drivers y fuente; (2) método y fórmulas; (3) matriz de tres escenarios; (4) dos políticas con regla, impacto por escenario y riesgos secundarios; (5) decisión condicionada y umbrales; (6) limitaciones y pruebas pendientes. Cita la procedencia junto a cada cifra y marca “PENDIENTE DE VALIDAR” si no hay evidencia suficiente.

## 2. Registro de interacciones (resumen de aplicación)

### Interacción 1 — Calidad de datos y unidades
**Prompt:** “Audita los datos históricos de ISA 2023–2025: identifica unidades, procedencia, datos estimados y campos que impiden valorar con confianza. No sustituyas faltantes por cero.”

**Resultado/validación:** el catálogo declara montos en miles de millones de COP; ingresos, EBITDA/EBIT ajustados, depreciación y CAPEX se describen como contrastados parcialmente con reportes oficiales; NWC se marca estimado. La ratio CAPEX/ingresos de 2025 es alta y debe conciliarse antes de usar el FCFF para un precio objetivo.

**Uso en el modelo:** preservar el dato NWC con etiqueta estimada; añadir advertencia sobre CAPEX y no presentar la salida académica como valoración oficial.

### Interacción 2 — Escenarios coherentes
**Prompt:** “Construye tres escenarios para ISA 2026–2030 con cinco drivers. Si cambias ingresos, evalúa simultáneamente margen EBIT, CAPEX, depreciación y capital de trabajo. Expón qué es supuesto.”

**Resultado/validación:** el script parametriza crecimiento de ingresos, margen EBIT, CAPEX/ingresos, NWC/ingresos y depreciación/ingresos. Pesimista: crecimiento 2%, margen −2 pp, CAPEX/ingresos +3% relativo, NWC/ingresos +2% relativo. Base: crecimiento 6,35% y ratios de 2025. Optimista: crecimiento 9%, margen +1 pp, CAPEX/ingresos −3% relativo y NWC/ingresos −1% relativo.

**Uso en el modelo:** estos shocks son escenarios de trabajo editables, no datos de consenso ni guía oficial.

### Interacción 3 — Políticas si–entonces
**Prompt:** “Simula dos políticas distintas para ISA en cada escenario. Define regla operativa, parámetro cuantitativo, impacto en FCFF y riesgos de segundo orden. No propongas recortar CAPEX de mantenimiento o seguridad.”

**Resultado/validación:** política CAPEX reduce 15% del componente de expansión supuesto en 30% del CAPEX total (ahorro teórico 4,5% del CAPEX); política de eficiencia incrementa margen EBIT 0,5 pp. El efecto cuantitativo por año y escenario se exporta en CSV.

**Uso en el modelo:** tratar ambas palancas como hipótesis; reemplazar el 30% por el presupuesto desagregado y verificar que las medidas de eficiencia sean realizables.

### Interacción 4 — Decisión y controles
**Prompt:** “Emite una recomendación condicionada a resultados; distingue FCFF acumulado, valor presente explícito, VPN de proyecto y valor empresarial. Enumera vetos de calidad y no inventes umbrales que no estén aprobados.”

**Resultado/validación:** el valor presente de flujos explícitos descontados a 10,5% se etiqueta como ilustrativo; no incluye valor terminal ni inversión inicial incremental, por lo que no es un VPN de proyecto ni un precio objetivo. El WACC debe sustituirse por el validado en la aplicación y la valoración debe esperar la conciliación de CAPEX, NWC y puente EV–patrimonio.

**Uso en el modelo:** recomendación provisional condicionada; sin decisión de inversión definitiva hasta resolver los vetos de datos.

## 3. Técnicas nombradas y evidencia
1. **Pronóstico por crecimiento compuesto:** función `build_projection`.
2. **Parametrización de escenarios:** diccionario `SCENARIOS`.
3. **Simulación contrafactual:** diccionario `POLICIES` y comparación de los 9 pares escenario–política.
4. **Sensibilidad por escenario:** exportación de FCFF anual y acumulado.
5. **Validación automatizada:** `tests/test_taller_isa.py`.

## 4. Requisito para la entrega final
Si el docente exige transcripciones literales de interacciones con IA, adjuntar los prompts y respuestas reales del proveedor utilizado, con fecha/modelo, y no presentar este resumen como registro literal. Las cuatro interacciones anteriores sirven como protocolo reproducible de trabajo y como plantilla para completar ese registro.
