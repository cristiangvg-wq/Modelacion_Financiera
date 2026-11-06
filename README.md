# Modelación Financiera

Aplicación Streamlit para valoración de empresas, análisis de escenarios y construcción de portafolios. El sistema es una herramienta de apoyo al análisis y no constituye asesoría financiera personalizada.

## Requisitos

- Python 3.11 recomendado.
- Dependencias de `requirements.txt`.
- Acceso a internet para cotizaciones Yahoo Finance y actualización de tasas/insumos externos.
- API key de Gemini solo si se desea utilizar el comité IA.

## Instalación local

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
```

## Ejecutar la aplicación

```bash
streamlit run streamlit_app.py
```

## Manual de usuario

La app ofrece desde la pantalla de inicio (y en la barra lateral, sección «Experiencia») el botón **📘 Descargar manual (PDF)**, una guía para principiantes con imágenes de ejemplo y un caso práctico completo.

- Texto fuente: `docs/manual_usuario.md` (las líneas `[[IMG:clave|pie]]` insertan los gráficos).
- PDF publicado: `docs/Manual_Usuario_Modelacion_Financiera.pdf`.
- Tras editar el texto, regenera gráficos y PDF:

```bash
python scripts/generar_manual_pdf.py
```

## Configurar el comité IA

No guardes claves en el código ni en archivos versionados. Puedes definir `GEMINI_API_KEY` como variable de entorno o en `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "PEGA_AQUI_TU_CLAVE"
```

No publiques ni compartas el archivo `secrets.toml`. Si usas GitHub, configura la clave como un secreto del entorno de despliegue.

## Pruebas de calidad

```bash
python -m compileall -q .
pytest -q
python scripts/evaluar_comite_ia.py
```

Las pruebas automatizadas son principalmente offline; no dependen de una API de IA real ni de una cotización intradía para ser deterministas.

## Contraste de mercado de seis activos

Desde la raíz del repositorio:

```bash
python scripts/contraste_mercado_real.py
```

El conjunto predeterminado combina ISA, Ecopetrol y Grupo Energía Bogotá (catálogo) con tres activos descargados dinámicamente: Nutresa, Apple y Palantir. También se pueden pasar tres tickers alternativos:

```bash
python scripts/contraste_mercado_real.py PFAVAL MSFT EC
```

Este procedimiento requiere conexión a Yahoo Finance. Revisa en la salida la fuente/fecha de los precios, la moneda del modelo y la moneda de cotización. No interpretes una valoración si existen vetos de calidad, unidades incompatibles o datos financieros proxy sin verificar.

## Actualizar tasas macroeconómicas

```bash
python scripts/actualizar_tasas.py
```

La actualización de tasas requiere conectividad a los endpoints públicos del Tesoro de EE. UU. y la OCDE. Conserva la fecha de observación de cada tasa y no confundas la fecha de descarga del archivo con la fecha efectiva del dato.

## Principios de interpretación

- Distinguir datos observados, datos curados, estimaciones y valores faltantes.
- No reemplazar N/D por cero.
- Mantener WACC, flujos y crecimiento terminal en la misma moneda y base nominal.
- No usar el modelo de Gordon si (g \ge WACC); si la diferencia es pequeña, informar sensibilidad alta.
- Diferenciar el upside simple del valor por acción de la TIR calculada sobre flujos de caja fechados.
- Revisar el puente EV–equity, la deuda neta, NCI, otros claims, asociadas, acciones/ADS y FX antes de interpretar el precio objetivo.
- Las recomendaciones generadas por IA deben basarse en métricas y hechos con procedencia identificable y respetar los vetos cuantitativos.

## Taller evaluativo 2026 — ISA

Respuesta completa al taller (camino: evaluación empresarial): pronóstico 2026–2030 por drivers, WACC por CAPM, VPN y TIR implícita, cuatro escenarios con seis drivers, tornado y matriz WACC × g, tres políticas con regla SI–ENTONCES, umbrales de decisión, Monte Carlo y dashboard.

```bash
python scripts/taller_isa.py                      # modelo y salidas en salidas_taller_isa/
python -m pytest -q tests/test_taller_isa.py      # pruebas
python scripts/generar_informe_taller_isa.py      # informe PDF en docs/
streamlit run scripts/dashboard_taller_isa.py     # dashboard interactivo
```

Consulta `docs/ENTREGA_TALLER_ISA.md` para la lista de entregables y `docs/Informe_Taller_ISA_2026.pdf` para el informe. Los supuestos de escenarios, políticas y umbrales son hipótesis editables; el resultado es académico, no un precio objetivo profesional.


## Academia Financiera interactiva

El repositorio incluye una academia didáctica con diseño inmersivo, siete rutas de aprendizaje, laboratorios con controles interactivos y evaluaciones breves.

### Integrada en la aplicación principal

Ejecuta la aplicación habitual:

```bash
streamlit run streamlit_app.py
```

En la barra lateral, dentro de **Experiencia**, abre **Academia financiera**.

### Publicar como aplicación independiente

Para disponer de un enlace separado y compartible en Streamlit Community Cloud:

1. Entra a [share.streamlit.io](https://share.streamlit.io/) e inicia sesión con GitHub.
2. Selecciona este repositorio y la rama `main`.
3. En **Main file path**, escribe `pages/11_Academia_Financiera.py`.
4. Pulsa **Deploy**. Streamlit creará una URL propia para compartir.
5. Mantén las dependencias de `requirements.txt`; la academia usa Streamlit y Plotly, ya incluidos.

La academia no requiere claves API. En esta primera entrega, el avance se conserva en la sesión del navegador; no hay cuentas, sincronización entre dispositivos ni base de datos de progreso. Los laboratorios son educativos y no alteran el motor de valoración de la aplicación principal.




## ISA Investment Intelligence Room — aplicación independiente

La presentación ejecutiva de ISA se ejecuta como una **aplicación Streamlit independiente**, con URL, pantalla, navegación y estilo propios. No se incorpora como una página del dashboard financiero.

### Despliegue

1. Abre [Streamlit Community Cloud](https://share.streamlit.io/) e inicia sesión con GitHub.
2. Selecciona este repositorio y la rama `main` después de fusionar el PR.
3. En **Main file path**, indica `presentacion_isa.py`.
4. Pulsa **Deploy**. Streamlit generará una URL independiente para compartir la presentación.
5. Conserva las dependencias de `requirements.txt`.

La experiencia incluye tesis, datos históricos, contexto eléctrico global, DCF, puente EV–patrimonio, escenarios, sensibilidad, Monte Carlo, decisión indicativa, guion de exposición y Data Room. Reutiliza `scripts/taller_isa.py` y `datos_taller_isa_2026.json`; no modifica ni duplica el motor de valoración.

El precio es una referencia fechada y no una cotización intradía. Los resultados son académicos y dependen de los supuestos seleccionados.


## Presentación ISA conectada a la valoración principal

La presentación ejecutiva independiente usa el snapshot de la pestaña 4 de la aplicación principal. Ya no ejecuta un DCF paralelo ni presenta escenarios calculados con supuestos distintos. Para conectar ambas apps se requiere un proyecto Supabase; la creación y configuración paso a paso está en [docs/CONFIGURAR_PRESENTACION_ISA_SUPABASE.md](docs/CONFIGURAR_PRESENTACION_ISA_SUPABASE.md).

- App principal: secrets SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY.
- App independiente: secrets SUPABASE_URL, SUPABASE_ANON_KEY e ISA_PRESENTATION_TOKEN.
- Ejecuta supabase/isa_presentation.sql en SQL Editor de Supabase.
- La tabla no permite lectura directa a usuarios anónimos; la presentación consulta mediante RPC con token.
- Sin credenciales o sin snapshot publicado, la presentación informa que no hay datos y no sustituye cifras.
