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
