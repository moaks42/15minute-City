"""Scoring (README §6.1–6.3): vectorized over the (cells × indicators) matrix of one city."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from .config import Config
from .data import UNREACHABLE, CityData, haversine_km
from .explain import display_value, fmt_number, indicator_text, render
from .models import Anchor, ScoreRequest

COMMUTE_GOOD, COMMUTE_BAD = 15.0, 60.0
HIGHLIGHT_MIN, WARNING_MAX = 60.0, 40.0   # an explained indicator must itself be good (highlight) or bad (warning)
WALK_KMH = 4.8
DETOUR = 1.3
NEAREST = [  # category → column with network walk minutes (None → straight-line estimate)
    ("tram_stop", "transit.tram_stop_walk_min"), ("metro_station", "poi.metro_station_walk_min"),
    ("rail_station", "transit.rail_station_walk_min"), ("bus_stop", None),
    ("supermarket", "shops.supermarket_walk_min"), ("pharmacy", "health.pharmacy_walk_min"),
    ("park", "green.park_walk_min"), ("playground", None), ("nursery", "education.nursery_walk_min"),
    ("kindergarten", "education.kindergarten_walk_min"), ("primary_school", "education.primary_school_walk_min"),
    ("gp_clinic", "health.gp_walk_min"), ("university", "education.university_walk_min"),
]


@dataclass
class Ctx:
    cd: CityData
    cfg: Config
    req: ScoreRequest
    lang: str
    wf: float
    v: np.ndarray                         # (k,) effective indicator weights
    S: np.ndarray                         # (n, k) sub-scores
    crit: dict[str, np.ndarray]           # criterion → (n,) score, every criterion with data
    levels: dict[str, int]
    W: dict[str, float]                   # included criterion → level weight
    total_w: float
    Mf: np.ndarray
    M: np.ndarray
    masks: dict[str, np.ndarray]
    passing: np.ndarray
    anchors: list[Anchor]
    anchor_min: dict[str, np.ndarray | None]
    medians: dict[str, float]
    excluded: list[str]
    t0: float = field(default_factory=time.perf_counter)


def _criterion_matrix(cd: CityData, cfg: Config) -> tuple[list[str], np.ndarray]:
    key = "_G"
    cached = getattr(cd, key, None)
    if cached is None:
        crit_ids = [c["id"] for c in cfg.criteria if not c.get("runtime")]
        G = np.zeros((cd.k, len(crit_ids)), dtype=np.float32)
        for j, s in enumerate(cd.specs):
            G[j, crit_ids.index(s.criterion)] = 1.0
        cached = (crit_ids, G)
        setattr(cd, key, cached)
    return cached


def effective_weights(cd: CityData, cfg: Config, req: ScoreRequest) -> np.ndarray:
    pers_iw = cfg.persona(req.persona).get("indicatorWeights", {}) or {}
    req_iw = req.indicatorWeights or {}
    v = np.zeros(cd.k, dtype=np.float32)
    for j, s in enumerate(cd.specs):
        if not cd.available(j):
            continue
        w = s.weight
        if s.key in pers_iw:
            w = pers_iw[s.key]
        if s.key in req_iw:
            w = req_iw[s.key]
        elif not s.is_alias and s.column in req_iw:
            w = req_iw[s.column]
        v[j] = max(0.0, float(w))
    return v


def _decay(t: np.ndarray, good: float, bad: float) -> np.ndarray:
    return np.clip((t - bad) / (good - bad) * 100.0, 0.0, 100.0)


def compute(cd: CityData, cfg: Config, req: ScoreRequest) -> Ctx:
    t0 = time.perf_counter()
    cc = cd.cc
    lang = req.lang or cc["defaultLang"]
    pers = cfg.persona(req.persona)
    wf = float(pers.get("walkFactor", 1.0))
    S = cd.normalized(wf)
    v = effective_weights(cd, cfg, req)

    crit_ids, G = _criterion_matrix(cd, cfg)
    Wm = G * v[:, None]
    den = Wm.sum(axis=0)
    ok = den > 0
    crit_mat = np.zeros((cd.n, len(crit_ids)), dtype=np.float32)
    if ok.any():
        crit_mat[:, ok] = (S @ Wm[:, ok]) / den[ok]
    crit = {c: crit_mat[:, i] for i, c in enumerate(crit_ids) if ok[i]}

    # commute (runtime criterion)
    anchors = list(req.anchors)
    anchor_min: dict[str, np.ndarray | None] = {a.id: cd.minutes_to(a.lat, a.lon, a.mode) for a in anchors}
    usable = [a for a in anchors if anchor_min[a.id] is not None]
    if usable:
        num = np.zeros(cd.n, dtype=np.float64)
        wsum = 0.0
        for a in usable:
            w = cfg.level_weight(a.level)
            num += w * _decay(anchor_min[a.id].astype(np.float64), COMMUTE_GOOD, COMMUTE_BAD)
            wsum += w
        crit["commute"] = (num / wsum).astype(np.float32)

    defaults = pers.get("weights", {})
    levels = {c: int(req.weights.get(c, defaults.get(c, 0) if req.persona else 0)) for c in cfg.criterion_ids}
    levels = {c: max(0, min(5, lv)) for c, lv in levels.items()}
    W = {c: cfg.level_weight(lv) for c, lv in levels.items() if lv > 0 and c in crit}
    excluded = [c for c, lv in levels.items() if lv > 0 and c not in crit]
    # Match % is a weighted average, so only the ratios between levels matter (all 😐 ranks exactly like all 🤩).
    if not W:  # everything skipped → neutral ranking over all criteria with data; the web shows a neutral state
        W = {c: 1.0 for c in crit}
    total_w = float(sum(W.values()))
    Mf = np.zeros(cd.n, dtype=np.float64)
    for c, w in W.items():
        Mf += w * crit[c]
    Mf /= total_w
    M = np.clip(np.rint(Mf), 0, 100).astype(np.int64)

    hab = cd.habitable
    medians = {c: float(np.median(s[hab])) for c, s in crit.items()}

    # hard filters
    f = req.filters
    masks: dict[str, np.ndarray] = {}
    price_field = cc["price"]["filterField"]
    pmax = getattr(f, price_field, None)
    price = cd.col_filled(cc["price"]["column"])      # unknown → city median (flagged imputed), as in scoring
    if pmax is not None and price is not None and not np.isnan(price).all():
        masks["price"] = price <= pmax
    noise = cd.col_filled("environment.noise_db")
    if f.maxNoiseDb is not None and noise is not None and not np.isnan(noise).all():
        masks["noise"] = noise <= f.maxNoiseDb
    for mh in f.mustHave:
        cat = cfg.must_have(mh.category)
        if cat is None or cd.city not in cat.get("cities", [cd.city]):
            continue
        col = cd.col(cat["column"])
        if col is None or not np.isfinite(col[hab]).any():
            continue
        with np.errstate(invalid="ignore"):
            masks[f"mustHave:{mh.category}"] = col <= mh.maxWalkMin   # NaN → cannot confirm → fails
    for a in usable:
        lim = a.maxMinutes or f.maxCommuteMinutes
        if lim:
            masks[f"commute:{a.id}"] = anchor_min[a.id] <= lim
    passing = hab.copy()
    for m in masks.values():
        passing &= m

    return Ctx(cd=cd, cfg=cfg, req=req, lang=lang, wf=wf, v=v, S=S, crit=crit, levels=levels, W=W,
               total_w=total_w, Mf=Mf, M=M, masks=masks, passing=passing, anchors=anchors,
               anchor_min=anchor_min, medians=medians, excluded=excluded, t0=t0)


# ───────────────────────────────────────── relax hint
def relax_hint(ctx: Ctx) -> dict | None:
    if ctx.passing.any() or not ctx.masks:
        return None
    hab = ctx.cd.habitable
    best_key, best = None, 0
    for key in ctx.masks:
        p = hab.copy()
        for k2, m in ctx.masks.items():
            if k2 != key:
                p &= m
        cnt = int(p.sum())
        if cnt > best:
            best_key, best = key, cnt
    if best_key is None:
        return None
    t = ctx.cfg.text("relax")
    lang = ctx.lang
    if best_key.startswith("mustHave:"):
        cat = ctx.cfg.must_have(best_key.split(":", 1)[1])
        text = render(t["mustHave"][lang], category=cat["label"][lang], count=best)
    elif best_key.startswith("commute:"):
        aid = best_key.split(":", 1)[1]
        a = next(a for a in ctx.anchors if a.id == aid)
        text = render(t["commute"][lang], anchor=a.label or a.id, count=best)
    else:
        text = render(t[best_key][lang], count=best)
    return {"filter": best_key, "passingAfter": best, "text": text}


# ───────────────────────────────────────── explanations (README §6.3)
def _row(ctx: Ctx, idx: np.ndarray, weights: np.ndarray | None = None):
    """Criterion scores, sub-scores, raw values, imputed flags and anchor minutes for one cell or a pool."""
    cd = ctx.cd
    if len(idx) == 1:
        i = int(idx[0])
        crit = {c: float(s[i]) for c, s in ctx.crit.items()}
        mins = {a: (None if m is None or m[i] >= UNREACHABLE else int(m[i])) for a, m in ctx.anchor_min.items()}
        return crit, ctx.S[i].astype(float), cd.raw[i], cd.imputed[i], mins
    w = weights if weights is not None else np.ones(len(idx))
    w = w / w.sum()
    crit = {c: float(np.dot(w, s[idx])) for c, s in ctx.crit.items()}
    sub = (w[:, None] * ctx.S[idx]).sum(axis=0)
    raw_pool = cd.raw[idx]
    valid = ~np.isnan(raw_pool)
    ww = valid * w[:, None]
    wsum = ww.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.where(wsum > 0, np.nansum(raw_pool * ww, axis=0) / wsum, np.nan)
    imputed = wsum == 0
    mins = {}
    for a, m in ctx.anchor_min.items():
        if m is None:
            mins[a] = None
            continue
        vals = m[idx]
        vals = vals[vals < UNREACHABLE]
        mins[a] = int(np.median(vals)) if len(vals) else None
    return crit, sub, raw, imputed, mins


def _pick(ctx: Ctx, c: str, sub, raw, imputed, mins, best: bool) -> dict | None:
    lang = ctx.lang
    if c == "commute":
        reach = [(a, mins[a.id]) for a in ctx.anchors if mins.get(a.id) is not None]
        if not reach:
            return None
        a, m = (min if best else max)(reach, key=lambda x: x[1])
        tpl = next(x for x in ctx.cfg.criteria if x["id"] == "commute")["explain"][lang]
        mode = ctx.cfg.raw["modes"][a.mode]["phrase"][lang]
        return {"criterion": "commute", "indicator": None, "value": m, "unit": "min",
                "text": render(tpl, anchor=a.label or a.id, value=display_value(m, "min", lang), mode=mode)}
    cand = [j for j, s in enumerate(ctx.cd.specs)
            if s.criterion == c and ctx.v[j] > 0 and not imputed[j] and not math.isnan(raw[j])
            and (sub[j] >= HIGHLIGHT_MIN if best else (sub[j] <= WARNING_MAX and not s.no_warning))]
    if not cand:
        return None
    if best:
        j = max(cand, key=lambda j: (ctx.v[j] * sub[j], ctx.v[j]))
    else:
        j = min(cand, key=lambda j: (sub[j], -ctx.v[j]))
    s = ctx.cd.specs[j]
    val = float(raw[j])
    return {"criterion": c, "indicator": s.column, "value": round(val, max(s.decimals, 2)), "unit": s.unit,
            "text": indicator_text(s, val, lang)}


def explain(ctx: Ctx, crit: dict, sub, raw, imputed, mins, n_high=2, n_warn=1):
    k = {c: w * (crit[c] - ctx.medians[c]) / ctx.total_w for c, w in ctx.W.items() if ctx.levels.get(c, 0) > 0}
    order = sorted(k, key=lambda c: k[c], reverse=True)
    highlights, warnings = [], []
    for c in order:
        if k[c] <= 0 or len(highlights) >= n_high:
            break
        e = _pick(ctx, c, sub, raw, imputed, mins, True)
        if e:
            highlights.append(e)
    for c in reversed(order):
        if k[c] >= 0 or len(warnings) >= n_warn:
            break
        e = _pick(ctx, c, sub, raw, imputed, mins, False)
        if e:
            warnings.append(e)
    return highlights, warnings


# ───────────────────────────────────────── place payload pieces
def price_info(ctx: Ctx, value: float | None) -> dict | None:
    cc = ctx.cd.cc
    j = next((j for j, s in enumerate(ctx.cd.specs) if s.column == cc["price"]["column"]), None)
    if j is None or not ctx.cd.available(j):
        return None
    imputed = value is None or math.isnan(value)
    if imputed:
        value = float(ctx.cd.median[j])
    return {"indicator": cc["price"]["indicator"], "value": round(float(value), 1),
            "unit": cc["price"]["unit"][ctx.lang], "currency": cc["currency"], "imputed": bool(imputed)}


def budget(ctx: Ctx, price: dict | None) -> tuple[int | None, str | None]:
    b = getattr(ctx.req.budget, ctx.cd.cc["price"]["budgetField"], None)
    if not b or not price or not price["value"]:
        return None, None
    m2 = int(round(b / price["value"]))
    return m2, render(ctx.cfg.text("budget")[ctx.lang], value=fmt_number(m2, ctx.lang))


def archetype(cd: CityData, idx: np.ndarray, weights: np.ndarray | None = None, with_probs=False) -> dict | None:
    if cd.archetype_proba is None:
        return None
    P = cd.archetype_proba[idx]
    p = P[0] if len(idx) == 1 else np.average(P, axis=0, weights=weights)
    j = int(np.argmax(p))
    out = {"id": cd.archetype_ids[j], "p": round(float(p[j]), 3)}
    if with_probs:
        out["probs"] = {a: round(float(x), 3) for a, x in zip(cd.archetype_ids, p) if x >= 0.005}
    return out


def anchor_times(ctx: Ctx, mins: dict) -> list[dict]:
    return [{"id": a.id, "label": a.label, "minutes": mins.get(a.id), "mode": a.mode} for a in ctx.anchors]


def imputed_columns(ctx: Ctx, imputed_row) -> list[str]:
    cols = {s.column for j, s in enumerate(ctx.cd.specs)
            if imputed_row[j] and ctx.v[j] > 0 and ctx.cd.available(j) and s.criterion in ctx.W}
    return sorted(cols)


def _centroid(lat, lon) -> dict:
    return {"lat": round(float(lat), 6), "lon": round(float(lon), 6)}


def ranked_hex(ctx: Ctx, i: int, rank: int) -> dict:
    cd = ctx.cd
    crit, sub, raw, imputed, mins = _row(ctx, np.array([i]))
    hl, wn = explain(ctx, crit, sub, raw, imputed, mins)
    pcol = cd.col(cd.cc["price"]["column"])
    pr = price_info(ctx, None if pcol is None else float(pcol[i]))
    m2, m2t = budget(ctx, pr)
    return {
        "id": cd.cells[i], "kind": "hex", "rank": rank, "score": int(ctx.M[i]),
        "name": cd.neighborhood[i] or cd.district_name[i],
        "district": {"id": str(cd.district_id[i]), "name": str(cd.district_name[i])},
        "centroid": _centroid(cd.lat[i], cd.lon[i]),
        "criteria": {c: int(round(v)) for c, v in crit.items()},
        "highlights": hl, "warnings": wn, "anchors": anchor_times(ctx, mins),
        "price": pr, "budgetM2": m2, "budgetText": m2t,
        "archetype": archetype(cd, np.array([i])), "imputed": imputed_columns(ctx, imputed),
        "passes": bool(ctx.passing[i]), "sharePassing": None, "cellCount": None,
        "populationEst": int(cd.population[i]),
    }


def rank_key(ctx: Ctx) -> np.ndarray:
    """Per-cell value `top` is ordered by (higher = better): the map lens the web shows (req.rankBy)."""
    rb = ctx.req.rankBy
    if rb and rb.startswith("anchor:"):
        m = ctx.anchor_min.get(rb.split(":", 1)[1])
        if m is not None:
            return -np.minimum(m, UNREACHABLE).astype(np.float64)
    elif rb in ctx.crit:
        return ctx.crit[rb].astype(np.float64)
    return ctx.Mf


def _median_minutes(m: np.ndarray, idx: np.ndarray) -> float | None:
    vals = m[idx]
    vals = vals[vals < UNREACHABLE]
    return float(np.median(vals)) if len(vals) else None


def _group_key(ctx: Ctx, pool: np.ndarray, w: np.ndarray, score: float) -> float:
    """A group's rank_key: the same number its card shows (criterion mean, median minutes, match %)."""
    rb = ctx.req.rankBy
    if rb and rb.startswith("anchor:"):
        m = ctx.anchor_min.get(rb.split(":", 1)[1])
        if m is not None:
            med = _median_minutes(m, pool)
            return -float(UNREACHABLE) if med is None else -int(med)
    elif rb in ctx.crit:
        return float(np.average(ctx.crit[rb][pool], weights=w))
    return score


def ranked_groups(ctx: Ctx, level: str, limit: int) -> list[dict]:
    """Districts/neighbourhoods: population-weighted means over ALL habitable cells of the group (the
    group as a whole, not its best part); hard filters only drop groups where no cell passes."""
    cd = ctx.cd
    groups = cd.districts if level == "district" else cd.neighborhoods
    price_col = cd.col(cd.cc["price"]["column"])
    rows = []
    for g in groups.values():
        pool = g.habitable
        if len(pool) == 0:
            continue
        share = float(ctx.passing[pool].mean())
        if share == 0:
            continue
        w = cd.population[pool].astype(float) + 1.0
        score = float(np.average(ctx.Mf[pool], weights=w))
        rows.append((_group_key(ctx, pool, w, score), score, share, g, pool, w))
    rows.sort(key=lambda r: (-r[0], -r[1], r[3].id))
    out = []
    for rank, (_, score, share, g, pool, w) in enumerate(rows[:limit], start=1):
        crit, sub, raw, imputed, mins = _row(ctx, pool, w)
        hl, wn = explain(ctx, crit, sub, raw, imputed, mins)
        pv = None
        if price_col is not None:
            vals = price_col[pool]
            m = ~np.isnan(vals)
            pv = float(np.average(vals[m], weights=w[m])) if m.any() else None
        pr = price_info(ctx, pv)
        m2, m2t = budget(ctx, pr)
        parent = None
        if level == "neighborhood" and g.parent is not None and g.parent in cd.districts:
            parent = {"id": g.parent, "name": cd.districts[g.parent].name}
        out.append({
            "id": g.id, "kind": level, "rank": rank, "score": int(round(score)), "name": g.name, "district": parent,
            "centroid": _centroid(g.lat, g.lon), "criteria": {c: int(round(v)) for c, v in crit.items()},
            "highlights": hl, "warnings": wn, "anchors": anchor_times(ctx, mins), "price": pr,
            "budgetM2": m2, "budgetText": m2t, "archetype": archetype(cd, pool, w), "imputed": imputed_columns(ctx, imputed),
            "passes": True, "sharePassing": round(share, 3), "cellCount": int(len(pool)),
            "populationEst": int(g.population),
        })
    return out


def score_response(cd: CityData, cfg: Config, req: ScoreRequest) -> dict:
    ctx = compute(cd, cfg, req)
    if req.aggregate == "hex":
        ok = ctx.passing if req.district is None else ctx.passing & (cd.district_id == str(req.district))
        cand = np.flatnonzero(ok)
        order = cand[np.lexsort((cand, -ctx.Mf[cand], -rank_key(ctx)[cand]))]   # the lens first, then match %
        picked, seen = [], set()
        for i in order:   # at most one cell per neighbourhood, so the list shows distinct places
            g = cd.neighborhood[i] or cd.district_name[i]
            if g in seen:
                continue
            seen.add(g)
            picked.append(int(i))
            if len(picked) >= req.limit:
                break
        top = [ranked_hex(ctx, i, r) for r, i in enumerate(picked, start=1)]
    else:
        top = ranked_groups(ctx, req.aggregate, req.limit)
    relax = relax_hint(ctx)
    cells = []
    if req.includeCells:
        cells = [list(t) for t in zip(cd.cells, ctx.M.tolist(), ctx.passing.astype(np.int8).tolist())]
    compute_ms = (time.perf_counter() - ctx.t0) * 1000
    return {
        "city": cd.city, "currency": cd.cc["currency"], "lang": ctx.lang, "computeMs": round(compute_ms, 2),
        "aggregate": req.aggregate,
        "count": {"cells": cd.n, "habitable": int(cd.habitable.sum()), "passing": int(ctx.passing.sum())},
        "cells": cells, "top": top, "relaxHint": relax, "excludedCriteria": ctx.excluded,
        "weightsUsed": ctx.levels, "cityMedian": {c: int(round(v)) for c, v in ctx.medians.items()},
    }


# ───────────────────────────────────────── place detail
def nearest_pois(cd: CityData, i: int) -> list[dict]:
    out = []
    for cat, column in NEAREST:
        p = cd.pois.get(cat)
        if not p or len(p["lat"]) == 0:
            continue
        dkm = haversine_km(cd.lat[i], cd.lon[i], p["lat"], p["lon"])
        j = int(np.argmin(dkm))
        walk = dkm[j] * DETOUR / WALK_KMH * 60.0
        col = cd.col(column) if column else None
        if col is not None and not math.isnan(col[i]):
            walk = float(col[i])
        if walk > 30:
            continue
        name = p["name"][j]
        out.append({"category": cat, "name": None if name is None else str(name), "lat": round(float(p["lat"][j]), 6),
                    "lon": round(float(p["lon"][j]), 6), "walkMin": round(float(walk), 1)})
    return out


def place_detail(cd: CityData, cfg: Config, req: ScoreRequest, i: int) -> dict:
    ctx = compute(cd, cfg, req)
    crit, sub, raw, imputed, mins = _row(ctx, np.array([i]))
    hl, wn = explain(ctx, crit, sub, raw, imputed, mins)
    lang = ctx.lang
    indicators = []
    for j, s in enumerate(cd.specs):
        if not cd.available(j) or (s.is_alias and ctx.v[j] <= 0):
            continue
        val = None if cd.imputed[i, j] else float(cd.raw[i, j])
        med = None if math.isnan(cd.median[j]) else round(float(cd.median[j]), max(s.decimals, 1))
        indicators.append({
            "criterion": s.criterion, "indicator": s.id, "column": s.column,
            "value": None if val is None else round(val, max(s.decimals, 2)), "unit": s.unit,
            "score": int(round(float(ctx.S[i, j]))), "weight": float(ctx.v[j]), "cityMedianValue": med,
            "imputed": bool(cd.imputed[i, j]), "text": indicator_text(s, val, lang) if val is not None else None,
        })
    pcol = cd.col(cd.cc["price"]["column"])
    pr = price_info(ctx, None if pcol is None else float(pcol[i]))
    m2, m2t = budget(ctx, pr)
    return {
        "id": cd.cells[i], "kind": "hex", "city": cd.city, "lang": lang, "centroid": _centroid(cd.lat[i], cd.lon[i]),
        "name": cd.neighborhood[i] or cd.district_name[i], "neighborhood": cd.neighborhood[i],
        "district": {"id": str(cd.district_id[i]), "name": str(cd.district_name[i])},
        "habitable": bool(cd.habitable[i]), "populationEst": int(cd.population[i]),
        "score": int(ctx.M[i]), "passes": bool(ctx.passing[i]),
        "criteria": {c: int(round(v)) for c, v in crit.items()},
        "cityMedian": {c: int(round(v)) for c, v in ctx.medians.items()},
        "indicators": indicators, "nearest": nearest_pois(cd, i), "anchors": anchor_times(ctx, mins),
        "price": pr, "budgetM2": m2, "budgetText": m2t,
        "archetype": archetype(cd, np.array([i]), with_probs=True), "highlights": hl, "warnings": wn,
    }


def default_criteria(cd: CityData, cfg: Config, persona: str = "custom") -> dict[str, np.ndarray]:
    """Criterion scores (n,) for a persona with no anchors — used by twins/similar/export."""
    p = cfg.persona(persona)
    ctx = compute(cd, cfg, ScoreRequest(persona=persona, weights=p["weights"]))
    return ctx.crit
