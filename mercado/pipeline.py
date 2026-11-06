"""Extracción → insumos fechados → motor de valoración existente.

No reimplementa ninguna fórmula: usa L.descargar_financieros_yfinance, L.derivar_params_desde_cero,
L.costo_equity_capm, L.beta_apalancado, L.calcular_wacc, L.proyectar_variables_con_meta y
L.valoracion_dcf. Lo que añade es: una sola descarga por símbolo, instantánea reproducible,
rf vigente en el momento de valorar (no al importar el módulo), beta auditable y un registro de
fuentes por insumo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import modelacion_logic as L

from . import beta as B
from . import tasas as T
from .yahoo_cliente import Snapshot, TickerReplay, YahooCliente


@dataclass
class InputsValoracion:
    ticker: str
    moneda_flujos: str
    mercado_capm: str
    rf: float
    erp: float
    crp: float
    beta_u: float | None
    beta_l: float | None
    de_mercado: float
    tax: float
    kd: float
    ke: float | None
    wacc: float | None
    g: float
    g_max_macro: float
    deuda_neta: float | None
    nci: float
    asociados: float
    acciones_millones: float | None
    fuentes: dict = field(default_factory=dict)
    avisos: list = field(default_factory=list)
    snapshot_huella: str = ""
    snapshot_fecha: str = ""

    def a_dict(self) -> dict:
        return asdict(self)


def construir_inputs(ticker: str, cliente: YahooCliente | None = None, *, snapshot: Snapshot | None = None,
                     snapshot_indice: Snapshot | None = None, simbolo_indice: str | None = None,
                     en_vivo: bool = True, proveedor_tes=None) -> tuple[InputsValoracion, "object"]:
    """Devuelve (inputs, df_hist). Con `snapshot` no se usa la red para la empresa (reproducible)."""
    if snapshot is None:
        cliente = cliente or YahooCliente()
        snapshot = cliente.descargar(ticker)
    replay = TickerReplay(snapshot)
    df_hist, msg = L.descargar_financieros_yfinance(snapshot.ticker, ticker_obj=replay)
    if df_hist is None:
        raise ValueError(f"Sin estados financieros usables para {snapshot.ticker}: {msg}")
    info = L._completar_info_yahoo(replay.info, replay, snapshot.ticker)
    info["_balance_sheet"] = replay.balance_sheet
    p = L.derivar_params_desde_cero(df_hist, info=info, ticker_yf=snapshot.ticker)

    # rf/ERP vigentes HOY en la moneda de los flujos (no los fijados al importar el módulo).
    moneda = str(df_hist.attrs.get("moneda") or "").upper()
    mercado = L.MERCADO_POR_MONEDA.get(moneda, "DEFAULT")
    tasas, avisos = T.tasas_actuales(en_vivo=en_vivo, proveedor_tes=proveedor_tes)
    capm = T.capm_mercado(mercado, tasas) if mercado in ("US", "CO") else {
        "rf": p["rf"], "erp": p["erp"], "crp": p["crp"], "rf_fuente": "parámetros de la app", "rf_bruto": p["rf"]}
    if mercado == "US" and capm["rf"] != p["rf"]:
        avisos.append(f"rf actualizada {p['rf']:.2%} → {capm['rf']:.2%} ({capm['rf_fuente']}).")

    # Beta: regresión semanal propia si hay índice declarado; si no, la regla bottom-up de Damodaran.
    simbolo_indice = simbolo_indice or B.INDICE_POR_MERCADO.get(L._mercado_desde_pais(info.get("country")) or "")
    reg = None
    if simbolo_indice and not snapshot.precios.empty:
        if snapshot_indice is None and cliente is not None:
            try:
                snapshot_indice = cliente.descargar(simbolo_indice)
            except Exception as e:
                avisos.append(f"Índice {simbolo_indice} no disponible: {e}")
        if snapshot_indice is not None and not snapshot_indice.precios.empty:
            reg = B.beta_regresion(snapshot.precios["Close"], snapshot_indice.precios["Close"])
    bd = L.damodaran_beta(info.get("sector") or "", info.get("industry") or "",
                          L._mercado_desde_pais(info.get("country")) or mercado)
    de = float(p.get("de_ratio") or 0.0)
    sel = B.seleccionar_beta_desapalancada(reg, de, p["tax"], bd, beta_min=L.BETA_REGRESION_MIN)
    if sel["beta_u"] is None:  # conserva la beta de la app (Yahoo info) y lo declara
        sel = {"beta_u": p["beta_u"], "fuente": f"app: {p.get('beta_fuente')}", "metodo": "app"}
        avisos.append("Beta propia no disponible: se usa la de la app (Yahoo `info`, metodología no auditable).")

    beta_l = L.beta_apalancado(sel["beta_u"], de, p["tax"])
    ke = L.costo_equity_capm(beta_l, rf=capm["rf"], erp=capm["erp"], crp=capm["crp"])
    # Kd: si la app lo derivó de rf_bruto + spread, se reancla al rf_bruto vigente (mismo spread).
    kd = float(p["kd"])
    rf_bruto_app = (L.CAPM_POR_MERCADO.get(mercado) or {}).get("rf_bruto")
    if ("calificación sintética" in str(p.get("kd_fuente", "")) and capm.get("rf_bruto") is not None
            and rf_bruto_app is not None):
        kd = float(capm["rf_bruto"]) + (kd - float(rf_bruto_app))  # mismo spread, base vigente
    wacc, _, _ = L.calcular_wacc(de, kd, ke, p["tax"])
    avisos += L.validar_inputs_valoracion(wacc, p["g"], g_max_macro=p["g_max_macro"],
                                          acciones=p.get("acciones"), kd=kd, rf=capm.get("rf_bruto"))
    if snapshot.errores:
        avisos.append(f"Partes no descargadas: {sorted(snapshot.errores)}")
    if df_hist.attrs.get("proxies"):
        avisos.append(f"Partidas estimadas por regla (no reportadas): {df_hist.attrs['proxies']}")

    inp = InputsValoracion(
        ticker=snapshot.ticker, moneda_flujos=moneda, mercado_capm=mercado,
        rf=capm["rf"], erp=capm["erp"], crp=capm["crp"], beta_u=sel["beta_u"], beta_l=beta_l,
        de_mercado=de, tax=p["tax"], kd=kd, ke=ke, wacc=wacc, g=p["g"], g_max_macro=p["g_max_macro"],
        deuda_neta=p.get("deuda_neta"), nci=float(p.get("nci") or 0.0),
        asociados=float(p.get("asociados_capitalizado") or p.get("asociados") or 0.0),
        acciones_millones=p.get("acciones"),
        fuentes={"rf": capm.get("rf_fuente"), "erp": capm.get("erp_fuente"), "beta": sel["fuente"],
                 "kd": p.get("kd_fuente"), "deuda": p.get("deuda_fuente"), "acciones": p.get("acciones_fuente"),
                 "tax": p.get("tax_fuente"), "financieros": msg},
        avisos=avisos, snapshot_huella=snapshot.huella, snapshot_fecha=snapshot.descargado_utc,
    )
    return inp, df_hist


def valorar(inp: InputsValoracion, df_hist, horizonte: int = 5, metodo: str = "drivers") -> dict:
    """DCF con el motor existente; el resultado lleva la huella de la instantánea usada."""
    if inp.wacc is None or inp.deuda_neta is None:
        raise ValueError("Faltan WACC o deuda neta: no se valora con insumos incompletos (N/D).")
    df_proj, meta = L.proyectar_variables_con_meta(df_hist, horizonte=horizonte, metodo=metodo, tax=inp.tax)
    nopat = float(df_proj["NOPAT"].iloc[-1]) if "NOPAT" in df_proj.columns else None
    val = L.valoracion_dcf(df_proj["FCFF"].tolist(), inp.wacc, inp.g, deuda_neta=inp.deuda_neta,
                           nci=inp.nci, asociados=inp.asociados, acciones=inp.acciones_millones,
                           g_max_macro=inp.g_max_macro, nopat_final=nopat, mid_year=True)
    val["trazabilidad"] = {"snapshot_sha256": inp.snapshot_huella, "snapshot_utc": inp.snapshot_fecha,
                           "fuentes": inp.fuentes, "avisos": inp.avisos}
    return val
