# Manual de Usuario — Modelación Financiera

Guía paso a paso para personas sin conocimientos previos de finanzas ni programación · Versión octubre 2026

## 1. 🚀 Introducción: ¿Para qué sirve esta herramienta?

Esta aplicación responde una pregunta muy simple: **¿lo que cuesta una acción hoy es caro, barato o justo frente a lo que realmente vale el negocio?** Y luego te ayuda a decidir **cuánto poner en esa acción y cuánto en otras**.

Imagina un puesto de limonada. Un vecino te ofrece venderte la mitad del puesto por 500.000 pesos. Para saber si es buen negocio no basta con mirar el precio: necesitas estimar cuántas limonadas venderá en los próximos años, cuánto le cuesta el limón y el azúcar, y cuánto debe todavía el puesto al banco. La app hace exactamente ese razonamiento, pero con empresas reales como ISA, Ecopetrol o Apple.

Todo funciona en el navegador: no tienes que programar nada. Eliges una empresa, ajustas unos pocos supuestos (o dejas los que vienen por defecto) y pulsas un botón.

### Los dos superpoderes de la app

**Superpoder 1 · Saber cuánto vale una empresa realmente (Valoración).** La app proyecta la "plata libre" que dejará el negocio en los próximos años y la convierte a pesos de hoy. El resultado es un **valor por acción** que puedes comparar con el precio de la bolsa. Si el valor estimado es mayor que el precio, la acción podría estar barata; si es menor, podría estar cara. Esto vive en las pestañas 1 a 7.

**Superpoder 2 · Combinar inversiones para ganar más arriesgando menos (Portafolios).** Un portafolio es como una canasta de frutas: si solo llevas mangos y llega una plaga de mangos, pierdes todo; si llevas mangos, bananos y fresas, una mala cosecha no te arruina. La app mira cómo se han movido varias acciones juntas en el pasado y sugiere **qué porcentaje de tu dinero poner en cada una**. También trae un simulador que muestra cuánto podrían valer tus ahorros en 1, 3 o 10 años. Esto vive en las pestañas 8 y 9.

> Importante: la app es una herramienta de estudio y apoyo para pensar. No es asesoría financiera ni una orden de comprar o vender. Sus resultados dependen de los supuestos que tú escribas.

## 2. 🧰 Guía de Herramientas y Módulos

La pantalla tiene tres zonas: la **barra lateral izquierda** (donde eliges la empresa y ajustas supuestos), la **franja superior** (indicadores, semáforo y herramientas rápidas) y las **9 pestañas** de resultados. El orden de uso casi siempre es el mismo:

1. Elegir la empresa en la barra lateral.
2. Revisar (o dejar como vienen) los parámetros.
3. Pulsar **▶ Generar todo**.
4. Leer las pestañas 1 a 7 para la valoración.
5. Usar las pestañas 8 y 9 para armar tu canasta y simular tu inversión.

[[IMG:flujo|El recorrido típico dentro de la app, de izquierda a derecha.]]

La primera vez que entras aparece un **tour guiado de 4 pasos** con botones «Siguiente →» y «Saltar tour». Si lo cierras, puedes repetirlo con el botón **Repetir tour guiado** al final de la barra lateral.

> Las imágenes de esta guía son ejemplos ilustrativos dibujados con los datos ficticios del caso de María (sección 3). En la app verás los mismos tipos de gráficos con los números de la empresa que elijas.

---

### 2.1 Elegir la empresa (barra lateral · «Empresa» y «Ficha»)

**¿Qué es en la vida real?** Es como escoger qué puesto de limonada vas a estudiar antes de hacer cuentas.

**¿Qué datos necesitas?** Solo el nombre de la empresa o su **ticker**, que es su "apodo" en la bolsa: AAPL es Apple, EC es Ecopetrol en Nueva York, ISA.CL es ISA en la Bolsa de Colombia.

**Paso a paso:**

1. En la lista desplegable de la barra lateral elige una empresa del catálogo (ISA, GEB, Celsia, EPM, Enel Colombia, BVC, Ecopetrol).
2. Si la empresa no está, abre **Buscar Yahoo Finance**, escribe el ticker (ej. AAPL) y, si quieres, empresas parecidas para comparar en «Peers» (ej. MSFT,GOOGL).
3. Pulsa **Descargar datos**. Verás «Cargada» en verde y la empresa aparecerá en la lista.

**¿Cómo interpretar el resultado?** La **Ficha** muestra el sector, la moneda y datos base de la empresa. Si sale «Sin datos» en rojo, el ticker está mal escrito o Yahoo no tiene información: revisa el apodo.

### 2.2 Subir tus propios estados financieros (barra lateral · «Estados financieros»)

**¿Qué es en la vida real?** Es entregarle a la app el cuaderno de cuentas real del puesto de limonada, en lugar de usar los números que encuentra en internet.

**¿Qué datos necesitas?** Un archivo Excel o CSV con varios años de: Año, Ingresos (ventas), EBITDA, EBIT, CAPEX (lo que se gasta en máquinas y equipos) y NWC (capital de trabajo). Son las columnas obligatorias.

**Paso a paso:**

1. Pulsa **Plantilla EEFF** para descargar el formato vacío. Las columnas en azul oscuro son obligatorias.
2. Llena la plantilla con las cifras de los informes anuales de la empresa. Opcionalmente, llena la hoja «Parámetros» (deuda, caja, número de acciones, impuesto).
3. Arrastra el archivo a la caja de carga de la barra lateral.
4. Deja marcada la casilla **Datos públicos si no hay Excel** si quieres que la app use Yahoo cuando no subes nada.

**¿Cómo interpretar el resultado?** Si el archivo no se puede leer, aparece un mensaje rojo con la razón. Con estados oficiales la recomendación final es más confiable: la app avisa cuando solo tiene datos públicos agregados.

### 2.3 Corregir histórico y Narrativa (botones de la barra lateral)

**¿Qué es en la vida real?** «Corregir histórico» es tachar un número mal copiado en el cuaderno. «Narrativa» es contar la historia que crees del negocio: "el puesto va a crecer 10 % el próximo año y con el tiempo ganará 30 centavos por cada peso vendido".

**¿Qué datos necesitas?** Para corregir: la cifra oficial correcta. Para la narrativa: cuatro "palancas": crecimiento de ventas del año 1, margen objetivo, años para llegar a ese margen y cuánto vende la empresa por cada peso que reinvierte.

**Paso a paso:** pulsa el botón, escribe los valores en la ventana que se abre y, si quieres, una frase que justifique cada número. Al guardar, aparece una nota «Narrativa fijada por el usuario» bajo los botones.

**¿Cómo interpretar el resultado?** Todas las pestañas se recalculan con tu historia. Si los resultados cambian mucho, tu valoración depende fuertemente de esa creencia.

### 2.4 Parámetros del modelo (barra lateral · acordeón)

**¿Qué es en la vida real?** Son los "tornillos" de la calculadora: cuánto cuesta el dinero, cuánto crecerá el negocio para siempre, cuánta deuda tiene.

**¿Qué datos necesitas?** Normalmente ninguno: la app los llena sola. Los más importantes son:

- **Horizonte (años):** cuántos años se proyectan uno por uno (3 a 10).
- **g terminal:** cuánto crecerá el negocio cada año después del horizonte, para siempre. Suele estar entre 2 % y 4 % en dólares.
- **D/E, Kd, Tax, β unlevered, rf, ERP, CRP:** las piezas con las que se calcula el WACC (ver glosario).
- **Puente a equity:** deuda neta, caja, número de acciones (en millones) y otros compromisos. Sirve para pasar del valor del negocio al valor de cada acción.
- **Ingresos por país (opcional):** ej. «Colombia 60, Perú 40» si la empresa vende en varios países.

**Paso a paso:** abre **Parámetros del modelo**, mueve la barra o escribe el valor exacto en la casilla. Las tasas van en fracción: 0,13 significa 13 %.

**¿Cómo interpretar el resultado?** Al cambiar cualquier parámetro aparece el aviso «Los supuestos cambiaron». Debes pulsar otra vez **▶ Generar todo**. Si la deuda neta queda en 0 pero la empresa tiene deuda, la app te advierte que el valor por acción saldrá inflado.

### 2.5 Indicadores y semáforo (franja superior)

**¿Qué es en la vida real?** Es el tablero del carro: te dice de un vistazo si algo anda mal antes de arrancar.

**¿Qué datos necesitas?** Ninguno; se calcula solo con los parámetros.

**Paso a paso:** pasa el cursor sobre cada tarjeta (WACC, Ke, Horizonte, Emisor) para leer su explicación en palabras simples.

**¿Cómo interpretar el resultado?**

- **Verde:** el supuesto es razonable.
- **Ámbar:** cuidado, revisa ese número.
- **Rojo:** el modelo puede dar resultados absurdos. Por ejemplo, si g es igual o mayor que el WACC, o si hay menos de 3 años de historia.

[[IMG:semaforo|Ejemplo de semáforo con los tres colores. Rojo no significa "no inviertas": significa "revisa este supuesto".]]

La franja también dice si el modelo y el precio están en la **misma moneda**. Si dice «Desalineación FX», no compares valor y precio todavía.

### 2.6 Herramientas rápidas: Sensibilidad, Glosario y Consulta IA

**¿Qué es en la vida real?** La sensibilidad es preguntar "¿y si el banco me cobrara un poco más?". El glosario es un diccionario de bolsillo. La Consulta IA es un tutor al que le preguntas lo que no entiendes.

**¿Qué datos necesitas?** Para la sensibilidad, un WACC y un g "de prueba". Para la IA, tu pregunta escrita.

**Paso a paso:**

1. **⚡ Sensibilidad WACC · g:** mueve las dos barras y pulsa **Ver impacto en valoración**.
2. **📚 Glosario:** elige un término de la lista y lee su analogía.
3. **🤖 Consulta IA:** escribe una pregunta (ej. "¿Qué es el WACC?" o "Resumen para el comité") y pulsa **Consultar**.

**¿Cómo interpretar el resultado?** En la sensibilidad verás el valor "antes → después". Subir el WACC casi siempre baja el valor; subir g lo sube. Si un cambio pequeño mueve muchísimo el valor, el resultado es frágil.

[[IMG:sensibilidad|Ejemplo: cómo cambia el valor por acción al mover el WACC, para tres valores de g.]]

### 2.7 Botón ▶ Generar todo

**¿Qué es en la vida real?** Es el botón de "calcular" de la calculadora: hace todas las cuentas de una vez.

**¿Qué datos necesitas?** Haber elegido empresa. Opcionalmente, el **método de pronóstico**: deja el recomendado («Drivers + identidad FCFF»). Los otros dos (ETS/Holt y ARIMA) son métodos estadísticos para comparar.

**Paso a paso:** pulsa **▶ Generar todo** y espera a que la barra de progreso llegue a «Listo». Si solo quieres recalcular una pestaña, elige «Solo pestaña seleccionada abajo» y pulsa su botón.

**¿Cómo interpretar el resultado?** Un mensaje verde «Pipeline completo» significa que todo salió bien. Si alguna pestaña falla, aparece la lista de errores. Si no hay clave de IA, el comité IA se omite, pero el resto del análisis sigue siendo válido.

### 2.8 Pestaña 1 · Pronóstico

**¿Qué es en la vida real?** Es estimar cuánta plata libre dejará el puesto de limonada cada año: lo que entra por ventas menos lo que se gasta en limones, sueldos, impuestos y equipos nuevos. A esa plata libre se le llama **FCFF**.

**¿Qué datos necesitas?** Ninguno adicional; usa la historia de la empresa.

**Paso a paso:** después de «Generar todo», abre la pestaña. Verás una tabla **Historial** (años pasados), una tabla **Proyección** (años futuros) y el gráfico **Fan chart**. Cada tabla tiene un botón para descargarla en CSV.

**¿Cómo interpretar el resultado?** En el fan chart, la línea azul es lo que ya pasó y la línea teal es lo que el modelo espera. La **sombra** alrededor muestra el rango probable: entre más ancha, más incertidumbre. Las cruces rojas marcan años raros (una crisis, la venta de un activo).

[[IMG:fan|Fan chart de ejemplo: historia en azul, proyección en teal y rango probable sombreado. La cruz roja marca un año atípico.]]

### 2.9 Pestaña 2 · Escenarios DCF

**¿Qué es en la vida real?** Es preguntar: "¿cuánto vale el puesto si el verano es malo, normal o excelente?".

**¿Qué datos necesitas?** Ninguno adicional.

**Paso a paso:** abre la pestaña y pasa el cursor por cada barra del gráfico.

**¿Cómo interpretar el resultado?** Hay tres escenarios: **pesimista, base y optimista**. Para cada uno verás:

- **EV (valor empresa):** el precio de todo el negocio, como una casa antes de restar la hipoteca.
- **Equity (valor dueños):** lo que queda para los accionistas después de pagar deudas.
- **TV / EV %:** qué parte del valor viene de los años lejanos. Si pasa de 70–80 %, el resultado depende mucho de g y del WACC.

[[IMG:escenarios|Ejemplo de escenarios: la diferencia entre cada par de barras es la deuda que se paga antes de llegar a los dueños.]]

Si el equity sigue positivo incluso en el escenario pesimista, la empresa tiene un buen colchón.

### 2.10 Pestaña 3 · Auditoría

**¿Qué es en la vida real?** Es la lista de chequeo del piloto antes de despegar.

**¿Qué datos necesitas?** Ninguno adicional.

**Paso a paso:** revisa la tabla de pruebas y sus colores.

**¿Cómo interpretar el resultado?** Verde = el supuesto pasa la prueba. Rojo **no significa "no inviertas"**: significa "revisa este supuesto antes de decidir". La regla más importante: el crecimiento g siempre debe ser menor que el WACC.

### 2.11 Pestaña 4 · Recomendación y Comité de inversión IA

**¿Qué es en la vida real?** Es una reunión de socios que, con las cuentas en la mano, dice si vale la pena seguir estudiando la compra.

**¿Qué datos necesitas?** Haber ejecutado «Generar todo». Para el comité IA, una clave de Gemini configurada por quien administra la app (o escrita por ti en «Proveedor y API key»).

**Paso a paso:**

1. Lee primero la **Decisión** del motor y la lista de **Gobernanza** (apoyos y alertas).
2. Baja a **🤖 Comité de inversión IA** y pulsa el botón para generar el dictamen.
3. Si quieres, descarga el historial de dictámenes en JSON.

**¿Cómo interpretar el resultado?** El motor da una de estas decisiones:

| Decisión | Qué significa en palabras simples |
| --- | --- |
| FAVORABLE CONDICIONADO | Los números se ven sanos y hay colchón en el escenario pesimista. Falta validar con cifras auditadas. |
| PRELIMINAR POSITIVO · PENDIENTE DE DATOS AUDITADOS | Se ve bien, pero con datos públicos. Sube estados oficiales para confirmar. |
| NEUTRAL / MONITOREAR | Señal mixta: obsérvala sin apurarte. |
| NEUTRAL / MONITOREAR · PRECIO SOBRE VALOR | El precio de bolsa está muy por encima de lo que vale según el modelo. No hay margen de seguridad. |
| EVITAR / REVISAR | Demasiadas alertas frente a los apoyos. |
| RECALIBRAR MODELO · VETO DE CALIDAD | Los supuestos se contradicen. No es una opinión sobre la acción: hay que corregir el modelo. |

El comité IA entrega tres bloques: una crítica a los números del modelo, el contexto del mercado con fuentes citadas y una postura **COMPRAR / MANTENER / VENDER** con riesgos y catalizadores. Úsalo como una segunda opinión, nunca como orden.

### 2.12 Pestaña 5 · VPN / TIR

**¿Qué es en la vida real?** Es preguntar si poner una nueva máquina de exprimir limones "se paga sola" y cuánto rinde.

**¿Qué datos necesitas?** El campo **Inversión proyecto** de la barra lateral (cuánto cuesta el proyecto hoy).

**Paso a paso:** escribe la inversión, pulsa «Generar todo» y abre la pestaña.

**¿Cómo interpretar el resultado?**

- **VPN mayor que 0:** el proyecto deja más valor del que cuesta el dinero. Buena señal.
- **TIR mayor que el WACC:** el proyecto rinde más de lo que exige el capital.
- **Payback:** en cuántos años recuperas lo invertido. No dice si el riesgo valía la pena.

[[IMG:vpn|Ejemplo de VPN acumulada: mientras la línea está en la zona roja aún no recuperas la inversión; al cruzar a la verde, ya sí.]]

### 2.13 Pestaña 6 · Sector

**¿Qué es en la vida real?** Es comparar tu puesto de limonada con los de la misma cuadra.

**¿Qué datos necesitas?** Ninguno adicional; usa las empresas parecidas (peers).

**Paso a paso:** revisa el ranking y pasa el cursor por cada empresa.

**¿Cómo interpretar el resultado?** Un **Score** más alto indica mejor posición frente a sus vecinas. El **margen EBITDA** dice cuánto queda de cada 100 pesos vendidos. Un **EV/EBITDA** muy bajo puede ser una ganga… o una señal de problemas.

### 2.14 Pestaña 7 · Informe PDF

**¿Qué es en la vida real?** Es el resumen de una página que le llevarías a tu socio.

**¿Qué datos necesitas?** Haber ejecutado «Generar todo».

**Paso a paso:** abre la pestaña, revisa el tablero ejecutivo y pulsa **Descargar informe ejecutivo (PDF)**. Puedes pulsar **↻ Consultar mercado y contrastar VPS** para traer el precio más reciente.

**¿Cómo interpretar el resultado?** Fíjate en tres números: **VPS modelo** (lo que vale cada acción según el modelo), **precio de mercado** y **Upside** (la diferencia en %). Un upside de +25 % significa que el modelo cree que la acción vale 25 % más que su precio. Si sale «N/D», revisa monedas y número de acciones.

[[IMG:upside|Ejemplo: valor por acción del modelo frente al precio de bolsa. La distancia entre ambos es el upside.]]

### 2.15 Pestaña 8 · Portafolios

**¿Qué es en la vida real?** Es decidir cuántas frutas de cada tipo poner en la canasta para que una mala cosecha no te arruine.

**¿Qué datos necesitas?**

- Los tickers de las acciones que te interesan (mínimo dos distintos), separados por coma.
- El **peso máximo por activo**: el porcentaje más alto que aceptas poner en una sola acción (por defecto 60 %).
- La **moneda de análisis**: USD o COP.

**Paso a paso:**

1. Deja marcada la casilla para incluir la empresa que estás valorando.
2. Escribe otros tickers, ej. «MSFT,NVDA».
3. Elige el **objetivo**: «Maximizar Sharpe» (la mejor ganancia por cada unidad de riesgo) o «Minimizar volatilidad» (la canasta más tranquila posible).
4. Elige la ventana histórica (2, 5 o 10 años) y deja el retorno «Anclado en riesgo y precio (recomendado)».
5. Pulsa **Optimizar portafolio**.

**¿Cómo interpretar el resultado?**

- **Pesos sugeridos:** qué porcentaje de tu dinero va en cada acción.
- **Retorno esperado anualizado y volatilidad:** cuánto podría ganar la canasta al año y cuánto suele subir y bajar.
- **Sharpe:** más alto es mejor; por encima de 0,5 es razonable, por encima de 1 es muy bueno.
- **Caída máxima histórica:** el peor bajón que habría sufrido tu dinero desde un pico.
- **VaR / CVaR diario:** cuánto podrías perder en un día malo y en los peores días.
- **Frontera eficiente:** la curva de las mejores canastas posibles; cada punto da el máximo retorno para cierto nivel de riesgo.
- **Prueba fuera de muestra:** revisa si la canasta habría funcionado en años que el optimizador no vio.

[[IMG:portafolio|Ejemplo de resultado: a la izquierda los pesos sugeridos; a la derecha la frontera eficiente con la canasta elegida (estrella) frente a cada acción sola.]]

Al final verás la **Recomendación integrada**, que cruza el peso sugerido con el upside del DCF. Si una acción recibe peso 0 %, no es una orden de venta: depende del objetivo y la ventana elegidos.

### 2.16 Pestaña 9 · Simular inversión

**¿Qué es en la vida real?** Es preguntarte: "si meto mis ahorros en esta acción, ¿cuánto podría tener en 3 años si las cosas van mal, normal o bien?".

**¿Qué datos necesitas?**

- **Capital disponible** y su moneda (COP o USD).
- **Horizonte de inversión:** 1, 2, 3, 5 o 10 años.
- **Dividendos anuales estimados (%)** que paga la empresa.
- **Costos de compra y venta (%)** que cobra tu comisionista, y la **retención sobre dividendos (%)**.
- Tres supuestos de valorización anual de la acción: **Pesimista, Base y Optimista**.
- La **tasa de cambio** si tu dinero está en pesos y la acción en dólares.

**Paso a paso:** revisa el ticker propuesto, llena los campos y pulsa **Simular inversión**.

**¿Cómo interpretar el resultado?**

- **Acciones comprables:** cuántas acciones enteras alcanzas a comprar.
- **Efectivo residual:** lo que te sobra porque no alcanza para otra acción.
- **Valor final y Ganancia / pérdida:** cuánto tendrías al final de cada escenario, ya descontando costos.
- **Gráfico de evolución:** cómo crecería o caería tu dinero año a año.

[[IMG:simulador|Ejemplo de evolución del capital en los tres escenarios. La línea punteada es lo que invertiste.]]

Un mensaje verde indica ganancia en el escenario base; uno ámbar, pérdida. Mira siempre también el pesimista: es el que te dice si podrías dormir tranquilo. El simulador no incluye inflación ni cambios futuros del dólar, y no reinvierte los dividendos.

## 3. 💡 Ejemplo Práctico "Paso a Paso"

**Conclusión del caso:** María decide invertir, pero solo el 35 % de sus ahorros en la Empresa X y el resto repartido en otras dos acciones. Así lo descubre con la app.

> Todos los datos de este ejemplo son ficticios. «Empresa X» y los tickers EMPX, ACCB y ACCC no existen; en la app real escribirías tickers de empresas que cotizan en bolsa.

### La situación

María tiene **10.000.000 de pesos** ahorrados que no necesitará en los próximos 3 años. Un amigo le dijo que la Empresa X "está barata". Ella quiere saber dos cosas: si de verdad está barata y cuánto de su dinero debería poner allí.

### Paso 1 · Elige la empresa

En la barra lateral abre **Buscar Yahoo Finance**, escribe **EMPX** en «Ticker» y **ACCB,ACCC** en «Peers». Pulsa **Descargar datos**. Aparece «Cargada» y la Ficha muestra:

| Dato de la Ficha | Valor |
| --- | --- |
| Sector | Energía |
| Moneda del modelo | COP |
| Precio de mercado | 20.000 COP por acción |
| Acciones en circulación | 1.000 millones |

### Paso 2 · Revisa los parámetros

María no es experta, así que deja casi todo como viene. Solo abre **Parámetros del modelo** y confirma dos números:

- **g terminal:** 0,04 (la empresa crecerá 4 % al año para siempre, parecido a la inflación en pesos).
- **Horizonte:** 5 años.

La franja superior muestra **WACC 11,5 %**. El semáforo sale así:

| Revisión | Color | Lo que dice |
| --- | --- | --- |
| Crecimiento (g) | Verde | g de 4 % está por debajo del WACC de 11,5 %: coherente. |
| Apalancamiento | Verde | D/E de 0,9: nivel moderado. |
| Historia | Verde | 6 años de datos: base razonable. |
| Impuestos | Verde | Tasa de 35 % en rango habitual. |

### Paso 3 · Pulsa ▶ Generar todo

La barra de progreso llega a «Listo» y aparece «Pipeline completo». María recorre las pestañas:

- **Pestaña 1 · Pronóstico:** la plata libre (FCFF) pasa de 1,8 billones de pesos a 2,6 billones en 5 años. La sombra del fan chart es angosta: el negocio es estable (ver la imagen de la sección 2.8).
- **Pestaña 2 · Escenarios:** el valor para los dueños (equity) es positivo en los tres escenarios. El valor terminal pesa 72 % del total: aceptable, aunque conviene revisar la sensibilidad a g y al WACC.
- **Pestaña 3 · Auditoría:** todas las pruebas en verde.
- **Pestaña 7 · Informe:** muestra el número que María buscaba.

| Indicador | Valor | Qué le dice a María |
| --- | --- | --- |
| VPS modelo | 25.000 COP | Cada acción vale 25.000 según el modelo. |
| Precio de mercado | 20.000 COP | La bolsa la vende a 20.000. |
| Upside | +25 % | El modelo cree que la acción vale 25 % más que su precio. |
| ROIC vs WACC | 14 % vs 11,5 % | La empresa gana más de lo que le cuesta su dinero: crea valor. |

- **Pestaña 4 · Recomendación:** la decisión es **PRELIMINAR POSITIVO · PENDIENTE DE DATOS AUDITADOS**. La app le avisa que usó datos públicos de Yahoo.

María descarga la **Plantilla EEFF**, la llena con el informe anual oficial de la Empresa X, la sube y vuelve a pulsar **▶ Generar todo**. Ahora la decisión es **FAVORABLE CONDICIONADO**. El comité IA opina **MANTENER con sesgo positivo** y menciona un riesgo: un cambio en la regulación de tarifas.

### Paso 4 · Arma la canasta (Pestaña 8 · Portafolios)

María sabe que poner todo en una sola empresa es arriesgado. En la pestaña 8 escribe:

| Campo | Lo que escribe María |
| --- | --- |
| Incluir la empresa valorada | Marcado (EMPX) |
| Otros tickers | ACCB,ACCC |
| Peso máximo por activo | 0,60 |
| Objetivo | Maximizar Sharpe |
| Ventana histórica | 5y |
| Moneda de análisis | COP |
| Tasa libre de riesgo | 0,095 |

Pulsa **Optimizar portafolio** y obtiene:

| Resultado | Valor |
| --- | --- |
| Peso sugerido EMPX | 35 % |
| Peso sugerido ACCB | 40 % |
| Peso sugerido ACCC | 25 % |
| Retorno esperado anualizado | 17,0 % |
| Volatilidad anualizada | 14,0 % |
| Sharpe estimado | 0,54 |
| Caída máxima histórica | −22 % |

La **Recomendación integrada** sale en verde: el DCF ve upside positivo y el optimizador asigna 35 % a EMPX. Ambas señales apuntan en la misma dirección.

### Paso 5 · Simula su inversión (Pestaña 9)

El 35 % de 10.000.000 son **3.500.000 pesos**. María los simula en EMPX:

| Campo | Lo que escribe María |
| --- | --- |
| Capital disponible | 3.500.000 COP |
| Horizonte | 3 años |
| Dividendos anuales estimados | 4 % |
| Costo de compra / venta | 0,5 % / 0,5 % |
| Retención sobre dividendos | 10 % |
| Pesimista / Base / Optimista | −12 % / 7 % / 20 % |

Pulsa **Simular inversión**. La app le dice que alcanza para **174 acciones** y le sobran **2.600 pesos**. Los tres escenarios, ya con costos y dividendos:

| Escenario | Valor final en 3 años | Ganancia / pérdida | Rentabilidad anualizada |
| --- | --- | --- | --- |
| Pesimista | 2.738.105 COP | −761.895 COP | −7,9 % |
| Base | 4.620.274 COP | +1.120.274 COP | +9,7 % |
| Optimista | 6.361.813 COP | +2.861.813 COP | +22,0 % |

### La decisión de María

María decide invertir **3.500.000 pesos en EMPX, 4.000.000 en ACCB y 2.500.000 en ACCC**, siguiendo los pesos sugeridos. Lo razona así:

1. **Hay valor:** el modelo dice que la acción vale 25 % más que su precio y la empresa crea valor (ROIC mayor que WACC).
2. **Los datos son confiables:** con estados oficiales la decisión subió a «Favorable condicionado».
3. **El riesgo está controlado:** en el peor escenario perdería unos 760.000 pesos en EMPX, una pérdida que puede soportar sin tocar sus gastos del mes. Si esa cifra le quitara el sueño, bajaría el peso de EMPX y volvería a optimizar.
4. **No pone todos los huevos en la misma canasta:** el 65 % restante queda en otras dos acciones.

María anota que debe repetir el análisis cuando la empresa publique su próximo informe anual o si el precio sube por encima de 25.000 pesos, porque ahí desaparecería el margen de seguridad.

## 4. ❓ Preguntas Frecuentes y Glosario Relámpago

### Preguntas frecuentes

**¿Necesito saber programar?** No. Todo se hace con clics, barras y casillas desde el navegador.

**Cambié un número y los resultados desaparecieron. ¿Se dañó algo?** No. La app borra los resultados viejos para que no mezcles supuestos distintos. Pulsa otra vez **▶ Generar todo**.

**El Upside sale «N/D». ¿Qué hago?** Casi siempre es porque el modelo y el precio están en monedas distintas o falta el número de acciones. Revisa el mensaje de moneda en la franja superior y el campo «Acciones (M)» en los parámetros.

**El semáforo está en rojo. ¿Significa que no debo invertir?** No. Significa que un supuesto se ve raro y conviene revisarlo antes de confiar en el resultado.

**El comité IA no aparece.** Necesita una clave de Gemini. Sin ella, todo lo demás funciona igual; solo se omite la opinión de la IA.

**¿Por qué una acción recibió 0 % en el portafolio?** Porque, con la ventana y el objetivo elegidos, no mejoraba la canasta. Prueba otra ventana o sube el peso máximo; no es una orden de venta.

**¿El simulador garantiza esas ganancias?** No. Solo multiplica tus supuestos. Si escribes que la acción subirá 20 % al año, eso es lo que calculará.

**¿Puedo confiar en los datos de Yahoo?** Sirven como punto de partida, pero no son estados auditados. Para decisiones importantes, sube los estados financieros oficiales con la plantilla.

### Glosario relámpago

| Término | En palabras simples |
| --- | --- |
| Beta (β) | Mide cuánto se mueve una acción cuando se mueve toda la bolsa. Beta 1,5 significa que si la bolsa sube 10 %, la acción tiende a subir 15 % (y lo mismo al bajar). |
| CAPEX | Lo que la empresa gasta en máquinas, edificios y equipos. Es como comprar un exprimidor nuevo para el puesto de limonada. |
| CRP (riesgo país) | Un pago extra que se exige por invertir en un país más inestable. En pesos ya viene incluido en otras tasas, por eso suele quedar en 0. |
| CVaR | El promedio de lo que pierdes en los peores días. Si el VaR es el "día malo", el CVaR es el "día terrible". |
| D/E | Cuánta deuda tiene la empresa por cada peso de los dueños. Más deuda, más riesgo. |
| DCF | Método que suma toda la plata libre futura del negocio, traída a pesos de hoy. Un peso mañana vale menos que un peso hoy, y el DCF lo tiene en cuenta. |
| EBITDA | Lo que gana el negocio con su operación antes de pagar intereses, impuestos y el desgaste de sus equipos. Es la ganancia "en bruto" del día a día. |
| Equity | Lo que les queda a los dueños después de pagar todas las deudas. Es tu parte del pastel. |
| ERP | El premio extra que piden los inversionistas por meterse en la bolsa en vez de en bonos seguros. |
| EV (valor empresa) | El precio de todo el negocio, como una casa antes de restar la hipoteca. |
| EV/EBITDA | Cuántas veces paga el mercado la ganancia operativa de un año. Un 8 significa que pagas 8 años de ganancias. |
| FCFF | La plata libre del negocio: lo que sobra después de operar e invertir. Es lo que el DCF trae a pesos de hoy. |
| Frontera eficiente | La curva de las mejores canastas posibles. Cada punto da la mayor ganancia para cierto nivel de riesgo. |
| g (crecimiento terminal) | Qué tan rápido crecerá el negocio para siempre después del horizonte. Debe ser siempre menor que el WACC. |
| Kd | La tasa de interés que la empresa paga por sus préstamos. |
| Ke | La rentabilidad que exigen los dueños por arriesgar su dinero. Suele ser mayor que la de los bancos. |
| Payback | Cuántos años tardas en recuperar lo que invertiste. No dice si valió la pena el riesgo. |
| rf (tasa libre de riesgo) | Lo que ganarías prestándole al gobierno, la inversión más segura. En pesos son los TES; en dólares, los bonos del Tesoro de EE. UU. |
| ROIC | Cuánto gana la empresa por cada peso invertido en el negocio. Si es mayor que el WACC, crea valor. |
| Sharpe Ratio | Cuánta ganancia extra obtienes por cada unidad de riesgo que aceptas. Más alto es mejor: por encima de 1 es muy bueno. |
| TIR | La rentabilidad anual que da un proyecto. Si es mayor que el WACC, el proyecto suele valer la pena. |
| Upside | La diferencia entre lo que vale la acción según el modelo y su precio. +25 % significa que podría estar 25 % barata. |
| Valor terminal (TV) | El valor de todos los años después del horizonte, resumido en un solo número. Si pesa demasiado, el resultado depende mucho de g y del WACC. |
| VaR diario | La pérdida que no se superó en el 95 % de los días. Es tu "día malo normal". |
| Volatilidad | Cuánto sube y baja el precio de una acción. Mucha volatilidad es como una montaña rusa: emocionante pero mareadora. |
| VPN | La ganancia de un proyecto en pesos de hoy, ya restando lo que cuesta. Si es positiva, el proyecto crea valor. |
| VPS | Valor por acción según el modelo: el equity dividido entre el número de acciones. Se compara con el precio de bolsa. |
| WACC | El costo promedio del dinero de la empresa, mezclando lo que cobran los bancos y lo que exigen los dueños. Es la vara mínima que el negocio debe superar para crear valor. |

> Recordatorio final: esta herramienta es pedagógica. No es un feed oficial de la Bolsa de Valores de Colombia ni asesoría de inversión. Antes de invertir dinero real, contrasta los resultados con un asesor autorizado.
