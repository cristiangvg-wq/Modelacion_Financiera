# Configurar la presentación independiente de ISA

## Arquitectura

- La aplicación principal calcula la valoración en la pestaña 4 y publica una instantánea de esa misma corrida.
- Supabase conserva un único registro vigente para el ticker ISA.
- La presentación independiente consulta ese registro mediante una función RPC protegida por token.
- La presentación no ejecuta el motor DCF, no altera supuestos y no sustituye cifras si la consulta falla.
- La clave service_role se configura únicamente en la aplicación principal. La presentación usa la clave anon/publicable y el token de lectura.

## 1. Crear el proyecto Supabase

1. Crea una cuenta en https://supabase.com/ y crea un proyecto nuevo.
2. Guarda la contraseña de base de datos en un gestor seguro.
3. En el panel del proyecto, abre SQL Editor.
4. Copia y ejecuta el contenido completo de supabase/isa_presentation.sql.

## 2. Generar el token de lectura

Genera un token largo y aleatorio en tu equipo. En Windows PowerShell:

~~~powershell
$bytes = New-Object byte[] 32
$rng = [Security.Cryptography.RNGCryptoServiceProvider]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
$shaProvider = [Security.Cryptography.SHA256]::Create()
$hashBytes = $shaProvider.ComputeHash([Text.Encoding]::UTF8.GetBytes($token))
$shaProvider.Dispose()
$sha = ([BitConverter]::ToString($hashBytes)).Replace('-','').ToLower()
$token
$sha
~~~

Copia el SHA-256 (no el token) y sustituye REEMPLAZAR_POR_SHA256_HEX en el SQL antes de ejecutarlo. Conserva el token original: se necesitará en los secrets de la presentación. No lo publiques en GitHub ni lo compartas por chat.

## 3. Obtener las claves del proyecto

En Supabase, abre Project Settings > API. Copia:
- Project URL.
- anon/public key (para la presentación).
- service_role key (solo para la aplicación principal; nunca la pongas en la presentación ni en GitHub).

## 4. Configurar la aplicación principal

En Streamlit Community Cloud, abre la app principal > Settings > Secrets y agrega:

~~~toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "TU_SERVICE_ROLE_KEY"
~~~

Guarda y reinicia/redeploy la aplicación. La publicación ocurre cuando se ejecuta correctamente la pestaña 4 para ISA. Una valoración de otra empresa no se publica.

## 5. Configurar la aplicación independiente

En la app desplegada con main file path presentacion_isa.py, abre Settings > Secrets y agrega:

~~~toml
SUPABASE_URL = "https://TU-PROYECTO.supabase.co"
SUPABASE_ANON_KEY = "TU_ANON_PUBLIC_KEY"
ISA_PRESENTATION_TOKEN = "EL_TOKEN_ALEATORIO_ORIGINAL"
~~~

Guarda y reinicia/redeploy. La presentación mostrará la última valoración publicada. Si no existe un registro, mostrará un aviso; no usará datos de ejemplo como sustituto.

## 6. Validación

1. Ejecuta la pestaña 4 de ISA en la aplicación principal.
2. Comprueba que no aparezca un aviso de publicación fallida.
3. Abre la app independiente y pulsa Actualizar valoración.
4. Compara valor por acción, precio de mercado, upside, WACC, g, EV y Equity Value con la pestaña 4.
5. Si cambias el token, calcula su nuevo SHA-256 y actualiza la fila de acceso en Supabase.

## Seguridad y límites

- Nunca guardes claves o tokens en el repositorio.
- Nunca uses la service_role key en la presentación independiente.
- La tabla no permite SELECT a anon/authenticated; la lectura se realiza solo mediante RPC con token.
- El snapshot contiene métricas y supuestos de la valoración ISA. No publiques la URL de la presentación si no deseas compartir esos datos con quienes tengan el token.
- Si Supabase no está configurado o no responde, la valoración principal continúa funcionando; la publicación es una función secundaria.
