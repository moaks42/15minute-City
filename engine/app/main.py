"""Kompas engine — FastAPI. The OpenAPI document served at /openapi.json IS contracts/openapi.yaml."""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import numpy as np
import yaml
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import live, ml, prefs
from .config import REPO_DIR, load_config, settings
from .data import CityData, load_all
from .geocode import GeoIndex, geocode
from .models import PrefFitRequest, ScoreRequest, decode_state
from .scoring import default_criteria, place_detail, score_response

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kompas")


class State:
    cfg = None
    cities: dict[str, CityData] = {}
    model: dict | None = None
    pooled: ml.Pooled | None = None
    geo: dict[str, GeoIndex] = {}
    default_crit: dict[str, dict[str, np.ndarray]] = {}
    built_at: str = ""


S = State()


def startup() -> None:
    t = time.perf_counter()
    S.cfg = load_config()
    S.cities = load_all(S.cfg)
    try:
        S.model, S.pooled = ml.load_or_train(S.cities, S.cfg)
    except Exception:  # noqa: BLE001 — ML is P1; the core must still serve
        log.exception("ML layer disabled")
        S.model, S.pooled = None, None
    S.geo = {c: GeoIndex(cd) for c, cd in S.cities.items()}
    S.default_crit = {c: default_criteria(cd, S.cfg) for c, cd in S.cities.items()}
    S.built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log.info("engine ready in %.1f s", time.perf_counter() - t)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not S.cities:
        startup()
    yield


app = FastAPI(title="Kompas engine", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings().cors_origins), allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=2048)

_contract = yaml.safe_load((REPO_DIR / "contracts" / "openapi.yaml").read_text(encoding="utf-8"))
app.openapi = lambda: _contract  # type: ignore[method-assign]


# ───────────────────────────────────────── errors (contract Error schema)
class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


@app.exception_handler(ApiError)
async def _api_error(_r: Request, e: ApiError):
    return JSONResponse(status_code=e.status, content={"error": {"code": e.code, "message": e.message}})


@app.exception_handler(RequestValidationError)
async def _invalid(_r: Request, e: RequestValidationError):
    msg = "; ".join(f"{'/'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:5])
    return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": msg}})


def city_or_404(city: str) -> CityData:
    cd = S.cities.get(city)
    if cd is None:
        raise ApiError(404, "unknown_city", f"unknown city {city!r}; known: {sorted(S.cities)}")
    return cd


def cell_or_404(cd: CityData, h3: str) -> int:
    i = cd.index.get(h3)
    if i is None:
        raise ApiError(404, "unknown_cell", f"{h3} is not a cell of {cd.city}")
    return i


def lang_of(cd: CityData, lang: str | None) -> str:
    return lang if lang in ("pl", "cs", "en") else cd.cc["defaultLang"]


def coverage(cd: CityData) -> dict[str, float]:
    out = {}
    for crit in S.cfg.criteria:
        if crit.get("runtime"):
            out[crit["id"]] = 1.0 if cd.tt else 0.0
            continue
        js = [j for j, s in enumerate(cd.specs) if s.criterion == crit["id"] and not s.is_alias and s.weight > 0]
        tw = sum(cd.specs[j].weight for j in js)
        out[crit["id"]] = round(float(sum(cd.specs[j].weight * cd.coverage[j] for j in js) / tw), 3) if tw else 0.0
    return out


# ───────────────────────────────────────── core
@app.get("/api/health")
def health():
    return {"status": "ok" if all(cd.source == "real" for cd in S.cities.values()) else "degraded",
            "dataVersion": {c: cd.data_version for c, cd in S.cities.items()},
            "dataSource": {c: cd.source for c, cd in S.cities.items()}, "builtAt": S.built_at}


@app.get("/api/cities")
def cities():
    out = []
    for c, cd in S.cities.items():
        cc = cd.cc
        out.append({"id": c, "name": cc["name"], "country": cc["country"], "defaultLang": cc["defaultLang"],
                    "currency": cc["currency"], "center": cc["center"], "zoom": cc["zoom"], "bbox": cc["bbox"],
                    "priceMode": cc["price"]["mode"], "coverage": coverage(cd), "dataVersion": cd.data_version,
                    "dataSource": cd.source})
    return out


@app.get("/api/{city}/meta")
def meta(city: str, lang: str | None = None):
    cd = city_or_404(city)
    cfg, cc = S.cfg, cd.cc
    cov = coverage(cd)
    crits = []
    for crit in cfg.criteria:
        inds = []
        for s in cfg.indicators[city]:
            if s.criterion != crit["id"]:
                continue
            j = next((j for j, x in enumerate(cd.specs) if x.key == s.key), None)
            c = float(cd.coverage[j]) if j is not None else 0.0
            inds.append({"id": s.id, "column": s.column, "label": s.label, "unit": s.unit,
                         "unitLabel": cfg.raw["units"][s.unit], "decimals": s.decimals, "norm": s.norm, "weight": s.weight,
                         "walkScaled": s.walk_scaled, "crossCity": s.cross_city, "priority": s.priority,
                         "coverage": round(c, 3), "available": j is not None and c > 0,
                         "sources": s.sources.get(city, [])})
        srcs = crit.get("sources", {}).get(city) or sorted({k for i in inds for k in i["sources"]})
        crits.append({"id": crit["id"], "emoji": crit["emoji"], "label": crit["label"], "runtime": crit.get("runtime"),
                      "caveat": crit.get("caveat"), "coverage": cov[crit["id"]], "beta": cov[crit["id"]] < 0.5,
                      "sources": srcs, "indicators": inds})
    pcol = cd.col(cc["price"]["column"])
    pv = pcol[cd.habitable] if pcol is not None else np.array([])
    pv = pv[~np.isnan(pv)]
    return {
        "city": city, "dataVersion": cd.data_version, "dataSource": cd.source, "walkSpeedKmh": cfg.raw["walkSpeedKmh"],
        "levels": [{"level": int(l), "weight": w, "emoji": cfg.raw["levelEmoji"][l], "label": cfg.raw["levelLabel"][l]}
                   for l, w in cfg.raw["levels"].items()],
        "criteria": crits,
        "personas": [{k: p[k] for k in ("id", "emoji", "label", "weights", "indicatorWeights", "walkFactor", "suggestedAnchors")}
                     for p in cfg.raw["personas"]],
        "mustHaveCategories": [{"id": m["id"], "emoji": m["emoji"], "label": m["label"],
                                "available": city in m.get("cities", [city]) and cd.col(m["column"]) is not None
                                and bool(np.isfinite(cd.col(m["column"])[cd.habitable]).any())}
                               for m in cfg.raw["mustHaveCategories"]],
        "archetypes": [{"id": a["id"], "emoji": a["emoji"]} for a in cfg.raw["archetypes"]],
        "modes": [{"id": k, "emoji": v["emoji"], "label": v["label"]} for k, v in cfg.raw["modes"].items() if k in cd.tt],
        "price": {"indicator": cc["price"]["indicator"], "mode": cc["price"]["mode"], "currency": cc["currency"],
                  "unit": cc["price"]["unit"], "filterField": cc["price"]["filterField"], "budgetField": cc["price"]["budgetField"],
                  "cityMedian": float(np.median(pv)) if len(pv) else None,
                  "min": float(pv.min()) if len(pv) else None, "max": float(pv.max()) if len(pv) else None},
        "adminLevels": {k: {"label": cc["levels"][k]["label"], "count": cc["levels"][k].get("count")} for k in ("district", "neighborhood")},
        "manifest": [{"key": m.get("key"), "url": m.get("url"), "fetchedAt": m.get("fetchedAt"), "licence": m.get("licence"),
                      "rows": m.get("rows"), "status": m.get("status", "missing"), "note": m.get("note")} for m in cd.manifest],
    }


@app.get("/api/{city}/grid")
def grid(city: str):
    cd = city_or_404(city)
    return FileResponse(cd.grid_path, media_type="application/geo+json", headers={"Cache-Control": "public, max-age=3600"})


@app.post("/api/{city}/score")
def score(city: str, req: ScoreRequest):
    cd = city_or_404(city)
    return JSONResponse(score_response(cd, S.cfg, req))


@app.get("/api/{city}/place/{h3}")
def place(city: str, h3: str, lang: str | None = None, state: str | None = None):
    cd = city_or_404(city)
    i = cell_or_404(cd, h3)
    try:
        req = decode_state(state) or ScoreRequest(persona="custom", weights=S.cfg.persona("custom")["weights"])
    except Exception as e:  # noqa: BLE001
        raise ApiError(422, "invalid_request", f"bad state: {e}") from e
    req.lang = lang_of(cd, lang or req.lang)
    return place_detail(cd, S.cfg, req, i)


@app.get("/api/{city}/commute")
def commute(city: str, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180), mode: str = "transit"):
    cd = city_or_404(city)
    t = time.perf_counter()
    if mode not in ("transit", "bike", "walk"):
        raise ApiError(422, "invalid_request", f"mode must be transit|bike|walk, got {mode!r}")
    if mode not in cd.tt:
        raise ApiError(503, "unavailable", f"no {mode} travel times for {city}")
    j = cd.nearest_dest(lat, lon)
    if j is None:
        raise ApiError(422, "out_of_area", f"({lat}, {lon}) is outside the routed area of {city}")
    m = cd.minutes_to(lat, lon, mode)
    idx = np.flatnonzero(m <= 120)
    cells = [[cd.cells[i], int(m[i])] for i in idx]
    return JSONResponse({"city": city, "anchorCell": cd.tt_dests[j], "mode": mode, "maxMinutes": 120, "cells": cells,
                         "computeMs": round((time.perf_counter() - t) * 1000, 2)})


@app.get("/api/{city}/districts")
def districts(city: str, level: str = "district"):
    cd = city_or_404(city)
    groups = cd.districts if level == "district" else cd.neighborhoods
    return {"city": city, "level": "district" if level == "district" else "neighborhood",
            "items": [{"id": g.id, "name": g.name, "centroid": {"lat": round(g.lat, 6), "lon": round(g.lon, 6)},
                       "cellCount": int(len(g.members)), "habitableCount": int(len(g.habitable)), "populationEst": g.population}
                      for g in sorted(groups.values(), key=lambda g: g.name)]}


@app.get("/api/{city}/geocode")
def geocode_ep(city: str, q: str = Query(min_length=2), limit: int = Query(8, ge=1, le=20), lang: str | None = None):
    city_or_404(city)
    return geocode(S.geo[city], q, limit)


# ───────────────────────────────────────── ML
def _ml_or_503():
    if S.pooled is None:
        raise ApiError(503, "unavailable", "ML layer not available")
    return S.pooled


def _place_ref(cd: CityData, i: int, sim: float, other_crit: dict | None = None) -> dict:
    from .scoring import archetype
    crit = {c: float(s[i]) for c, s in S.default_crit[cd.city].items()}
    return {"id": cd.cells[i], "kind": "hex", "name": cd.neighborhood[i] or cd.district_name[i],
            "district": {"id": str(cd.district_id[i]), "name": str(cd.district_name[i])},
            "centroid": {"lat": round(float(cd.lat[i]), 6), "lon": round(float(cd.lon[i]), 6)},
            "similarity": round(min(max(float(sim), 0.0), 1.0), 3), "archetype": archetype(cd, np.array([i])),
            "sharedTraits": ml.shared_traits(other_crit, crit) if other_crit else []}


@app.get("/api/{city}/similar/{h3}")
def similar(city: str, h3: str, limit: int = Query(5, ge=1, le=20), lang: str | None = None):
    import h3 as h3lib
    cd = city_or_404(city)
    i = cell_or_404(cd, h3)
    pooled = _ml_or_503()
    Z = pooled.Z[city]
    sim = ml.distance_sim(Z[i], Z, pooled.d_ref[(city, city)])
    near = {cd.index[c] for c in h3lib.grid_disk(h3, 2) if c in cd.index}
    cand = np.array([j for j in np.flatnonzero(cd.habitable) if j not in near])
    groups = np.where(cd.neighborhood == None, cd.district_name, cd.neighborhood)  # noqa: E711
    groups[i] = "__self__"
    crit_i = {c: float(s[i]) for c, s in S.default_crit[city].items()}
    top = ml.diverse_top(sim, cand, groups, limit, per_group=1)
    return {"city": city, "from": h3, "items": [_place_ref(cd, j, sim[j], crit_i) for j in top]}


@app.get("/api/twins")
def twins(from_: str = Query(alias="from"), to: str = Query(...), h3: str | None = None, district: str | None = None,
          limit: int = Query(5, ge=1, le=20), lang: str | None = None):
    from .scoring import archetype
    src, dst = city_or_404(from_), city_or_404(to)
    if from_ == to:
        raise ApiError(422, "invalid_request", "from and to must be different cities")
    pooled = _ml_or_503()
    Zs, Zd = pooled.Z[from_], pooled.Z[to]
    if h3:
        i = cell_or_404(src, h3)
        q = Zs[i]
        crit_q = {c: float(s[i]) for c, s in S.default_crit[from_].items()}
        frm = {"city": from_, "id": h3, "kind": "hex", "name": src.neighborhood[i] or src.district_name[i],
               "district": {"id": str(src.district_id[i]), "name": str(src.district_name[i])},
               "centroid": {"lat": round(float(src.lat[i]), 6), "lon": round(float(src.lon[i]), 6)},
               "archetype": archetype(src, np.array([i]))}
        sim = ml.distance_sim(q, Zd, pooled.d_ref[(from_, to)])
        groups = np.where(dst.neighborhood == None, dst.district_name, dst.neighborhood)  # noqa: E711
        top = ml.diverse_top(sim, np.flatnonzero(dst.habitable), groups, limit)
        return {"from": frm, "to": to, "items": [_place_ref(dst, j, sim[j], crit_q) for j in top]}
    if district:
        g = src.districts.get(district)
        if g is None or len(g.habitable) == 0:
            raise ApiError(404, "unknown_district", f"{district} is not a district of {from_}")
        q = ml.group_vector(Zs, src, g.habitable)
        crit_q = {c: float(np.mean(s[g.habitable])) for c, s in S.default_crit[from_].items()}
        frm = {"city": from_, "id": g.id, "kind": "district", "name": g.name, "district": None,
               "centroid": {"lat": round(g.lat, 6), "lon": round(g.lon, 6)}, "archetype": archetype(src, g.habitable)}
        items = []
        for gd in dst.districts.values():
            if len(gd.habitable) == 0:
                continue
            v = ml.group_vector(Zd, dst, gd.habitable)
            sim = float(ml.distance_sim(q, v, pooled.d_ref_district[(from_, to)])[0])
            crit_d = {c: float(np.mean(s[gd.habitable])) for c, s in S.default_crit[to].items()}
            items.append((sim, {"id": gd.id, "kind": "district", "name": gd.name, "district": None,
                                "centroid": {"lat": round(gd.lat, 6), "lon": round(gd.lon, 6)},
                                "similarity": round(max(sim, 0.0), 3), "archetype": archetype(dst, gd.habitable),
                                "sharedTraits": ml.shared_traits(crit_q, crit_d, 55)}))
        items.sort(key=lambda x: -x[0])   # unclipped, so districts beyond "random" stay ordered
        return {"from": frm, "to": to, "items": [x for _, x in items[:limit]]}
    raise ApiError(422, "invalid_request", "give h3 or district")


# ───────────────────────────────────────── live
@app.get("/api/{city}/live/air")
def live_air(city: str, lat: float = Query(ge=-90, le=90), lon: float = Query(ge=-180, le=180)):
    cd = city_or_404(city)
    return live.air(city, cd.cc, lat, lon)


@app.get("/api/{city}/live/departures")
def live_departures(city: str, stopId: str):
    city_or_404(city)
    return {"city": city, "stopId": stopId, "stopName": None, "status": "unavailable", "source": "not implemented (P2)",
            "departures": [], "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


# ───────────────────────────────────────── preference learning (P2)
@app.get("/api/{city}/prefs/pairs")
def pref_pairs(city: str, n: int = Query(6, ge=2, le=12)):
    cd = city_or_404(city)
    return {"city": city, "pairs": prefs.pairs(cd, S.default_crit[city], n)}


@app.post("/api/prefs/fit")
def pref_fit(req: PrefFitRequest):
    return prefs.fit(req, S.cfg.criterion_ids)
