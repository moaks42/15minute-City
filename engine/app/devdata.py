"""Synthetic dev data in the exact data/processed/{city}/ layout (contracts/DATA_CONTRACT.md).

Used only until Workstream A's real data lands. Written to engine/.devdata/ (gitignored), never into data/.
Values are plausible functions of distance from the centre + noise; manifest marks every source "fallback".

    uv run python -m app.devdata            # writes engine/.devdata/{krakow,praha}
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import h3
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

ENGINE = Path(__file__).resolve().parents[1]
REPO = ENGINE.parent
DEVDATA = ENGINE / ".devdata"

# k-ring radius → ≈ README §5 cell counts (K ≈ 3,100, P ≈ 4,700)
K_RING = {"krakow": 32, "praha": 40}

DISTRICTS = {
    "krakow": [
        ("1", "Stare Miasto", 50.0619, 19.9369), ("2", "Grzegórzki", 50.0620, 19.9620),
        ("3", "Prądnik Czerwony", 50.0900, 19.9700), ("4", "Prądnik Biały", 50.0950, 19.9250),
        ("5", "Krowodrza", 50.0750, 19.9150), ("6", "Bronowice", 50.0800, 19.8800),
        ("7", "Zwierzyniec", 50.0550, 19.8700), ("8", "Dębniki", 50.0350, 19.9000),
        ("9", "Łagiewniki-Borek Fałęcki", 50.0250, 19.9350), ("10", "Swoszowice", 49.9950, 19.9400),
        ("11", "Podgórze Duchackie", 50.0180, 19.9600), ("12", "Bieżanów-Prokocim", 50.0200, 20.0100),
        ("13", "Podgórze", 50.0420, 19.9700), ("14", "Czyżyny", 50.0700, 20.0050),
        ("15", "Mistrzejowice", 50.1000, 20.0050), ("16", "Bieńczyce", 50.0850, 20.0250),
        ("17", "Wzgórza Krzesławickie", 50.0950, 20.0650), ("18", "Nowa Huta", 50.0700, 20.0800),
    ],
    "praha": [
        (str(i), f"Praha {i}", la, lo) for i, (la, lo) in enumerate([
            (50.087, 14.420), (50.074, 14.433), (50.085, 14.460), (50.035, 14.445), (50.060, 14.385),
            (50.100, 14.360), (50.103, 14.435), (50.115, 14.465), (50.110, 14.505), (50.068, 14.485),
            (50.030, 14.505), (50.000, 14.425), (50.050, 14.330), (50.105, 14.565), (50.050, 14.545),
            (49.985, 14.360), (50.065, 14.300), (50.140, 14.505), (50.120, 14.600), (50.100, 14.640),
            (50.080, 14.680), (50.040, 14.610)], start=1)
    ],
}
NEIGHBORHOODS = {
    "krakow": {
        "Stare Miasto": (50.0614, 19.9366), "Kazimierz": (50.0510, 19.9460), "Podgórze": (50.0440, 19.9560),
        "Zabłocie": (50.0490, 19.9640), "Grzegórzki": (50.0610, 19.9600), "Kleparz": (50.0700, 19.9390),
        "Nowy Świat": (50.0570, 19.9280), "Półwsie Zwierzynieckie": (50.0530, 19.9130), "Dębniki": (50.0450, 19.9220),
        "Ludwinów": (50.0400, 19.9320), "Krowodrza": (50.0760, 19.9200), "Łobzów": (50.0790, 19.9130),
        "Olsza": (50.0760, 19.9620), "Dąbie": (50.0570, 19.9820), "Płaszów": (50.0390, 19.9800),
        "Bronowice Małe": (50.0830, 19.8850), "Wola Justowska": (50.0640, 19.8700), "Salwator": (50.0550, 19.9000),
        "Ruczaj": (50.0220, 19.9050), "Kurdwanów": (50.0100, 19.9550), "Prokocim": (50.0150, 20.0050),
        "Czyżyny": (50.0700, 20.0050), "Mistrzejowice": (50.1000, 20.0050), "Bieńczyce": (50.0850, 20.0250),
        "Nowa Huta": (50.0720, 20.0380), "Azory": (50.0900, 19.9150), "Prądnik Czerwony": (50.0950, 19.9700),
        "Swoszowice": (49.9950, 19.9400), "Bielany": (50.0450, 19.8450), "Pleszów": (50.0650, 20.0900),
    },
    "praha": {
        "Nové Město": (50.0790, 14.4260), "Staré Město": (50.0870, 14.4210), "Vinohrady": (50.0750, 14.4450),
        "Žižkov": (50.0850, 14.4550), "Karlín": (50.0925, 14.4520), "Vyšehrad": (50.0640, 14.4190),
        "Nusle": (50.0630, 14.4400), "Vršovice": (50.0680, 14.4600), "Holešovice": (50.1030, 14.4400),
        "Smíchov": (50.0700, 14.4030), "Malá Strana": (50.0880, 14.4040), "Bubeneč": (50.1000, 14.4150),
        "Libeň": (50.1050, 14.4750), "Michle": (50.0550, 14.4500), "Dejvice": (50.1030, 14.3900),
        "Břevnov": (50.0850, 14.3600), "Strašnice": (50.0700, 14.4950), "Chodov": (50.0300, 14.4950),
        "Modřany": (50.0000, 14.4100), "Prosek": (50.1200, 14.5000), "Vysočany": (50.1100, 14.5000),
        "Stodůlky": (50.0450, 14.3100), "Hostivař": (50.0550, 14.5300), "Letňany": (50.1350, 14.5100),
        "Hloubětín": (50.1050, 14.5350), "Krč": (50.0350, 14.4500), "Řepy": (50.0650, 14.3000),
        "Černý Most": (50.1050, 14.5800), "Kobylisy": (50.1250, 14.4600), "Troja": (50.1150, 14.4200),
    },
}
RIVERS = {
    "krakow": [(50.0700, 19.8200), (50.0560, 19.8950), (50.0510, 19.9200), (50.0480, 19.9340), (50.0500, 19.9480),
               (50.0470, 19.9600), (50.0440, 19.9750), (50.0480, 19.9900), (50.0420, 20.0300), (50.0350, 20.0800)],
    "praha": [(49.9800, 14.3950), (50.0300, 14.4080), (50.0550, 14.4150), (50.0650, 14.4135), (50.0750, 14.4135),
              (50.0850, 14.4130), (50.0920, 14.4180), (50.0960, 14.4300), (50.0980, 14.4500), (50.1030, 14.4650),
              (50.1150, 14.4300), (50.1300, 14.4000)],
}
PRICE = {"krakow": ("price.buy_per_m2", 17500, 900, 8500), "praha": ("price.rent_per_m2", 440, 18, 230)}

POI_CATEGORIES = {  # category → (count, centre bias 0..1, column used to sanity-check)
    "supermarket": (260, 0.6), "discount_grocery": (150, 0.4), "pharmacy": (280, 0.6), "post_office": (60, 0.5),
    "parcel_locker": (600, 0.4), "bakery": (200, 0.6), "marketplace": (20, 0.6), "atm": (400, 0.7),
    "playground": (450, 0.2), "park": (80, 0.2), "nursery": (120, 0.4), "kindergarten": (260, 0.3),
    "primary_school": (170, 0.3), "secondary_school": (90, 0.6), "university": (25, 0.8), "library": (60, 0.5),
    "gp_clinic": (180, 0.5), "paediatrician": (110, 0.5), "gynaecology": (90, 0.6), "dentist": (300, 0.6),
    "hospital_er": (8, 0.6), "maternity_ward": (6, 0.6), "tram_stop": (220, 0.6), "bus_stop": (900, 0.2),
    "metro_station": (40, 0.7), "rail_station": (20, 0.4), "culture": (140, 0.8), "sports": (200, 0.4),
    "kids_sports": (90, 0.3), "restaurant": (1500, 0.8), "cafe": (700, 0.8), "bar": (400, 0.85),
}
STREETS = {  # real street names at approximate positions (dev geocoder only; positions are not surveyed)
    "krakow": [("Rakowicka", 50.0680, 19.9530), ("Długa", 50.0700, 19.9390), ("Karmelicka", 50.0680, 19.9280),
               ("Floriańska", 50.0640, 19.9400), ("Grodzka", 50.0570, 19.9380), ("Starowiślna", 50.0560, 19.9470),
               ("Józefa Dietla", 50.0520, 19.9420), ("Kalwaryjska", 50.0420, 19.9500), ("Wielicka", 50.0350, 19.9700),
               ("Mogilska", 50.0670, 19.9700), ("Juliusza Lea", 50.0760, 19.9150), ("Królewska", 50.0740, 19.9230),
               ("Lipowa", 50.0480, 19.9600), ("Kapelanka", 50.0400, 19.9200), ("Czarnowiejska", 50.0680, 19.9180),
               ("Aleja Pokoju", 50.0600, 19.9800), ("Nowohucka", 50.0500, 19.9900), ("Ruczaj", 50.0220, 19.9050)],
    "praha": [("Vinohradská", 50.0770, 14.4500), ("Národní", 50.0820, 14.4170), ("Žitná", 50.0750, 14.4250),
              ("Korunní", 50.0750, 14.4450), ("Seifertova", 50.0850, 14.4450), ("Sokolovská", 50.0930, 14.4600),
              ("Křižíkova", 50.0920, 14.4450), ("Bělehradská", 50.0700, 14.4320), ("Nuselská", 50.0580, 14.4450),
              ("Táborská", 50.0620, 14.4300), ("Plzeňská", 50.0700, 14.3850), ("Štefánikova", 50.0760, 14.4040),
              ("Milady Horákové", 50.1000, 14.4200), ("Dukelských hrdinů", 50.1020, 14.4320), ("Evropská", 50.1000, 14.3700),
              ("Kodaňská", 50.0680, 14.4600), ("Na Pankráci", 50.0550, 14.4350), ("Chodovská", 50.0350, 14.4900)],
}
UNIVERSITY_NAMES = {
    "krakow": ["Uniwersytet Jagielloński", "Akademia Górniczo-Hutnicza", "Politechnika Krakowska",
               "Uniwersytet Ekonomiczny w Krakowie", "Uniwersytet Pedagogiczny"],
    "praha": ["Univerzita Karlova", "České vysoké učení technické", "Vysoká škola ekonomická",
              "Česká zemědělská univerzita", "Vysoká škola chemicko-technologická"],
}


def _km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _dist_polyline(lat, lon, pts):
    best = np.full(len(lat), 1e9)
    for (a_lat, a_lon), (b_lat, b_lon) in zip(pts, pts[1:]):
        for t in np.linspace(0, 1, 30):
            best = np.minimum(best, _km(lat, lon, a_lat + t * (b_lat - a_lat), a_lon + t * (b_lon - a_lon)))
    return best


def _indicator_columns(cfg: dict, city: str) -> dict[str, dict]:
    out = {}
    for crit in cfg["criteria"]:
        for ind in crit.get("indicators", []):
            if "column" not in ind and city in ind.get("cities", [city]):
                out[f"{crit['id']}.{ind['id']}"] = ind
    return out


def _synth(col: str, unit: str, d, river, rng, city):
    n = len(d)
    z = rng.normal(0, 1, n)
    walk = {  # base minutes at centre, growth per km
        "transit.stop_walk_min": (1.5, 0.35), "transit.tram_stop_walk_min": (2.5, 1.4),
        "transit.rail_station_walk_min": (6, 2.0), "poi.metro_station_walk_min": (4, 3.2),
        "health.hospital_er_walk_min": (10, 2.5), "health.maternity_walk_min": (14, 3.0),
        "education.university_walk_min": (7, 3.0), "active.car_free_walk_min": (3, 2.5),
        "active.bikeshare_walk_min": (2, 1.0), "green.park_walk_min": (6, 0.2),
        "health.gynaecology_walk_min": (4, 1.5), "leisure.culture_walk_min": (3, 2.2),
    }
    if col in walk or unit == "min":
        b, g = walk.get(col, (3, 1.0))
        return np.clip(b + g * d + np.abs(z) * 2.5, 0.5, 60.0)
    if col == PRICE[city][0]:
        _, c, drop, floor = PRICE[city]
        return np.maximum(c - drop * d + z * c * 0.07, floor).round(0)
    table = {
        "environment.noise_db": lambda: np.clip(64 - 1.6 * d + z * 5 + np.where(river < 0.4, 3, 0), 38, 78),
        "environment.pm25": lambda: np.clip((19 if city == "krakow" else 14) - 0.35 * d + z * 1.3
                                           + (np.where(d > 7, 2.5, 0) if city == "krakow" else 0), 7, 32),
        "environment.pm10": lambda: np.clip((30 if city == "krakow" else 24) - 0.5 * d + z * 2.2, 12, 48),
        "environment.major_road_m": lambda: np.clip(100 + 70 * d + z * 120, 10, 2500),
        "environment.industrial_ha_1km": lambda: np.clip(1 + 2.2 * d + z * 6, 0, 120),
        "safety.crime_per_1000": None,  # district level, set by caller
        "safety.lit_share": lambda: np.clip(92 - 4 * d + z * 6, 20, 100),
        "green.green_share_500m": lambda: np.clip(9 + 4.5 * d + z * 8 + np.where(river < 0.5, 8, 0), 1, 90),
        "green.forest_meadow_ha_1km": lambda: np.clip(-5 + 9 * d + z * 12, 0, 300),
        "transit.departures_per_h_500m": lambda: np.clip(110 - 16 * d + z * 14, 0, 300),
        "transit.lines_500m": lambda: np.clip(20 - 2.4 * d + z * 2.5, 0, 40).round(),
        "transit.night_departures_500m": lambda: np.clip(26 - 4 * d + z * 4, 0, 60).round(),
        "active.cycleway_km_1km": lambda: np.clip(6.5 - 0.5 * d + z * 1.4, 0, 15),
        "active.intersection_density": lambda: np.clip(170 - 17 * d + z * 20, 5, 320),
        "active.bike_racks_300m": lambda: np.clip(14 - 2 * d + z * 3, 0, 40).round(),
        "family.playgrounds_500m": lambda: np.clip(3 + 0.4 * d + z * 1.8, 0, 14).round(),
        "shops.shops_10min": lambda: np.clip(170 - 25 * d + z * 22, 0, 400).round(),
        "leisure.food_10min": lambda: np.clip(150 - 25 * d + z * 20, 0, 400).round(),
        "leisure.nightlife_10min": lambda: np.clip(50 - 10 * d + z * 7, 0, 120).round(),
        "accessibility.accessible_stop_share": lambda: np.clip(70 + 2 * d + z * 10, 0, 100),
        "accessibility.lowfloor_trip_share": lambda: np.clip((82 if city == "krakow" else 76) + 1.5 * d + z * 7, 20, 100),
        "accessibility.benches_300m": lambda: np.clip(18 - 2 * d + z * 4, 0, 50).round(),
        "accessibility.slope_pct": lambda: np.full(n, np.nan),  # P2: no DEM yet → 0% coverage
    }
    f = table.get(col)
    if f is None:
        raise KeyError(f"no synthetic recipe for {col}")
    return f().astype(float)


def generate_city(city: str, out_dir: Path, cfg: dict) -> None:
    cc = yaml.safe_load((REPO / f"config/cities/{city}.yaml").read_text(encoding="utf-8"))
    rng = np.random.default_rng({"krakow": 11, "praha": 23}[city])
    lat0, lon0 = cc["center"]
    cells = sorted(h3.grid_disk(h3.latlng_to_cell(lat0, lon0, 9), K_RING[city]))
    ll = np.array([h3.cell_to_latlng(c) for c in cells])
    lat, lon = ll[:, 0], ll[:, 1]
    d = _km(lat0, lon0, lat, lon)
    river = _dist_polyline(lat, lon, RIVERS[city])

    dist = DISTRICTS[city]
    dd = np.stack([_km(la, lo, lat, lon) for _, _, la, lo in dist])
    di = dd.argmin(0)
    district_id = [dist[i][0] for i in di]
    district_name = [dist[i][1] for i in di]
    nb = NEIGHBORHOODS[city]
    nn = np.stack([_km(la, lo, lat, lon) for la, lo in nb.values()]).argmin(0)
    neighborhood = [list(nb)[i] for i in nn]

    edge = d / d.max()
    habitable = (river > 0.12) & (rng.random(len(cells)) > 0.05 + 0.45 * edge ** 3)
    pop = np.where(habitable, np.clip(700 - 70 * d + rng.normal(0, 160, len(d)), 3, 1800), 0).round().astype(np.int32)

    cols: dict[str, np.ndarray] = {}
    for col, ind in _indicator_columns(cfg, city).items():
        if col == "safety.crime_per_1000":
            per_d = {k: max(15.0, 90 - 8 * float(np.mean(d[np.array(district_id) == k])) + rng.normal(0, 10))
                     for k in set(district_id)}
            cols[col] = np.array([round(per_d[k], 1) for k in district_id])
        else:
            cols[col] = _synth(col, ind["unit"], d, river, rng, city)
    if city == "praha":
        cols["poi.metro_station_walk_min"] = _synth("poi.metro_station_walk_min", "min", d, river, rng, city)
    for col in ("health.gynaecology_walk_min", "environment.industrial_ha_1km"):
        cols[col][rng.random(len(cells)) < 0.04] = np.nan  # exercise imputation

    out = out_dir / city
    out.mkdir(parents=True, exist_ok=True)

    feats = []
    for i, c in enumerate(cells):
        ring = [[round(x, 6), round(y, 6)] for y, x in h3.cell_to_boundary(c)]
        feats.append({"type": "Feature", "id": i, "geometry": {"type": "Polygon", "coordinates": [ring + [ring[0]]]},
                      "properties": {"h3": c, "district_id": district_id[i], "district_name": district_name[i],
                                     "neighborhood": neighborhood[i], "habitable": bool(habitable[i]),
                                     "population_est": int(pop[i])}})
    (out / "grid.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False), encoding="utf-8")

    data = {"h3": cells, "lat": lat, "lon": lon, "habitable": habitable, "district_id": district_id,
            "district_name": district_name, "neighborhood": neighborhood, "population_est": pop}
    data.update({k: v.astype(np.float32) for k, v in cols.items()})
    pq.write_table(pa.table(data), out / "features.parquet", compression="snappy")

    # POIs
    rows = {k: [] for k in ("category", "name", "lat", "lon", "h3_9", "source", "extra_json")}
    w_all = np.where(habitable, 1.0, 0.05)
    for cat, (n, bias) in POI_CATEGORIES.items():
        n = int(n * len(cells) / 4700)
        if cat == "metro_station" and city == "krakow":
            continue
        w = w_all * np.exp(-d * bias * 0.6)
        idx = rng.choice(len(cells), size=max(n, 2), p=w / w.sum())
        for j, i in enumerate(idx):
            name = (UNIVERSITY_NAMES[city][j % 5] if cat == "university" else f"{cat.replace('_', ' ').title()} {j + 1} (dev)")
            jl, jo = lat[i] + rng.normal(0, 0.0007), lon[i] + rng.normal(0, 0.0011)
            rows["category"].append(cat); rows["name"].append(name)
            rows["lat"].append(float(jl)); rows["lon"].append(float(jo))
            rows["h3_9"].append(h3.latlng_to_cell(jl, jo, 9)); rows["source"].append("synthetic")
            rows["extra_json"].append(None)
    pq.write_table(pa.table(rows), out / "pois.parquet", compression="snappy")

    # addresses (optional file, contracts-v2): cells within 400 m of a street anchor get consecutive numbers
    arows = {k: [] for k in ("street", "housenumber", "postcode", "lat", "lon", "h3_9", "source")}
    for street, sla, slo in STREETS[city]:
        near = np.flatnonzero((_km(sla, slo, lat, lon) < 0.4) & habitable)
        for no, i in enumerate(near[np.argsort(lon[near])], start=1):
            arows["street"].append(street); arows["housenumber"].append(str(2 * no - 1)); arows["postcode"].append(None)
            arows["lat"].append(float(lat[i])); arows["lon"].append(float(lon[i])); arows["h3_9"].append(cells[i])
            arows["source"].append("synthetic")
    pq.write_table(pa.table(arows), out / "addresses.parquet", compression="snappy")

    # travel times: habitable res-9 origins × res-8 dests
    origins = np.array([c for c, h in zip(cells, habitable) if h])
    dests = np.array(sorted({h3.cell_to_parent(c, 8) for c in cells}))
    o_ll = np.array([h3.cell_to_latlng(c) for c in origins])
    d_ll = np.array([h3.cell_to_latlng(c) for c in dests])
    D = _km(o_ll[:, :1], o_ll[:, 1:], d_ll[None, :, 0], d_ll[None, :, 1])  # (n_o, n_d) km
    jitter = rng.normal(0, 1, D.shape)
    def u8(m):
        m = np.round(m)
        return np.where(m > 120, 255, np.clip(m, 0, 120)).astype(np.uint8)
    np.savez_compressed(
        out / "travel_times.npz", origins=origins, dests=dests,
        transit=u8(7 + 3.0 * D + np.abs(jitter) * 3), bike=u8(2 + 4.2 * D + np.abs(jitter)),
        walk=u8(12.5 * D * 1.2), meta_json=np.array(json.dumps({"method": "synthetic", "departure": "08:00"})),
    )

    # admin layers
    def admin(ids, names, parent=None):
        fs = []
        for k in dict.fromkeys(ids):
            members = [c for c, x in zip(cells, ids) if x == k]
            geo = h3.cells_to_geo(members)
            p = {"id": k, "name": names[ids.index(k)], "population_est": int(sum(pop[i] for i, x in enumerate(ids) if x == k))}
            if parent is not None:
                p["district_id"] = parent[ids.index(k)]
            fs.append({"type": "Feature", "geometry": geo, "properties": p})
        return {"type": "FeatureCollection", "features": fs}
    (out / "districts.geojson").write_text(json.dumps(admin(district_id, district_name), ensure_ascii=False), encoding="utf-8")
    (out / "neighborhoods.geojson").write_text(json.dumps(admin(neighborhood, neighborhood, district_id), ensure_ascii=False), encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sources = sorted({k for c in cfg["criteria"] for i in c.get("indicators", []) for k in i.get("sources", {}).get(city, [])})
    manifest = {"city": city, "dataVersion": f"synthetic-{now}", "builtAt": now,
                "sources": [{"key": k, "url": None, "fetchedAt": None, "licence": None, "rows": None,
                             "status": "fallback", "note": "synthetic dev data (engine/app/devdata.py) — not real"} for k in sources]}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")


def generate(out_dir: Path = DEVDATA, cities=("krakow", "praha")) -> Path:
    cfg = yaml.safe_load((REPO / "config/indicators.yaml").read_text(encoding="utf-8"))
    for city in cities:
        generate_city(city, out_dir, cfg)
    return out_dir


if __name__ == "__main__":
    print("wrote", generate())
