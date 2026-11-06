"""Cliente Yahoo Finance con reintentos, caché e instantáneas reproducibles.

Problemas que corrige (auditoría nov-2026):
  · Cada clic creaba varios yf.Ticker para el mismo símbolo (info, financials, cashflow, balance
    y precio por separado). En Streamlit Cloud la IP es compartida y Yahoo responde con límites de
    tasa (YFRateLimitError) o con info vacío: el error se traducía en «sin datos» sin reintento.
  · Nada de lo descargado se guardaba: Yahoo revisa cifras y la misma valoración no podía
    reproducirse días después (requisito de trazabilidad del proyecto y del taller).

Diseño:
  · YahooCliente.descargar(ticker) hace UNA pasada por símbolo, con reintento exponencial solo
    ante errores transitorios, y devuelve una Snapshot inmutable con fecha UTC, versión de
    yfinance y huella SHA-256 del contenido.
  · Snapshot.guardar()/cargar() persisten en JSON (sin dependencias extra como pyarrow).
  · TickerReplay expone la interfaz de yfinance.Ticker sobre una Snapshot, de modo que el motor
    existente (descargar_financieros_yfinance, _completar_info_yahoo) corre igual con datos
    guardados que con datos en vivo.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Tablas que el motor consume. quarterly_income_stmt alimenta los 12 meses (LTM) de _completar_info_yahoo.
TABLAS = ("financials", "cashflow", "balance_sheet", "quarterly_income_stmt")


class DatosNoDisponibles(RuntimeError):
    """La fuente no devolvió datos usables tras los reintentos (no es un dato en cero)."""


def _es_transitorio(exc: BaseException) -> bool:
    """Límite de tasa, timeout o error de red: vale la pena reintentar. Un ticker inexistente no."""
    nombre = type(exc).__name__.lower()
    texto = str(exc).lower()
    claves = ("ratelimit", "rate limit", "too many requests", "429", "timeout", "timed out",
              "connection", "temporarily", "502", "503", "504", "curl: (28)", "curl: (35)")
    return any(k in nombre or k in texto for k in claves)


def _a_json_frame(df) -> dict | None:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return None
    d = df.copy()
    d.columns = [str(c) for c in d.columns]  # fechas de cierre → texto ISO
    d.index = [str(i) for i in d.index]
    return json.loads(d.to_json(orient="split", date_format="iso"))


def _de_json_frame(obj, columnas_fecha: bool) -> pd.DataFrame:
    if not obj:
        return pd.DataFrame()
    df = pd.DataFrame(obj["data"], index=obj["index"], columns=obj["columns"])
    if columnas_fecha:  # yfinance entrega columnas Timestamp (cierres fiscales)
        try:
            df.columns = pd.to_datetime(df.columns)
        except (ValueError, TypeError):
            pass
    return df.apply(pd.to_numeric, errors="coerce")


def _info_serializable(info: dict) -> dict:
    out = {}
    for k, v in (info or {}).items():
        if isinstance(v, (str, bool, int)) or v is None:
            out[k] = v
        elif isinstance(v, float):
            out[k] = v if np.isfinite(v) else None
        elif isinstance(v, (np.integer, np.floating)):
            fv = float(v)
            out[k] = fv if np.isfinite(fv) else None
    return out  # se descartan objetos no serializables (no los usa el motor)


@dataclass(frozen=True)
class Snapshot:
    """Lo que Yahoo devolvió para un símbolo en un instante. Inmutable y fechado."""

    ticker: str
    descargado_utc: str
    version_yfinance: str
    info: dict
    tablas: dict                      # nombre → DataFrame (filas = partidas, columnas = cierres)
    precios: pd.DataFrame             # OHLC diario ajustado (auto_adjust=True)
    errores: dict = field(default_factory=dict)

    @property
    def huella(self) -> str:
        """SHA-256 del contenido (no de la fecha): dos descargas idénticas tienen la misma huella."""
        h = hashlib.sha256()
        h.update(json.dumps(_info_serializable(self.info), sort_keys=True, default=str).encode())
        for k in sorted(self.tablas):
            h.update(k.encode())
            h.update(json.dumps(_a_json_frame(self.tablas[k]), sort_keys=True, default=str).encode())
        h.update(json.dumps(_a_json_frame(self.precios), sort_keys=True, default=str).encode())
        return h.hexdigest()

    def a_dict(self) -> dict:
        return {
            "ticker": self.ticker, "descargado_utc": self.descargado_utc,
            "version_yfinance": self.version_yfinance, "huella_sha256": self.huella,
            "info": _info_serializable(self.info),
            "tablas": {k: _a_json_frame(v) for k, v in self.tablas.items()},
            "precios": _a_json_frame(self.precios), "errores": dict(self.errores),
        }

    def guardar(self, carpeta: str | Path) -> Path:
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        sello = self.descargado_utc.replace(":", "").replace("-", "")[:15]
        ruta = carpeta / f"{self.ticker.replace('^', '_')}_{sello}.json"
        ruta.write_text(json.dumps(self.a_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        return ruta

    @classmethod
    def cargar(cls, ruta: str | Path) -> "Snapshot":
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        tablas = {k: _de_json_frame(v, columnas_fecha=True) for k, v in (d.get("tablas") or {}).items()}
        precios = _de_json_frame(d.get("precios"), columnas_fecha=False)
        if not precios.empty:
            precios.index = pd.to_datetime(precios.index)
        snap = cls(ticker=d["ticker"], descargado_utc=d["descargado_utc"],
                   version_yfinance=d.get("version_yfinance", "N/D"), info=d.get("info") or {},
                   tablas=tablas, precios=precios, errores=d.get("errores") or {})
        if d.get("huella_sha256") and d["huella_sha256"] != snap.huella:
            raise ValueError(f"Instantánea alterada o corrupta: la huella no coincide ({ruta}).")
        return snap


class TickerReplay:
    """Interfaz mínima de yfinance.Ticker servida desde una Snapshot (sin red)."""

    def __init__(self, snap: Snapshot):
        self._s = snap
        self.ticker = snap.ticker

    @property
    def info(self) -> dict:
        return dict(self._s.info)

    def get_info(self) -> dict:
        return self.info

    def __getattr__(self, nombre):
        if nombre in TABLAS or nombre in ("income_stmt", "quarterly_financials"):
            alias = {"income_stmt": "financials", "quarterly_financials": "quarterly_income_stmt"}
            return self._s.tablas.get(alias.get(nombre, nombre), pd.DataFrame())
        raise AttributeError(nombre)

    def history(self, period=None, interval="1d", auto_adjust=True, **_):
        p = self._s.precios
        if p.empty:
            return p
        if interval in ("1wk", "1w"):
            return p.resample("W-FRI").last().dropna(how="all")
        return p.copy()


class YahooCliente:
    """Descarga con reintentos y caché en memoria (TTL). Seguro entre hilos de Streamlit."""

    def __init__(self, reintentos: int = 3, espera_base: float = 1.5, ttl_seg: int = 900,
                 fabrica_ticker: Callable | None = None, dormir: Callable[[float], None] = time.sleep):
        self.reintentos = int(reintentos)
        self.espera_base = float(espera_base)
        self.ttl = int(ttl_seg)
        self._dormir = dormir
        self._cache: dict[tuple, tuple[float, Snapshot]] = {}
        self._lock = threading.Lock()
        if fabrica_ticker is None:
            import yfinance as yf  # import diferido: el módulo se puede probar sin red
            fabrica_ticker = yf.Ticker
            self.version = getattr(yf, "__version__", "N/D")
        else:
            self.version = "inyectada"
        self._fabrica = fabrica_ticker

    def _con_reintento(self, etiqueta: str, fn: Callable):
        ultimo = None
        for intento in range(self.reintentos + 1):
            try:
                return fn()
            except Exception as exc:  # noqa: BLE001 - se clasifica abajo
                ultimo = exc
                if not _es_transitorio(exc) or intento == self.reintentos:
                    break
                espera = self.espera_base * (2 ** intento) * (1 + 0.25 * random.random())
                log.warning("Yahoo %s: %s (reintento %d en %.1fs)", etiqueta, exc, intento + 1, espera)
                self._dormir(espera)
        raise DatosNoDisponibles(f"{etiqueta}: {type(ultimo).__name__}: {ultimo}") from ultimo

    def descargar(self, ticker: str, periodo_precios: str = "5y", usar_cache: bool = True) -> Snapshot:
        clave = (str(ticker).upper(), periodo_precios)
        ahora = time.time()
        if usar_cache:
            with self._lock:
                hit = self._cache.get(clave)
                if hit and ahora - hit[0] < self.ttl:
                    return hit[1]
        t = self._fabrica(clave[0])
        errores: dict[str, str] = {}

        def _info():
            d = getattr(t, "info", None) or {}
            if not d and hasattr(t, "get_info"):
                d = t.get_info() or {}
            if not d:
                raise ConnectionError("info vacío (frecuente bajo límite de tasa)")
            return d

        try:
            info = self._con_reintento(f"{clave[0]} info", _info)
        except DatosNoDisponibles as e:
            info, errores["info"] = {}, str(e)
        tablas = {}
        for nombre in TABLAS:
            try:
                df = self._con_reintento(f"{clave[0]} {nombre}", lambda n=nombre: getattr(t, n))
                tablas[nombre] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
            except DatosNoDisponibles as e:
                tablas[nombre], errores[nombre] = pd.DataFrame(), str(e)
        try:
            precios = self._con_reintento(
                f"{clave[0]} precios",
                lambda: t.history(period=periodo_precios, interval="1d", auto_adjust=True))
            precios = precios if isinstance(precios, pd.DataFrame) else pd.DataFrame()
            if not precios.empty and getattr(precios.index, "tz", None) is not None:
                precios.index = precios.index.tz_localize(None)  # fechas comparables entre bolsas
        except DatosNoDisponibles as e:
            precios, errores["precios"] = pd.DataFrame(), str(e)
        if not info and all(v.empty for v in tablas.values()) and precios.empty:
            raise DatosNoDisponibles(f"Yahoo no devolvió nada para {clave[0]}: {errores}")
        snap = Snapshot(ticker=clave[0], descargado_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        version_yfinance=self.version, info=dict(info), tablas=tablas,
                        precios=precios, errores=errores)
        with self._lock:
            self._cache[clave] = (ahora, snap)
        return snap
