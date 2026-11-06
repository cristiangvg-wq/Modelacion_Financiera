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

Completa en `.env.local` las tres variables de servidor:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `ISA_PRESENTATION_TOKEN`

Abre http://localhost:3000.

**Seguridad:** no uses el prefijo `NEXT_PUBLIC_` para estas variables. El token de lectura y la clave anon se utilizan exclusivamente en la ruta de servidor `/api/valuation`; nunca se envían al navegador.

## Despliegue en Vercel
1. Importa el repositorio GitHub.
2. Configura Root Directory como `presentation_web`.
3. Define las tres variables anteriores en Project Settings → Environment Variables.
4. Despliega la rama de trabajo para revisión.
5. Después de aprobar el PR, despliega desde `main`.

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
- Controles locales ilustrativos para WACC, g y margen EBITDA.
- Estados explícitos de error, ausencia de publicación y carga.
- Accesibilidad básica, semántica y movimiento reducido.

## Limitación deliberada
Los sliders todavía no ejecutan una nueva valoración. El repositorio debe exponer primero un servicio de escenarios que reutilice las funciones del motor Python, valide parámetros y devuelva resultados tipados. No se muestran EV, Equity Value ni precio por acción simulados hasta conectar y probar ese servicio. Esto evita crear un segundo DCF en JavaScript o presentar cifras ficticias.

## Verificación
```bash
npm install
npm run build
```
