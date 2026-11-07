"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowDown, ArrowRight, Activity, Database, ShieldCheck, RefreshCw,
  CircleAlert, Network, Gauge, TrendingUp, Layers3, Zap
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";

type ScenarioMetric = {
  EV: number | null;
  Equity_Value: number | null;
  value_per_share: number | null;
  upside_pct: number | null;
  WACC: number | null;
  g_used: number | null;
  PV_FCFF: number | null;
  PV_TV: number | null;
  TV: number | null;
  tv_pct_ev: number | null;
  mult_terminal: number | null;
};
type ScenarioResult = {
  currency: string;
  unit: string;
  base: ScenarioMetric;
  scenarios: Record<string, { parameters: { wacc: number; g: number; ebitda_margin: number } } & ScenarioMetric>;
  sensitivity: Array<{ wacc: number; cells: Array<{ g: number; EV: number | null; Equity_Value: number | null; value_per_share: number | null; valid: boolean }> }>;
  tornado: Array<{ driver: string; delta_low: number | null; delta_high: number | null }>;
  diagnostics: { official_ev: number | null; scenario_ev_delta_vs_official: number | null; baseline_margin_from_projection: number; margin_adjustment_applied: number; official_publication_is_unchanged: boolean; calculation_is_persisted: boolean };
};

type Snapshot = {
  ticker?: string;
  company_name?: string;
  model_version?: string;
  published_at?: string;
  payload?: {
    metrics?: Record<string, unknown>;
    decision_text?: string;
    memo?: string;
  };
};

const acts = [
  ["00", "OPENING", "opening"],
  ["01", "THESIS", "thesis"],
  ["02", "VALUATION", "valuation"],
  ["03", "SIMULATION", "simulation"],
  ["04", "RISK", "risk"],
  ["05", "DATA ROOM", "data"],
  ["06", "DECISION", "decision"]
];

function numeric(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
function money(value: unknown, currency = "COP") {
  const n = numeric(value);
  return n === null ? "N/D" : new Intl.NumberFormat("es-CO", {
    style: "currency", currency: currency === "COP" ? "COP" : currency,
    maximumFractionDigits: 0
  }).format(n);
}
function percent(value: unknown) {
  const n = numeric(value);
  return n === null ? "N/D" : `${(n * 100).toFixed(2)}%`;
}
function label(value: unknown, fallback = "No disponible") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export default function Home() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [lastSync, setLastSync] = useState("");
  const [wacc, setWacc] = useState(14.34);
  const [growth, setGrowth] = useState(3.5);
  const [margin, setMargin] = useState(57.8);
  const [scenarioResult, setScenarioResult] = useState<ScenarioResult | null>(null);
  const [scenarioError, setScenarioError] = useState("");
  const [scenarioLoading, setScenarioLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/valuation", { cache: "no-store" });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "No se pudo cargar la valoración.");
      setSnapshot(body as Snapshot);
      setLastSync(new Date().toISOString());
      const metrics = body?.payload?.metrics || {};
      const officialWacc = numeric(metrics.wacc_calc);
      const officialGrowth = numeric(metrics.g_usada);
      const officialMargin = numeric(metrics.margen_ebitda_base_simulacion);
      if (officialWacc !== null) setWacc(officialWacc * 100);
      if (officialGrowth !== null) setGrowth(officialGrowth * 100);
      if (officialMargin !== null) setMargin(officialMargin * 100);
      setScenarioResult(null);
      setScenarioError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error inesperado de conexión.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const metrics = snapshot?.payload?.metrics || {};
  const currency = label(metrics.moneda, "COP");
  const fcff = Array.isArray(metrics.fcff_proy) ? metrics.fcff_proy : [];
  const cashFlows = useMemo(() => fcff.map((v, i) => ({
    year: `Año ${i + 1}`, fcff: numeric(v) ?? 0
  })), [fcff]);
  const officialPublished = snapshot?.published_at
    ? new Date(snapshot.published_at).toLocaleString("es-CO")
    : "Sin publicación";

  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  const runScenario = async () => {
    setScenarioLoading(true);
    setScenarioError("");
    setScenarioResult(null);
    try {
      const response = await fetch("/api/scenario", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ wacc, growth, margin }),
        cache: "no-store"
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "No fue posible calcular el escenario.");
      setScenarioResult(body as ScenarioResult);
    } catch (e) {
      setScenarioError(e instanceof Error ? e.message : "Error inesperado al calcular el escenario.");
    } finally {
      setScenarioLoading(false);
    }
  };


  return (
    <main>
      <header className="fixed top-0 z-50 w-full border-b border-white/[.07] bg-ink/85 backdrop-blur-xl">
        <div className="shell flex h-[68px] items-center justify-between gap-4">
          <a href="#opening" className="flex items-center gap-3" aria-label="ISA Investment Experience, inicio">
            <span className="grid h-8 w-8 place-items-center border border-mint/40 text-mint"><Activity size={17}/></span>
            <span className="text-[11px] font-semibold tracking-[.16em]">ISA <span className="text-mint">/</span> INVESTMENT EXPERIENCE</span>
          </a>
          <nav className="hidden items-center gap-5 lg:flex" aria-label="Navegación principal">
            {acts.map(([n, name, id]) => <a className="nav-link" key={id} href={`#${id}`}>{n} {name}</a>)}
          </nav>
          <button onClick={() => void load()} disabled={loading} className="flex items-center gap-2 text-[10px] text-mint disabled:opacity-50" aria-label="Actualizar valoración">
            <RefreshCw size={14} className={loading ? "animate-spin" : ""}/> <span className="hidden sm:inline">ACTUALIZAR</span>
          </button>
        </div>
      </header>

      <section id="opening" className="relative flex min-h-[94svh] items-center overflow-hidden pt-20">
        <div className="pointer-events-none absolute -right-40 top-1/4 h-[620px] w-[620px] rounded-full border border-mint/10 shadow-[0_0_0_60px_rgba(118,226,189,.025),0_0_0_130px_rgba(118,226,189,.018),0_0_120px_rgba(118,226,189,.08)]"/>
        <div className="shell relative grid items-end gap-12 pb-20 pt-16 lg:grid-cols-[1.3fr_.7fr]">
          <div>
            <div className="eyebrow mb-8 flex items-center gap-3"><span className="h-px w-9 bg-mint"/> INVESTMENT CASE · {label(snapshot?.ticker, "ISA")}</div>
            <h1 className="display-title max-w-4xl">El valor detrás<br/>de la infraestructura<span className="text-mint">.</span></h1>
            <p className="lead mt-8">Una experiencia para explorar el valor fundamental de ISA, entender los supuestos que lo sostienen y evaluar los riesgos que pueden cambiar la decisión.</p>
            <div className="mt-10 flex flex-wrap gap-3">
              <button className="cta" onClick={() => scrollTo("thesis")}>Explorar la tesis <ArrowDown size={15}/></button>
              <span className="pill self-center">DATOS DE LA VALORACIÓN CENTRAL</span>
            </div>
          </div>
          <div className="glass p-6 sm:p-8">
            <div className="eyebrow">ESTADO DE LA VALORACIÓN</div>
            {loading && !snapshot ? <p className="mt-5 text-sm muted">Conectando con la fuente oficial…</p> :
              error ? <div className="mt-5 flex gap-3 text-sm text-amber-200"><CircleAlert size={18}/><span>{error}</span></div> :
              <><div className="mt-5 text-3xl font-medium">{label(snapshot?.company_name, "ISA")}</div>
                <div className="mt-2 text-xs muted">Última publicación · {officialPublished}</div>
                <div className="mt-7 flex items-center gap-2 text-xs text-mint"><span className="h-2 w-2 rounded-full bg-mint"/> Snapshot oficial conectado</div>
              </>}
            <div className="mt-7 border-t border-white/10 pt-5 text-[10px] leading-6 muted">La experiencia presenta la valoración publicada por Modelación Financiera. Las simulaciones exploratorias no alteran el resultado oficial.</div>
          </div>
        </div>
      </section>

      {error && <div className="shell pb-10"><div className="border border-amber-300/20 bg-amber-200/5 p-4 text-sm text-amber-100">{error} Configura las variables de entorno del servidor y verifica que exista una publicación ISA.</div></div>}

      <section id="thesis" className="act">
        <div className="shell">
          <div className="eyebrow">01 / INVESTMENT THESIS</div>
          <h2 className="section-title mt-5 max-w-3xl">El mercado tiene un precio.<br/><span className="text-mint">El modelo busca el valor.</span></h2>
          <p className="lead mt-6">La tesis comienza comparando el valor fundamental estimado con el precio de mercado. Ninguna cifra se presenta sin identificar su procedencia.</p>
          <div className="mt-14 grid gap-x-10 gap-y-6 sm:grid-cols-2 lg:grid-cols-4">
            <Metric title="Valor estimado / acción" value={money(metrics.vps_modelo, currency)} note="Resultado oficial"/>
            <Metric title="Precio de mercado" value={money(metrics.precio_mercado_moneda_modelo ?? metrics.precio_mercado, currency)} note={label(metrics.fecha_precio, "Fecha no registrada")}/>
            <Metric title="Potencial vs. mercado" value={percent(metrics.upside)} note="Upside / downside del motor"/>
            <Metric title="WACC · g" value={`${percent(metrics.wacc_calc)} · ${percent(metrics.g_usada)}`} note="Costo de capital · crecimiento terminal"/>
          </div>
          <blockquote className="mt-10 max-w-4xl border-l-2 border-mint bg-mint/[.045] px-6 py-5 font-display text-xl leading-relaxed text-paper sm:text-2xl">{label(snapshot?.payload?.decision_text, "La corrida publicada no incluye una conclusión textual. Consulta los supuestos y riesgos antes de emitir una decisión.")}</blockquote>
        </div>
      </section>

      <section id="valuation" className="act">
        <div className="shell">
          <div className="eyebrow">02 / THE VALUATION ENGINE</div>
          <h2 className="section-title mt-5 max-w-3xl">El valor se construye.<br/><span className="text-mint">No se adivina.</span></h2>
          <p className="lead mt-6">El DCF convierte los flujos de caja libre proyectados y el valor terminal en una estimación del valor presente de las operaciones y del patrimonio.</p>
          <div className="mt-12 grid gap-8 lg:grid-cols-[.7fr_1.3fr]">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-1">
              <Metric title="Enterprise Value" value={money(metrics.val_ev, currency)} note="Valor de las operaciones"/>
              <Metric title="Equity Value" value={money(metrics.val_equity, currency)} note="Valor atribuible al patrimonio"/>
              <Metric title="Valor por acción" value={money(metrics.vps_modelo, currency)} note="Resultado de la corrida"/>
            </div>
            <div className="glass min-h-[340px] p-4 sm:p-6">
              <div className="mb-5 flex items-center justify-between"><span className="eyebrow">FREE CASH FLOW</span><span className="text-[10px] muted">Serie publicada · {currency}</span></div>
              {cashFlows.length ? <div className="h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={cashFlows} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs><linearGradient id="fcffFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#76e2bd" stopOpacity={.35}/><stop offset="95%" stopColor="#76e2bd" stopOpacity={0}/></linearGradient></defs>
                    <CartesianGrid strokeDasharray="3 5" className="chart-grid" vertical={false}/>
                    <XAxis dataKey="year" tick={{ fill: "#91a59f", fontSize: 11 }} axisLine={false} tickLine={false}/>
                    <YAxis tick={{ fill: "#91a59f", fontSize: 10 }} axisLine={false} tickLine={false} width={58}/>
                    <Tooltip contentStyle={{ background: "#0c1d26", border: "1px solid #31534c", borderRadius: 4, color: "#edf2ec" }} formatter={(v) => [Number(v).toLocaleString("es-CO"), "FCFF"]}/>
                    <Area type="monotone" dataKey="fcff" stroke="#76e2bd" strokeWidth={2} fill="url(#fcffFill)" connectNulls={false}/>
                  </AreaChart>
                </ResponsiveContainer>
              </div> : <div className="grid h-[280px] place-items-center text-center text-sm muted">La publicación no contiene una serie FCFF utilizable.<br/>No se generan datos sustitutos.</div>}
            </div>
          </div>
          <p className="mt-5 text-[10px] muted">La visualización refleja exclusivamente la serie fcff_proy del snapshot. La moneda y unidad corresponden a los metadatos publicados.</p>
        </div>
      </section>

      <section id="simulation" className="act">
        <div className="shell">
          <div className="eyebrow">03 / THE SIMULATION LAB</div>
          <h2 className="section-title mt-5 max-w-3xl">Una valoración es una hipótesis.<br/><span className="text-mint">Pongámosla a prueba.</span></h2>
          <p className="lead mt-6">Modifica los drivers y ejecuta el DCF real en el motor Python. La valoración publicada permanece intacta; cada resultado de esta sala es experimental, trazable y no se persiste como valoración oficial.</p>
          <div className="glass mt-12 grid gap-10 p-6 sm:p-9 lg:grid-cols-[1fr_.8fr]">
            <div className="space-y-9">
              <Range label="WACC" value={wacc} min={8} max={22} step={0.01} suffix="% " onChange={setWacc}/>
              <Range label="CRECIMIENTO PERPETUO (g)" value={growth} min={0.5} max={6} step={0.05} suffix="% " onChange={setGrowth}/>
              <Range label="MARGEN EBITDA PROMEDIO PROYECTADO" value={margin} min={35} max={70} step={0.1} suffix="% " onChange={setMargin}/>
            </div>
            <div className="flex flex-col justify-between border-t border-white/10 pt-7 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
              <div><span className="pill">ESCENARIO EXPERIMENTAL · NO PUBLICADO</span>
                <div className="mt-7 flex items-center gap-3 text-mint"><Gauge size={22}/><span className="text-sm">Parámetros de exploración</span></div>
                <p className="mt-4 text-sm leading-7 muted">WACC: <strong className="text-paper">{wacc.toFixed(2)}%</strong><br/>g: <strong className="text-paper">{growth.toFixed(2)}%</strong><br/>Margen EBITDA: <strong className="text-paper">{margin.toFixed(1)}%</strong></p>
                <p className="mt-5 text-xs leading-6 text-amber-100/80">{wacc <= growth ? "Advertencia: el WACC debe ser superior a g para aplicar el modelo de perpetuidad de Gordon." : "Los cambios se aplicarán al motor Python cuando ejecutes la simulación."}</p>
              </div>
              <button className="mt-8 self-start text-xs text-mint underline underline-offset-4" onClick={() => {
                setWacc(numeric(metrics.wacc_calc) === null ? 14.34 : Number(metrics.wacc_calc) * 100);
                setGrowth(numeric(metrics.g_usada) === null ? 3.5 : Number(metrics.g_usada) * 100);
                setMargin(numeric(metrics.margen_ebitda_base_simulacion) === null ? 57.8 : Number(metrics.margen_ebitda_base_simulacion) * 100);
                setScenarioResult(null); setScenarioError("");
              }}>Restablecer supuestos oficiales</button>
            </div>
          </div>
          <div className="mt-7 flex flex-wrap items-center gap-4">
            <button className="cta disabled:cursor-not-allowed disabled:opacity-50" onClick={() => void runScenario()} disabled={scenarioLoading || loading || !snapshot}>
              {scenarioLoading ? <RefreshCw size={15} className="animate-spin"/> : <Gauge size={15}/>}
              {scenarioLoading ? "Calculando en Python…" : "Ejecutar simulación DCF"}
            </button>
            <span className="text-xs muted">Cada ejecución consulta el snapshot oficial en servidor y envía sus drivers al servicio privado.</span>
          </div>
          {scenarioError && <div role="alert" className="mt-5 border border-amber-300/25 bg-amber-200/5 p-4 text-sm text-amber-100">{scenarioError}</div>}
          {scenarioResult && <div className="mt-10 space-y-8" aria-live="polite">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div><div className="eyebrow">RESULTADO EXPERIMENTAL</div><h3 className="mt-2 text-2xl font-semibold">El escenario recalculado</h3></div>
              <span className="pill">MOTOR PYTHON · NO PUBLICADO</span>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Metric title="Enterprise Value" value={money(scenarioResult.base.EV, scenarioResult.currency)} note={scenarioResult.unit}/>
              <Metric title="Equity Value" value={money(scenarioResult.base.Equity_Value, scenarioResult.currency)} note="Después del bridge oficial"/>
              <Metric title="Valor por acción" value={money(scenarioResult.base.value_per_share, scenarioResult.currency)} note="Acciones del snapshot"/>
              <Metric title="Upside / downside" value={percent(scenarioResult.base.upside_pct)} note="Frente al precio comparable"/>
            </div>
            <div className="glass p-5 sm:p-7">
              <div className="eyebrow mb-5">COMPARACIÓN DE ESCENARIOS</div>
              <div className="grid gap-5 md:grid-cols-3">
                {Object.entries(scenarioResult.scenarios).map(([name, item]) => <div key={name} className="border-t border-mint/25 pt-4">
                  <div className="text-xs tracking-[.14em] text-mint">{name.toUpperCase()}</div>
                  <div className="mt-3 text-2xl font-medium">{money(item.Equity_Value, scenarioResult.currency)}</div>
                  <div className="mt-2 text-xs muted">Equity Value · {money(item.value_per_share, scenarioResult.currency)} por acción</div>
                  <div className="mt-4 text-[11px] leading-6 muted">WACC {percent(item.parameters.wacc)} · g {percent(item.parameters.g)} · margen {percent(item.parameters.ebitda_margin)}</div>
                </div>)}
              </div>
            </div>
            <div className="glass p-5 sm:p-7">
              <div className="eyebrow mb-2">SENSIBILIDAD · WACC × g</div>
              <p className="mb-5 text-xs muted">Enterprise Value en la unidad publicada. Las celdas no válidas se bloquean cuando g no es menor que WACC.</p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] border-collapse text-right text-xs">
                  <thead><tr><th className="p-3 text-left text-muted">WACC / g</th>{scenarioResult.sensitivity[0]?.cells.map(cell => <th key={cell.g} className="p-3 text-mint">{percent(cell.g)}</th>)}</tr></thead>
                  <tbody>{scenarioResult.sensitivity.map(row => <tr key={row.wacc} className="border-t border-white/10">
                    <th className="p-3 text-left font-mono text-mint">{percent(row.wacc)}</th>
                    {row.cells.map(cell => <td key={cell.g} className="p-2">
                      <span className={`inline-block min-w-[88px] rounded px-2 py-3 ${cell.valid ? "bg-mint/10 text-paper" : "bg-white/5 text-muted"}`}>
                        {cell.valid ? money(cell.EV, scenarioResult.currency) : "—"}
                      </span>
                    </td>)}
                  </tr>)}</tbody>
                </table>
              </div>
            </div>
            <div className="glass p-5 sm:p-7">
              <div className="eyebrow mb-5">TORNADO · IMPACTO EN EQUITY VALUE</div>
              <div className="space-y-4">{scenarioResult.tornado.map(item => <div key={item.driver} className="grid gap-2 sm:grid-cols-[190px_1fr_1fr] sm:items-center">
                <span className="text-xs">{item.driver}</span>
                <span className="text-xs text-amber-200">Shock bajo: {item.delta_low === null ? "N/D" : money(item.delta_low, scenarioResult.currency)}</span>
                <span className="text-xs text-mint">Shock alto: {item.delta_high === null ? "N/D" : money(item.delta_high, scenarioResult.currency)}</span>
              </div>)}</div>
            </div>
            <p className="text-xs leading-6 muted">Control de trazabilidad: diferencia del EV experimental base frente al EV publicado: {scenarioResult.diagnostics.scenario_ev_delta_vs_official === null ? "N/D" : money(scenarioResult.diagnostics.scenario_ev_delta_vs_official, scenarioResult.currency)}. El snapshot oficial no se modifica y el cálculo no se guarda como nueva publicación.</p>
          </div>}
        </div>
      </section>

      <section id="risk" className="act">
        <div className="shell">
          <div className="eyebrow">04 / RISK INTELLIGENCE</div>
          <h2 className="section-title mt-5 max-w-3xl">¿Qué puede salir mal<br/><span className="text-mint">y cuánto importa?</span></h2>
          <p className="lead mt-6">Una valoración útil también expone sus puntos vulnerables. Los riesgos deben vincularse con alertas, vetos y sensibilidades generadas por el modelo central.</p>
          <div className="mt-12 grid gap-4 md:grid-cols-3">
            <InfoCard icon={<TrendingUp/>} title="Riesgo de supuestos" text="WACC, crecimiento terminal y recuperación de márgenes."/>
            <InfoCard icon={<ShieldCheck/>} title="Calidad del modelo" text="Validaciones, vetos cuantitativos y consistencia de unidades."/>
            <InfoCard icon={<Activity/>} title="Riesgo financiero" text="Apalancamiento, capacidad de generación de caja y estructura de capital."/>
          </div>
          <div className="mt-6 border border-white/10 p-5 text-sm leading-7 muted">{label(metrics.decision_modelo, "La instantánea no contiene un resumen estructurado de riesgos. La siguiente integración incorporará las alertas y vetos reales de la corrida.")}</div>
        </div>
      </section>

      <section id="data" className="act">
        <div className="shell">
          <div className="eyebrow">05 / DATA INTELLIGENCE</div>
          <h2 className="section-title mt-5 max-w-3xl">Cada cifra tiene<br/><span className="text-mint">una historia.</span></h2>
          <p className="lead mt-6">La trazabilidad conecta cada resultado con la corrida, el motor y los supuestos que lo produjeron. La transparencia no es un apéndice: forma parte de la decisión.</p>
          <div className="glass mt-12 p-6 sm:p-9">
            <div className="grid gap-8 md:grid-cols-3">
              <InfoCard icon={<Database/>} title="Snapshot oficial" text="Instantánea persistida en Supabase y recuperada mediante RPC protegida."/>
              <InfoCard icon={<Layers3/>} title="Versión del modelo" text={label(snapshot?.model_version, "Versión no informada en el snapshot")}/>
              <InfoCard icon={<Network/>} title="Fecha de publicación" text={officialPublished}/>
            </div>
            <div className="mt-8 border-t border-white/10 pt-6">
              <div className="eyebrow mb-4">CADENA DE PROCEDENCIA</div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                {["Modelación Financiera","Motor Python","Snapshot JSONB","RPC protegida","Experiencia web"].map((step, i) => <span key={step} className="flex items-center gap-2"><span className="border border-mint/25 bg-mint/[.06] px-3 py-2 text-mint">{step}</span>{i < 4 && <ArrowRight size={13} className="text-mint/60"/>}</span>)}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="decision" className="act">
        <div className="shell">
          <div className="eyebrow">06 / THE DECISION ROOM</div>
          <h2 className="section-title mt-5 max-w-4xl">La decisión no depende<br/>de una cifra. <span className="text-mint">Depende de la evidencia.</span></h2>
          <p className="lead mt-6">La valoración permite contrastar el precio de mercado con el valor fundamental, identificar los supuestos críticos y evaluar la relación entre rentabilidad y riesgo.</p>
          <div className="glass mt-12 grid gap-8 p-6 sm:p-10 lg:grid-cols-[1fr_auto] lg:items-end">
            <div><div className="eyebrow">CONCLUSIÓN DE LA CORRIDA OFICIAL</div><p className="mt-5 max-w-3xl font-display text-2xl leading-relaxed">{label(snapshot?.payload?.decision_text, "No se registró una conclusión textual para esta corrida.")}</p><p className="mt-5 text-xs muted">Snapshot publicado: {officialPublished} · Modelo: {label(snapshot?.model_version)}</p></div>
            <button className="cta" onClick={() => scrollTo("opening")}>Volver al inicio <ArrowDown size={14} className="rotate-180"/></button>
          </div>
          <footer className="mt-20 flex flex-col justify-between gap-4 border-t border-white/10 pt-6 text-[10px] muted sm:flex-row"><span>ISA INVESTMENT EXPERIENCE · MODELACIÓN FINANCIERA</span><span>Herramienta de análisis. No constituye recomendación de inversión.</span></footer>
        </div>
      </section>
    </main>
  );
}

function Metric({ title, value, note }: { title: string; value: string; note: string }) {
  return <div className="metric"><div className="metric-label">{title}</div><div className="metric-value">{value}</div><div className="metric-note">{note}</div></div>;
}
function InfoCard({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div className="border-t border-mint/25 pt-5"><div className="mb-4 text-mint">{icon}</div><h3 className="text-sm font-semibold">{title}</h3><p className="mt-2 text-xs leading-6 muted">{text}</p></div>;
}
function Range({ label, value, min, max, step, suffix, onChange }: { label: string; value: number; min: number; max: number; step: number; suffix: string; onChange: (n: number) => void }) {
  return <label className="block"><span className="flex items-center justify-between gap-3 text-[10px] tracking-[.12em] text-muted"><span>{label}</span><strong className="font-mono text-base tracking-normal text-mint">{value.toFixed(2)}{suffix}</strong></span><input className="range mt-5" type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(Number(e.target.value))}/><span className="mt-2 flex justify-between text-[10px] text-muted"><span>{min}{suffix}</span><span>{max}{suffix}</span></span></label>;
}
