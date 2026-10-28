# Auditoría del Comité Director — 28 de octubre de 2026

## Alcance y limitación

Auditoría estática inicial del repositorio `cristiangvg-wq/Modelacion_Financiera`, rama `main`, complementada con inspección de pruebas y de cotizaciones públicas consultadas el 28-oct-2026. Esta nota no afirma que se haya ejecutado localmente toda la suite ni que se haya corrido el script de valoración con conectividad Yahoo Finance. Los precios de abajo son referencias de mercado externas y no resultados calculados por el modelo.

## Hallazgos reproducibles de arquitectura

1. La lógica financiera central está concentrada en `modelacion_logic.py` (~625 KB / 12.874 líneas); la interfaz en `streamlit_app.py` (~251 KB / 5.639 líneas); el módulo IA en `comite_ia.py` (~70 KB / 1.229 líneas). Es una alta concentración de responsabilidades que eleva el costo de revisión, aunque no prueba por sí sola una fuga de memoria.
2. El proyecto tiene un script de contraste de mercado en `scripts/contraste_mercado_real.py` que prueba 3 empresas predefinidas (ISA, Ecopetrol, GEB) y 3 activos dinámicos (por defecto Nutresa, AAPL y PLTR). Comprueba consistencia de precio, EV, Equity, VPS y upside entre pestañas 2, 4 y 7.
3. La suite incluye pruebas de moneda, datos faltantes de Yahoo, NCI, conversión COP/USD, CAPM, tasa terminal, sensibilidad WACC/g, estado de sesión, comité IA y motor de portafolios. La ejecución de calidad de `main` consultada para el commit `4b92d70c` terminó en éxito; una ejecución posterior en rama de auditoría estaba en curso.
4. `datos_mercado.json` fue generado el 2026-10-28. Su tasa US a 10 años tiene observación 2026-10-27; la observación colombiana proviene del promedio OCDE de 2026-09-15. La aplicación también contiene una referencia TES más reciente codificada en `modelacion_logic.py` (13,18 %, 2026-10-16), por lo que deben distinguirse la fecha de actualización del archivo y la fecha efectiva de cada ancla macro.
5. El cálculo de WACC valida tasas finitas, D/E no negativo y tasa fiscal entre 0 y 1. El FCFF rechaza columnas faltantes/no finitas y la valoración limita g terminal para evitar que alcance o supere WACC. El comité IA tiene validación determinista del esquema, de las anclas de precio objetivo y de la coherencia con el motor.
6. La raíz no contiene un README.md. Esto dificulta la instalación reproducible y la explicación de secretos, ejecución de pruebas y flujo de valoración.

## Cotizaciones externas de referencia

Valores de mercado publicados para el 28-oct-2026, salvo donde se indica cierre anterior. Los precios BVC son COP por acción; AAPL y PLTR son USD por acción. La consulta de mercado no sustituye la instantánea capturada por la aplicación, y pueden existir diferencias intradía entre proveedores.

| Grupo | Empresa / ticker de contraste | Precio de referencia | Fecha / observación | Fuente |
|---|---|---:|---|---|
| Catálogo | ISA (ticker de modelo: ISA.CL) | 28.080 COP | 28-oct-2026, 11:53 hora local | La República / BVC: https://www.larepublica.co/indicadores-economicos/movimiento-accionario/isa |
| Catálogo | Ecopetrol (ticker local) | 2.795 COP | Cierre 28-oct-2026 | Stock Analysis / BVC: https://stockanalysis.com/quote/bvc/ECOPETROL/history/ |
| Catálogo | Grupo Energía Bogotá (GEB) | 3.000 COP | 28-oct-2026, 12:26 hora local | La República / BVC: https://www.larepublica.co/indicadores-economicos/movimiento-accionario/geb |
| Dinámico | Grupo Nutresa (NUTRESA) | 322.000 COP | Referencia intradía 28-oct-2026 | Grupo Aval: https://www.grupoaval.com/wps/portal/grupo-aval/aval/portal-financiero/indica |
| Dinámico | Apple (AAPL) | 343,82 USD | Cierre 28-oct-2026 | Stock Analysis: https://stockanalysis.com/stocks/aapl/history/ |
| Dinámico | Palantir (PLTR) | 196,88 USD | Cierre 28-oct-2026 | Twelve Data: https://twelvedata.com/markets/486896/stock/nasdaq/pltr/historical-data |

## Comparativa del modelo vs. mercado: estado

La valoración intrínseca, el upside y la TIR deben calcularse en una misma ejecución del repositorio para cada activo, con la misma instantánea de precio y supuestos documentados. No se consignan valores de modelo en esta tabla porque no se ejecutó el motor financiero contra las fuentes en vivo en este entorno; inventar VPS, TIR o WACC sería una falsa validación.

Comando reproducible desde la raíz del repositorio:

```bash
python scripts/contraste_mercado_real.py
```

Para activos dinámicos alternativos:

```bash
python scripts/contraste_mercado_real.py PFAVAL MSFT EC
```

El comando necesita conectividad de red a Yahoo Finance. La salida compara precio, VPS, upside y consistencia entre pestañas. El script actual no imprime explícitamente la TIR por activo; debe añadirse a la salida del informe con una definición inequívoca (TIR del equity o retorno implícito del FCFF) antes de afirmar que esa métrica se contrastó.

## Riesgos matemáticos que deben bloquear una recomendación automática

- **Perpetuidad:** el valor terminal de Gordon (TV_n = FCFF_{n+1}/(WACC-g)) no está definido para (g \ge WACC) y se vuelve extremadamente sensible cuando (WACC-g) es pequeño. La app ya incluye límites y vetos; debe conservarse la alerta de dependencia del valor terminal.
- **Moneda:** RF, ERP, g nominal y flujos deben estar en la misma moneda/base nominal. Aplicar TES COP a FCFF USD mezcla inflación y riesgo de moneda; el motor implementa CAPM por moneda y riesgo país para cruces.
- **Puente EV–equity:** equity = EV − deuda neta − NCI − otros claims + asociadas (según el tratamiento contable configurado). Mezclar miles de millones, unidades, acciones ordinarias y ADS puede alterar materialmente el VPS.
- **Datos ausentes:** N/D debe mantenerse como dato ausente; convertirlo en cero puede fabricar D/E, ROIC, upside o TIR.
- **TIR:** no debe confundirse la TIR del proyecto/empresa con el upside simple (VPS/precio − 1). La TIR exige una serie de flujos fechados y un flujo terminal coherente.

## Acciones recomendadas

1. Ejecutar el contraste de seis activos con cotizaciones descargadas en la misma corrida y guardar salida con timestamp, fuente, moneda, VPS, upside, WACC, g, TIR definida y banderas de calidad.
2. Añadir una tabla de procedencia y frescura para RF/ERP/CRP/g, con fecha efectiva por cada input, no solo la fecha de descarga del JSON.
3. Mantener el veto de calidad de IA cuando haya datos incompletos, monedas no alineadas o puente EV–equity sin conciliar.
4. Mantener las pruebas offline en CI y tratar los contrastes online como una ejecución separada/reproducible: la red, los límites de Yahoo y las cotizaciones intradía no deben volver inestable la suite de cada commit.
5. Añadir README con instalación, secretos `GEMINI_API_KEY`, ejecución de pruebas y comandos de auditoría.

## UI/UX

La app usa layout ancho, tema oscuro y tablas `st.dataframe(width="stretch")`. La inspección estática confirma reglas CSS para tablas y wrappers para gráficos; la validación visual final requiere abrir la app en escritorio y móvil. Evitar fijar anchos rígidos, mostrar moneda/unidad en cada KPI y dejar visibles fecha y fuente de cotización.
