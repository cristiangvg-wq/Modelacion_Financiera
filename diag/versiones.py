"""VPS de los 6 activos con la versión de código del directorio actual (datos reales Yahoo)."""
import json, os, sys
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
import modelacion_logic as L
import contraste_mercado_real as C
out = []
for n in ["ISA — Interconexión Eléctrica", "ECOPETROL", "GEB — Grupo Energía Bogotá", "MINEROS.CL", "AAPL", "PLTR"]:
    try:
        L.vincular_estado_sesion({})
        if n in L.EMPRESAS:
            L.preparar_empresa(n); nombre = n
        else:
            ok, _h, nombre, _ = L.buscar_y_descargar_empresa(n)
        p = L.params_empresa(nombre)
        m = C.correr(nombre)["4"]
        out.append({"activo": n, "vps": m.get("vps_modelo"), "precio": m.get("precio_mercado"), "upside": m.get("upside"),
                    "wacc": m.get("wacc_calc"), "g": p.get("g"), "tax": p.get("tax"), "nci": p.get("nci"),
                    "asociados": p.get("asociados"), "ev": m.get("val_ev")})
    except Exception as e:
        out.append({"activo": n, "error": str(e)[:200]})
print(json.dumps(out, ensure_ascii=False, default=str))
