"""Academia Financiera: página Streamlit independiente y multipágina."""
from __future__ import annotations
import math
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Academia Financiera | Aprende haciendo",page_icon="🎓",layout="wide",initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&display=swap');
html,body,[data-testid="stAppViewContainer"]{background:radial-gradient(900px 500px at 5% 0%,rgba(45,212,191,.12),transparent 60%),radial-gradient(900px 500px at 95% 5%,rgba(96,165,250,.12),transparent 55%),#070b14!important;color:#f8fafc!important;font-family:'DM Sans',sans-serif}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0d1728,#080d18)!important;border-right:1px solid rgba(148,163,184,.18)}
.block-container{max-width:1420px;padding-top:2rem;padding-bottom:4rem}
h1,h2,h3{font-family:'Space Grotesk',sans-serif!important;letter-spacing:-.035em}
.ac-hero{padding:2rem 2.2rem;border:1px solid rgba(45,212,191,.25);border-radius:24px;background:linear-gradient(125deg,rgba(15,45,61,.92),rgba(24,37,66,.88) 55%,rgba(13,78,75,.65));box-shadow:0 24px 80px rgba(0,0,0,.35);margin-bottom:1.3rem}
.eyebrow{color:#5eead4;text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:800}
.ac-hero h1{margin:.45rem 0;font-size:2.5rem!important;color:#fff!important}
.ac-hero p{color:#cbd5e1;max-width:760px}
.glass{background:rgba(17,26,43,.78);border:1px solid rgba(148,163,184,.18);border-radius:18px;padding:1.1rem 1.25rem;backdrop-filter:blur(14px);box-shadow:0 12px 35px rgba(0,0,0,.18);height:100%}
.tag{display:inline-block;border:1px solid rgba(45,212,191,.3);background:rgba(45,212,191,.09);color:#99f6e4;border-radius:999px;padding:.22rem .65rem;font-size:.72rem;margin-right:.35rem}
.muted{color:#a7b5c9;font-size:.88rem}
[data-testid="stMetric"]{background:rgba(17,26,43,.75);border:1px solid rgba(148,163,184,.18);padding:1rem;border-radius:14px}
div.stButton>button,div.stLinkButton>a{border-radius:12px;border:1px solid rgba(45,212,191,.35);font-weight:700}
hr{border-color:rgba(148,163,184,.18)}
</style>""",unsafe_allow_html=True)

MODULES={
"01 · El lenguaje del dinero":{"level":"Fundamentos","time":"12 min","goal":"Entender cómo se mueve el dinero de una empresa antes de valorarla.","analogy":"Imagina una tienda de barrio. Vende productos, paga arriendo y salarios, compra inventario y al final queda —o no— dinero disponible. Una empresa grande funciona igual, solo que con más ceros.","concepts":[("Ingresos","Todo lo que factura la empresa. No significa que el dinero ya esté en el banco."),("Costos y gastos","Recursos consumidos para operar: materias primas, nómina, arriendos y administración."),("EBITDA","Resultado operativo antes de intereses, impuestos, depreciación y amortización. No es caja libre."),("EBIT","Resultado operativo después de reconocer depreciación y amortización."),("Utilidad neta","Lo que queda contablemente después de gastos financieros e impuestos."),("Flujo de caja","Dinero que efectivamente entra y sale. Utilidad contable y efectivo no son lo mismo.")],"formula":"Ingresos − costos y gastos operativos = EBITDA (aproximación didáctica)","why":"Permite leer estados financieros sin confundir ventas, ganancias contables y efectivo disponible.","source":"Estados financieros auditados, notas contables, informes de gestión y reportes regulatorios."},
"02 · Pronosticar el negocio":{"level":"Proyección","time":"15 min","goal":"Traducir la historia de una compañía en hipótesis explícitas sobre el futuro.","analogy":"Planear las ventas de una cafetería: estimas cuántos clientes llegarán, cuánto gastarán y qué costos tendrás. No adivinas: construyes supuestos comprobables.","concepts":[("Crecimiento de ventas","Cambio porcentual de ingresos. Puede venir de unidades, precios o nuevos mercados."),("Margen EBITDA","Porcentaje de ingresos que queda como EBITDA."),("CAPEX","Inversión en activos de largo plazo: maquinaria, redes, edificios o tecnología."),("Capital de trabajo (NWC)","Recursos en inventarios y cuentas por cobrar, netos de financiación espontánea de proveedores."),("Depreciación","Distribución contable del costo de un activo durante su vida útil; no es salida de caja del periodo."),("FCFF","Flujo de caja libre para todos los financiadores: deuda y accionistas.")],"formula":"FCFF = EBIT × (1 − tasa de impuesto) + D&A − CAPEX − ΔNWC","why":"El FCFF es el dinero disponible para remunerar a prestamistas y accionistas después de sostener la operación.","source":"Históricos financieros, presupuesto, plan de inversiones, capacidad instalada, inflación y drivers operativos."},
"03 · Riesgo, CAPM y WACC":{"level":"Valoración","time":"18 min","goal":"Comprender por qué el dinero futuro vale menos hoy y cómo estimar el rendimiento exigido.","analogy":"Prestar dinero a un amigo confiable no es igual que financiar un negocio incierto. Cuanto mayor el riesgo, mayor rendimiento exigirías.","concepts":[("Tasa libre de riesgo (Rf)","Referencia soberana de muy bajo riesgo en la moneda del análisis."),("Beta (β)","Sensibilidad del rendimiento de una acción frente al mercado."),("Prima de mercado","Rendimiento adicional exigido por invertir en acciones frente a la tasa libre de riesgo."),("Ke","Costo del patrimonio: rendimiento exigido por accionistas."),("Kd","Costo de deuda antes de impuestos."),("WACC","Promedio ponderado del costo de deuda y patrimonio, ajustado por estructura de capital y beneficio fiscal.")],"formula":"Ke = Rf + β × prima de mercado · WACC = E/(D+E)×Ke + D/(D+E)×Kd×(1−T)","why":"El WACC descuenta FCFF cuando flujo y tasa comparten moneda, inflación y riesgo coherentes.","source":"Bonos soberanos, fuentes documentadas de primas y betas, estados financieros y tasas de deuda."},
"04 · DCF: cuánto vale hoy":{"level":"Valoración","time":"20 min","goal":"Convertir flujos futuros en valor presente y entender el puente de empresa a accionista.","analogy":"Una promesa de recibir 110 dentro de un año no equivale necesariamente a 110 hoy: el dinero de hoy puede invertirse y existe riesgo de impago.","concepts":[("Descuento","Traer una cantidad futura al presente usando una tasa que refleja tiempo y riesgo."),("Valor terminal","Valor de flujos posteriores al periodo proyectado explícitamente."),("Crecimiento perpetuo (g)","Crecimiento estable de largo plazo; debe ser menor que WACC en Gordon."),("Enterprise Value (EV)","Valor de las operaciones para todos los proveedores de capital."),("Equity Value","Valor atribuible a accionistas después de conciliar deuda neta y otros derechos."),("Valor por acción","Equity atribuible a accionistas ordinarios dividido por el número correcto de acciones.")],"formula":"EV = Σ FCFFₜ/(1+WACC)ᵗ + [FCFFₙ×(1+g)/(WACC−g)]/(1+WACC)ⁿ","why":"El DCF estima cuánto valen hoy los flujos que el negocio podría producir bajo supuestos explícitos.","source":"FCFF, WACC, g, deuda neta, caja, NCI, asociadas, otros claims y acciones diluidas."},
"05 · Múltiplos y comparación":{"level":"Valoración","time":"12 min","goal":"Comparar una compañía con empresas similares sin perder de vista sus diferencias.","analogy":"Para estimar el precio de una casa miras viviendas parecidas, pero ajustas ubicación, tamaño, estado y deudas.","concepts":[("EV/EBITDA","Valor de empresa frente a EBITDA; compara operaciones con cautela."),("EV/Ventas","Valor de empresa frente a ingresos; ignora diferencias de rentabilidad."),("P/VL","Precio de mercado frente al valor contable del patrimonio."),("Deuda neta/EBITDA","Indicador aproximado de apalancamiento; no son años exactos para pagar deuda."),("Peers","Empresas comparables por sector, geografía, regulación, crecimiento, margen y riesgo."),("Rango de valoración","Varios comparables reducen la dependencia de un único múltiplo.")],"formula":"Valor implícito = métrica financiera × múltiplo de comparables","why":"Los múltiplos muestran cómo valora el mercado negocios comparables; no reemplazan el análisis fundamental.","source":"Precios de mercado fechados, estados financieros homogéneos y muestra de comparables justificable."},
"06 · Portafolios y diversificación":{"level":"Inversión","time":"16 min","goal":"Entender por qué combinar activos puede cambiar el riesgo total.","analogy":"Una canasta con varios tipos de frutas resiste mejor una mala cosecha de una sola fruta. Importa que los activos no se muevan todos igual.","concepts":[("Rendimiento","Cambio porcentual del valor de una inversión."),("Volatilidad","Dispersión de rendimientos; describe variabilidad, no garantiza pérdidas."),("Correlación","Mide cómo se mueven dos activos en conjunto."),("Covarianza","Mide movimiento conjunto en unidades dependientes de escala."),("Sharpe","Exceso de rendimiento por unidad de volatilidad, sujeto a supuestos."),("Frontera eficiente","Carteras que maximizan rendimiento esperado para cada nivel de riesgo.")],"formula":"E(Rₚ)=ΣwᵢE(Rᵢ) · σₚ² = wᵀΣw","why":"La diversificación ayuda a gestionar riesgo específico; no elimina riesgo de mercado ni asegura ganancias.","source":"Precios ajustados, moneda y frecuencia homogéneas, tasas libres de riesgo y pesos."},
"07 · Escenarios y decisiones":{"level":"Riesgo","time":"14 min","goal":"Medir qué supuestos mueven el resultado y cómo responder ante futuros distintos.","analogy":"Antes de abrir un restaurante preguntas qué pasa si llegan menos clientes, sube el arriendo o debes renovar equipos.","concepts":[("Escenario","Conjunto coherente de supuestos: base, optimista o adverso."),("Sensibilidad","Cambia variables para observar cuánto cambia el resultado."),("Tornado","Ordena factores según su impacto en el valor."),("Monte Carlo","Simula resultados a partir de distribuciones y relaciones supuestas."),("VPN","Valor presente de entradas menos salidas."),("TIR","Tasa que hace que el VPN sea cero; puede ser ambigua en flujos no convencionales.")],"formula":"VPN = Σ FCₜ/(1+r)ᵗ − inversión inicial","why":"Ayuda a reconocer incertidumbre, priorizar riesgos y definir umbrales de acción.","source":"Históricos, contratos, escenarios macro, límites operativos y decisiones de la empresa."}
}
QUIZZES={
"01 · El lenguaje del dinero":("Ventas 100 y costos/gastos operativos 75. ¿EBITDA simplificado?",["25","75","100"],0,"100 − 75 = 25."),
"02 · Pronosticar el negocio":("¿Qué partida representa inversión en activos de largo plazo?",["Nómina","CAPEX","Intereses"],1,"CAPEX es inversión en activos como maquinaria, redes o tecnología."),
"03 · Riesgo, CAPM y WACC":("Si aumenta el riesgo percibido, ¿qué suele pasar con el rendimiento exigido?",["Disminuye","Aumenta","Siempre es cero"],1,"Mayor riesgo normalmente exige mayor rendimiento."),
"04 · DCF: cuánto vale hoy":("En Gordon, ¿qué condición debe cumplirse?",["g > WACC","g < WACC","g = WACC"],1,"La fórmula divide por WACC − g; si g ≥ WACC deja de ser válida."),
"05 · Múltiplos y comparación":("¿Qué expresa EV/EBITDA?",["Precio/ventas","EV frente a EBITDA","Deuda/caja"],1,"Relaciona valor de empresa con EBITDA."),
"06 · Portafolios y diversificación":("¿Qué favorece la diversificación?",["Correlación +1","Correlación baja o negativa","Mismo emisor"],1,"Si no se mueven igual, combinarlos puede reducir volatilidad."),
"07 · Escenarios y decisiones":("¿Qué responde una sensibilidad?",["Qué variable mueve más el resultado","El precio exacto futuro","Qué dato histórico es verdadero"],0,"Cuantifica el efecto de cambiar supuestos.")
}
if "academy_done" not in st.session_state: st.session_state.academy_done=[]
st.markdown('<div class="ac-hero"><div class="eyebrow">◈ ACADEMIA · APRENDE HACIENDO</div><h1>Las finanzas, sin misterio.</h1><p>Una ruta práctica desde cero hasta la valoración de empresas y los portafolios. Aprende el concepto, modifica los números y observa cómo cambian las decisiones.</p><span class="tag">7 rutas</span><span class="tag">Laboratorios interactivos</span><span class="tag">Retos y progreso</span></div>',unsafe_allow_html=True)
done=len(st.session_state.academy_done); progress=done/len(MODULES)
k1,k2,k3,k4=st.columns(4); k1.metric("Rutas completadas",f"{done}/{len(MODULES)}"); k2.metric("Avance",f"{progress:.0%}"); k3.metric("Nivel","Explorador" if done<3 else "Analista" if done<6 else "Estratega"); k4.metric("Próximo paso","Continuar" if done<len(MODULES) else "Repasar")
st.progress(progress,text="Tu recorrido de aprendizaje")
with st.sidebar:
 st.markdown("## 🎓 Tu academia")
 selected=st.radio("Ruta de aprendizaje",list(MODULES.keys()))
 st.divider(); st.caption("RUTA RECOMENDADA")
 st.markdown("1. Lenguaje financiero\n2. Pronósticos\n3. WACC\n4. DCF\n5. Comparables y portafolios")
 st.caption("El progreso se conserva durante la sesión activa. La persistencia entre dispositivos requiere autenticación y base de datos.")
 st.link_button("← Volver a Modelación Financiera","https://modelacionfinanciera-dc24z9cnmvc3u6znfwzyik.streamlit.app/")
data=MODULES[selected]
st.markdown(f"### {selected}"); st.caption(f"{data['level']} · {data['time']} · {data['goal']}")
tab1,tab2,tab3=st.tabs(["📖 Aprende el concepto","🧪 Laboratorio","🎯 Comprueba lo aprendido"])
with tab1:
 a,b=st.columns([1.25,.75],gap="large")
 with a:
  st.markdown("#### La idea en palabras sencillas")
  st.markdown(f'<div class="glass"><div class="eyebrow">ANALOGÍA COTIDIANA</div><p>{data["analogy"]}</p></div>',unsafe_allow_html=True)
  st.markdown("#### Conceptos que debes dominar")
  for title,desc in data["concepts"]:
   with st.expander(title): st.write(desc)
  st.markdown("#### Fórmula clave"); st.code(data["formula"])
 with b:
  st.markdown("#### ¿Para qué sirve?")
  st.markdown(f'<div class="glass"><div class="eyebrow">APLICACIÓN REAL</div><p>{data["why"]}</p></div>',unsafe_allow_html=True)
  st.markdown("#### ¿De dónde salen los datos?"); st.info(data["source"])
  st.markdown("#### Regla de oro"); st.success("Pregunta siempre: ¿qué dato alimenta el resultado?, ¿de qué fecha es?, ¿es observado o estimado?, ¿en qué moneda está expresado?")
  st.caption("Contenido educativo. Las analogías simplifican conceptos; las decisiones reales requieren validar datos y supuestos.")
with tab2:
 st.markdown("#### Experimenta: cambia los supuestos")
 st.caption("Laboratorios didácticos; no modifican el motor de valoración principal.")
 if selected=="03 · Riesgo, CAPM y WACC":
  c1,c2=st.columns(2)
  with c1:
   rf=st.slider("Tasa libre de riesgo (%)",0.,15.,4.,.25); beta=st.slider("Beta",.2,2.5,1.,.05); premium=st.slider("Prima de mercado (%)",0.,12.,5.5,.25); kd=st.slider("Costo de deuda (%)",0.,25.,8.,.25)
  with c2:
   tax=st.slider("Impuestos (%)",0.,45.,30.,.5); dw=st.slider("Peso de deuda (%)",0,90,30,1)
  ke=rf+beta*premium; wacc=(1-dw/100)*ke+(dw/100)*kd*(1-tax/100)
  x,y=st.columns(2); x.metric("Costo del patrimonio (Ke)",f"{ke:.2f}%"); y.metric("WACC ilustrativo",f"{wacc:.2f}%")
  st.plotly_chart(go.Figure(go.Bar(x=["Ke","Kd después de impuestos","WACC"],y=[ke,kd*(1-tax/100),wacc],text=[f"{ke:.2f}%",f"{kd*(1-tax/100):.2f}%",f"{wacc:.2f}%"],textposition="outside")).update_layout(template="plotly_dark",height=320,margin=dict(l=10,r=10,t=25,b=10),yaxis_title="Porcentaje (%)",showlegend=False),use_container_width=True)
  st.caption("Supone pesos de capital a valor de mercado. Justifica cada tasa, moneda y estructura en un caso real.")
 elif selected=="04 · DCF: cuánto vale hoy":
  c1,c2=st.columns(2)
  with c1:
   fcff=st.number_input("FCFF del próximo año (millones)",min_value=1.,value=1000.,step=100.); wd=st.slider("WACC (%)",1.,25.,10.,.25); g=st.slider("Crecimiento perpetuo g (%)",0.,9.,3.,.25)
  with c2:
   years=st.slider("Años explícitos",1,10,5); debt=st.number_input("Deuda neta (millones)",min_value=0.,value=2000.,step=100.); shares=st.number_input("Acciones (millones)",min_value=.01,value=100.,step=10.)
  if g>=wd: st.error("g debe ser menor que WACC para aplicar Gordon.")
  else:
   flows=[fcff*((1+g/100)**i) for i in range(years)]; pv=sum(v/((1+wd/100)**(i+1)) for i,v in enumerate(flows)); tv=flows[-1]*(1+g/100)/(wd/100-g/100); pvt=tv/((1+wd/100)**years); ev=pv+pvt; equity=ev-debt
   q1,q2,q3=st.columns(3); q1.metric("VP de flujos",f"{pv:,.0f} M"); q2.metric("VP terminal",f"{pvt:,.0f} M"); q3.metric("Enterprise Value",f"{ev:,.0f} M")
   st.metric("Equity simplificado",f"{equity:,.0f} M"); st.metric("Valor por acción ilustrativo",f"{equity/shares:,.2f}")
   st.plotly_chart(go.Figure(go.Bar(x=[f"Año {i+1}" for i in range(years)]+["Terminal"],y=[v/((1+wd/100)**(i+1)) for i,v in enumerate(flows)]+[pvt])).update_layout(template="plotly_dark",height=290,margin=dict(l=10,r=10,t=20,b=10),yaxis_title="Valor presente (millones)"),use_container_width=True)
   st.caption("Simplificación: crecimiento uniforme, sin NCI, asociadas, caja excedente, otros claims ni ajustes de moneda. No es precio objetivo.")
 elif selected=="02 · Pronosticar el negocio":
  sales=st.number_input("Ventas actuales (millones)",min_value=1.,value=10000.,step=500.); growth=st.slider("Crecimiento anual (%)",-20.,30.,8.,.5); margin=st.slider("Margen EBITDA (%)",0.,70.,25.,.5); capex_pct=st.slider("CAPEX / ventas (%)",0.,30.,8.,.5); year=st.slider("Año proyectado",1,5,3)
  projected=sales*((1+growth/100)**year); ebitda=projected*margin/100; capex=projected*capex_pct/100
  x,y,z=st.columns(3); x.metric("Ventas",f"{projected:,.0f} M"); y.metric("EBITDA",f"{ebitda:,.0f} M"); z.metric("CAPEX",f"{capex:,.0f} M")
  st.caption("EBITDA menos CAPEX no es FCFF: faltan impuestos, capital de trabajo, depreciación y otros ajustes.")
 elif selected=="05 · Múltiplos y comparación":
  metric=st.number_input("EBITDA (millones)",min_value=1.,value=2500.,step=100.); multiple=st.slider("Múltiplo EV/EBITDA",2.,25.,8.,.25); debt=st.number_input("Deuda neta (millones)",min_value=0.,value=3000.,step=100.)
  ev=metric*multiple; st.metric("EV implícito",f"{ev:,.0f} M"); st.metric("Equity simplificado",f"{ev-debt:,.0f} M")
  st.caption("El múltiplo debe provenir de comparables defendibles y datos homogéneos. No incluye otros derechos sobre EV.")
 elif selected=="06 · Portafolios y diversificación":
  w1=st.slider("Peso activo A (%)",0,100,50,5); r1=st.slider("Rendimiento esperado A (%)",-20.,30.,10.,.5); r2=st.slider("Rendimiento esperado B (%)",-20.,30.,7.,.5); v1=st.slider("Volatilidad A (%)",1.,60.,20.,.5); v2=st.slider("Volatilidad B (%)",1.,60.,12.,.5); corr=st.slider("Correlación A/B",-1.,1.,.2,.05)
  w=w1/100; ret=w*r1/100+(1-w)*r2/100; variance=(w*v1/100)**2+((1-w)*v2/100)**2+2*w*(1-w)*(v1/100)*(v2/100)*corr; vol=math.sqrt(max(variance,0))*100
  x,y=st.columns(2); x.metric("Rendimiento esperado",f"{ret*100:.2f}%"); y.metric("Volatilidad estimada",f"{vol:.2f}%")
  st.caption("Ejercicio hipotético de dos activos. Los rendimientos no son promesas y la volatilidad no representa todo el riesgo.")
 elif selected=="07 · Escenarios y decisiones":
  base=st.number_input("Valor base (millones)",min_value=1.,value=20000.,step=500.); down=st.slider("Choque adverso (%)",-60.,0.,-20.,1.); up=st.slider("Escenario favorable (%)",0.,60.,20.,1.)
  x,y,z=st.columns(3); x.metric("Adverso",f"{base*(1+down/100):,.0f} M"); y.metric("Base",f"{base:,.0f} M"); z.metric("Favorable",f"{base*(1+up/100):,.0f} M")
  st.caption("Los escenarios deben combinar hipótesis coherentes, no porcentajes arbitrarios.")
 else:
  sales=st.number_input("Ingresos (millones)",min_value=1.,value=10000.,step=500.); costs=st.slider("Costos y gastos operativos (%)",0.,100.,75.,.5); st.metric("EBITDA didáctico",f"{sales*(1-costs/100):,.0f} M")
  st.caption("Simplificación educativa: un estado de resultados real puede incluir otras partidas.")
with tab3:
 question,options,correct,explanation=QUIZZES[selected]; st.markdown("#### Reto de comprensión"); st.write(question); answer=st.radio("Selecciona una respuesta",options,key="quiz_"+selected)
 if st.button("Comprobar respuesta",type="primary",key="check_"+selected):
  if options.index(answer)==correct:
   st.success("¡Correcto! "+explanation)
   if selected not in st.session_state.academy_done: st.session_state.academy_done.append(selected)
  else: st.error("Repasa el concepto. "+explanation)
 if selected in st.session_state.academy_done: st.success("Ruta completada. Puedes volver a practicar.")
 st.caption("El progreso de esta versión se guarda en la sesión activa; no se almacena información personal.")
st.divider(); st.markdown("### Tu mapa de aprendizaje")
cols=st.columns(4)
for i,(name,mod) in enumerate(MODULES.items()):
 with cols[i%4]:
  completed=name in st.session_state.academy_done
  st.markdown(f'<div class="glass"><div class="eyebrow">{mod["level"]}</div><b>{name}</b><p class="muted">{mod["time"]}</p><span class="tag">{"✓ Completado" if completed else "Pendiente"}</span></div>',unsafe_allow_html=True)
st.markdown('<div style="text-align:center;color:#94a3b8;padding:2rem 0">ACADEMIA FINANCIERA · Aprende, experimenta, cuestiona y decide · Contenido educativo, no asesoría de inversión.</div>',unsafe_allow_html=True)
