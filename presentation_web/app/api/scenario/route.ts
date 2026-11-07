import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const runtime = "nodejs";

async function readOfficialMetrics() {
  const url = process.env.SUPABASE_URL?.replace(/\/$/, "");
  const anonKey = process.env.SUPABASE_ANON_KEY;
  const token = process.env.ISA_PRESENTATION_TOKEN;
  if (!url || !anonKey || !token) {
    throw new Error("La conexión oficial de Supabase no está configurada en el servidor.");
  }
  const response = await fetch(`${url}/rest/v1/rpc/get_isa_latest_snapshot`, {
    method: "POST",
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${anonKey}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ p_token: token }),
    cache: "no-store"
  });
  if (response.status === 401 || response.status === 403) {
    throw new Error("El token de lectura de Supabase no fue autorizado.");
  }
  if (!response.ok) throw new Error(`Supabase respondió HTTP ${response.status}.`);
  const result: unknown = await response.json();
  const snapshot = Array.isArray(result) ? result[0] : result;
  if (!snapshot || typeof snapshot !== "object" || !("payload" in snapshot)) {
    throw new Error("Todavía no existe una valoración ISA publicada.");
  }
  const payload = (snapshot as { payload?: { metrics?: unknown } }).payload;
  if (!payload?.metrics || typeof payload.metrics !== "object") {
    throw new Error("La publicación no contiene métricas financieras.");
  }
  return payload.metrics;
}

export async function POST(request: NextRequest) {
  const apiUrl = process.env.SCENARIO_API_URL?.replace(/\/$/, "");
  const apiToken = process.env.SCENARIO_API_TOKEN;
  if (!apiUrl || !apiToken) {
    return NextResponse.json(
      { error: "El servicio privado de escenarios todavía no está configurado en Vercel." },
      { status: 503, headers: { "Cache-Control": "no-store" } }
    );
  }

  try {
    const body = await request.json() as { wacc?: unknown; growth?: unknown; margin?: unknown };
    const wacc = Number(body.wacc);
    const growth = Number(body.growth);
    const margin = Number(body.margin);
    if (![wacc, growth, margin].every(Number.isFinite)) {
      return NextResponse.json({ error: "WACC, crecimiento y margen deben ser valores numéricos." }, { status: 400 });
    }
    if (wacc <= 0 || wacc > 50 || growth < -5 || growth > 15 || margin < 20 || margin > 85) {
      return NextResponse.json({ error: "Los parámetros están fuera de los rangos admitidos." }, { status: 400 });
    }
    const metrics = await readOfficialMetrics();
    const response = await fetch(`${apiUrl}/v1/scenario`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiToken}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        metrics,
        parameters: {
          wacc: wacc / 100,
          g: growth / 100,
          ebitda_margin: margin / 100
        }
      }),
      cache: "no-store"
    });
    const result = await response.json();
    if (!response.ok) {
      const message = typeof result?.detail === "string" ? result.detail : "El motor de escenarios no pudo completar el cálculo.";
      return NextResponse.json({ error: message }, { status: response.status, headers: { "Cache-Control": "no-store" } });
    }
    return NextResponse.json(result, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Error inesperado al ejecutar el escenario.";
    return NextResponse.json({ error: message }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
