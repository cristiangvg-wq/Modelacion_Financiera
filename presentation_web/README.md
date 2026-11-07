# ISA Investment Experience

Aplicación web independiente de storytelling financiero para ISA. Esta primera entrega crea la experiencia Next.js de siete actos y consume el snapshot oficial existente de Supabase. No reemplaza ni modifica el motor de valoración Python ni la aplicación Streamlit.

## Requisitos
- Node.js 20.9 o superior.
- Proyecto Supabase configurado según `../docs/CONFIGURAR_PRESENTACION_ISA_SUPABASE.md`.
- Una valoración ISA publicada desde la pestaña 4 de la aplicación principal.

## Desarrollo local

Desde esta carpeta:

```bash
cp .env.example .env.local
npm install
npm run dev
```

Completa en `.env.local` las variables de servidor:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `ISA_PRESENTATION_TOKEN`
- `SCENARIO_API_URL`
- `SCENARIO_API_TOKEN`

Abre http://localhost:3000.

**Seguridad:** no uses el prefijo `NEXT_PUBLIC_` para estas variables. Las credenciales de Supabase y el token compartido con Render se usan exclusivamente en rutas de servidor; nunca se envían al navegador.

## Despliegue en Vercel
1. Importa el repositorio GitHub.
2. Configura Root Directory como `presentation_web`.
3. En Render, crea un servicio desde el Blueprint `render.yaml` en la raíz del repositorio. Render instalará las dependencias del motor Python y levantará `scenario_api.main:app`.
4. En Render, define `SCENARIO_API_TOKEN` como secreto aleatorio. Copia el mismo valor en Vercel, junto con `SCENARIO_API_URL` (URL pública del servicio Render).
5. En Vercel, define también `SUPABASE_URL`, `SUPABASE_ANON_KEY` e `ISA_PRESENTATION_TOKEN`.
6. Configura Root Directory de Vercel como `presentation_web`.
7. Despliega la rama de trabajo para revisión. Después de aprobar el PR, despliega desde `main` y verifica las variables en ambos servicios.

## Arquitectura de datos
- Fuente oficial: `public.isa_valuation_snapshots`.
- Lectura: RPC `get_isa_latest_snapshot(p_token)`.
- La API de Next.js hace la llamada desde servidor y desactiva caché.
- El frontend solo recibe la instantánea devuelta por la RPC.
- No se escribe en Supabase desde la presentación.

## Alcance de esta primera entrega
- Siete actos narrativos con navegación por anclas.
- Diseño responsive Institutional Cyber-Luxe.
- Indicadores alimentados por el snapshot real.
- Gráfico FCFF cuando la serie existe en el payload.
- Metadatos de publicación y versión del motor.
- Simulación DCF autenticada en Render mediante el motor Python oficial.
- Comparación Bear / Base / Bull, matriz WACC × g y tornado de sensibilidad.
- Drivers de proyección publicados por el motor para permitir cambios de margen sin duplicar fórmulas en JavaScript.
- Estados explícitos de error, ausencia de publicación y carga.
- Accesibilidad básica, semántica y movimiento reducido.

## Servicio de escenarios
- Render expone `POST /v1/scenario`, protegido con `SCENARIO_API_TOKEN`; `GET /health` es un health check sin datos financieros.
- Vercel expone `POST /api/scenario`. Esta ruta vuelve a leer el snapshot oficial desde la RPC de Supabase en el servidor y reenvía los drivers a Render con el token privado.
- Render llama a `modelacion_logic.valoracion_dcf()` y `modelacion_logic.recalcular_fcff()`; no contiene una implementación alternativa del DCF.
- La publicación debe incluir `proyeccion_sensibilidad`. Tras desplegar esta rama y publicar el cambio del motor Python, vuelve a ejecutar la pestaña 4 para generar un snapshot compatible con escenarios.
- Los escenarios no se persisten ni actualizan la publicación oficial. El precio de mercado solo se usa para upside si la moneda está alineada.
- Configura el mismo secreto aleatorio en Render (`SCENARIO_API_TOKEN`) y Vercel (`SCENARIO_API_TOKEN`). `SCENARIO_API_URL` debe apuntar al servicio Render.
- El Blueprint usa el plan Free para evitar crear cargos sin autorización. Ese plan puede suspender el servicio por inactividad y provocar arranques en frío; para uso institucional continuo, cambia Render a Starter y confirma el presupuesto antes de activar producción.

## Verificación
```bash
npm install
npm run build
```
