# Taller evaluativo 2026 — ISA
## Entrega reproducible: pronóstico, escenarios, políticas y decisión

**Camino elegido:** Evaluación empresarial.  
**Empresa:** ISA — Interconexión Eléctrica.  
**Unidades:** miles de millones de COP; acciones (si se usan en el modelo de valoración principal) en millones y precio en COP/acción.  
**Corte del catálogo de respaldo:** 27 de octubre de 2026.  
**Estado:** versión académica reproducible; los shocks y políticas son hipótesis editables y deben contrastarse con datos oficiales y con el motor DCF principal.

## 1. Alcance y trazabilidad
El script `scripts/taller_isa.py` lee el histórico de ISA del catálogo `datos_curados.json` (2023–2025), proyecta 2026–2030 y exporta:
- `salidas_taller_isa/detalle_escenarios_politicas.csv`: FCFF y drivers por año, escenario y política.
- `salidas_taller_isa/resumen_escenarios_politicas.csv`: FCFF acumulado y valor presente explícito con tasa ilustrativa.
- `salidas_taller_isa/sensibilidad_tasa_impuesto.csv`: sensibilidad del FCFF acumulado a tasas de 22% y 35% para cada escenario y política.
- `salidas_taller_isa/metadatos_modelo.json`: supuestos, fuente y advertencias.

Los valores históricos de ingresos, EBIT, depreciación y CAPEX se declaran en el catálogo como contrastados parcialmente con informes oficiales de ISA; el NWC es estimado. Por ello, los resultados no se presentan como guía oficial de ISA ni como valoración definitiva.

## 2. Método de pronóstico
Se utiliza un modelo de drivers determinista y auditable. El escenario base aplica crecimiento compuesto de ingresos de 6,35% anual, calculado aproximadamente a partir del crecimiento compuesto 2023–2025. Se utiliza la razón EBIT/ingresos, depreciación/ingresos, CAPEX/ingresos y NWC/ingresos de 2025 como punto de partida. La tasa tributaria del catálogo es 22%, pero queda marcada como **provisional y no validada fiscalmente para ISA** porque el catálogo no incluye una conciliación específica que la sustente. Se conserva como caso base únicamente para reproducibilidad; el 35% se usa como estrés de sensibilidad, no como afirmación de que sea la tasa correcta para ISA consolidada.

```
Ingresos_t = Ingresos_(t-1) × (1 + crecimiento)
EBIT_t = Ingresos_t × margen EBIT_t
NOPAT_t = EBIT_t × (1 − tasa tributaria)
D&A_t = Ingresos_t × (D&A/Ingresos)_2025
CAPEX_t = Ingresos_t × (CAPEX/Ingresos)_2025 × shocks
NWC_t = Ingresos_t × (NWC/Ingresos)_2025 × shocks
ΔNWC_t = NWC_t − NWC_(t-1)
FCFF_t = NOPAT_t + D&A_t − CAPEX_t − ΔNWC_t
```

La elección es apropiada como línea base transparente para cinco años y permite aislar los supuestos. No es una serie temporal sofisticada: el historial disponible solo tiene tres observaciones anuales, por lo que un ARIMA/regresión con más parámetros daría falsa precisión.

## 3. Escenarios
Los escenarios cambian de forma conjunta cinco drivers, evitando un shock aislado. Todos los porcentajes son hipótesis de trabajo que deben validarse con el equipo y con evidencia operativa.

| Driver | Pesimista | Base | Optimista |
|---|---:|---:|---:|
| Crecimiento de ingresos anual | 2,0% | 6,35% | 9,0% |
| Variación del margen EBIT vs. margen 2025 | −2,0 pp | 0,0 pp | +1,0 pp |
| Variación de CAPEX/ingresos | +3,0% relativo | 0,0% | −3,0% relativo |
| Variación de NWC/ingresos | +2,0% relativo | 0,0% | −1,0% relativo |
| Depreciación/ingresos | Ratio 2025 | Ratio 2025 | Ratio 2025 |

## 4. Dos políticas simuladas
1. **Priorizar CAPEX:** se asume que 30% del CAPEX corresponde a expansión y se reduce 15% de esa porción (ahorro equivalente a 4,5% del CAPEX total). Regla: *si el escenario base o pesimista no soporta el presupuesto de inversión, diferir una parte del CAPEX de expansión, sin recortar mantenimiento, seguridad ni obligaciones regulatorias*. La proporción 30% es una hipótesis y debe ser reemplazada por el presupuesto real desagregado.
2. **Eficiencia operativa:** mejora hipotética de 0,5 puntos porcentuales en margen EBIT, manteniendo los demás drivers del escenario. Regla: *si el margen operativo cae por debajo del presupuesto, activar medidas de eficiencia que no comprometan la continuidad ni la calidad del servicio*.

La aplicación evalúa ambas políticas en los tres escenarios; el script las implementa de manera independiente y exporta el detalle anual. La recomendación no es automática: debe condicionarse a la ejecución del plan, seguridad, regulación y a la validación de CAPEX y capital de trabajo.

## 5. Métricas y límites
El script presenta FCFF anual, FCFF acumulado 2026–2030 y valor presente de los flujos explícitos descontados a un WACC de 10,5% **solo ilustrativo**. Este valor presente no incluye valor terminal ni inversión inicial incremental; por tanto, no se rotula como VPN de proyecto ni como valor empresarial definitivo. El WACC final debe tomarse del modelo principal validado y coincidir con la moneda y base nominal de los flujos.

La ratio CAPEX/ingresos de 2025 del catálogo es 39,15%, frente a 30,24% en 2024; debe conciliarse con presupuesto y clasificación de inversiones. EBITDA−EBIT en 2025 es 1.344, mientras que la depreciación reportada es 1.078 (diferencia 266); verificar amortización y D&A total antes de usar el FCFF. El NWC es estimado, no extraído de una conciliación de capital de trabajo operativo. El FCFF resultante es sensible a pequeños cambios de margen, impuestos y CAPEX. Antes de emitir una valoración final se debe conciliar el CAPEX por mantenimiento/expansión, verificar NWC y revisar que las unidades sean consistentes. No se deben interpretar valores negativos de patrimonio como señal de inversión hasta completar esas conciliaciones.

## 6. Decisión condicionada
**Recomendación provisional:** no adoptar una decisión definitiva de inversión a partir de este módulo aislado. Priorizar la política de eficiencia como hipótesis a validar y evaluar diferimiento únicamente del CAPEX de expansión; no reducir mantenimiento/seguridad. La decisión final solo se libera cuando:
- el FCFF base y los tres escenarios se reconcilien con los estados financieros;
- la tasa fiscal, el WACC y el crecimiento terminal coincidan con el DCF principal y tengan soporte documentado;
- el puente EV–patrimonio concilie deuda, caja, minoritarios, asociadas y acciones;
- la política supere el umbral acordado en el escenario base y no genere una pérdida de viabilidad inaceptable en el pesimista.

Los umbrales definitivos (VPN mínimo, caja mínima, ratio de endeudamiento) deben aprobarse por el equipo; no se inventan aquí porque requieren el presupuesto, covenants y datos actuales de ISA.

## 7. Técnicas del taller evidenciadas
- Pronóstico por crecimiento compuesto y ratios operativos.
- Parametrización de escenarios mediante diccionarios de drivers.
- Simulación contrafactual de dos políticas.
- Sensibilidad por escenario y comparación de FCFF.
- Pruebas unitarias y exportación de resultados con metadatos de trazabilidad.
- Ingeniería de prompts: plantilla maestra y registro de interacciones en `docs/ingenieria_prompts_taller_isa.md`.

## 8. Reproducción
Desde la raíz del repositorio:
```bash
python scripts/taller_isa.py
python -m unittest tests.test_taller_isa -v
# La ejecución también genera sensibilidad_tasa_impuesto.csv
```
Las salidas CSV/JSON se regeneran en `salidas_taller_isa/`. La ejecución no requiere una API de IA ni datos de mercado intradía.

## 9. Fuentes y honestidad académica
- Histórico y supuestos de respaldo: `datos_curados.json` del repositorio, corte 27-oct-2026; allí se describe la procedencia de cada serie y sus limitaciones.
- Especificación del taller: `Taller evaluativo 2026 — Modelación financiera aplicada: pronóstico, escenarios y simulación de políticas`.
- No se afirma que las hipótesis de escenarios o políticas sean decisiones oficiales, ni que las interacciones de prompt de ejemplo sean respuestas literales de un modelo externo.
