"""Live air quality, proxied and cached (README §7.2). Never fails hard: status ok | stale | unavailable.

K (gios):            api.gios.gov.pl/pjp-api/v1/rest — station/findAll + aqindex/getIndex/{id}; 2 req/min → rate limiter.
P (chmi_or_golemio): opendata.chmi.cz/air_quality/now — metadata.json (stations) + airquality_1h_avg_CZ.csv (all values).
Verified against the live services on 2026-10-03.
"""
from __future__ import annotations

import csv
import io
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import numpy as np
from cachetools import TTLCache

from .config import settings
from .data import haversine_km

log = logging.getLogger("kompas.live")
UA = {"User-Agent": "Kompas/0.1 (HackYeah 2026 demo)"}
AIR_TTL = 600

GIOS = "https://api.gios.gov.pl/pjp-api/v1/rest"
CHMI = "https://opendata.chmi.cz/air_quality/now"
CHMI_INDEX = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}  # ČHMÚ INDX id (1A…3B) → common 0–5 scale

_lock = threading.Lock()
_cache: TTLCache = TTLCache(maxsize=256, ttl=AIR_TTL)       # fresh values
_stale: dict = {}                                           # last good value per key (served as "stale")
_static: TTLCache = TTLCache(maxsize=16, ttl=24 * 3600)     # station lists / metadata
_gios_calls: deque = deque()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url: str, **params):
    r = httpx.get(url, params=params or None, headers=UA, timeout=8.0)
    r.raise_for_status()
    return r


def _gios_allowed() -> bool:
    """GIOŚ allows ~2 req/min. Refuse (→ serve stale) rather than get blocked."""
    now = time.monotonic()
    while _gios_calls and now - _gios_calls[0] > 60:
        _gios_calls.popleft()
    if len(_gios_calls) >= 2:
        return False
    _gios_calls.append(now)
    return True


def _local_to_utc(s: str | None, tz: str) -> str | None:
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo(tz))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


# ───────────────────────────────────────── GIOŚ (Kraków)
def _gios_stations(bbox) -> list[dict]:
    key = ("gios_stations",)
    if key not in _static:
        if not _gios_allowed():
            raise RuntimeError("GIOŚ rate limit")
        d = _get(f"{GIOS}/station/findAll", size=500).json()
        lst = next(v for k, v in d.items() if k.startswith("Lista"))
        _static[key] = [{"id": str(s["Identyfikator stacji"]), "name": s["Nazwa stacji"],
                         "lat": float(s["WGS84 φ N"]), "lon": float(s["WGS84 λ E"])} for s in lst]
    pad = 0.1
    return [s for s in _static[key] if bbox[1] - pad <= s["lat"] <= bbox[3] + pad and bbox[0] - pad <= s["lon"] <= bbox[2] + pad]


def _gios(cc: dict, lat: float, lon: float) -> dict:
    stations = _gios_stations(cc["bbox"])
    if not stations:
        raise RuntimeError("no GIOŚ station near the city")
    d = haversine_km(lat, lon, np.array([s["lat"] for s in stations]), np.array([s["lon"] for s in stations]))
    st = stations[int(np.argmin(d))]
    key = ("gios_index", st["id"])
    if key not in _cache:
        if not _gios_allowed():
            raise RuntimeError("GIOŚ rate limit")
        idx = _get(f"{GIOS}/aqindex/getIndex/{st['id']}").json()["AqIndex"]
        level = idx.get("Wartość indeksu")
        if level is None or level < 0:   # "Brak indeksu" → worst available pollutant sub-index
            subs = [v for k, v in idx.items() if k.startswith("Wartość indeksu dla wskaźnika") and isinstance(v, int) and v >= 0]
            level = max(subs) if subs else None
        measured = next((v for k, v in idx.items() if k.startswith("Data danych źródłowych") and v), None)
        _cache[key] = {"level": level, "measuredAt": _local_to_utc(measured or idx.get("Data wykonania obliczeń indeksu"), cc["timezone"])}
    v = _cache[key]
    return {"source": "GIOŚ", "station": {**st, "distanceKm": round(float(d.min()), 2)}, "level": v["level"],
            "pollutants": {"pm25": None, "pm10": None, "no2": None, "o3": None}, "measuredAt": v["measuredAt"]}


# ───────────────────────────────────────── ČHMÚ (Praha)
def _chmi_registry() -> dict:
    key = ("chmi_meta",)
    if key not in _static:
        meta = _get(f"{CHMI}/metadata/metadata.json").json()["data"]["Localities"]
        stations, regs = {}, {}
        for loc in meta:
            ll = loc.get("Localization", {})
            if ll.get("LatAsNumber") is None:
                continue
            stations[loc["LocalityCode"]] = {"id": loc["LocalityCode"], "name": loc["Name"],
                                             "lat": float(ll["LatAsNumber"]), "lon": float(ll["LonAsNumber"])}
            for prog in loc.get("MeasuringPrograms", []):
                for m in prog.get("Measurements", []):
                    regs[int(m["IdRegistration"])] = (loc["LocalityCode"], m["ComponentCode"])
        _static[key] = {"stations": stations, "regs": regs}
    return _static[key]


def _chmi_values() -> dict:
    key = ("chmi_now",)
    if key not in _cache:
        reg = _chmi_registry()["regs"]
        text = _get(f"{CHMI}/data/airquality_1h_avg_CZ.csv").text
        vals: dict[str, dict] = {}
        for row in csv.DictReader(io.StringIO(text), skipinitialspace=True):
            r = reg.get(int(row["idRegistration"]))
            if not r or row["idValueType"] not in ("8", "9", "148"):
                continue
            code, comp = r
            st = vals.setdefault(code, {"time": row["startTime"]})
            st[comp] = float(row["value"])
        _cache[key] = vals
    return _cache[key]


def _chmi(cc: dict, lat: float, lon: float) -> dict:
    reg = _chmi_registry()
    vals = _chmi_values()
    cands = [reg["stations"][c] for c, v in vals.items() if c in reg["stations"] and "INDX" in v and v["INDX"] in CHMI_INDEX]
    if not cands:
        raise RuntimeError("no ČHMÚ station with an index")
    d = haversine_km(lat, lon, np.array([s["lat"] for s in cands]), np.array([s["lon"] for s in cands]))
    st = cands[int(np.argmin(d))]
    v = vals[st["id"]]
    return {"source": "ČHMÚ", "station": {**st, "distanceKm": round(float(d.min()), 2)},
            "level": CHMI_INDEX.get(int(v["INDX"])),
            "pollutants": {"pm25": v.get("PM2_5"), "pm10": v.get("PM10"), "no2": v.get("NO2"), "o3": v.get("O3")},
            "measuredAt": v.get("time")}


PROVIDERS = {"gios": _gios, "chmi_or_golemio": _chmi, "chmi": _chmi}


def air(city: str, cc: dict, lat: float, lon: float) -> dict:
    provider = cc.get("live", {}).get("air")
    fn = PROVIDERS.get(provider)
    key = (city, round(lat, 2), round(lon, 2))
    base = {"city": city, "fetchedAt": _now(), "cacheTtlS": AIR_TTL}
    if fn is None or settings().offline:
        return {**base, "status": "unavailable", "source": provider or "none", "station": None, "level": None,
                "pollutants": {}, "measuredAt": None}
    try:
        with _lock:
            out = fn(cc, lat, lon)
        _stale[key] = out
        return {**base, "status": "ok", **out}
    except Exception as e:  # noqa: BLE001
        log.warning("live air %s failed: %s", city, e)
        if key in _stale:
            return {**base, "status": "stale", **_stale[key]}
        return {**base, "status": "unavailable", "source": "GIOŚ" if provider == "gios" else "ČHMÚ", "station": None,
                "level": None, "pollutants": {}, "measuredAt": None}
