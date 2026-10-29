# Cierre de auditoría financiera y funcional — 29 de octubre de 2026

## Resultado ejecutivo

La auditoría de ingeniería puede cerrarse con controles de regresión y trazabilidad reforzados. La certificación financiera de cada empresa no puede declararse completa: los datos disponibles no permiten sustituir los estados financieros detallados, cotizaciones/FX sincronizados ni valoraciones independientes de participadas que faltan. El modelo debe mostrar esta distinción y no convertir supuestos numéricos en datos auditados.

## Cambios aplicados en esta fase

1. La función _construir_catalogo ahora expone calidad_datos, tax_estado y fuente_tax en los parámetros y metadatos de cada emisor. Las etiquetas viajan con los parámetros en vez de quedarse únicamente en datos_curados.json.
2. Los campos de calidad incluyen histórico, NWC, impuestos, asociadas, mercado y metodología sectorial. Los estados predeterminados son conservadores: la existencia de un número no implica que esté verificado.
3. Se agregan pruebas para todas las empresas del catálogo, para los supuestos provisionales de ISA y para evitar que EPM/ENEL (sin serie histórica) se presenten como empresas con histórico validado.
4. Se confirma el estado de la PR #69: integrada en main; el workflow de calidad financiera terminó en success con sintaxis, pruebas automatizadas, evaluación offline del comité IA y smoke test Streamlit.

## Estado de ISA — conciliación conocida

| Control | Valor | Estado |
|---|---:|---|
| Precio de referencia | COP 27.500/acción, 29-oct-2026 11:38:41 America/Bogota | Instantánea fechada, no cotización en vivo verificada en esta auditoría |
| Acciones | 1.107,7 millones | Dato del catálogo; requiere cotejo con fuente corporativa vigente al usarlo |
| Capitalización implícita | COP 30.461,75 miles de millones | Identidad aritmética consistente |
| Deuda financiera bruta | COP 34.155 miles de millones | Deuda neta 30.430 + caja 3.725 |
| D/E de mercado | 1,1212 | Deuda bruta / capitalización; consistente con los datos del catálogo |
| Tasa fiscal | 22 % | Provisional, no validada como tasa operativa sostenible sobre EBIT |
| NWC | Serie 1.750, 1.850, 1.950 | Estimación; no conciliada con partidas operativas del balance |
| Asociadas | COP 4.332 miles de millones | Valor contable; no valoración independiente |
| CAPEX 2025 / ingresos | 39,15 % | Requiere comprobar perímetro, clasificación y consistencia de CAPEX |

La prueba de consistencia aritmética no demuestra que las cifras de origen sean actuales, auténticas, comparables o de igual perímetro contable.

## Hallazgos y acciones residuales

### Datos y mercado
- No se ha demostrado una descarga simultánea de BVC/Yahoo con timestamps comparables para todos los emisores. La fecha as_of del catálogo no equivale a la fecha de actualización de cada dato.
- Antes de una valoración real, verificar precio, acciones, moneda, tipo de cambio, fecha de estados financieros y fecha de mercado; conservar la fuente y fecha de cada campo.
- Las empresas sin histórico en el catálogo (EPM y ENEL Colombia) necesitan estados financieros del usuario. No se deben generar series ficticias para completar la valoración.

### Finanzas operativas
- Recalcular NWC como activos corrientes operativos menos pasivos corrientes operativos, excluyendo caja y deuda financiera; derivar ΔNWC por periodo consistente.
- Validar impuestos operativos en caja, jurisdicciones, pérdidas fiscales y diferencias temporarias. La tasa estatutaria o efectiva contable no es automáticamente la tasa correcta de FCFF.
- Conciliar CAPEX con altas de PP&E/intangibles, adquisiciones y perímetro consolidado.
- Para ISA, GEB, Ecopetrol y otras empresas con participadas, documentar si el DCF excluye el resultado de asociadas y si el puente agrega el valor de esas participaciones; no duplicar el mismo activo/resultado.

### Metodología sectorial
- FCFF/WACC es apropiado para muchas empresas no financieras, pero no debe tratarse como universal.
- Bancos y aseguradoras requieren considerar FCFE/dividendos/exceso de retornos y métricas regulatorias; REITs requieren FFO/AFFO y métricas inmobiliarias; holdings con participaciones materiales requieren suma de partes.
- La selección metodológica debe ser explicable, editable y basada en la actividad económica real, no solo en una etiqueta textual. Esta PR propaga una advertencia de metodología; no implementa por sí sola módulos completos de valoración bancaria, aseguradora o REIT.

## Criterios de aceptación para el cierre

- [x] La PR #69 está integrada y su CI pasó.
- [x] Conversión FX explícita incompleta falla de forma cerrada.
- [x] La consistencia aritmética de la instantánea ISA tiene pruebas.
- [x] Los parámetros curados exponen calidad/procedencia y estado de la tasa fiscal.
- [x] Se agregan pruebas de metadatos de calidad para todas las empresas del catálogo.
- [ ] Conciliación de estados financieros y NWC con balances detallados.
- [ ] Validación de tasa fiscal operativa sostenible de ISA.
- [ ] Valoración independiente de participadas y revisión de CAPEX/perímetro.
- [ ] Cotizaciones y FX simultáneos para cada emisor.
- [ ] Validación metodológica específica para bancos, aseguradoras, REITs y holdings.

Conclusión: queda cerrada la fase de auditoría de controles de código y trazabilidad una vez que el CI de esta PR pase. La auditoría financiera de ISA y la certificación sectorial siguen parcialmente abiertas hasta completar los datos y metodologías señalados. No usar la salida como recomendación automática de inversión mientras haya bloqueos de calidad.
