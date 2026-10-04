# /// script
# requires-python = ">=3.11"
# dependencies = ["h3>=4,<5", "pyyaml>=6", "numpy>=1.26"]
# ///
"""Generate contracts/fixtures/** from config/*.yaml.

Fixtures use REAL H3 res-9 cells around each city centre with PLAUSIBLE FAKE values.
Every JSON matches contracts/openapi.yaml. Run from the repo root:

    uv run contracts/tools/make_fixtures.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import h3
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT / "config/indicators.yaml").read_text(encoding="utf-8"))
OUT = ROOT / "contracts/fixtures"
RES = 9
K_RING = 8  # 217 cells
DATA_VERSION = "fixture-2026-10-03"
LANGS = ("pl", "cs", "en", "ko")

# Approximate centroids (fixture only — real admin data comes from Workstream A).
PLACES = {
    "krakow": {
        "districts": {
            "1": ("Stare Miasto", 50.0619, 19.9369), "2": ("Grzegórzki", 50.0620, 19.9620),
            "3": ("Prądnik Czerwony", 50.0900, 19.9700), "4": ("Prądnik Biały", 50.0950, 19.9250),
            "5": ("Krowodrza", 50.0750, 19.9150), "7": ("Zwierzyniec", 50.0550, 19.8900),
            "8": ("Dębniki", 50.0380, 19.9150), "9": ("Łagiewniki-Borek Fałęcki", 50.0250, 19.9350),
            "11": ("Podgórze Duchackie", 50.0180, 19.9600), "13": ("Podgórze", 50.0420, 19.9700),
            "14": ("Czyżyny", 50.0700, 20.0050),
        },
        "neighborhoods": {
            "Stare Miasto": (50.0614, 19.9366), "Kazimierz": (50.0510, 19.9460), "Stradom": (50.0550, 19.9390),
            "Podgórze": (50.0440, 19.9560), "Zabłocie": (50.0490, 19.9640), "Grzegórzki": (50.0610, 19.9600),
            "Kleparz": (50.0700, 19.9390), "Piasek": (50.0630, 19.9260), "Nowy Świat": (50.0570, 19.9280),
            "Półwsie Zwierzynieckie": (50.0530, 19.9130), "Dębniki": (50.0450, 19.9220), "Ludwinów": (50.0400, 19.9320),
            "Wesoła": (50.0650, 19.9490), "Krowodrza": (50.0760, 19.9200), "Łobzów": (50.0790, 19.9130),
            "Olsza": (50.0760, 19.9620), "Dąbie": (50.0570, 19.9820), "Płaszów": (50.0390, 19.9800),
            "Czarna Wieś": (50.0710, 19.9230),
        },
        # (lat, lon) of a river polyline → cells within ~120 m are not habitable
        "river": [(50.0560, 19.8950), (50.0510, 19.9200), (50.0480, 19.9340), (50.0500, 19.9480),
                  (50.0470, 19.9600), (50.0440, 19.9750), (50.0480, 19.9900)],
        "anchors": {
            "student": [{"id": "a1", "label": "AGH", "lat": 50.0646, "lon": 19.9234, "mode": "transit", "level": 5, "maxMinutes": None}],
            "parent": [
                {"id": "a1", "label": "Praca – Zabłocie", "lat": 50.0487, "lon": 19.9625, "mode": "transit", "level": 4, "maxMinutes": 30},
                {"id": "a2", "label": "Szkoła Podstawowa nr 1", "lat": 50.0655, "lon": 19.9420, "mode": "walk", "level": 4, "maxMinutes": None},
            ],
        },
        "filters": {
            "student": {"maxPricePerM2": 18000, "mustHave": [], "maxNoiseDb": None},
            "parent": {"maxPricePerM2": 17000, "mustHave": [{"category": "primary_school", "maxWalkMin": 12}], "maxNoiseDb": 65},
            "nomatch": {"maxPricePerM2": 7000, "mustHave": [{"category": "pharmacy", "maxWalkMin": 10}], "maxNoiseDb": None},
        },
        "budget": {"student": {"total": 600000}, "parent": {"total": 1100000}},
        "price": (17500, 4500),  # centre value, drop per km… in zł/m²
        "geocode": [
            ("Rynek Główny", "Stare Miasto", "address", None, 50.0617, 19.9373),
            ("Rakowicka 27", "Grzegórzki", "address", None, 50.0687, 19.9532),
            ("Akademia Górniczo-Hutnicza (AGH)", "Krowodrza", "poi", "university", 50.0646, 19.9234),
            ("Uniwersytet Jagielloński – Collegium Novum", "Stare Miasto", "poi", "university", 50.0608, 19.9330),
            ("Kazimierz", "Stare Miasto", "place", None, 50.0510, 19.9460),
            ("Zabłocie", "Podgórze", "place", None, 50.0490, 19.9640),
        ],
        "air": {"source": "GIOŚ", "station": {"id": "400", "name": "Kraków, Aleja Krasińskiego", "lat": 50.0577, "lon": 19.9265}},
    },
    "praha": {
        "districts": {
            "500054": ("Praha 1", 50.0870, 14.4200), "500089": ("Praha 2", 50.0740, 14.4330),
            "500097": ("Praha 3", 50.0850, 14.4600), "500119": ("Praha 4", 50.0420, 14.4450),
            "500143": ("Praha 5", 50.0700, 14.4000), "500186": ("Praha 7", 50.1030, 14.4350),
            "500208": ("Praha 8", 50.1050, 14.4700), "500224": ("Praha 10", 50.0700, 14.4850),
        },
        "neighborhoods": {
            "Nové Město": (50.0790, 14.4260), "Staré Město": (50.0870, 14.4210), "Vinohrady": (50.0750, 14.4450),
            "Žižkov": (50.0850, 14.4550), "Karlín": (50.0925, 14.4520), "Vyšehrad": (50.0640, 14.4190),
            "Nusle": (50.0630, 14.4400), "Vršovice": (50.0680, 14.4600), "Holešovice": (50.1030, 14.4400),
            "Smíchov": (50.0700, 14.4030), "Malá Strana": (50.0880, 14.4040), "Bubeneč": (50.1000, 14.4150),
            "Libeň": (50.1050, 14.4750), "Michle": (50.0550, 14.4500),
        },
        "river": [(50.0550, 14.4150), (50.0650, 14.4135), (50.0750, 14.4135), (50.0850, 14.4130),
                  (50.0920, 14.4180), (50.0960, 14.4300), (50.0980, 14.4500), (50.1030, 14.4650)],
        "anchors": {
            "student": [{"id": "a1", "label": "UK – Albertov", "lat": 50.0680, "lon": 14.4240, "mode": "transit", "level": 5, "maxMinutes": None}],
            "parent": [
                {"id": "a1", "label": "Práce – Karlín", "lat": 50.0925, "lon": 14.4520, "mode": "transit", "level": 4, "maxMinutes": 30},
                {"id": "a2", "label": "ZŠ Vinohradská", "lat": 50.0770, "lon": 14.4440, "mode": "walk", "level": 4, "maxMinutes": None},
            ],
        },
        "filters": {
            "student": {"maxRentPerM2": 450, "mustHave": [{"category": "metro_station", "maxWalkMin": 12}], "maxNoiseDb": None},
            "parent": {"maxRentPerM2": 430, "mustHave": [{"category": "primary_school", "maxWalkMin": 12}], "maxNoiseDb": 65},
            "nomatch": {"maxRentPerM2": 230, "mustHave": [{"category": "pharmacy", "maxWalkMin": 10}], "maxNoiseDb": None},
        },
        "budget": {"student": {"monthlyRent": 14000}, "parent": {"monthlyRent": 26000}},
        "price": (430, 22),  # Kč/m²/month at centre, drop per km
        "geocode": [
            ("Václavské náměstí", "Praha 1", "address", None, 50.0810, 14.4280),
            ("Žižkov", "Praha 3", "place", None, 50.0850, 14.4550),
            ("Karlín", "Praha 8", "place", None, 50.0925, 14.4520),
            ("Univerzita Karlova – Albertov", "Praha 2", "poi", "university", 50.0680, 14.4240),
            ("Vinohradská 12", "Praha 2", "address", None, 50.0775, 14.4370),
            ("Náměstí Míru", "Praha 2", "place", None, 50.0753, 14.4378),
        ],
        "air": {"source": "ČHMÚ", "station": {"id": "AKALA", "name": "Praha 8-Karlín", "lat": 50.0942, "lon": 14.4428}},
    },
}

ARCH_COLORS = [a["id"] for a in CFG["archetypes"]]


def city_cfg(city: str) -> dict:
    return yaml.safe_load((ROOT / f"config/cities/{city}.yaml").read_text(encoding="utf-8"))


def km(lat1, lon1, lat2, lon2) -> float:
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def dist_to_polyline(lat, lon, pts) -> float:
    """Approximate distance (km) to a polyline by sampling segments."""
    best = 1e9
    for (a_lat, a_lon), (b_lat, b_lon) in zip(pts, pts[1:]):
        for t in np.linspace(0, 1, 25):
            best = min(best, km(lat, lon, a_lat + t * (b_lat - a_lat), a_lon + t * (b_lon - a_lon)))
    return best


# ───────────────────────────────────────── number formatting (pl/cs/en/ko)
def fmt(value: float, lang: str, decimals: int = 0) -> str:
    v = round(float(value), decimals)
    s = f"{v:,.{decimals}f}"  # en/ko style "12,450.5"
    if lang in ("en", "ko"):
        return s
    int_part, _, dec_part = s.partition(".")
    digits = int_part.replace(",", "")
    group = len(digits.lstrip("-")) >= (5 if lang == "pl" else 4)
    int_out = int_part.replace(",", " ") if group else digits
    return int_out + ("," + dec_part if dec_part else "")


def render(template: str, **kw) -> str:
    for k, v in kw.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


# ───────────────────────────────────────── indicator catalogue
def indicators_for(city: str, cc: dict) -> list[dict]:
    out = []
    for crit in CFG["criteria"]:
        for ind in crit.get("indicators", []):
            col = f"{crit['id']}.{ind['id']}"
            spec = dict(ind)
            spec["criterion"] = crit["id"]
            spec["key"] = col
            spec["column"] = ind.get("column", col)
            spec["available"] = city in ind.get("cities", [city])
            ov = cc.get("indicatorOverrides", {}).get(col, {})
            spec.update({k: v for k, v in ov.items()})
            out.append(spec)
    return out


# ───────────────────────────────────────── synthetic features
def synth_column(name: str, d: np.ndarray, rng: np.random.Generator, city: str, base_price) -> np.ndarray:
    n = len(d)
    z = rng.normal(0, 1, n)
    if name == "price.buy_per_m2" or name == "price.rent_per_m2":
        c, drop = base_price
        return np.round(np.maximum(c - drop * d + z * c * 0.06, c * 0.45), 0)
    if name == "environment.noise_db":
        return np.round(np.clip(66 - 2.2 * d + z * 4, 42, 75), 0)
    if name == "environment.pm25":
        return np.round(np.clip((19 if city == "krakow" else 14) - 0.6 * d + z * 1.2, 8, 30), 1)
    if name == "environment.pm10":
        return np.round(np.clip((30 if city == "krakow" else 24) - 0.8 * d + z * 2, 14, 45), 1)
    if name == "environment.major_road_m":
        return np.round(np.clip(120 + 60 * d + z * 80, 15, 900), 0)
    if name == "environment.industrial_ha_1km":
        return np.round(np.clip(2 + 3 * d + z * 3, 0, 40), 0)
    if name == "safety.crime_per_1000":
        return np.round(np.clip(95 - 18 * d + z * 8, 18, 140), 0)
    if name == "safety.lit_share":
        return np.round(np.clip(92 - 6 * d + z * 5, 35, 100), 0)
    if name == "green.green_share_500m":
        return np.round(np.clip(10 + 7 * d + z * 6, 2, 70), 0)
    if name == "green.forest_meadow_ha_1km":
        return np.round(np.clip(-2 + 6 * d + z * 5, 0, 120), 0)
    if name == "transit.departures_per_h_500m":
        return np.round(np.clip(85 - 22 * d + z * 10, 4, 160), 0)
    if name == "transit.lines_500m":
        return np.round(np.clip(18 - 4 * d + z * 2, 1, 30), 0)
    if name == "transit.night_departures_500m":
        return np.round(np.clip(22 - 6 * d + z * 3, 0, 40), 0)
    if name == "active.cycleway_km_1km":
        return np.round(np.clip(6 - 0.8 * d + z * 1.2, 0.2, 12), 1)
    if name == "active.intersection_density":
        return np.round(np.clip(160 - 30 * d + z * 15, 20, 260), 0)
    if name == "active.bike_racks_300m":
        return np.round(np.clip(14 - 4 * d + z * 3, 0, 30), 0)
    if name == "family.playgrounds_500m":
        return np.round(np.clip(3 + 1.2 * d + z * 1.5, 0, 12), 0)
    if name == "shops.shops_10min":
        return np.round(np.clip(160 - 45 * d + z * 20, 3, 320), 0)
    if name == "leisure.food_10min":
        return np.round(np.clip(140 - 45 * d + z * 18, 2, 300), 0)
    if name == "leisure.nightlife_10min":
        return np.round(np.clip(45 - 16 * d + z * 6, 0, 90), 0)
    if name == "accessibility.accessible_stop_share":
        return np.round(np.clip(70 + 5 * d + z * 8, 20, 100), 0)
    if name == "accessibility.lowfloor_trip_share":
        return np.round(np.clip((80 if city == "krakow" else 75) + 3 * d + z * 6, 40, 100), 0)
    if name == "accessibility.benches_300m":
        return np.round(np.clip(18 - 3 * d + z * 4, 0, 40), 0)
    if name == "accessibility.slope_pct":
        return np.round(np.clip(2 + 0.5 * d + np.abs(z) * 1.5, 0.2, 12), 1)
    if name.endswith("_walk_min") or name == "poi.metro_station_walk_min":
        base = {
            "transit.stop_walk_min": (1.5, 0.8), "transit.tram_stop_walk_min": (2.5, 1.6),
            "transit.rail_station_walk_min": (6, 3), "poi.metro_station_walk_min": (4, 3.5),
            "health.hospital_er_walk_min": (12, 4), "health.maternity_walk_min": (16, 5),
            "education.university_walk_min": (8, 4), "active.car_free_walk_min": (4, 3),
            "active.bikeshare_walk_min": (2, 1.5),
        }.get(name, (3, 1.8))
        return np.round(np.clip(base[0] + base[1] * d + np.abs(z) * 2, 0.5, 60), 0)
    raise KeyError(name)


def build_city(city: str) -> dict:
    cc = city_cfg(city)
    P = PLACES[city]
    rng = np.random.default_rng(42 if city == "krakow" else 7)
    lat0, lon0 = cc["center"]
    centre = h3.latlng_to_cell(lat0, lon0, RES)
    cells = sorted(h3.grid_disk(centre, K_RING))
    lat = np.array([h3.cell_to_latlng(c)[0] for c in cells])
    lon = np.array([h3.cell_to_latlng(c)[1] for c in cells])
    d = np.array([km(lat0, lon0, a, b) for a, b in zip(lat, lon)])

    def nearest(table):
        keys = list(table)
        out = []
        for a, b in zip(lat, lon):
            dd = [km(a, b, *table[k][-2:]) for k in keys]
            out.append(keys[int(np.argmin(dd))])
        return out

    district_id = nearest(P["districts"])
    district_name = [P["districts"][i][0] for i in district_id]
    neighborhood = nearest(P["neighborhoods"])
    river = np.array([dist_to_polyline(a, b, P["river"]) for a, b in zip(lat, lon)])
    habitable = river > 0.12
    population = np.where(habitable, np.round(np.clip(900 - 180 * d + rng.normal(0, 150, len(d)), 40, 1600)), 0).astype(int)

    inds = indicators_for(city, cc)
    columns: dict[str, np.ndarray] = {}
    needed = {i["column"] for i in inds if i["available"]} | {m["column"] for m in CFG["mustHaveCategories"] if city in m.get("cities", [city])}
    for col in sorted(needed):
        if col == "accessibility.slope_pct":
            continue  # P2 — demonstrates an indicator with 0% coverage
        v = synth_column(col, d, rng, city, P["price"])
        if col in ("health.gynaecology_walk_min", "environment.industrial_ha_1km"):
            v[rng.random(len(v)) < 0.06] = np.nan  # demonstrates imputation
        columns[col] = v

    return dict(city=city, cc=cc, cells=cells, lat=lat, lon=lon, d=d, district_id=district_id,
                district_name=district_name, neighborhood=neighborhood, habitable=habitable,
                population=population, inds=inds, columns=columns, P=P)


# ───────────────────────────────────────── scoring (same rules as engine; README §6)
def level_w(level: int) -> float:
    return float(CFG["levels"][int(level)])


def persona(pid: str) -> dict:
    return next(p for p in CFG["personas"] if p["id"] == pid)


def norm_scores(spec, raw, hab, walk_factor):
    v = raw.copy()
    med = np.nanmedian(v[hab]) if np.any(~np.isnan(v[hab])) else np.nan
    imputed = np.isnan(v)
    v[imputed] = med
    n = spec["norm"]
    t = n["type"]
    if t == "decay":
        x = v * (walk_factor if spec.get("walkScaled") else 1.0)
        s = (x - n["bad"]) / (n["good"] - n["bad"]) * 100
    elif t in ("percentile", "inverse_percentile"):
        ref = np.sort(v[hab])
        s = np.searchsorted(ref, v, side="right") / len(ref) * 100
        if t == "inverse_percentile":
            s = 100 - np.searchsorted(ref, v, side="left") / len(ref) * 100
    else:
        s = np.where(v >= n["at"], 100.0, 0.0)
    return np.clip(s, 0, 100), imputed


def travel_minutes(C, a):
    dd = np.array([km(a["lat"], a["lon"], x, y) for x, y in zip(C["lat"], C["lon"])])
    mode = a.get("mode", "transit")
    if mode == "walk":
        m = dd / 4.8 * 60 * 1.25
    elif mode == "bike":
        m = 3 + dd / 15 * 60 * 1.2
    else:
        m = 6 + dd * 3.2 + np.abs(np.sin(C["lat"] * 900)) * 5
    return np.round(m).astype(int)


def score(C, req):
    city, cc, hab = C["city"], C["cc"], C["habitable"]
    lang = req.get("lang", cc["defaultLang"])
    pers = persona(req.get("persona") or "custom")
    wf = pers["walkFactor"]
    iw = dict(pers.get("indicatorWeights", {}))
    iw.update(req.get("indicatorWeights", {}))
    levels = {c["id"]: int(req["weights"].get(c["id"], 0)) for c in CFG["criteria"]}

    crit_scores: dict[str, np.ndarray] = {}
    sub: dict[str, tuple] = {}
    for crit in CFG["criteria"]:
        if crit.get("runtime") == "anchors":
            continue
        num = np.zeros(len(C["cells"]))
        den = 0.0
        for spec in [i for i in C["inds"] if i["criterion"] == crit["id"] and i["available"]]:
            if spec["column"] not in C["columns"]:
                continue
            w = float(iw.get(spec["key"], spec["weight"]))
            s, imp = norm_scores(spec, C["columns"][spec["column"]], hab, wf)
            sub[spec["key"]] = (s, imp, w, spec)
            if w > 0:
                num += w * s
                den += w
        if den > 0:
            crit_scores[crit["id"]] = num / den

    anchors = req.get("anchors", [])
    anchor_min = {a["id"]: travel_minutes(C, a) for a in anchors}
    if anchors:
        num = np.zeros(len(C["cells"]))
        den = 0.0
        for a in anchors:
            t = anchor_min[a["id"]]
            s = np.clip((t - 60) / (15 - 60) * 100, 0, 100)
            num += level_w(a.get("level", 3)) * s
            den += level_w(a.get("level", 3))
        crit_scores["commute"] = num / den

    excluded = [c for c, lv in levels.items() if lv > 0 and c not in crit_scores]
    total_w = sum(level_w(lv) for c, lv in levels.items() if c in crit_scores)
    M = np.zeros(len(C["cells"]))
    for c, s in crit_scores.items():
        M += level_w(levels[c]) * s
    M = np.round(M / total_w if total_w else M).astype(int)
    medians = {c: int(round(float(np.median(s[hab])))) for c, s in crit_scores.items()}

    f = req.get("filters", {})
    masks = {}
    pf = cc["price"]["filterField"]
    if f.get(pf) is not None:
        masks["price"] = C["columns"][cc["price"]["column"]] <= f[pf]
    if f.get("maxNoiseDb") is not None:
        masks["noise"] = C["columns"]["environment.noise_db"] <= f["maxNoiseDb"]
    for mh in f.get("mustHave", []):
        cat = next(m for m in CFG["mustHaveCategories"] if m["id"] == mh["category"])
        col = C["columns"].get(cat["column"])
        if col is not None:
            masks[f"mustHave:{mh['category']}"] = np.nan_to_num(col, nan=999) <= mh["maxWalkMin"]
    for a in anchors:
        lim = a.get("maxMinutes") or f.get("maxCommuteMinutes")
        if lim:
            masks[f"commute:{a['id']}"] = anchor_min[a["id"]] <= lim
    passing = hab.copy()
    for m in masks.values():
        passing &= m

    relax = None
    if passing.sum() == 0 and masks:
        best = None
        for key in masks:
            p = hab.copy()
            for k2, m in masks.items():
                if k2 != key:
                    p &= m
            if best is None or p.sum() > best[1]:
                best = (key, int(p.sum()))
        key, cnt = best
        tx = CFG["texts"]["relax"]
        if key.startswith("mustHave:"):
            cat = next(m for m in CFG["mustHaveCategories"] if m["id"] == key.split(":")[1])
            text = render(tx["mustHave"][lang], category=cat["label"][lang], count=cnt)
        elif key.startswith("commute:"):
            a = next(a for a in anchors if a["id"] == key.split(":")[1])
            text = render(tx["commute"][lang], anchor=a.get("label", a["id"]), count=cnt)
        else:
            text = render(tx[key][lang], count=cnt)
        relax = {"filter": key, "passingAfter": cnt, "text": text}

    ctx = dict(levels=levels, crit=crit_scores, sub=sub, medians=medians, total_w=total_w, lang=lang,
               anchors=anchors, anchor_min=anchor_min, M=M, passing=passing, req=req, wf=wf)
    return ctx, relax, excluded


def explain_indicator(C, key, i, lang):
    s, imp, w, spec = C["_ctx"]["sub"][key]
    raw = C["columns"][spec["column"]][i]
    return {
        "criterion": spec["criterion"], "indicator": spec["column"], "value": float(raw), "unit": spec["unit"],
        "text": render(spec["explain"][lang], value=fmt(raw, lang, spec.get("decimals", 0))),
    }


def explanations(C, ctx, i):
    lang = ctx["lang"]
    k = {c: level_w(ctx["levels"][c]) * (s[i] - ctx["medians"][c]) / max(ctx["total_w"], 1)
         for c, s in ctx["crit"].items() if ctx["levels"][c] > 0}
    order = sorted(k, key=k.get, reverse=True)

    def pick(c, best: bool):
        if c == "commute":
            a = ctx["anchors"][0]
            m = int(ctx["anchor_min"][a["id"]][i])
            mode = CFG["modes"][a.get("mode", "transit")]["phrase"][lang]
            crit = next(x for x in CFG["criteria"] if x["id"] == "commute")
            return {"criterion": "commute", "indicator": None, "value": m, "unit": "min",
                    "text": render(crit["explain"][lang], anchor=a.get("label", a["id"]), value=m, mode=mode)}
        cands = [(key, v) for key, v in ctx["sub"].items()
                 if v[3]["criterion"] == c and v[2] > 0 and not v[1][i] and (best or not v[3].get("noWarning"))]
        if not cands:
            return None
        key = (max if best else min)(cands, key=lambda kv: kv[1][0][i] * (kv[1][2] if best else 1))[0]
        return explain_indicator(C, key, i, lang)

    highlights = [e for e in (pick(c, True) for c in order if k[c] > 0) if e][:2]
    warnings = [e for e in (pick(c, False) for c in reversed(order) if k[c] < 0) if e][:1]
    return highlights, warnings


def archetype_of(C, i):
    d, j = C["d"][i], C["columns"]
    if d < 0.8:
        probs = {"historic_core": 0.72, "urban_mix": 0.18, "student_buzz": 0.10}
    elif j["leisure.nightlife_10min"][i] > 25:
        probs = {"student_buzz": 0.61, "urban_mix": 0.29, "historic_core": 0.10}
    elif j["green.green_share_500m"][i] > 25:
        probs = {"green_residential": 0.66, "family_suburb": 0.22, "urban_mix": 0.12}
    elif j["environment.industrial_ha_1km"][i] > 12:
        probs = {"industrial_edge": 0.55, "estate_blocks": 0.30, "urban_mix": 0.15}
    else:
        probs = {"urban_mix": 0.58, "estate_blocks": 0.27, "green_residential": 0.15}
    best = max(probs, key=probs.get)
    return {"id": best, "p": probs[best]}, probs


def price_info(C, i, lang):
    cc = C["cc"]
    col = C["columns"][cc["price"]["column"]]
    return {"indicator": cc["price"]["indicator"], "value": float(col[i]), "unit": cc["price"]["unit"][lang],
            "currency": cc["currency"], "imputed": False}


def budget_m2(C, i, req, lang):
    cc = C["cc"]
    b = (req.get("budget") or {}).get(cc["price"]["budgetField"])
    if not b:
        return None, None
    m2 = int(round(b / C["columns"][cc["price"]["column"]][i]))
    return m2, render(CFG["texts"]["budget"][lang], value=fmt(m2, lang))


def ranked_hex(C, ctx, i, rank):
    lang = ctx["lang"]
    hl, wn = explanations(C, ctx, i)
    m2, m2t = budget_m2(C, i, ctx["req"], lang)
    imputed = [v[3]["column"] for v in ctx["sub"].values() if v[1][i] and v[2] > 0]
    return {
        "id": C["cells"][i], "kind": "hex", "rank": rank, "score": int(ctx["M"][i]),
        "name": C["neighborhood"][i],
        "district": {"id": C["district_id"][i], "name": C["district_name"][i]},
        "centroid": {"lat": round(float(C["lat"][i]), 6), "lon": round(float(C["lon"][i]), 6)},
        "criteria": {c: int(round(float(s[i]))) for c, s in ctx["crit"].items()},
        "highlights": hl, "warnings": wn,
        "anchors": [{"id": a["id"], "label": a.get("label"), "minutes": int(ctx["anchor_min"][a["id"]][i]), "mode": a.get("mode", "transit")} for a in ctx["anchors"]],
        "price": price_info(C, i, lang), "budgetM2": m2, "budgetText": m2t,
        "archetype": archetype_of(C, i)[0], "imputed": sorted(set(imputed)),
        "passes": bool(ctx["passing"][i]), "sharePassing": None, "cellCount": None,
        "populationEst": int(C["population"][i]),
    }


def score_response(C, req):
    ctx, relax, excluded = score(C, req)
    C["_ctx"] = ctx
    hab, passing, M = C["habitable"], ctx["passing"], ctx["M"]
    limit = req.get("limit", 20)
    agg = req.get("aggregate", "hex")
    order = [i for i in np.argsort(-M, kind="stable") if passing[i]]
    if agg == "hex":
        top = [ranked_hex(C, ctx, i, r + 1) for r, i in enumerate(order[:limit])]
    else:
        top = []
        groups: dict[str, list[int]] = {}
        for i, did in enumerate(C["district_id"]):
            if hab[i]:
                groups.setdefault(did, []).append(i)
        rows = []
        for did, idx in groups.items():
            ok = [i for i in idx if passing[i]]
            pool = sorted(ok or idx, key=lambda i: -M[i])[: max(1, math.ceil(len(ok or idx) / 2))]
            w = np.array([C["population"][i] for i in pool], float) + 1
            sc = int(round(float(np.average([M[i] for i in pool], weights=w))))
            rows.append((did, idx, ok, pool, w, sc))
        rows.sort(key=lambda r: -r[5])
        for r, (did, idx, ok, pool, w, sc) in enumerate(rows[:limit]):
            rep = pool[0]
            hl, wn = explanations(C, ctx, rep)
            top.append({
                "id": did, "kind": "district", "rank": r + 1, "score": sc, "name": C["district_name"][rep], "district": None,
                "centroid": {"lat": round(float(np.mean(C["lat"][idx])), 6), "lon": round(float(np.mean(C["lon"][idx])), 6)},
                "criteria": {c: int(round(float(np.average(s[pool], weights=w)))) for c, s in ctx["crit"].items()},
                "highlights": hl, "warnings": wn,
                "anchors": [{"id": a["id"], "label": a.get("label"), "minutes": int(np.median(ctx["anchor_min"][a["id"]][pool])), "mode": a.get("mode", "transit")} for a in ctx["anchors"]],
                "price": price_info(C, rep, ctx["lang"]), "budgetM2": budget_m2(C, rep, req, ctx["lang"])[0],
                "budgetText": budget_m2(C, rep, req, ctx["lang"])[1],
                "archetype": archetype_of(C, rep)[0], "imputed": [], "passes": bool(ok),
                "sharePassing": round(len(ok) / len(idx), 3), "cellCount": len(idx),
                "populationEst": int(sum(C["population"][i] for i in idx)),
            })
    return {
        "city": C["city"], "currency": C["cc"]["currency"], "lang": ctx["lang"], "computeMs": 12.4, "aggregate": agg,
        "count": {"cells": len(C["cells"]), "habitable": int(hab.sum()), "passing": int(passing.sum())},
        "cells": [[h, int(M[i]), int(passing[i])] for i, h in enumerate(C["cells"])] if req.get("includeCells", True) else [],
        "top": top, "relaxHint": relax, "excludedCriteria": excluded,
        "weightsUsed": ctx["levels"], "cityMedian": ctx["medians"],
    }


# ───────────────────────────────────────── other endpoints
def coverage(C):
    cov_ind, cov_crit = {}, {}
    hab = C["habitable"]
    for spec in C["inds"]:
        col = C["columns"].get(spec["column"])
        cov_ind[spec["key"]] = 0.0 if (col is None or not spec["available"]) else round(float(np.mean(~np.isnan(col[hab]))), 3)
    for crit in CFG["criteria"]:
        if crit.get("runtime") == "anchors":
            cov_crit[crit["id"]] = 1.0
            continue
        specs = [s for s in C["inds"] if s["criterion"] == crit["id"] and s["available"] and s["weight"] > 0]
        tw = sum(s["weight"] for s in specs)
        cov_crit[crit["id"]] = round(sum(s["weight"] * cov_ind[s["key"]] for s in specs) / tw, 3) if tw else 0.0
    return cov_ind, cov_crit


def meta(C):
    cc = C["cc"]
    cov_ind, cov_crit = coverage(C)
    crits = []
    for crit in CFG["criteria"]:
        inds = []
        for spec in [s for s in C["inds"] if s["criterion"] == crit["id"]]:
            inds.append({
                "id": spec["id"], "column": spec["column"], "label": spec["label"], "unit": spec["unit"],
                "unitLabel": CFG["units"][spec["unit"]], "decimals": spec.get("decimals", 0), "norm": spec["norm"],
                "weight": spec["weight"], "walkScaled": bool(spec.get("walkScaled")), "crossCity": spec["crossCity"],
                "priority": spec.get("priority", "P1"), "coverage": cov_ind[spec["key"]],
                "available": spec["available"] and cov_ind[spec["key"]] > 0, "sources": spec.get("sources", {}).get(C["city"], []),
            })
        crits.append({
            "id": crit["id"], "emoji": crit["emoji"], "label": crit["label"], "runtime": crit.get("runtime"),
            "caveat": crit.get("caveat"), "coverage": cov_crit[crit["id"]], "beta": cov_crit[crit["id"]] < 0.5,
            "sources": crit.get("sources", {}).get(C["city"], sorted({k for i in crit.get("indicators", []) for k in i.get("sources", {}).get(C["city"], [])})),
            "indicators": inds,
        })
    pcol = C["columns"][cc["price"]["column"]][C["habitable"]]
    return {
        "city": C["city"], "dataVersion": DATA_VERSION, "dataSource": "fixture", "walkSpeedKmh": CFG["walkSpeedKmh"],
        "levels": [{"level": int(l), "weight": w, "emoji": CFG["levelEmoji"][l], "label": CFG["levelLabel"][l]} for l, w in CFG["levels"].items()],
        "criteria": crits,
        "personas": [{k: p[k] for k in ("id", "emoji", "label", "weights", "indicatorWeights", "walkFactor", "suggestedAnchors")} for p in CFG["personas"]],
        "mustHaveCategories": [{"id": m["id"], "emoji": m["emoji"], "label": m["label"], "available": C["city"] in m.get("cities", [C["city"]])} for m in CFG["mustHaveCategories"]],
        "archetypes": [{"id": a["id"], "emoji": a["emoji"]} for a in CFG["archetypes"]],
        "modes": [{"id": k, "emoji": v["emoji"], "label": v["label"]} for k, v in CFG["modes"].items()],
        "price": {"indicator": cc["price"]["indicator"], "mode": cc["price"]["mode"], "currency": cc["currency"], "unit": cc["price"]["unit"],
                  "filterField": cc["price"]["filterField"], "budgetField": cc["price"]["budgetField"],
                  "cityMedian": float(np.median(pcol)), "min": float(pcol.min()), "max": float(pcol.max())},
        "adminLevels": {"district": {"label": cc["levels"]["district"]["label"], "count": cc["levels"]["district"].get("count")},
                        "neighborhood": {"label": cc["levels"]["neighborhood"]["label"], "count": cc["levels"]["neighborhood"].get("count")}},
        "manifest": [{"key": k, "url": None, "fetchedAt": None, "licence": None, "rows": None, "status": "missing",
                      "note": "fixture — no real data yet"} for k in sorted({s for c in crits for s in c["sources"]})],
    }


def place(C, req, h):
    i = C["cells"].index(h)
    resp = score_response(C, req)
    ctx = C["_ctx"]
    lang = ctx["lang"]
    hl, wn = explanations(C, ctx, i)
    indicators = []
    for key, (s, imp, w, spec) in ctx["sub"].items():
        raw = C["columns"][spec["column"]][i]
        indicators.append({
            "criterion": spec["criterion"], "indicator": spec["id"], "column": spec["column"],
            "value": None if imp[i] else float(raw), "unit": spec["unit"], "score": int(round(float(s[i]))), "weight": w,
            "cityMedianValue": float(np.nanmedian(C["columns"][spec["column"]][C["habitable"]])), "imputed": bool(imp[i]),
            "text": None if imp[i] else render(spec["explain"][lang], value=fmt(raw, lang, spec.get("decimals", 0))),
        })
    nearest_specs = [("tram_stop", "transit.tram_stop_walk_min", {"krakow": "Plac Wszystkich Świętych", "praha": "Náměstí Míru"}),
                     ("supermarket", "shops.supermarket_walk_min", {"krakow": "Carrefour Express", "praha": "Albert"}),
                     ("pharmacy", "health.pharmacy_walk_min", {"krakow": "Apteka Pod Opatrznością", "praha": "Lékárna Vinohrady"}),
                     ("park", "green.park_walk_min", {"krakow": "Planty", "praha": "Riegrovy sady"}),
                     ("primary_school", "education.primary_school_walk_min", {"krakow": "Szkoła Podstawowa nr 1", "praha": "ZŠ Vinohradská"}),
                     ("gp_clinic", "health.gp_walk_min", {"krakow": "Przychodnia Lekarska", "praha": "Praktický lékař MUDr. Novák"})]
    nearest = []
    for n, (cat, col, names) in enumerate(nearest_specs):
        wm = float(C["columns"][col][i])
        off = 0.0011 * (n + 1) * (1 if n % 2 else -1)
        nearest.append({"category": cat, "name": names[C["city"]], "lat": round(float(C["lat"][i]) + off, 6),
                        "lon": round(float(C["lon"][i]) - off, 6), "walkMin": wm})
    arch, probs = archetype_of(C, i)
    m2, m2t = budget_m2(C, i, req, lang)
    return {
        "id": h, "kind": "hex", "city": C["city"], "lang": lang,
        "centroid": {"lat": round(float(C["lat"][i]), 6), "lon": round(float(C["lon"][i]), 6)},
        "name": C["neighborhood"][i], "neighborhood": C["neighborhood"][i],
        "district": {"id": C["district_id"][i], "name": C["district_name"][i]},
        "habitable": bool(C["habitable"][i]), "populationEst": int(C["population"][i]),
        "score": int(ctx["M"][i]), "passes": bool(ctx["passing"][i]),
        "criteria": {c: int(round(float(s[i]))) for c, s in ctx["crit"].items()},
        "cityMedian": resp["cityMedian"], "indicators": indicators, "nearest": nearest,
        "anchors": [{"id": a["id"], "label": a.get("label"), "minutes": int(ctx["anchor_min"][a["id"]][i]), "mode": a.get("mode", "transit")} for a in ctx["anchors"]],
        "price": price_info(C, i, lang), "budgetM2": m2, "budgetText": m2t,
        "archetype": {**arch, "probs": probs}, "highlights": hl, "warnings": wn,
    }


def cross_vectors(C):
    keys = sorted(s["column"] for s in C["inds"] if s["crossCity"] and s["available"] and s["column"] in C["columns"])
    X = np.column_stack([np.nan_to_num(C["columns"][k], nan=np.nanmedian(C["columns"][k])) for k in keys])
    return keys, X


def similar_items(C_from, i, C_to, limit, mu, sd, same_city):
    _, Xf = cross_vectors(C_from)
    _, Xt = cross_vectors(C_to)
    a = (Xf[i] - mu) / sd
    B = (Xt - mu) / sd
    sim = B @ a / (np.linalg.norm(B, axis=1) * np.linalg.norm(a) + 1e-9)
    sim = (sim + 1) / 2
    order = [j for j in np.argsort(-sim) if C_to["habitable"][j] and not (same_city and j == i)]
    ctx_from = score(C_from, {"weights": persona("custom")["weights"], "persona": "custom"})[0]
    ctx_to = score(C_to, {"weights": persona("custom")["weights"], "persona": "custom"})[0]
    items = []
    for j in order[:limit]:
        shared = [c for c in ctx_to["crit"] if c in ctx_from["crit"] and ctx_to["crit"][c][j] >= 60 and ctx_from["crit"][c][i] >= 60]
        items.append({
            "id": C_to["cells"][j], "kind": "hex", "name": C_to["neighborhood"][j],
            "district": {"id": C_to["district_id"][j], "name": C_to["district_name"][j]},
            "centroid": {"lat": round(float(C_to["lat"][j]), 6), "lon": round(float(C_to["lon"][j]), 6)},
            "similarity": round(float(sim[j]), 3), "archetype": archetype_of(C_to, j)[0], "sharedTraits": shared[:4],
        })
    return items


def grid_geojson(C):
    feats = []
    for i, h in enumerate(C["cells"]):
        ring = [[round(lng, 6), round(la, 6)] for la, lng in h3.cell_to_boundary(h)]
        ring.append(ring[0])
        feats.append({"type": "Feature", "id": i, "geometry": {"type": "Polygon", "coordinates": [ring]},
                      "properties": {"h3": h, "district_id": C["district_id"][i], "district_name": C["district_name"][i],
                                     "neighborhood": C["neighborhood"][i], "habitable": bool(C["habitable"][i]),
                                     "population_est": int(C["population"][i])}})
    return {"type": "FeatureCollection", "features": feats}


def commute(C, a, mode):
    dest = h3.latlng_to_cell(a["lat"], a["lon"], 8)
    m = travel_minutes(C, {**a, "mode": mode})
    return {"city": C["city"], "anchorCell": dest, "mode": mode, "maxMinutes": 120, "computeMs": 3.1,
            "cells": [[h, int(m[i])] for i, h in enumerate(C["cells"]) if C["habitable"][i] and m[i] <= 120]}


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    cities = {c: build_city(c) for c in ("krakow", "praha")}
    covs = {c: coverage(C)[1] for c, C in cities.items()}
    # pooled standardisation for cross-city similarity
    keys = set.intersection(*[set(cross_vectors(C)[0]) for C in cities.values()])
    assert all(cross_vectors(C)[0] == sorted(keys) for C in cities.values()), "cross-city columns differ"
    pooled = np.vstack([cross_vectors(C)[1][C["habitable"]] for C in cities.values()])
    mu, sd = pooled.mean(0), pooled.std(0) + 1e-9

    dump(OUT / "cities.json", [{
        "id": c, "name": C["cc"]["name"], "country": C["cc"]["country"], "defaultLang": C["cc"]["defaultLang"],
        "currency": C["cc"]["currency"], "center": C["cc"]["center"], "zoom": C["cc"]["zoom"], "bbox": C["cc"]["bbox"],
        "priceMode": C["cc"]["price"]["mode"], "coverage": covs[c], "dataVersion": DATA_VERSION, "dataSource": "fixture",
    } for c, C in cities.items()])
    dump(OUT / "health.json", {"status": "ok", "dataVersion": {c: DATA_VERSION for c in cities},
                               "dataSource": {c: "fixture" for c in cities}, "builtAt": "2026-10-03T16:00:00Z"})

    for c, C in cities.items():
        P, lang = C["P"], C["cc"]["defaultLang"]
        d = OUT / c
        dump(d / "meta.json", meta(C))
        dump(d / "grid.sample.geojson", grid_geojson(C))
        req_student = {"v": 1, "lang": lang, "persona": "student", "weights": persona("student")["weights"],
                       "anchors": P["anchors"]["student"], "filters": P["filters"]["student"],
                       "budget": P["budget"]["student"], "aggregate": "hex", "limit": 20}
        req_parent = {"v": 1, "lang": lang, "persona": "parent", "weights": persona("parent")["weights"],
                      "anchors": P["anchors"]["parent"], "filters": P["filters"]["parent"],
                      "budget": P["budget"]["parent"], "aggregate": "hex", "limit": 20}
        s1 = score_response(C, req_student)
        dump(d / "score_student.json", s1)
        dump(d / "score_parent.json", score_response(C, req_parent))
        dump(d / "score_districts.json", score_response(C, {**req_parent, "aggregate": "district", "limit": 10, "includeCells": False}))
        dump(d / "score_nomatch.json", score_response(C, {**req_parent, "filters": P["filters"]["nomatch"]}))
        top_h = s1["top"][0]["id"]
        dump(d / "place.json", place(C, req_student, top_h))
        dump(d / "commute.json", commute(C, P["anchors"]["parent"][0], "transit"))
        dump(d / "similar.json", {"city": c, "from": top_h, "items": similar_items(C, C["cells"].index(top_h), C, 5, mu, sd, True)})
        dump(d / "districts.json", {"city": c, "level": "district", "items": [
            {"id": did, "name": name, "centroid": {"lat": la, "lon": lo},
             "cellCount": int(sum(1 for x in C["district_id"] if x == did)),
             "habitableCount": int(sum(1 for x, hb in zip(C["district_id"], C["habitable"]) if x == did and hb)),
             "populationEst": int(sum(p for x, p in zip(C["district_id"], C["population"]) if x == did))}
            for did, (name, la, lo) in P["districts"].items() if did in C["district_id"]]})
        dump(d / "geocode.json", {"query": "fixture", "items": [
            {"label": lab, "sublabel": sub, "kind": kind, "category": cat, "lat": la, "lon": lo,
             "h3": h3.latlng_to_cell(la, lo, RES), "source": "local"} for lab, sub, kind, cat, la, lo in P["geocode"]]})
        st = P["air"]["station"]
        dump(d / "live_air.json", {"city": c, "status": "ok", "source": P["air"]["source"],
                                   "station": {**st, "distanceKm": 0.8}, "level": 1 if c == "praha" else 2,
                                   "pollutants": {"pm25": 11.0 if c == "praha" else 17.4, "pm10": 19.0 if c == "praha" else 26.1, "no2": 21.3, "o3": 44.0},
                                   "measuredAt": "2026-10-03T15:00:00Z", "fetchedAt": "2026-10-03T15:12:00Z", "cacheTtlS": 600})

    # twins: Kazimierz (Kraków) → Praha, and the reverse from Žižkov
    K, Pr = cities["krakow"], cities["praha"]
    def cell_near(C, name):
        idx = [i for i, n in enumerate(C["neighborhood"]) if n == name and C["habitable"][i]]
        la, lo = C["P"]["neighborhoods"][name]
        return min(idx, key=lambda i: km(la, lo, C["lat"][i], C["lon"][i]))
    def twins(Cf, i, Ct):
        return {"from": {"city": Cf["city"], "id": Cf["cells"][i], "kind": "hex", "name": Cf["neighborhood"][i],
                         "district": {"id": Cf["district_id"][i], "name": Cf["district_name"][i]},
                         "centroid": {"lat": round(float(Cf["lat"][i]), 6), "lon": round(float(Cf["lon"][i]), 6)},
                         "archetype": archetype_of(Cf, i)[0]},
                "to": Ct["city"], "items": similar_items(Cf, i, Ct, 5, mu, sd, False)}
    dump(OUT / "twins.json", twins(K, cell_near(K, "Kazimierz"), Pr))
    dump(OUT / "twins_praha_krakow.json", twins(Pr, cell_near(Pr, "Žižkov"), K))
    print("fixtures written to", OUT)


if __name__ == "__main__":
    main()
