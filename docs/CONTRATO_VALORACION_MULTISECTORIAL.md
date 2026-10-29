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

## Auditoría adicional: moneda y alcance sectorial

### Conversión de moneda del precio
`convertir_precio_a_moneda_modelo` admite ahora un mapa explícito `tasas_cop_por_moneda`, con tasas expresadas como COP por unidad de divisa. Por ejemplo, si 1 EUR = 4.400 COP y 1 USD = 4.000 COP, el cruce EUR→USD es 1,10 USD por EUR. Las cifras son ilustrativas; no son una cotización actual. La función rechaza precios no finitos, tasas no positivas y cruces sin tasas suficientes. Sin mapa explícito, conserva el comportamiento previo para COP↔USD usando la tasa spot existente.

**Limitación:** el caller debe suministrar tasas confiables y registrar fecha/fuente; este cambio no crea una fuente FX universal ni convierte los estados históricos. La interfaz todavía debe exponer y conservar la fuente/fecha de FX para los cruces distintos de COP/USD.

### Impuestos, CAPEX y capital de trabajo
- La tasa estatutaria de un país es solo un punto de partida, no equivale necesariamente al impuesto operativo en caja. Para multinacionales, empresas con pérdidas fiscales o diferencias temporarias, la valoración debe permitir una tasa normalizada documentada o un calendario fiscal explícito.
- CAPEX debe conciliarse con compras de propiedad, planta y equipo, intangibles y adquisiciones según la política del modelo; no se deben mezclar CAPEX de mantenimiento y expansión sin declararlo.
- La variación de NWC debe calcularse sobre partidas operativas, excluyendo efectivo y deuda financiera. Cuando NWC se estime como proxy, la salida debe conservar la etiqueta de estimación y no presentarlo como dato auditado.
- Las tasas de crecimiento, márgenes y ratios históricos deben probarse contra años atípicos y ciclos; una mediana robusta no sustituye el juicio sobre cambios estructurales.

### Método por tipo de negocio
El motor DCF FCFF/WACC no debe presentarse como universal para todos los sectores. Para bancos y aseguradoras, considerar FCFE, dividendos o exceso de retornos; para holdings con participaciones materiales, suma de partes; para REITs, métricas y flujos propios del sector. Cualquier selección automática futura debe ser una recomendación explicable y editable, no un bloqueo ciego por etiqueta sectorial.
