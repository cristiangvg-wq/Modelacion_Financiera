# Arquitectura multiagente — Modelación Financiera

**Estado:** diseño técnico inicial, sin cambios en el motor financiero ni en la aplicación productiva.  
**Fecha de inspección:** 5 de noviembre de 2026.  
**Rama de trabajo:** `feat/arquitectura-multiagente-v1`.

## 1. Objetivo y criterio rector

Incorporar agentes especializados para auditar, explicar y asistir en la evolución del producto sin duplicar ni sustituir los cálculos deterministas existentes.

**Regla fundamental:** Python calcula; los agentes inspeccionan, contrastan, explican y proponen. Ningún agente puede cambiar supuestos financieros, escribir en `main`, fusionar Pull Requests ni desplegar por su cuenta.

## 2. Diagnóstico del repositorio inspeccionado

La inspección se hizo sobre la rama `main`, sin ejecutar código ni afirmar que la suite se haya corrido en este entorno.

| Área | Estado observado | Implicación para la arquitectura |
|---|---|---|
| Interfaz | `streamlit_app.py` (~315 KB, 6.568 líneas) concentra el shell, sidebar, parámetros y diez pestañas. | Añadir la integración como módulo/página aislada; no seguir ampliando el monolito. |
| Motor financiero | `modelacion_logic.py` (~695 KB en el listado de GitHub) contiene la lógica central y estado por sesión. | Exponer adaptadores de solo lectura y reutilizar funciones existentes. No mover ni reescribir fórmulas en la primera fase. |
| Comité IA | `comite_ia.py` (~70,5 KB, 1.239 líneas) ya implementa recopilación de hechos, razonamiento en dos pasos, validación del dictamen, caché e historial. | Reutilizarlo como subsistema de análisis existente; no crear un segundo comité que duplique su función. |
| Escenarios | `financial_scenarios.py` implementa proyección FCFF, escenarios y políticas. | Agente financiero consume resultados y reglas existentes. |
| Múltiplos | `multiples_valuation.py` contiene valoración por múltiplos. | Herramienta determinista del agente financiero. |
| Portafolios | `portfolio_engine.py` contiene rendimientos, covarianza, optimización, riesgo y validación fuera de muestra. | Agente financiero puede auditar salidas sin recalcularlas con LLM. |
| Datos | `datos_curados.json`, `datos_damodaran.json`, `datos_mercado.json` y proveedores existentes. | Agente de datos revisa procedencia, vigencia, moneda, unidades y faltantes. |
| Pruebas | Hay pruebas en raíz y en `tests/`, incluidas validaciones financieras, comité IA, mercado, portafolio y regresiones. | Ampliar las pruebas offline y deterministas antes de habilitar acciones. |
| CI | Existen workflows en `.github/workflows/`, incluido `quality-checks.yml`. | Integrar nuevas pruebas en CI; separar verificaciones que requieren red/API. |
| Dependencias | `requirements.txt` no declara LangGraph ni un SDK de orquestación multiagente. | No introducir dependencias hasta implementar y probar el primer flujo. |

### Hallazgos de diseño

1. La lógica y la UI son módulos grandes y altamente concentrados. La nueva arquitectura debe vivir en paquetes pequeños, sin refactor masivo inicial.
2. Ya existe un flujo IA útil en `comite_ia.py`: hechos de mercado con fuentes, dictamen estructurado, validación determinista y caché. Debe integrarse como capacidad existente, no duplicarse.
3. El estado de la lógica está vinculado a la sesión Streamlit mediante `vincular_estado_sesion`. Los agentes deben recibir un contexto serializable y explícito; no deben leer ni modificar globales de la app directamente.
4. Los resultados de mercado y los supuestos pueden variar por sesión. Cada ejecución de agente debe guardar un snapshot del contexto y sus identificadores de fuente/fecha.
5. El README actual ya contiene instalación, configuración de Gemini, comandos de pruebas y scripts. La auditoría histórica `AUDITORIA_COMITE_DIRECTOR_2026-10-28.md` contiene observaciones fechadas que deben tratarse como históricas y no como estado actual cuando contradigan el repositorio.

### Limitaciones de esta auditoría

- Inspección estática de archivos y estructura en GitHub; no se ejecutó pytest, Streamlit, scripts de mercado ni llamadas reales a proveedores.
- No se verificó el estado visual de la aplicación desplegada.
- No se verificaron secretos, permisos de producción ni configuración efectiva de Streamlit Cloud.
- Las cifras de tamaño son las reportadas por GitHub en la inspección; no equivalen a complejidad funcional medida.

## 3. Arquitectura lógica propuesta

```text
Streamlit — Centro de Agentes IA
          |
          v
Agent Service / API interna
          |
          v
Coordinator (flujo controlado)
  |          |           |            |
  v          v           v            v
Financial   Data       Code         QA / Audit
Agent       Agent      Agent        Agent
  |          |           |            |
  +----------+-----------+------------+
                     |
                     v
       Tool adapters (solo lectura al inicio)
       - modelacion_logic
       - comite_ia
       - financial_scenarios
       - multiples_valuation
       - portfolio_engine
       - tests / CI metadata
                     |
                     v
        Informe de hallazgos + evidencia
                     |
                     v
       Aprobación humana / Pull Request
```

### Componentes

- **UI Streamlit:** presenta tareas, progreso, resultados, fuentes, severidad y acciones disponibles.
- **Agent service:** valida entradas, crea un identificador de ejecución, captura el contexto y entrega resultados normalizados.
- **Coordinador:** decide qué agentes invocar según el tipo de tarea, valida que cada agente devuelva su contrato y consolida hallazgos. No calcula métricas.
- **Agentes especializados:** generan observaciones acotadas a su dominio y deben citar la evidencia recibida.
- **Adaptadores de herramientas:** encapsulan funciones existentes en interfaces pequeñas y tipadas. Por defecto no exponen escritura.
- **Registro de auditoría:** conserva tarea, versión de prompt, modelo/proveedor, timestamp, snapshot hash, herramientas invocadas, resultados, errores y aprobación.
- **Puerta de cambios:** cualquier propuesta de código se convierte en un plan/diff revisable; la aplicación de cambios y el merge quedan fuera del flujo autónomo.

## 4. Responsabilidad de cada agente

### 4.1 Coordinador

- Clasifica la solicitud: auditoría financiera, calidad de datos, diagnóstico de software o revisión UX.
- Construye un plan de trabajo con los agentes estrictamente necesarios.
- Pasa el mismo snapshot de contexto a todos los agentes pertinentes.
- Consolida hallazgos duplicados y resuelve discrepancias solicitando evidencia, no votando por mayoría.
- Bloquea el dictamen cuando falta evidencia crítica o falla un control determinista.

### 4.2 Agente financiero

- Revisa consistencia conceptual y aritmética de DCF/FCFF, WACC/CAPM, puente EV–equity, valor terminal, múltiplos, escenarios y portafolios.
- Contrasta resultados del motor con identidades y reglas deterministas existentes.
- Señala supuestos frágiles y sensibilidades materiales.
- No cambia beta, rf, ERP, CRP, g, márgenes, deuda, impuestos, múltiplos ni horizonte.
- No presenta una recomendación de inversión como certeza ni convierte datos faltantes en cero.

### 4.3 Agente de datos

- Revisa fuente, fecha efectiva, fecha de descarga, ticker, moneda, unidad, frecuencia, periodo y transformación.
- Distingue observado, curado, estimado, proxy y ausente.
- Detecta datos stale, monedas incompatibles, unidades mezcladas, series discontinuas y campos faltantes.
- No rellena datos sin una política aprobada ni inventa fuentes.

### 4.4 Agente desarrollador

- Analiza excepciones, dependencias, modularidad, rendimiento, estado de sesión y regresiones.
- Propone cambios pequeños con archivo, función, motivo y prueba de aceptación.
- En la primera versión no escribe archivos ni ejecuta comandos destructivos.
- En fases posteriores podrá preparar una rama/diff aislado con permisos limitados, nunca modificar `main`.

### 4.5 Agente auditor / QA

- Diseña y ejecuta pruebas offline deterministas.
- Comprueba invariantes financieras y regresiones relevantes.
- Rechaza evidencia basada únicamente en afirmaciones del agente desarrollador.
- Distingue pruebas unitarias, integración, smoke tests y pruebas online.
- No declara éxito si una prueba no fue ejecutada o su resultado no está disponible.

### 4.6 Agente UX/UI y documentación

- Revisa legibilidad, jerarquía, consistencia de métricas, unidades, moneda, estados vacíos y errores.
- Propone mejoras accesibles y compatibles con móvil/escritorio.
- Genera documentación y guías a partir de comportamiento verificado, no de supuestos.

## 5. Contrato común de entrada y salida

Todo agente recibe un objeto de contexto inmutable y serializable:

```python
AgentContext(
    run_id: str,
    task: str,
    company: str | None,
    ticker: str | None,
    snapshot_at: str,
    snapshot_hash: str,
    currency: str | None,
    model_inputs: dict,
    model_outputs: dict,
    data_provenance: list[dict],
    quality_flags: list[dict],
    repository_ref: str,
)
```

Cada agente devuelve:

```python
AgentFinding(
    agent: str,
    status: str,          # ok | warning | blocked | error
    summary: str,
    findings: list[dict],
    evidence: list[dict],
    recommendations: list[dict],
    limitations: list[str],
)
```

Cada hallazgo debe incluir como mínimo:
- `id`, `severity` (critical/high/medium/low/info), `title`, `description`.
- `evidence_ref`: función, archivo, línea, dato o prueba que respalda la observación.
- `impact`: consecuencia financiera/técnica/operativa.
- `suggested_action`: propuesta, no ejecución automática.
- `confidence`: grado de confianza y limitaciones.

No se acepta un hallazgo financiero sin referencia al dato, fórmula, regla o prueba que lo respalda.

## 6. Flujo de ejecución

1. El usuario elige una tarea y empresa.
2. El servicio captura los resultados actuales de la sesión y calcula un hash del snapshot.
3. El coordinador clasifica la tarea y define agentes requeridos.
4. Los agentes trabajan en paralelo solo cuando sus entradas son independientes.
5. Cada salida pasa validación de esquema y reglas deterministas.
6. El coordinador consolida hallazgos, evidencia, conflictos y limitaciones.
7. Se genera informe con estado: `APROBADO PARA REVISIÓN`, `ADVERTENCIAS` o `BLOQUEADO`.
8. El usuario decide si solicita una propuesta de código.
9. Los cambios de código se desarrollan en rama separada, pasan CI y se presentan en Pull Request.
10. Solo una persona autorizada aprueba el merge y el despliegue.

## 7. Stack técnico y decisión de framework

**Recomendación inicial: LangGraph**, condicionado a validar compatibilidad con Python 3.11 y el proveedor LLM ya utilizado.

- Mantener Streamlit como interfaz.
- Mantener las funciones financieras actuales como fuente de verdad.
- Reutilizar la integración actual de Gemini en `comite_ia.py` donde sea pertinente.
- Encapsular proveedores de LLM detrás de una interfaz común; no acoplar la lógica financiera a un proveedor.
- Evaluar LangGraph en una prueba de concepto aislada antes de añadirlo a `requirements.txt`.
- No instalar simultáneamente LangGraph, CrewAI y otros frameworks.
- No introducir una base de datos nueva en la primera fase: empezar con historial por sesión y exportación de informe; evaluar persistencia solo cuando exista requisito de historial multiusuario.

## 8. Estructura objetivo (incremental)

No crear toda esta estructura de golpe. Añadir módulos a medida que cada fase se pruebe:

```text
agents/
  contracts.py
  coordinator.py
  financial_agent.py
  data_agent.py
  developer_agent.py
  audit_agent.py
  ux_agent.py
agent_tools/
  financial_tools.py
  data_tools.py
  repository_tools.py
  test_tools.py
workflows/
  audit_workflow.py
  valuation_review.py
services/
  agent_service.py
  run_store.py
pages/
  12_Centro_Agentes.py
tests/agents/
  test_contracts.py
  test_coordinator.py
  test_financial_agent.py
  test_data_agent.py
  test_permissions.py
docs/
  ARQUITECTURA_MULTIAGENTE.md
```

## 9. Mapa de integración con el código actual

| Archivo actual | Integración propuesta | Restricción |
|---|---|---|
| `streamlit_app.py` | Punto de entrada y navegación; delegar el nuevo centro a un módulo independiente. | Evitar insertar prompts, lógica de agentes y herramientas dentro del archivo monolítico. |
| `modelacion_logic.py` | Adaptadores de lectura para métricas, contexto de mercado, validaciones y resultados de sesión. | No editar fórmulas ni mutar estado desde agentes. |
| `comite_ia.py` | Reutilizar generación/validación de dictamen y hechos con fuentes. | No duplicar el flujo de hechos y dictamen. |
| `financial_scenarios.py` | Proveer resultados de proyección y escenarios. | Sin cálculo LLM. |
| `multiples_valuation.py` | Proveer valoración por comparables/múltiplos. | Respetar datos ausentes y trazabilidad. |
| `portfolio_engine.py` | Proveer métricas y validaciones de portafolio. | El agente no optimiza por su cuenta ni altera pesos. |
| `datos_*.json` | Fuentes curadas y metadatos para auditoría. | Nunca sobrescribir datos fuente desde un agente. |
| `tests/` y `test_*.py` | Pruebas de contratos, permisos, invariantes y regresiones. | Separar offline de online. |
| `.github/workflows/quality-checks.yml` | Ejecutar pruebas nuevas offline en CI. | No exigir API keys ni red para el conjunto base. |
| `requirements.txt` | Añadir dependencias solo después de prueba de concepto. | Versiones acotadas y despliegue Streamlit validado. |

## 10. Fases de implementación y criterios de aceptación

### Fase 0 — Línea base y contratos
- Registrar la versión de Python/dependencias y resultado de la suite actual.
- Crear contratos tipados y pruebas sin LLM.
- Definir snapshot inmutable y registro de auditoría.
- **Aceptación:** contratos probados; la aplicación principal no cambia su comportamiento.

### Fase 1 — Primer flujo: coordinador + agente financiero
- Implementar auditoría financiera de solo lectura.
- Reutilizar cálculos existentes y reglas deterministas.
- Presentar hallazgos con evidencia, severidad y limitaciones.
- **Aceptación:** casos de prueba conocidos producen hallazgos esperados; ninguna variable del modelo se modifica.

### Fase 2 — Agente de datos
- Incorporar procedencia, frescura, monedas, unidades y clasificación del dato.
- **Aceptación:** detecta escenarios sintéticos de dato vencido, moneda/unidad incompatible y faltante.

### Fase 3 — QA y auditor independiente
- Ejecutar pruebas unitarias e invariantes; comparar resultados.
- **Aceptación:** un fallo crítico bloquea el informe final y queda registrado.

### Fase 4 — Desarrollador con permisos limitados
- Generar propuestas de diff en rama de trabajo.
- **Aceptación:** no hay escritura en main; PR incluye pruebas y resumen del impacto.

### Fase 5 — UX/UI y documentación
- Incorporar revisión visual, accesibilidad y documentación.
- **Aceptación:** checklist de UI y documentación contrastada con funciones reales.

## 11. Seguridad, privacidad y gobernanza

- Secretos solo en Streamlit Secrets o variables de entorno; nunca en prompts, logs, commits ni informes.
- No enviar archivos financieros privados a un proveedor externo sin autorización explícita y minimización de datos.
- Permisos por herramienta: lectura por defecto; escritura solo en rama aislada y tras autorización.
- Prohibido ejecutar shell arbitrario, SQL libre, comandos destructivos o despliegues desde agentes.
- Límite de coste, tokens, reintentos, tiempo y número de herramientas por ejecución.
- Registrar proveedor/modelo, versión de prompt, snapshot hash y resultado de cada herramienta.
- Las salidas del LLM son datos no confiables: validar esquema, escapar HTML y no ejecutar instrucciones devueltas por el modelo.
- La IA no sustituye el criterio profesional ni emite asesoría financiera personalizada.

## 12. Próximo paso técnico recomendado

Implementar **Fase 0 y Fase 1** en esta rama, empezando por contratos, adaptadores de solo lectura y pruebas offline. Antes de conectar el Centro de Agentes a la navegación de Streamlit, ejecutar y guardar la línea base de `pytest` y `compileall`. No modificar los supuestos, fórmulas ni archivos de datos del modelo durante esta primera entrega.
