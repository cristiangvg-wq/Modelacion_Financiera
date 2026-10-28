import os, sys, shutil
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ); sys.path.insert(0, os.path.join(RAIZ, "scripts"))
import modelacion_logic as L, contraste_mercado_real as C
os.makedirs("out/pdf", exist_ok=True)
def pdf_de(nombre, preparar):
    L.vincular_estado_sesion({})
    if preparar: L.preparar_empresa(nombre)
    C.correr(nombre)
    p = L.params_empresa(nombre); rf, erp, crp, gmax = L._capm_para_ui(p); H = L.horizonte_recomendado(nombre)
    a = (p["de_ratio"], p["kd"], p["tax"], p["g"])
    r = L.tab7_informe_ejecutivo(nombre, None, H, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"],
                                 p.get("inversion_inicial", 0), rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0),
                                 p.get("otros_claims", 0), p.get("asociados", 0), p.get("acciones"), p.get("exit_multiple", 8.0), True, gmax)
    ruta = r[3]
    m4 = L.metricas_valoracion_sesion(nombre) or {}
    print(nombre, ruta, "eq_pes tab4", m4.get("equity_pesimista"), "vps", m4.get("vps_modelo"))
    if ruta: shutil.copy(ruta, f"out/pdf/{nombre.split(' ')[0]}.pdf")
pdf_de("ISA — Interconexión Eléctrica", True)
for tk in ["MINEROS.CL", "AAPL"]:
    L.vincular_estado_sesion({}); ok, html, nombre, _ = L.buscar_y_descargar_empresa(tk)
    try:
        C.correr(nombre)
        p = L.params_empresa(nombre); rf, erp, crp, gmax = L._capm_para_ui(p); H = L.horizonte_recomendado(nombre)
        a = (p["de_ratio"], p["kd"], p["tax"], p["g"])
        r = L.tab7_informe_ejecutivo(nombre, None, H, *a, 0.0, p["beta_u"], p["capital_invertido"], p["deuda_neta"], p.get("inversion_inicial", 0), rf, erp, crp, True, p.get("caja", 0), p.get("nci", 0), p.get("otros_claims", 0), p.get("asociados", 0), p.get("acciones"), p.get("exit_multiple", 8.0), True, gmax)
        m4 = L.metricas_valoracion_sesion(nombre) or {}
        print(nombre, r[3], "eq_pes tab4", m4.get("equity_pesimista"), "vps", m4.get("vps_modelo"))
        if r[3]: shutil.copy(r[3], f"out/pdf/{tk.split('.')[0]}.pdf")
    except Exception as e:
        import traceback; traceback.print_exc()
