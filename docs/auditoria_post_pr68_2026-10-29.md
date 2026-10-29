# Auditoría posterior a PR #68 — 29 de octubre de 2026

## Alcance y evidencia

Se revisaron la lógica de conversión FX, el catálogo curado, las pruebas de contrato multisectorial y el workflow de calidad financiera. La PR #68 actualiza una instantánea de mercado de ISA; sus pruebas no constituyen una descarga de cotizaciones en vivo ni una auditoría de estados financieros completos.

## Hallazgos y correcciones de esta rama

### 1. Fallback FX silencioso con mapa explícito incompleto — corregido

**Riesgo:** la conversión COP/USD podía recurrir al proveedor spot si el llamador había proporcionado un mapa FX explícito, pero ese mapa no contenía todas las tasas necesarias. Eso mezclaba potencialmente fuentes y fechas sin avisar, contrario al contrato de trazabilidad.

**Corrección:** cuando se suministra un mapa FX explícito, COP/USD ahora falla de forma cerrada si falta una tasa requerida. El proveedor spot solo se utiliza cuando no se proporcionó mapa explícito. Se agregaron pruebas para el bloqueo y para la dirección de conversión COP→USD.

### 2. Fecha global de curación anterior a la instantánea ISA — corregido

**Riesgo:** `datos_curados.json` indicaba `as_of=2026-10-27`, aunque la instantánea de ISA incluida en el mismo catálogo es del 29 de octubre de 2026.

**Corrección:** se actualizó la fecha de curación a `2026-10-29` y se agregó una prueba para impedir que la fecha global quede antes de la fecha del precio de ISA. Esto actualiza la fecha del catálogo, pero **no implica que todas las cotizaciones o datos de todas las empresas se hayan descargado en vivo ese día**.

### 3. Conciliación aritmética del snapshot de ISA

Con los valores curados:

- Precio de referencia: COP 27.500 por acción.
- Acciones: 1.107,7 millones.
- Capitalización derivada: COP 30.461,75 miles de millones.
- Deuda bruta derivada: 30.430 + 3.725 = COP 34.155 miles de millones.
- D/E: 34.155 / 30.461,75 ≈ 1,1212.

La prueba valida las identidades y las unidades declaradas; no valida por sí sola la autenticidad, simultaneidad o vigencia de la cotización de origen.

## Estado de los riesgos financieros que permanecen abiertos

1. **NWC:** la serie histórica de ISA sigue siendo estimada; conciliar con balances detallados y separar activos/pasivos operativos de caja y deuda.
2. **Tasa fiscal:** 22 % sigue siendo un supuesto provisional. La tasa efectiva contable no basta para demostrar la tasa fiscal operativa sostenible sobre EBIT.
3. **Asociadas y negocios conjuntos:** el puente usa COP 4.332 miles de millones a valor contable, no una valoración independiente.
4. **Perímetro contable:** preservar la separación entre operación ajustada y participadas para evitar doble conteo.
5. **Mercado en vivo:** no se ha demostrado una conciliación BVC/Yahoo con timestamps simultáneos ni se han refrescado aquí precios y FX de todos los emisores.
6. **Cobertura multisectorial:** las pruebas sintéticas verifican identidades generales, pero no certifican metodologías específicas para bancos, aseguradoras, REITs, holdings o empresas con estructuras de deuda no comparables.

## Criterio de cierre

Esta rama agrega correcciones y pruebas de regresión. Debe considerarse lista para revisión solo después de que CI ejecute la suite completa. La valoración real de ISA permanece **parcialmente validada**, no certificada para decisión de inversión.