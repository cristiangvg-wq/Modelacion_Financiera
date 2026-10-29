# Escenarios y políticas simuladas — módulo académico

Este módulo agrega una capa reproducible al flujo **Datos → Pronóstico → Escenarios → Políticas → Decisión** sin reemplazar la valoración corporativa existente. Todas las cifras de entrada deben estar expresadas en una única moneda y escala (por ejemplo, COP miles de millones); no mezcla COP con USD ni convierte unidades automáticamente.

## Cinco drivers y escenarios

El módulo usa al menos cinco drivers conectados:
1. Crecimiento anual de ingresos.
2. Margen EBIT.
3. CAPEX / ingresos.
4. Capital de trabajo neto (NWC) / ingresos.
5. WACC.

La configuración de escenarios es explícita y modificable en `financial_scenarios.py`: pesimista reduce crecimiento y margen, aumenta CAPEX/NWC y eleva WACC; optimista hace lo contrario. Son shocks de demostración, no datos de mercado ni pronósticos oficiales. Deben reemplazarse por supuestos justificados con información financiera de ISA y su fuente/fecha.

FCFF = NOPAT + D&A − CAPEX − ΔNWC. EV = valor presente de FCFF explícito + valor presente del valor terminal. VPN = EV − inversión inicial declarada. La TIR se calcula sobre inversión inicial negativa y los FCFF anuales; puede ser N/D cuando no existe una raíz válida. No se debe interpretar como TIR de la acción.

## Dos políticas

- **Optimización de CAPEX:** reduce el CAPEX/ventas por el ahorro parametrizado, respetando un piso de CAPEX mínimo. Regla: adoptar solo si ΔVPN > 0 y no se comprometen mantenimiento, seguridad ni proyectos obligatorios.
- **Eficiencia operativa:** aumenta el margen EBIT en el supuesto indicado y descuenta un costo de implementación en el FCFF del primer año. Regla: adoptar solo si ΔVPN > 0 y el beneficio supera el costo total de ejecución.

El módulo devuelve FCFF, VPN, EV, TIR (cuando se puede calcular) y un indicador descriptivo de dispersión de FCFF por año. Este último **no** es VaR, CVaR ni riesgo probabilístico; debe leerse como diagnóstico simple. Los supuestos no son evidencia de que una política realmente vaya a producir esos efectos.

## Reproducibilidad

Ejecutar desde la raíz del repositorio:

```bash
python -m unittest test_financial_scenarios.py
```

Ejemplo:

```python
from financial_scenarios import construir_escenarios, simular_politicas

base = {
    "ingresos": 1000, "crecimiento_ingresos": 0.05, "margen_ebit": 0.20,
    "tasa_impuesto": 0.35, "da_pct_ventas": 0.04, "capex_pct_ventas": 0.06,
    "nwc_pct_ventas": 0.10, "wacc": 0.12, "g_terminal": 0.03,
    "inversion_inicial": 500,
}
escenarios = construir_escenarios(base, horizonte=5)
politicas = simular_politicas(base, horizonte=5)
```

## Prompt maestro sugerido

> Actúa como analista financiero corporativo. Usa únicamente los estados financieros y fuentes entregados; identifica moneda, unidad, periodo y fecha de cada dato. No inventes cifras. Proyecta ingresos, margen EBIT, impuestos, D&A, CAPEX y NWC para 3–5 años; explica las relaciones causales. Construye escenarios pesimista, base y optimista con al menos cinco drivers; calcula FCFF, EV, VPN y TIR con supuestos transparentes. Simula una política de optimización de CAPEX y otra de eficiencia operativa, incluyendo regla de activación, costo de implementación, restricciones operativas y efectos sobre FCFF, VPN, TIR y un indicador de riesgo. Distingue datos observados de supuestos. Recomienda adoptar, condicionar o rechazar cada política solo con base en resultados y limitaciones. Si falta un dato, solicita el dato o declara la limitación; nunca fuerces un resultado positivo.

## Registro de interacciones para el anexo

Registrar 3–5 interacciones reales ejecutadas, con fecha, prompt íntegro, archivo/datos usados, salida relevante, comprobación manual y cambio realizado. Las siguientes son plantillas y no deben presentarse como interacciones ya ejecutadas:
1. Validación de unidad/moneda y consistencia de EEFF.
2. Justificación de los cinco drivers y sus rangos.
3. Comparación de escenarios y sensibilidad de VPN.
4. Evaluación de política de CAPEX y restricciones de mantenimiento.
5. Evaluación de eficiencia operativa y costo de implementación.

## Limitaciones que deben declararse

- Los shocks iniciales son demostrativos, no están calibrados con datos históricos de ISA.
- El WACC y g terminal requieren fuente, fecha, moneda y consistencia nominal.
- La TIR requiere interpretación cautelosa y puede no existir o no ser única en flujos no convencionales.
- El indicador de dispersión no sustituye simulación Monte Carlo, VaR/CVaR ni pruebas de estrés.
- Antes de entregar el taller, conectar los datos reales de la pestaña Pronóstico y verificar manualmente cada supuesto y resultado.
