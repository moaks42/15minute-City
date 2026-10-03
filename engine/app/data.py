"""Load data/processed/{city}/ into NumPy matrices (contracts/DATA_CONTRACT.md).

Real data is validated with contracts/tools/validate_data.py and refused on errors (fail loudly).
Missing real data → synthetic dev data (engine/.devdata) unless DATA_FALLBACK=none.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

import h3
import numpy as np
import pyarrow.parquet as pq

from .config import REPO_DIR, Config, IndicatorSpec, settings

log = logging.getLogger("kompas.data")

sys.path.insert(0, str(REPO_DIR / "contracts" / "tools"))
from validate_data import validate_city  # noqa: E402

TT_MODES = ("transit", "bike", "walk")
PLAUSIBLE = {"db": (20.0, 120.0), "pct": (0.0, 100.0), "ugm3": (0.0, 500.0)}  # outside → NaN (missing), logged
UNREACHABLE = 255


class DataError(RuntimeError):
    pass


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


@dataclass
class Group:
    id: str
    name: str
    members: np.ndarray          # cell indices (all cells)
    habitable: np.ndarray        # cell indices (habitable)
    lat: float
    lon: float
    population: int
    parent: str | None = None


@dataclass
class CityData:
    city: str
    cc: dict
    source: str                   # real | synthetic
    data_dir: Path
    data_version: str
    manifest: list[dict]
    cells: list[str]
    index: dict[str, int]
    lat: np.ndarray
    lon: np.ndarray
    habitable: np.ndarray
    district_id: np.ndarray
    district_name: np.ndarray
    neighborhood: np.ndarray
    population: np.ndarray
    specs: list[IndicatorSpec]    # indicators applicable to the city, in matrix column order (incl. aliases)
    raw: np.ndarray               # (n, k) float64, NaN = missing
    imputed: np.ndarray           # (n, k) bool
    filled: np.ndarray            # (n, k) float64, NaN → city median
    median: np.ndarray            # (k,) median over habitable cells (NaN when no data)
    coverage: np.ndarray          # (k,) share of habitable cells with real values
    aux: dict[str, np.ndarray]    # aux / filter-only columns (raw)
    tt: dict[str, np.ndarray]     # mode → (n_origins, n_dests) uint8
    tt_origin_cell: np.ndarray    # (n_origins,) cell index
    tt_dests: list[str]
    tt_dest_index: dict[str, int]
    tt_dest_ll: np.ndarray        # (n_dests, 2)
    pois: dict[str, dict[str, np.ndarray]]
    districts: dict[str, Group]
    neighborhoods: dict[str, Group]
    grid_path: Path
    _norm_cache: dict[float, np.ndarray] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    # filled by ml.py at startup
    archetype_ids: list[str] = field(default_factory=list)
    archetype_proba: np.ndarray | None = None

    @property
    def n(self) -> int:
        return len(self.cells)

    @property
    def k(self) -> int:
        return len(self.specs)

    def col(self, column: str) -> np.ndarray | None:
        """Raw values of a features.parquet column (indicator or aux)."""
        for j, s in enumerate(self.specs):
            if s.column == column:
                return self.raw[:, j]
        return self.aux.get(column)

    def col_filled(self, column: str) -> np.ndarray | None:
        """Like col(), but NaN replaced by the city median (README §6.1 imputation)."""
        for j, s in enumerate(self.specs):
            if s.column == column:
                return self.filled[:, j]
        return self.aux.get(column)

    def spec_index(self, key: str) -> int | None:
        for j, s in enumerate(self.specs):
            if s.key == key:
                return j
        return None

    def available(self, j: int) -> bool:
        return self.coverage[j] > 0

    # ── normalization (README §6.1), cached per walkFactor
    def normalized(self, walk_factor: float = 1.0) -> np.ndarray:
        wf = round(float(walk_factor), 3)
        m = self._norm_cache.get(wf)
        if m is None:
            with self._lock:
                m = self._norm_cache.get(wf)
                if m is None:
                    m = self._normalize(wf)
                    self._norm_cache[wf] = m
        return m

    def _normalize(self, wf: float) -> np.ndarray:
        out = np.zeros((self.n, self.k), dtype=np.float32)
        hab = self.habitable
        for j, s in enumerate(self.specs):
            if not self.available(j):
                continue
            v = self.filled[:, j]
            t = s.norm["type"]
            if t == "decay":
                x = v * wf if s.walk_scaled else v
                good, bad = float(s.norm["good"]), float(s.norm["bad"])
                sc = (x - bad) / (good - bad) * 100.0
            elif t in ("percentile", "inverse_percentile"):
                ref = np.sort(v[hab])
                lt = np.searchsorted(ref, v, side="left")
                le = np.searchsorted(ref, v, side="right")
                sc = (lt + le) / 2.0 / len(ref) * 100.0   # mid-rank: ties share a percentile
                if t == "inverse_percentile":
                    sc = 100.0 - sc
            elif t == "threshold":
                sc = np.where(v >= float(s.norm["at"]), 100.0, 0.0)
            else:
                raise DataError(f"unknown norm type {t} for {s.key}")
            out[:, j] = np.clip(sc, 0.0, 100.0)
        return out

    # ── travel times
    def nearest_dest(self, lat: float, lon: float) -> int | None:
        """Destination column for (lat, lon); None when the point is outside the routed area (> 1.5 km away)."""
        if not self.tt_dests:
            return None
        cell = h3.latlng_to_cell(lat, lon, int(self.cc.get("commuteDestResolution", 8)))
        j = self.tt_dest_index.get(cell)
        if j is None:
            d = haversine_km(lat, lon, self.tt_dest_ll[:, 0], self.tt_dest_ll[:, 1])
            j = int(np.argmin(d))
            if d[j] > 1.5:
                return None
        return j

    def minutes_to(self, lat: float, lon: float, mode: str) -> np.ndarray | None:
        """(n,) minutes from every cell to the res-8 cell containing (lat, lon); 255 = unreachable / not an origin."""
        m = self.tt.get(mode)
        j = self.nearest_dest(lat, lon)
        if m is None or j is None:
            return None
        out = np.full(self.n, UNREACHABLE, dtype=np.int16)
        out[self.tt_origin_cell] = m[:, j]
        return out

    def modes(self) -> list[str]:
        return [m for m in TT_MODES if m in self.tt]


# ───────────────────────────────────────── loading
def _groups(ids, names, lat, lon, hab, pop, parent=None) -> dict[str, Group]:
    out: dict[str, Group] = {}
    ids = np.asarray(ids, dtype=object)
    order = {}
    for i, g in enumerate(ids):
        if g is None:
            continue
        order.setdefault(g, []).append(i)
    for g, idx in order.items():
        idx = np.array(idx)
        par = None
        if parent is not None:
            vals, counts = np.unique(np.asarray(parent, dtype=object)[idx].astype(str), return_counts=True)
            par = str(vals[np.argmax(counts)])
        out[str(g)] = Group(id=str(g), name=str(names[idx[0]]), members=idx, habitable=idx[hab[idx]],
                            lat=float(lat[idx].mean()), lon=float(lon[idx].mean()),
                            population=int(pop[idx].sum()), parent=par)
    return out


def load_city(city: str, cfg: Config, data_dir: Path, source: str) -> CityData:
    d = data_dir / city
    rep = validate_city(data_dir, city, settings().config_dir)
    if rep.errors:
        raise DataError(f"{city}: {d} fails contracts/DATA_CONTRACT.md:\n  " + "\n  ".join(rep.errors))
    for w in rep.warnings:
        log.warning("%s: %s", city, w)

    table = pq.read_table(d / "features.parquet")
    colnames = set(table.column_names)
    g = lambda c: table.column(c).to_numpy(zero_copy_only=False)  # noqa: E731
    cells = [str(x) for x in g("h3")]
    lat, lon = g("lat").astype(float), g("lon").astype(float)
    hab = g("habitable").astype(bool)
    pop = g("population_est").astype(np.int64)
    district_id = np.array([str(x) for x in g("district_id")], dtype=object)
    district_name = np.array([str(x) for x in g("district_name")], dtype=object)
    neighborhood = np.array([None if x is None else str(x) for x in g("neighborhood")], dtype=object)

    specs = [s for s in cfg.indicators[city] if s.applies_to(city)]
    n = len(cells)
    raw = np.full((n, len(specs)), np.nan)
    for j, s in enumerate(specs):
        if s.column in colnames:
            raw[:, j] = g(s.column).astype(float)
    for j, s in enumerate(specs):
        lo_hi = PLAUSIBLE.get(s.unit)
        if lo_hi is not None and not s.is_alias:
            bad = (raw[:, j] < lo_hi[0]) | (raw[:, j] > lo_hi[1])
            if bad.any():
                log.warning("%s: %s has %d physically implausible values (outside %s–%s %s) → treated as missing",
                            city, s.column, int(bad.sum()), lo_hi[0], lo_hi[1], s.unit)
                raw[bad, j] = np.nan
    nan = np.isnan(raw)
    with np.errstate(all="ignore"):
        median = np.array([np.nanmedian(raw[hab, j]) if (~nan[hab, j]).any() else np.nan for j in range(len(specs))])
    coverage = (~nan[hab]).mean(axis=0)
    filled = np.where(nan, median[None, :], raw)
    aux = {c: g(c).astype(float) for c in colnames if c.startswith(("poi.", "aux.")) or c == "price.buy_n_transactions"}

    # travel times
    tt: dict[str, np.ndarray] = {}
    origin_cell = np.zeros(0, dtype=np.int64)
    dests: list[str] = []
    dest_ll = np.zeros((0, 2))
    if (d / "travel_times.npz").exists():
        z = np.load(d / "travel_times.npz", allow_pickle=False)
        idx = {c: i for i, c in enumerate(cells)}
        origin_cell = np.array([idx[str(o)] for o in z["origins"]], dtype=np.int64)
        dests = [str(x) for x in z["dests"]]
        dest_ll = np.array([h3.cell_to_latlng(x) for x in dests])
        tt = {m: z[m] for m in TT_MODES if m in z}

    # POIs
    pois: dict[str, dict[str, np.ndarray]] = {}
    if (d / "pois.parquet").exists():
        pt = pq.read_table(d / "pois.parquet", columns=["category", "name", "lat", "lon"])
        cat = np.array(pt.column("category").to_pylist(), dtype=object)
        names = np.array(pt.column("name").to_pylist(), dtype=object)
        plat = pt.column("lat").to_numpy().astype(float)
        plon = pt.column("lon").to_numpy().astype(float)
        for c in np.unique(cat):
            m = cat == c
            pois[str(c)] = {"name": names[m], "lat": plat[m], "lon": plon[m]}

    manifest_raw = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    manifest = manifest_raw.get("sources", []) if isinstance(manifest_raw, dict) else manifest_raw
    version = (manifest_raw.get("dataVersion") if isinstance(manifest_raw, dict) else None) or str(int((d / "features.parquet").stat().st_mtime))

    cd = CityData(
        city=city, cc=cfg.cities[city], source=source, data_dir=d, data_version=str(version), manifest=manifest,
        cells=cells, index={c: i for i, c in enumerate(cells)}, lat=lat, lon=lon, habitable=hab,
        district_id=district_id, district_name=district_name, neighborhood=neighborhood, population=pop,
        specs=specs, raw=raw, imputed=nan, filled=filled, median=median, coverage=coverage, aux=aux,
        tt=tt, tt_origin_cell=origin_cell, tt_dests=dests, tt_dest_index={c: i for i, c in enumerate(dests)},
        tt_dest_ll=dest_ll, pois=pois,
        districts=_groups(district_id, district_name, lat, lon, hab, pop),
        neighborhoods=_groups(neighborhood, neighborhood, lat, lon, hab, pop, parent=district_id),
        grid_path=d / "grid.geojson",
    )
    cd.normalized(1.0)
    log.info("%s: loaded %s data v=%s · %d cells (%d habitable) · %d/%d indicators with data · modes %s",
             city, source, cd.data_version, n, int(hab.sum()), int((coverage > 0).sum()), len(specs), cd.modes())
    return cd


def load_all(cfg: Config) -> dict[str, CityData]:
    s = settings()
    out = {}
    for city in cfg.cities:
        real = s.data_dir / city
        if (real / "features.parquet").exists():
            try:
                out[city] = load_city(city, cfg, s.data_dir, "real")
                continue
            except DataError:
                if s.data_fallback != "synthetic":
                    raise
                log.exception("%s: REAL DATA REJECTED — falling back to synthetic dev data", city)
        elif s.data_fallback != "synthetic":
            raise DataError(f"{city}: no data at {real} and DATA_FALLBACK={s.data_fallback}")
        if not (s.devdata_dir / city / "features.parquet").exists():
            from .devdata import generate
            log.warning("%s: generating synthetic dev data in %s", city, s.devdata_dir)
            generate(s.devdata_dir, cities=(city,))
        out[city] = load_city(city, cfg, s.devdata_dir, "synthetic")
    return out
