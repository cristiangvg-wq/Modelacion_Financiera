# Validación y conciliación de ISA — 29 de octubre de 2026

## Alcance

Esta nota separa los datos observados en fuentes públicas, los datos del catálogo del modelo y los cálculos derivados. Los importes financieros están expresados en **miles de millones de COP**, salvo el precio por acción y el número de acciones.

## 1. Cotización y razón deuda/patrimonio de mercado

**Instantánea BVC:** 29-oct-2026, 11:38:41 a. m. hora de Colombia; precio observado COP 27.500. La página de ISA/BVC y la página de La República muestran el precio y la fecha de consulta. Es una observación intradía, no un cierre oficial de fin de jornada.

- Fuente de precio: [La República — movimiento accionario ISA, fuente BVC](https://www.larepublica.co/indicadores-economicos/movimiento-accionario/isa).
- Contraste: [Yahoo Finance — ISA.CL](https://es.finance.yahoo.com/quote/ISA.CL/). La cotización de Yahoo consultada durante la sesión difería porque la observación no era necesariamente simultánea; no se deben mezclar precios de horas distintas sin registrar la hora de cada fuente.
- Datos de deuda y caja: catálogo, atribuidos al informe consolidado de ISA 2T26.

| Concepto | Valor |
|---|---:|
| Precio BVC observado | COP 27.500 por acción |
| Acciones usadas | 1.107,7 millones |
| Capitalización calculada | COP 30.461,75 mil millones |
| Deuda financiera bruta | COP 34.155 mil millones |
| Caja | COP 3.725 mil millones |
| Deuda neta | COP 30.430 mil millones |
| D/E de mercado recalculado | 1,1212 |

Fórmulas:

`Capitalización = COP\ 27.500 \times 1.107,7\ millones / 1.000.000 = COP\ 30.461,75\ mil\ millones`

`D/E = deuda financiera bruta / capitalización = 34.155 / 30.461,75 = 1,1212`

La instantánea previa del catálogo usaba COP 28.300 y D/E ≈ 1,09, pero esa referencia no debe tratarse como cotización vigente. Se actualizó el catálogo a COP 27.500, 1.107,7 millones de acciones y D/E 1,1212. La cotización es temporal: para nuevas valoraciones se debe refrescar el precio y recalcular D/E con la misma fecha/hora y una fuente documentada.

**Importante:** el D/E recalculado usa deuda bruta sobre capitalización de mercado, de forma consistente con la metodología indicada en el catálogo. No sustituirlo por deuda neta/capitalización sin etiquetar el cambio metodológico.

## 2. Histórico operativo y diferencia de perímetro

El catálogo contiene esta serie ajustada para el DCF:

| Indicador | 2023 | 2024 | 2025 |
|---|---:|---:|---:|
| Ingresos | 14.168 | 15.829 | 16.034 |
| EBITDA ajustado | 8.584 | 9.207 | 8.186 |
| EBIT ajustado | 7.068 | 7.870 | 6.842 |
| Depreciación y amortización | 1.268 | 1.072 | 1.078 |
| CAPEX | 4.600 | 4.785 | 6.278 |
| NWC | 1.750 | 1.850 | 1.950 |

ISA comunicó para 2025 EBITDA consolidado de COP 8,7 billones. No debe reemplazarse automáticamente el EBITDA ajustado del catálogo (8.186) por el consolidado oficial: el modelo documenta que excluye resultados de asociadas y negocios conjuntos para valorarlos separadamente en el puente de equity. La conciliación requiere mantener el mismo perímetro entre EBIT/EBITDA, flujo operativo y participaciones.

Fuente oficial de resultados: [ISA — resultados de 2025](https://isa.co/press/resultados-isa-2025-valor-accionistas/).

El NWC histórico del catálogo está expresamente identificado como **estimado**; no es un dato validado contra balances detallados. Por tanto, el FCFF derivado de esta serie también es una estimación de modelo.

## 3. Recalculo ilustrativo de FCFF 2025

Usando EBIT ajustado = 6.842, D&A = 1.078, CAPEX = 6.278 y `ΔNWC = 1.950 - 1.850 = 100`:

`FCFF = EBIT × (1 - tasa fiscal) + D&A - CAPEX - ΔNWC`

| Concepto | Tasa 22 % | Tasa 35 % |
|---|---:|---:|
| EBIT | 6.842,00 | 6.842,00 |
| NOPAT | 5.336,76 | 4.447,30 |
| D&A | 1.078,00 | 1.078,00 |
| CAPEX | -6.278,00 | -6.278,00 |
| ΔNWC estimado | -100,00 | -100,00 |
| **FCFF derivado** | **36,76** | **-852,70** |

La tasa del 22 % es provisional; la tasa efectiva contable no valida por sí sola la tasa fiscal operativa sobre EBIT. El 35 % se presenta como estrés, no como una tasa efectiva consolidada verificada. Estos valores son cálculos derivados del catálogo y **no son FCFF publicados por ISA**.

## 4. Puente de valor de empresa a patrimonio

La identidad de deuda neta sí concilia aritméticamente:

`Deuda neta = deuda bruta - caja = 34.155 - 3.725 = 30.430`

El puente del catálogo registra NCI de 10.539 y asociadas/negocios conjuntos por 4.332. Las asociadas se incorporan a valor contable, no a una valoración de mercado independiente. Esto se debe declarar como limitación del valor del patrimonio resultante.

No restar deuda neta y sumar caja nuevamente: eso duplicaría el efecto de caja. Si se usa deuda bruta, restar deuda bruta y sumar caja una sola vez.

## 5. Monedas y pruebas funcionales

El PR #67 propagó tasas FX explícitas al cálculo del precio por acción y del upside. Las pruebas sintéticas comprueban conversión entre monedas cuando se suministran tasas y bloquean el upside si faltan tasas verificables. Esto valida la lógica funcional, pero no equivale a una descarga y conciliación de tasas FX reales en vivo.

En una comparación BVC/Yahoo se debe registrar para cada precio: proveedor, ticker, moneda, fecha y hora. Para el ticker ISA.CL, la cotización está en COP. No comparar precios con marcas de tiempo distintas como si fueran una sola observación.

Cambios de código: [PR #67 — conversión FX multimoneda](https://github.com/cristiangvg-wq/Modelacion_Financiera/pull/67).

## 6. Estado de validación

- **Conciliado aritméticamente:** deuda neta; capitalización derivada de precio × acciones; D/E recalculado con instantánea BVC.
- **Contrastado parcialmente con fuente oficial:** ingresos y resultados operativos; mantener separado el perímetro consolidado del ajustado.
- **Pendiente:** validar NWC con balances detallados; determinar una tasa fiscal operativa sostenible; valorar independientemente las asociadas; ejecutar conciliación automatizada de cotización BVC/Yahoo y FX con timestamp simultáneo.
- **Conclusión:** la valoración sigue siendo **parcialmente validada**. La actualización de precio/D/E no elimina las limitaciones de NWC, tasa fiscal ni valoración de participadas.

