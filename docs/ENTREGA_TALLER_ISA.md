# Entrega del Taller Evaluativo 2026 — ISA

Archivos:
- `scripts/taller_isa.py`: proyección 2026–2030, tres escenarios, dos políticas y exportación CSV/JSON.
- `tests/test_taller_isa.py`: pruebas unitarias de drivers, fórmula FCFF, políticas y exportación.
- `docs/taller_evaluativo_isa_2026.md`: método, supuestos, resultados que deben interpretarse con cautela y decisión condicionada.
- `docs/ingenieria_prompts_taller_isa.md`: prompt maestro y cuatro interacciones resumidas.
- Salidas generadas localmente: `salidas_taller_isa/` (se crean al ejecutar el script).

## Ejecutar
```bash
python scripts/taller_isa.py
python -m unittest discover -s tests -p 'test_taller_isa.py' -v
```

**Advertencia importante:** las políticas y shocks son hipótesis académicas. El WACC del script es ilustrativo y los resultados no son un precio objetivo. Antes de una recomendación definitiva deben verificarse el CAPEX, NWC, WACC y puente EV–patrimonio con datos vigentes y el motor principal de la aplicación.
