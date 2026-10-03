# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "pyarrow>=15", "numpy>=1.26", "h3>=4,<5"]
# ///
"""Validate data/processed/{city}/ against contracts/DATA_CONTRACT.md + config/indicators.yaml.

    uv run contracts/tools/validate_data.py --city all [--data-dir data/processed]

Importable: the engine calls `validate_city()` at startup and refuses to load on errors.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import h3
import numpy as np
import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parents[2]
MAX_BYTES = 50 * 1024 * 1024
NAN_WARN = 0.20

ID_COLUMNS = {
    "h3": "string", "lat": "float", "lon": "float", "habitable": "bool",
    "district_id": "string", "district_name": "string", "neighborhood": "string", "population_est": "int",
}
# aux column → cities where it is REQUIRED (empty = optional everywhere)
AUX_COLUMNS = {"poi.metro_station_walk_min": ["praha"], "price.buy_n_transactions": []}
RANGES = {
    "min": (0, 60), "pct": (0, 100), "dep_h": (0, 600), "count": (0, 1e6), "km": (0, 100), "per_km2": (0, 1000),
    "ha": (0, 315), "m": (0, 20000), "db": (30, 90), "ugm3": (0, 150), "per_1000": (0, 1000),
    "pln_m2": (2000, 60000), "czk_m2_month": (100, 1500),
}
POI_COLUMNS = ["category", "name", "lat", "lon", "h3_9", "source", "extra_json"]
ADDRESS_COLUMNS = ["street", "housenumber", "lat", "lon", "h3_9"]
POI_VOCAB = set("""supermarket discount_grocery pharmacy post_office parcel_locker bakery marketplace atm playground park
nursery kindergarten primary_school secondary_school university library gp_clinic paediatrician gynaecology dentist
hospital_er maternity_ward bus_stop tram_stop metro_station rail_station bike_rack bikeshare_station culture sports
kids_sports restaurant cafe bar nightclub bench""".split())
REQUIRED_FILES = ["grid.geojson", "features.parquet", "manifest.json"]
OPTIONAL_FILES = ["pois.parquet", "travel_times.npz", "districts.geojson", "neighborhoods.geojson"]
SILENT_OPTIONAL = ["addresses.parquet"]  # contracts-v2; absence is fine


@dataclass
class Report:
    city: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage: dict[str, float] = field(default_factory=dict)
    nan_share: dict[str, float] = field(default_factory=dict)

    def err(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def load_config(config_dir: Path) -> dict:
    return yaml.safe_load((config_dir / "indicators.yaml").read_text(encoding="utf-8"))


def expected_indicators(cfg: dict, city: str) -> dict[str, dict]:
    """column → indicator spec for every scored, non-alias indicator that applies to `city`."""
    out = {}
    for crit in cfg["criteria"]:
        for ind in crit.get("indicators", []):
            if "column" in ind or city not in ind.get("cities", [city]):
                continue
            out[f"{crit['id']}.{ind['id']}"] = {**ind, "criterion": crit["id"]}
    return out


def _kind(arrow_type) -> str:
    import pyarrow as pa
    if pa.types.is_floating(arrow_type):
        return "float"
    if pa.types.is_integer(arrow_type):
        return "int"
    if pa.types.is_boolean(arrow_type):
        return "bool"
    if pa.types.is_string(arrow_type) or pa.types.is_large_string(arrow_type) or pa.types.is_dictionary(arrow_type):
        return "string"
    if pa.types.is_null(arrow_type):
        return "null"
    return str(arrow_type)


def _valid_h3(values, res: int) -> int:
    bad = 0
    for v in values:
        if not isinstance(v, str) or not h3.is_valid_cell(v) or h3.get_resolution(v) != res:
            bad += 1
    return bad


def validate_city(data_dir: Path, city: str, config_dir: Path = ROOT / "config") -> Report:
    r = Report(city)
    cfg = load_config(config_dir)
    d = Path(data_dir) / city
    if not d.is_dir():
        r.err(f"{d} does not exist")
        return r
    for f in REQUIRED_FILES + OPTIONAL_FILES + SILENT_OPTIONAL:
        p = d / f
        if not p.exists() and f in SILENT_OPTIONAL:
            continue
        if not p.exists():
            (r.err if f in REQUIRED_FILES else r.warn)(f"missing {f}" + ("" if f in REQUIRED_FILES else " (engine runs degraded)"))
        elif p.stat().st_size > MAX_BYTES:
            r.err(f"{f} is {p.stat().st_size / 1e6:.1f} MB > 50 MB")
    if r.errors:
        return r

    # ── grid
    grid = json.loads((d / "grid.geojson").read_text(encoding="utf-8"))
    feats = grid.get("features", [])
    if grid.get("type") != "FeatureCollection" or not feats:
        r.err("grid.geojson: not a non-empty FeatureCollection")
        return r
    grid_h3 = []
    for i, f in enumerate(feats):
        p = f.get("properties", {})
        if f.get("id") != i:
            r.err(f"grid.geojson: feature {i} id={f.get('id')!r}, expected {i}")
            break
        if f.get("geometry", {}).get("type") != "Polygon":
            r.err(f"grid.geojson: feature {i} geometry is not a Polygon")
            break
        for k, t in (("h3", str), ("district_id", str), ("district_name", str), ("habitable", bool), ("population_est", int)):
            if not isinstance(p.get(k), t):
                r.err(f"grid.geojson: feature {i} property {k}={p.get(k)!r} is not {t.__name__}")
                break
        if "neighborhood" not in p:
            r.err(f"grid.geojson: feature {i} lacks property neighborhood")
        grid_h3.append(p.get("h3"))
        if r.errors:
            break
    if r.errors:
        return r
    if (bad := _valid_h3(grid_h3, 9)):
        r.err(f"grid.geojson: {bad} invalid / non-res-9 h3 values")
    if len(set(grid_h3)) != len(grid_h3):
        r.err("grid.geojson: duplicate h3 cells")

    # ── features
    table = pq.read_table(d / "features.parquet")
    schema = {f.name: _kind(f.type) for f in table.schema}
    cols = set(schema)
    for c, kind in ID_COLUMNS.items():
        if c not in cols:
            r.err(f"features.parquet: missing identity column {c}")
        elif schema[c] != kind and not (c == "neighborhood" and schema[c] == "null"):
            r.err(f"features.parquet: {c} has dtype {schema[c]}, expected {kind}")
    expected = expected_indicators(cfg, city)
    for c in expected:
        if c not in cols:
            r.err(f"features.parquet: missing indicator column {c} (write it all-NaN if you have no data)")
        elif schema[c] not in ("float", "null"):
            r.err(f"features.parquet: {c} has dtype {schema[c]}, expected float")
    for c, req_cities in AUX_COLUMNS.items():
        if city in req_cities and c not in cols:
            r.err(f"features.parquet: missing auxiliary column {c}")
    allowed = set(ID_COLUMNS) | set(expected) | set(AUX_COLUMNS)
    for c in sorted(cols - allowed):
        if not c.startswith("aux."):
            r.err(f"features.parquet: unknown column {c!r} (typo? not in indicators.yaml / DATA_CONTRACT)")
    if r.errors:
        return r

    fh3 = table.column("h3").to_pylist()
    if fh3 != grid_h3:
        r.err("features.parquet: h3 column differs from grid.geojson (same cells, same order required)")
        return r
    hab = np.asarray(table.column("habitable").to_pylist(), dtype=bool)
    grid_hab = np.array([f["properties"]["habitable"] for f in feats], dtype=bool)
    if not np.array_equal(hab, grid_hab):
        r.err("features.parquet: habitable differs from grid.geojson")
    if hab.sum() == 0:
        r.err("features.parquet: no habitable cells")
        return r

    for c, spec in expected.items():
        v = np.asarray(table.column(c).to_numpy(zero_copy_only=False), dtype=float)
        vh = v[hab]
        nan = float(np.mean(np.isnan(vh)))
        r.nan_share[c] = round(nan, 3)
        if nan == 1.0:
            r.warn(f"{c}: all NaN → 0% coverage (dropped from the criterion)")
            continue
        if nan > NAN_WARN:
            r.warn(f"{c}: {nan:.0%} NaN among habitable cells")
        lo, hi = RANGES[spec["unit"]]
        finite = vh[~np.isnan(vh)]
        out = np.mean((finite < lo) | (finite > hi))
        if out > 0:
            r.warn(f"{c}: {out:.1%} of values outside expected range {lo}–{hi} {spec['unit']} (min {finite.min():.3g}, max {finite.max():.3g})")
        if spec["unit"] == "min" and finite.max() > 60.0001:
            r.warn(f"{c}: walk minutes above the 60 cap")

    for crit in cfg["criteria"]:
        if crit.get("runtime"):
            continue
        specs = [(f"{crit['id']}.{i['id']}", i) for i in crit.get("indicators", [])
                 if "column" not in i and city in i.get("cities", [city]) and i["weight"] > 0]
        tw = sum(i["weight"] for _, i in specs)
        r.coverage[crit["id"]] = round(sum(i["weight"] * (1 - r.nan_share.get(c, 1.0)) for c, i in specs) / tw, 3) if tw else 0.0

    # ── pois
    if (d / "pois.parquet").exists():
        pt = pq.read_table(d / "pois.parquet")
        missing = [c for c in POI_COLUMNS if c not in pt.column_names]
        if missing:
            r.err(f"pois.parquet: missing columns {missing}")
        else:
            cats = set(pt.column("category").to_pylist())
            if unknown := sorted(c for c in cats if c not in POI_VOCAB):
                r.warn(f"pois.parquet: categories outside the vocabulary: {unknown}")
            sample = pt.column("h3_9").to_pylist()[:5000]
            if (bad := _valid_h3(sample, 9)):
                r.err(f"pois.parquet: {bad} invalid h3_9 values (first 5000 rows)")

    # ── addresses (contracts-v2, optional)
    if (d / "addresses.parquet").exists():
        at = pq.read_table(d / "addresses.parquet")
        if missing := [c for c in ADDRESS_COLUMNS if c not in at.column_names]:
            r.err(f"addresses.parquet: missing columns {missing}")
        elif at.num_rows and (bad := _valid_h3(at.column("h3_9").to_pylist()[:5000], 9)):
            r.err(f"addresses.parquet: {bad} invalid h3_9 values (first 5000 rows)")

    # ── travel times
    if (d / "travel_times.npz").exists():
        z = np.load(d / "travel_times.npz", allow_pickle=False)
        if "origins" not in z or "dests" not in z:
            r.err("travel_times.npz: needs origins and dests")
        else:
            o, de = z["origins"], z["dests"]
            if (bad := _valid_h3(o.tolist(), 9)):
                r.err(f"travel_times.npz: {bad} invalid res-9 origins")
            if (bad := _valid_h3(de.tolist(), 8)):
                r.err(f"travel_times.npz: {bad} invalid res-8 dests")
            gset = set(grid_h3)
            if (missing := sum(1 for x in o.tolist() if x not in gset)):
                r.err(f"travel_times.npz: {missing} origins are not grid cells")
            modes = [m for m in ("transit", "bike", "walk") if m in z]
            if not modes:
                r.err("travel_times.npz: no mode arrays (transit/bike/walk)")
            for m in modes:
                a = z[m]
                if a.dtype != np.uint8 or a.shape != (len(o), len(de)):
                    r.err(f"travel_times.npz: {m} is {a.dtype}{a.shape}, expected uint8({len(o)}, {len(de)})")
            for m in {"transit", "bike", "walk"} - set(modes):
                r.warn(f"travel_times.npz: mode {m} missing → disabled for {city}")

    # ── admin layers
    for f in ("districts.geojson", "neighborhoods.geojson"):
        if (d / f).exists():
            g = json.loads((d / f).read_text(encoding="utf-8"))
            for i, feat in enumerate(g.get("features", [])):
                p = feat.get("properties", {})
                if not isinstance(p.get("id"), str) or not isinstance(p.get("name"), str):
                    r.err(f"{f}: feature {i} needs string properties id and name")
                    break
    if (d / "districts.geojson").exists():
        dist_ids = {f["properties"]["id"] for f in json.loads((d / "districts.geojson").read_text(encoding="utf-8"))["features"]}
        if (unknown := {f["properties"]["district_id"] for f in feats} - dist_ids):
            r.warn(f"grid district_id values not in districts.geojson: {sorted(unknown)[:5]}")

    # ── manifest
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(m, dict) or not isinstance(m.get("sources"), list) or not m.get("dataVersion"):
        r.err("manifest.json: expected {city, dataVersion, builtAt, sources: [...]}")
    else:
        for s in m["sources"]:
            if not isinstance(s.get("key"), str) or s.get("status") not in ("ok", "fallback", "missing"):
                r.err(f"manifest.json: bad source entry {s}")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="all")
    ap.add_argument("--data-dir", default=str(ROOT / "data/processed"))
    ap.add_argument("--config-dir", default=str(ROOT / "config"))
    a = ap.parse_args()
    cities = ["krakow", "praha"] if a.city == "all" else [a.city]
    failed = False
    for city in cities:
        r = validate_city(Path(a.data_dir), city, Path(a.config_dir))
        print(f"\n== {city}: {len(r.errors)} errors, {len(r.warnings)} warnings")
        for e in r.errors:
            print("  ERROR  ", e)
        for w in r.warnings:
            print("  warn   ", w)
        if r.coverage:
            print("  coverage per criterion:", json.dumps(r.coverage))
        failed |= bool(r.errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
