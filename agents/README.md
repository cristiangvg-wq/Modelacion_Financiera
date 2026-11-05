# Centro de Agentes IA — primera versión

La primera fase incorpora una auditoría financiera determinista y de solo lectura. No usa un LLM, no cambia los parámetros del modelo y no requiere dependencias nuevas.

## Uso desde Streamlit

La página `pages/12_Centro_Agentes.py` utiliza `agents/session_adapter.py` para leer, en modo de solo lectura, la empresa seleccionada, los supuestos vigentes, la proyección FCFF de la pestaña 1 y las métricas guardadas por la pestaña 4. No recalcula ni descarga datos. Si el modelo está marcado como modificado (`modelo_dirty`), si faltan resultados o si las métricas pertenecen a otra empresa, bloquea la auditoría y solicita ejecutar «Generar todo».

## Uso desde Python

```python
from agents.service import audit_snapshot

report = audit_snapshot({
    "task": "Revisión DCF",
    "company": "ISA",
    "currency": "COP",
    "model_inputs": {
        "debt_weight": 0.4,
        "equity_weight": 0.6,
        "kd": 0.08,
        "ke": 0.12,
        "tax_rate": 0.25,
        "nopat": 100,
        "depreciation": 20,
        "capex": 30,
        "change_nwc": 10,
        "wacc": 0.096,
        "terminal_growth": 0.035,
        "fcff_next": 80,
    },
    "model_outputs": {
        "wacc": 0.096,
        "fcff": 80,
        "terminal_value": 1311.475409836,
    },
})
```

## Contrato de entrada

- `model_inputs`: datos que alimentan las identidades, expresados en unidades coherentes.
- `model_outputs`: resultados producidos por el motor financiero que se quieren contrastar.
- Las tasas son decimales: 10% = `0.10`.
- Para FCFF se utiliza la convención `NOPAT + D&A - CAPEX - variación de NWC`; verifica que la definición y el signo de capital de trabajo coincidan con los datos que entregas.
- Para valor terminal se utiliza `FCFF_next / (WACC - g)`. El adaptador lee de la corrida de la pestaña 4 el FCFF terminal normalizado que el motor usó y el `TV_Gordon` efectivamente calculado; no aproxima el terminal con el último FCFF de la proyección.

## Verificaciones

- Pesos de deuda y patrimonio.
- Fórmula de WACC: `wd * kd * (1-tax) + we * ke`.
- Identidad de FCFF.
- Condición `WACC > g` y Gordon-Shapiro.
- Alertas de calidad proporcionadas por el snapshot.

## Seguridad y límites

El agente no modifica el contexto ni el estado de Streamlit, no ejecuta código proporcionado por el usuario y no accede a APIs externas. Las salidas son hallazgos de auditoría, no recomendaciones de inversión. No incluyas secretos ni datos personales en snapshots.

## Pruebas

```bash
python -m pytest tests/test_agent_system -q
python -m compileall -q agents pages/12_Centro_Agentes.py
```


Implementación incorporada en la rama de trabajo; ejecutar las pruebas anteriores antes de fusionar. La integración con el estado de la sesión principal está implementada mediante el adaptador de solo lectura. La página exige resultados vigentes y descarta visualmente informes de auditoría asociados a snapshots anteriores. La pestaña 4 conserva los insumos exactos del valor terminal para comprobar Gordon-Shapiro. CI ejecuta además AppTest de la página 12 y un smoke test de arranque de esa página.
