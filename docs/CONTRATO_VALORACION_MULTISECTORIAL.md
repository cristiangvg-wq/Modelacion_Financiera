# Contrato de valoración multisectorial

## Alcance
La aplicación debe valorar compañías de distintos sectores, geografías, monedas y estructuras de capital. ISA, Ecopetrol, GEB, Apple o cualquier emisor precargado son ejemplos y pruebas de regresión; no deben definir reglas universales del motor.

## Invariantes financieros
1. **FCFF:** FCFF = NOPAT + depreciación y amortización − CAPEX − variación del capital de trabajo operativo. Cada partida debe compartir unidad, periodo, perímetro contable y moneda.
2. **NOPAT:** el impuesto operativo se aplica al EBIT positivo según el supuesto fiscal introducido y documentado. No se genera automáticamente un beneficio fiscal por pérdidas sin modelar explícitamente su uso y restricciones.
3. **WACC:** D/E, Kd, Ke y tasa fiscal se expresan en decimales; los pesos de deuda y patrimonio deben sumar uno. Costos de capital y flujos deben tener la misma moneda y base nominal (inflación).
4. **DCF:** el WACC debe superar el crecimiento terminal. El valor terminal debe normalizar la reinversión y no extrapolar ciegamente un año atípico.
5. **Puente EV → Equity:** definir si la deuda se introduce neta o bruta. No restar deuda neta y volver a sumar caja; ajustar NCI, otros claims y participaciones no operativas sin duplicarlas.
6. **Valor por acción:** acciones, ADS/ADR y precio deben estar en la misma base de unidades y moneda; FX debe ser explícito y fechado.
7. **Datos:** distinguir estados auditados, datos descargados, catálogo curado y estimaciones/proxies. Datos ausentes o unidades incompatibles deben generar advertencias o detener el cálculo, nunca convertirse silenciosamente en cero.
8. **Neutralidad sectorial:** no fijar márgenes, CAPEX/ventas, capital de trabajo, beta, tasa fiscal, g ni estructura de capital de ISA como valores universales. Los defaults son solo iniciales y deben poder editarse o estimarse para cada empresa.

## Pruebas
```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

La suite `tests/test_contrato_multisectorial.py` usa casos sintéticos de distintos tamaños y perfiles operativos para probar identidades e invariantes, no para afirmar que una valoración concreta sea correcta. Para certificar un emisor real todavía se requiere conciliar estados financieros, moneda, impuestos, CAPEX, NWC, deuda, participadas y acciones con fuentes verificables.

## Limitaciones que deben permanecer visibles
- Una sola tasa fiscal aplicada al EBIT es una simplificación: en multinacionales, pérdidas fiscales, impuestos diferidos y regímenes jurisdiccionales pueden cambiar el impuesto en caja.
- CAPEX y variación de NWC necesitan datos consistentes; las estimaciones deben etiquetarse como tales.
- Un DCF no sustituye una valoración por suma de partes cuando participadas, activos regulados, bancos, aseguradoras o negocios con flujos muy distintos requieren metodologías específicas.
- Los bancos y aseguradoras normalmente necesitan enfoques de patrimonio (p. ej., FCFE/dividendos o exceso de retornos) porque la deuda es parte del negocio; no se debe aplicar automáticamente FCFF/WACC como si fueran una empresa industrial.
