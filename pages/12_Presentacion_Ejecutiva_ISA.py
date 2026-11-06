"""Presentación ejecutiva interactiva de ISA."""
from __future__ import annotations
import math, sys
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.taller_isa import load_isa,historical_drivers,scenario_params,cost_of_capital,evaluate,monte_carlo,tornado,investment_decision,SCENARIO_ORDER,DECISION_THRESHOLDS

st.set_page_config(page_title="ISA | Investment Intelligence Room",page_icon="◈",layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(ellipse at 12% 0%,#10313a 0%,transparent 32%),radial-gradient(ellipse at 95% 5%,#172747 0%,transparent 30%),#070B14;color:#F3F7FC;font-family:'Manrope',sans-serif}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d1726,#080e18);border-right:1px solid #263b51}
.block-container{max-width:1480px;padding-top:1.5rem;padding-bottom:4rem}
h1,h2,h3{font-family:'Manrope',sans-serif;letter-spacing:-.04em;color:#F5F8FC}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(22,37,55,.9),rgba(12,22,36,.8));border:1px solid #2b4058;border-radius:16px;padding:15px}
[data-testid="stMetricLabel"]{color:#9FB0C5!important;text-transform:uppercase;letter-spacing:.09em;font-size:.68rem!important}
[data-testid="stMetricValue"]{font-family:'DM Mono',monospace;color:#F7FAFF!important}
.hero{padding:32px 36px;border:1px solid #31546a;border-radius:22px;background:linear-gradient(120deg,rgba(10,35,49,.96),rgba(18,37,64,.88) 58%,rgba(10,91,84,.45));box-shadow:0 22px 65px #0007}
.hero p{max-width:780px;color:#b8d5df;font-size:1.02rem}
.eyebrow{color:#57e3c4;font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;font-weight:800}
.callout{border-left:3px solid #42e3c1;padding:10px 15px;background:#0e292b;border-radius:0 10px 10px 0;color:#d9fff5}
hr{border-color:#23364b}
</style>
""",unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_snapshot():
    return load_isa(ROOT/"datos_taller_isa_2026.json")
try:
    isa=load_snapshot()
    hist=isa["history"]
    price=float(isa["mercado"]["precio_ref"])
    bridge=isa["puente"]
    cut=isa.get("corte_catalogo","N/D")
    price_date=isa["mercado"].get("fecha_precio_ref","N/D")
except Exception as exc:
    st.error("No se pudo cargar la instantánea de ISA.")
    st.exception(exc)
    st.stop()

def money(x,d=0): return "COP {:,.{d}f}".format(x,d=d)
def pct(x): return "{:.1%}".format(x) if math.isfinite(float(x)) else "N/D"
def style(fig,h=370):
    fig.update_layout(template="plotly_dark",height=h,paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(11,22,36,.7)",font=dict(family="Manrope",color="#dce8f4"),margin=dict(l=25,r=25,t=50,b=35),legend=dict(orientation="h",y=-.2))
    fig.update_xaxes(showgrid=False,linecolor="#294057")
    fig.update_yaxes(gridcolor="#23364b")
    return fig

chapters=["01 · Tesis de inversión","02 · La compañía","03 · Motor de valor","04 · Riesgo y escenarios","05 · Mercado y decisión","06 · Comité / Q&A","DATA ROOM · Fuentes"]
with st.sidebar:
    st.markdown("### ◈ INVESTMENT ROOM")
    st.caption("ISA · Comité de inversión · COP")
    chapter=st.radio("RECORRIDO EJECUTIVO",chapters)
    st.divider()
    st.markdown("#### Laboratorio de supuestos")
    scenario=st.selectbox("Escenario",SCENARIO_ORDER,index=2)
    bp=scenario_params(isa,scenario)
    w_delta=st.slider("Ajuste WACC (pp)",-3.0,4.0,0.0,0.25)
    g_pct=st.slider("Crecimiento perpetuo g (%)",1.0,8.0,float(bp["g_terminal"]*100),0.25)
    growth_delta=st.slider("Crecimiento ingresos (pp)",-4.0,4.0,0.0,0.25)
    margin_delta=st.slider("Margen EBIT (pp)",-4.0,4.0,0.0,0.25)
    capex_mult=st.slider("Intensidad CAPEX (x)",0.60,1.50,1.0,0.05)
    nwc_mult=st.slider("Capital de trabajo (x)",0.70,1.40,1.0,0.05)
    tax_pct=st.slider("Tasa fiscal provisional (%)",15.0,35.0,float(isa["capital"]["tax"]*100),0.5)
    st.caption("Los controles modifican hipótesis, no el histórico.")
    st.divider()
    st.caption("Corte: {} · Precio: {}".format(cut,price_date))

overrides={"wacc_delta":bp["wacc_delta"]+w_delta/100,"g_terminal":g_pct/100,"growth":bp["growth"]+growth_delta/100,"ebit_margin":bp["ebit_margin"]+margin_delta/100,"capex_intensity":bp["capex_intensity"]*capex_mult,"nwc_ratio":bp["nwc_ratio"]*nwc_mult,"tax":tax_pct/100}
try:
    result=evaluate(isa,scenario,overrides=overrides,con_tir=True)
except Exception as exc:
    st.error("Supuestos incompatibles con el motor: {}".format(exc))
    st.stop()
v,p=result["valuation"],result["params"]
share=float(v["valor_por_accion"]); upside=share/price-1
wacc=float(p["wacc"]); g_used=float(v.get("g_usada",p["g_terminal"]))
ev=float(v["ev"]); equity=float(v["patrimonio"])
st.markdown('<div class="eyebrow">ISA · INTERCONEXIÓN ELÉCTRICA / VALORACIÓN ESTRATÉGICA</div>',unsafe_allow_html=True)
st.progress((chapters.index(chapter)+1)/len(chapters))

if chapter==chapters[0]:
    st.markdown('<div class="hero"><span class="eyebrow">INVESTMENT THESIS · {}</span><h1>ISA: infraestructura crítica,<br>valor bajo escrutinio.</h1><p>La pregunta no es si la red eléctrica será necesaria. La pregunta es cuánto valor económico puede capturar ISA y qué precio justifica pagar hoy por ese futuro.</p><p>Presentación interactiva · 15 minutos · COP</p></div>'.format(cut),unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    a.metric("Valor por acción",money(share),pct(upside)+" vs. mercado")
    b.metric("Precio de referencia",money(price))
    c.metric("Enterprise Value",money(ev)+" mil M")
    d.metric("WACC / g","{:.2%} / {:.2%}".format(wacc,g_used))
    st.markdown("### La tesis en una frase")
    st.markdown('<div class="callout">La electrificación global crea una oportunidad estructural para las redes, pero la creación de valor para el accionista depende de márgenes, reinversión, apalancamiento y disciplina en el precio de entrada.</div>',unsafe_allow_html=True)
    left,right=st.columns([1.3,1])
    with left:
        fig=go.Figure(go.Bar(x=["Valor intrínseco","Precio de referencia"],y=[share,price],text=[money(share),money(price)],textposition="outside"))
        fig.update_layout(title="Precio vs. valor intrínseco",yaxis_title="COP por acción")
        st.plotly_chart(style(fig,330),use_container_width=True)
    with right: st.metric("Upside / downside",pct(upside))
    with st.expander("Guion del expositor · 3 minutos"):
        st.write("Quiero comenzar con una pregunta: ¿cuánto vale realmente ISA? La transición energética y la digitalización hacen que las redes sean un activo estratégico. Pero una buena empresa no es automáticamente una buena inversión a cualquier precio. El análisis conecta el contexto global con la capacidad de ISA para generar caja, financiar su expansión y remunerar al accionista. No presentamos un número como verdad absoluta: mostramos tesis, evidencia y riesgos.")

elif chapter==chapters[1]:
    st.title("01 / La compañía detrás del ticker")
    last=hist[-1]; a,b,c,d=st.columns(4)
    a.metric("Ingresos 2025",money(last["Ingresos"],1)+" mil M")
    b.metric("EBITDA 2025",money(last["EBITDA"],1)+" mil M")
    c.metric("Margen EBITDA",pct(last["EBITDA"]/last["Ingresos"]))
    d.metric("Deuda neta",money(bridge["deuda_neta"],1)+" mil M")
    hdf=pd.DataFrame(hist); left,right=st.columns([1.3,1])
    with left:
        fig=go.Figure()
        for col in ["Ingresos","EBITDA","EBIT"]: fig.add_trace(go.Scatter(x=hdf["Año"],y=hdf[col],name=col,mode="lines+markers"))
        fig.update_layout(title="Trayectoria financiera histórica",yaxis_title="COP miles de millones")
        st.plotly_chart(style(fig),use_container_width=True)
    with right:
        margins=[x["EBIT"]/x["Ingresos"] for x in hist]
        fig=go.Figure(go.Bar(x=[x["Año"] for x in hist],y=margins,text=[pct(x) for x in margins],textposition="outside"))
        fig.update_layout(title="Margen EBIT histórico",yaxis_tickformat=".0%")
        st.plotly_chart(style(fig),use_container_width=True)
    st.subheader("El contexto eléctrico global")
    a,b,c=st.columns(3)
    a.metric("Demanda eléctrica global","+3,6 % anual","promedio previsto 2026–2030")
    b.metric("Proyectos en cola de conexión",">2.500 GW","renovables, almacenamiento y grandes cargas")
    c.metric("Inversión anual en redes","+50 %","requerida hacia 2030 vs. nivel actual")
    st.markdown('<div class="callout">La expansión de demanda y generación renovable refuerza la relevancia estratégica de la transmisión. No demuestra por sí sola que ISA capture rentabilidades superiores al costo de capital.</div>',unsafe_allow_html=True)
    st.markdown("**Tensiones a vigilar:** permisos, ejecución, CAPEX, congestión, flexibilidad, ciberseguridad, resiliencia climática y regulación.")
    st.caption("Fuente sectorial: IEA Electricity 2026.")

elif chapter==chapters[2]:
    st.title("02 / Del negocio al valor")
    a,b,c,d=st.columns(4)
    a.metric("WACC",pct(wacc)); b.metric("g terminal efectiva",pct(g_used)); c.metric("EV",money(ev)+" mil M"); d.metric("Equity Value",money(equity)+" mil M")
    rows=[r for r in result["rows"] if not r.get("terminal")]
    df=pd.DataFrame({"Año":[r["año"] for r in rows],"Ingresos":[r["ingresos"] for r in rows],"FCFF":[r["fcff"] for r in rows]})
    fig=go.Figure(); fig.add_trace(go.Bar(x=df["Año"],y=df["FCFF"],name="FCFF")); fig.add_trace(go.Scatter(x=df["Año"],y=df["Ingresos"],name="Ingresos",yaxis="y2",mode="lines+markers"))
    fig.update_layout(title="Crecimiento operativo y caja libre",yaxis_title="FCFF · COP miles de millones",yaxis2=dict(title="Ingresos",overlaying="y",side="right",showgrid=False))
    st.plotly_chart(style(fig),use_container_width=True)
    labels=["EV","Deuda neta","NCI","Otros claims","Asociadas","Equity"]
    vals=[ev,-bridge["deuda_neta"],-bridge["nci"],-bridge.get("otros_claims",0),bridge["asociados"],equity]
    fig=go.Figure(go.Waterfall(x=labels,measure=["absolute","relative","relative","relative","relative","total"],y=vals))
    fig.update_layout(title="Puente de valor empresarial a patrimonio",yaxis_title="COP miles de millones")
    st.plotly_chart(style(fig,350),use_container_width=True)
    st.info("El valor terminal representa {} del EV; una participación elevada aumenta la sensibilidad a WACC, g y FCFF terminal.".format(pct(v.get("peso_valor_terminal",float("nan")))))
    with st.expander("Guion del expositor · 3 minutos"):
        st.write("Proyectamos la operación, estimamos el efectivo disponible después de impuestos y reinversión, y descontamos esos flujos al WACC. El resultado inicial es el Enterprise Value. Para llegar al patrimonio restamos deuda neta y participaciones minoritarias, y sumamos las inversiones en asociadas. Una porción importante del EV proviene del valor terminal: por eso los supuestos de largo plazo merecen tanta atención como los años explícitos.")

elif chapter==chapters[3]:
    st.title("03 / Lo que puede cambiar la tesis")
    st.caption("Los shocks de escenarios son hipótesis de análisis, no pronósticos oficiales.")
    evals={s:evaluate(isa,s,con_tir=True) for s in SCENARIO_ORDER}
    sdf=pd.DataFrame([{"Escenario":s,"Valor por acción":e["valuation"]["valor_por_accion"],"WACC":e["params"]["wacc"],"g":e["params"]["g_terminal"],"Máx. DN/EBITDA":e["max_deuda_ebitda"]} for s,e in evals.items()])
    fig=go.Figure(go.Bar(x=sdf["Escenario"],y=sdf["Valor por acción"],text=[money(x) for x in sdf["Valor por acción"]],textposition="outside")); fig.add_hline(y=price,line_dash="dash",annotation_text="Precio de referencia")
    fig.update_layout(title="Valor por acción por escenario",yaxis_title="COP por acción")
    st.plotly_chart(style(fig),use_container_width=True)
    st.dataframe(sdf.style.format({"Valor por acción":"{:,.0f}","WACC":"{:.2%}","g":"{:.2%}","Máx. DN/EBITDA":"{:.2f}x"}),hide_index=True,use_container_width=True)
    st.subheader("Tornado · drivers que mueven el valor")
    tor=pd.DataFrame(tornado(isa,scenario))
    fig=go.Figure(go.Bar(y=tor["driver"],x=tor["rango"],orientation="h",text=[money(x) for x in tor["rango"]],textposition="outside")); fig.update_layout(title="Amplitud del cambio en valor por acción",xaxis_title="COP por acción")
    st.plotly_chart(style(fig,350),use_container_width=True)
    st.subheader("Mapa de sensibilidad WACC × g")
    wb=cost_of_capital(isa)["wacc"]; ws=[wb+x/100 for x in [-2,-1,0,1,2]]; gs=[x/100 for x in [3,4,5,6]]; z=[]
    for gg in gs:
        row=[]
        for ww in ws:
            try: row.append(evaluate(isa,"Base",overrides={"wacc_delta":ww-wb,"g_terminal":gg},con_tir=False)["valuation"]["valor_por_accion"])
            except Exception: row.append(None)
        z.append(row)
    fig=go.Figure(go.Heatmap(x=[pct(x) for x in ws],y=[pct(x) for x in gs],z=z,colorscale="Tealgrn",colorbar=dict(title="COP/acción"))); fig.update_layout(title="Valor intrínseco bajo distintas tasas")
    st.plotly_chart(style(fig,340),use_container_width=True)
    with st.expander("Simulación Monte Carlo"):
        st.write("Las distribuciones son hipótesis del modelo, no probabilidades objetivas de mercado.")
        n=st.select_slider("Número de simulaciones",options=[500,1000,2500,5000],value=1000)
        if st.button("Ejecutar simulación",type="primary"):
            with st.spinner("Ejecutando simulaciones..."): mc=monte_carlo(isa,n=int(n))
            a,b,c,d=st.columns(4)
            a.metric("Mediana",money(mc["p50"])); b.metric("P5–P95",money(mc["p5"])+" – "+money(mc["p95"])); c.metric("P(valor > precio)",pct(mc["prob_valor_mayor_precio"])); d.metric("P(covenant roto)",pct(mc["prob_covenant_roto"]))
            vals=pd.DataFrame(mc["simulaciones"]); fig=px.histogram(vals,x="valor_por_accion",nbins=36,title="Distribución simulada del valor por acción"); fig.add_vline(x=price,line_dash="dash",annotation_text="Precio de referencia")
            st.plotly_chart(style(fig,330),use_container_width=True)
            st.caption("Semilla reproducible: {} · {:,} corridas.".format(mc["semilla"],mc["n"]))

elif chapter==chapters[4]:
    st.title("04 / Precio, margen de seguridad y decisión")
    a,b,c=st.columns(3); a.metric("Valor intrínseco / acción",money(share)); b.metric("Precio de referencia",money(price)); c.metric("Upside / downside",pct(upside))
    fig=go.Figure(go.Bar(x=["Valor DCF","Precio BVC"],y=[share,price],text=[money(share),money(price)],textposition="outside")); fig.add_hline(y=price*(1+DECISION_THRESHOLDS["margen_seguridad_compra"]),line_dash="dot",annotation_text="Umbral de compra +15 %"); fig.update_layout(title="¿El precio deja margen de seguridad?",yaxis_title="COP por acción")
    st.plotly_chart(style(fig,350),use_container_width=True)
    decision=investment_decision(isa,{s:evaluate(isa,s) for s in SCENARIO_ORDER})
    st.subheader("Regla de decisión del motor"); st.success(decision["decision"]); st.write(decision["regla"])
    st.metric("Precio máximo de compra por margen de seguridad",money(decision["precio_max_compra"]))
    st.caption("Precio de referencia: {}. No es cotización en tiempo real.".format(price_date))
    st.warning("La valoración relativa debe completarse con comparables, múltiplos observados y fecha de mercado verificada. No se inventan peers.")
    st.subheader("Hoja de ruta de 90 días")
    a,b,c=st.columns(3)
    a.markdown("**DÍAS 1–30**\n\nValidar EEFF, deuda neta, NCI, asociadas, acciones y cotización. Conciliar CAPEX y capital de trabajo.")
    b.markdown("**DÍAS 31–60**\n\nActualizar WACC, tasa fiscal, comparables, escenarios y sensibilidad. Contrastar supuestos con guía corporativa.")
    c.markdown("**DÍAS 61–90**\n\nRecalibrar DCF, definir precio de entrada y documentar decisión, límites de riesgo y señales de revisión.")

elif chapter==chapters[5]:
    st.title("05 / Del análisis a la decisión")
    st.markdown('<div class="hero"><span class="eyebrow">COMITÉ DE INVERSIÓN</span><h1>El valor no es el precio.<br>La disciplina está en la diferencia.</h1><p>La tesis debe sobrevivir a preguntas sobre crecimiento, reinversión, riesgo, deuda y calidad de los datos.</p></div>',unsafe_allow_html=True)
    q1=st.radio("1. ¿Qué condición es imprescindible?",["Crecimiento de ingresos","Recuperación del margen EBIT","CAPEX eficiente y rentable","Reducción del costo de capital"],index=2)
    q2=st.radio("2. ¿Qué riesgo merece seguimiento prioritario?",["Regulatorio y ejecución","Apalancamiento","Tasa fiscal / calidad de datos","Capital de trabajo"],index=0)
    q3=st.radio("3. ¿Qué acción propone el comité?",["Aprobar compra","Mantener y monitorear","No incrementar / esperar","Solicitar validación adicional"],index=3)
    if st.button("Registrar síntesis del comité",type="primary"): st.session_state["isa_committee_vote"]={"condicion":q1,"riesgo":q2,"accion":q3}
    if "isa_committee_vote" in st.session_state: st.success("Síntesis registrada en esta sesión."); st.json(st.session_state["isa_committee_vote"])
    checks=["Precio y fecha de mercado actualizados","Tasa fiscal validada por jurisdicción","CAPEX y capital de trabajo conciliados","Asociadas revisadas para evitar doble conteo","Comparables con fuente y fecha","Sensibilidad y escenarios revisados","Margen de seguridad y límites de riesgo aprobados"]
    selected=[x for i,x in enumerate(checks) if st.checkbox(x,key="isa_check_"+str(i))]
    st.progress(len(selected)/len(checks),text="Validaciones completadas: {} de {}".format(len(selected),len(checks)))

else:
    st.title("DATA ROOM / Trazabilidad y límites")
    st.caption("Separación entre dato observado, supuesto, estimación y contexto externo.")
    st.subheader("Fuentes internas")
    st.write("- datos_taller_isa_2026.json: instantánea de datos y supuestos.")
    st.write("- scripts/taller_isa.py: escenarios, valoración, sensibilidad y Monte Carlo.")
    st.write("- modelacion_logic.py: motor DCF del modelo principal.")
    st.subheader("Calidad y limitaciones"); st.warning(isa.get("verificacion","Revisar la verificación de datos en la instantánea.")); st.write(isa.get("fuente_historico",""))
    for warning in isa.get("advertencias",[]): st.markdown("- "+warning)
    st.subheader("Contexto global · IEA Electricity 2026")
    st.markdown("- Demanda eléctrica mundial: crecimiento medio previsto de 3,6 % anual en 2026–2030.\n- Más de 2.500 GW de proyectos renovables, almacenamiento y grandes cargas esperan conexión.\n- La inversión anual en redes debería crecer aproximadamente 50 % hacia 2030.\n- Tecnologías de mejora de redes podrían liberar capacidad de conexión de 450–700 GW.")
    st.markdown("Fuentes: [IEA Electricity 2026](https://www.iea.org/reports/electricity-2026/executive-summary) · [IEA Grids 2026](https://www.iea.org/reports/electricity-2026/grids)")
    st.subheader("Tendencias de presentación ejecutiva")
    st.markdown("- Micrositios digitales e informes interactivos como complemento del PDF.\n- Narrativa orientada a decisión: tesis → evidencia → riesgo → acción.\n- Complejidad progresiva: resumen primero; detalle y trazabilidad bajo demanda.\n- Gobernanza visible: cada métrica con fecha, unidad, fuente y limitación.")
    st.write("Empresa: {} · Corte: {} · Precio: {}".format(isa["empresa"],cut,price_date))
    st.download_button("Descargar instantánea ISA (JSON)",data=(ROOT/"datos_taller_isa_2026.json").read_bytes(),file_name="datos_taller_isa_2026.json",mime="application/json")

st.divider()
st.caption("ISA Investment Intelligence Room · Herramienta académica y de apoyo a decisiones. No constituye asesoría financiera ni recomendación personalizada. Los resultados dependen de los supuestos activos y de la fecha de los datos.")
