# Entrega del Taller Evaluativo 2026 — ISA

**Camino:** Evaluación empresarial.

## Entregables (según el enunciado)
1. **Informe PDF:** `docs/Informe_Taller_ISA_2026.pdf` — portada, pronóstico y método, matriz de escenarios, políticas, decisión con umbrales, sección de ingeniería de prompts y técnicas. Antes de entregar, regenerarlo con los nombres del equipo y la fecha:
   ```bash
   python scripts/generar_informe_taller_isa.py --equipo "Nombre 1; Nombre 2; Nombre 3; Nombre 4" --fecha "AAAA-MM-DD"
   ```
2. **Código:** `scripts/taller_isa.py` (proyección, escenarios, políticas, sensibilidad, Monte Carlo, decisión), `tests/test_taller_isa.py` (18 pruebas) y `datos_taller_isa_2026.json` (datos con fuentes).
3. **Anexo de prompts:** `docs/ingenieria_prompts_taller_isa.md` (también incluido como Anexo A del PDF).
4. **Bonificación:** Monte Carlo en el script y dashboard `scripts/dashboard_taller_isa.py`.

## Ejecutar
```bash
python scripts/taller_isa.py
python -m pytest -q tests/test_taller_isa.py
streamlit run scripts/dashboard_taller_isa.py
```
Salidas en `salidas_taller_isa/` (no se versionan; se regeneran).

## Pendiente del equipo antes de entregar
- Poner nombres y fecha en la portada (comando de arriba).
- Si el equipo usa otra IA, añadir sus interacciones al anexo con el mismo formato (prompt → salida clave → uso en el modelo) y regenerar el PDF.
- Revisar y, si lo decide, ajustar los supuestos hipotéticos (`SCENARIOS`, `POLICIES`, `DECISION_THRESHOLDS`); el informe se actualiza solo al regenerarlo.

Ver método y mapa criterio → código en `docs/taller_evaluativo_isa_2026.md`.
