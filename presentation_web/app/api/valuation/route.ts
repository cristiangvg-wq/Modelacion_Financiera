import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET() {
  const url = process.env.SUPABASE_URL?.replace(/\/$/, "");
  const anonKey = process.env.SUPABASE_ANON_KEY;
  const token = process.env.ISA_PRESENTATION_TOKEN;

  if (!url || !anonKey || !token) {
    return NextResponse.json(
      { error: "La conexión con Supabase no está configurada en el servidor." },
      { status: 503, headers: { "Cache-Control": "no-store" } }
    );
  }

  try {
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
      return NextResponse.json({ error: "El token de lectura no fue autorizado." }, { status: 403 });
    }
    if (!response.ok) {
      return NextResponse.json(
        { error: `Supabase respondió HTTP ${response.status}.` },
        { status: 502, headers: { "Cache-Control": "no-store" } }
      );
    }

    const result: unknown = await response.json();
    const snapshot = Array.isArray(result) ? result[0] : result;
    if (!snapshot || typeof snapshot !== "object") {
      return NextResponse.json({ error: "Todavía no existe una valoración ISA publicada." }, { status: 404 });
    }

    return NextResponse.json(snapshot, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json(
      { error: "No fue posible conectar con Supabase. Intenta actualizar más tarde." },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
