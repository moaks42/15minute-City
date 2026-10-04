"""ML layer (README §6.4): pooled archetypes (KMeans → MLP), similar places, twin neighbourhoods.

Pooled across cities on the ABSOLUTE cross-city indicators (crossCity: true, present in every city).
Model + metrics are saved to engine/models/ (B never writes into data/). Retrained when the data version changes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from .config import Config, settings
from .data import CityData

log = logging.getLogger("kompas.ml")
SEED = 42
LOG_UNITS = {"count", "dep_h", "ha", "m", "per_km2", "km"}  # heavy-tailed → log1p before scaling

SIL_TOLERANCE = 0.005  # silhouettes within this of the best are "equal" → prefer the larger k (finer archetypes)


def name_cluster(z: dict[str, float]) -> str:
    """Archetype id for a cluster centroid (pooled z-scores; walk minutes: + = farther). First matching rule wins.
    Several clusters may share an id. Rules were checked against the real K + P clusters (docs/ML.md)."""
    g = lambda c: float(z.get(c, 0.0))  # noqa: E731
    mean = lambda *cs: sum(g(c) for c in cs) / len(cs)  # noqa: E731
    dense = mean("leisure.food_10min", "leisure.nightlife_10min", "shops.shops_10min")
    services_far = mean("health.gp_walk_min", "health.pharmacy_walk_min", "shops.supermarket_walk_min",
                        "education.primary_school_walk_min", "health.dentist_walk_min")
    green = mean("green.green_share_500m", "green.forest_meadow_ha_1km")
    if dense > 2.0 and g("leisure.culture_walk_min") < -1.0:
        return "historic_core"
    if dense > 0.8:
        return "urban_mix"
    if g("education.university_walk_min") < -1.0 and g("leisure.nightlife_10min") > 0.5:
        return "student_buzz"
    if g("environment.industrial_ha_1km") > 1.0:
        return "industrial_edge"
    if services_far > 1.0:
        return "quiet_outskirts"
    if g("family.playgrounds_500m") > 0.5 and g("shops.shops_10min") > 0.3:
        return "estate_blocks"
    if green > 0.5:
        return "green_residential"
    if g("transit.departures_per_h_500m") > 0.3:
        return "urban_mix"
    return "family_suburb"


@dataclass
class Pooled:
    columns: list[str]
    units: list[str]
    scaler: StandardScaler
    Z: dict[str, np.ndarray]     # city → (n, d) standardized vectors (all cells; NaN → city median)
    # (from, to) → median distance between two random habitable cells / two districts (see calibrate)
    d_ref: dict[tuple[str, str], float] = field(default_factory=dict)
    d_ref_district: dict[tuple[str, str], float] = field(default_factory=dict)


def cross_columns(cities: dict[str, CityData]) -> tuple[list[str], list[str]]:
    sets = []
    for cd in cities.values():
        sets.append({s.column: s.unit for j, s in enumerate(cd.specs) if s.cross_city and not s.is_alias and cd.coverage[j] > 0})
    common = sorted(set.intersection(*[set(s) for s in sets]))
    return common, [sets[0][c] for c in common]


def _features(cd: CityData, columns: list[str], units: list[str]) -> np.ndarray:
    idx = {s.column: j for j, s in enumerate(cd.specs) if not s.is_alias}
    X = np.column_stack([cd.filled[:, idx[c]] for c in columns]).astype(float)
    for k, u in enumerate(units):
        if u in LOG_UNITS:
            X[:, k] = np.log1p(np.maximum(X[:, k], 0))
    return X


def pool(cities: dict[str, CityData]) -> Pooled:
    columns, units = cross_columns(cities)
    if len(columns) < 3:
        raise RuntimeError(f"only {len(columns)} cross-city columns with data in every city")
    X = {c: _features(cd, columns, units) for c, cd in cities.items()}
    scaler = StandardScaler().fit(np.vstack([X[c][cd.habitable] for c, cd in cities.items()]))
    return Pooled(columns, units, scaler, {c: scaler.transform(x) for c, x in X.items()})


def _assign_ids(centroids: np.ndarray, columns: list[str], ids: list[str]) -> list[str]:
    out = [name_cluster(dict(zip(columns, c))) for c in centroids]
    assert all(o in ids for o in out), out
    return out


def train(cities: dict[str, CityData], cfg: Config, pooled: Pooled) -> dict:
    ids = [a["id"] for a in cfg.raw["archetypes"]]
    Xs = np.vstack([pooled.Z[c][cd.habitable] for c, cd in cities.items()])
    city_lab = np.concatenate([[c] * int(cd.habitable.sum()) for c, cd in cities.items()])
    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(Xs), size=min(4000, len(Xs)), replace=False)
    fits, sil = {}, {}
    for k in range(6, min(8, len(ids)) + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Xs)
        sil[k] = round(float(silhouette_score(Xs[sample], km.labels_[sample])), 4)
        fits[k] = km
    top = max(sil.values())
    k = max(kk for kk, v in sil.items() if v >= top - SIL_TOLERANCE)
    km = fits[k]
    labels = km.labels_
    Xtr, Xte, ytr, yte = train_test_split(Xs, labels, test_size=0.2, random_state=SEED, stratify=labels)
    mlp = MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=600, early_stopping=True, random_state=SEED).fit(Xtr, ytr)
    acc = float(mlp.score(Xte, yte))
    cluster_ids = _assign_ids(km.cluster_centers_, pooled.columns, ids)
    share: dict[str, dict[str, float]] = {}
    for c in range(k):
        for city in cities:
            d = share.setdefault(cluster_ids[c], {})
            d[city] = round(d.get(city, 0.0) + float(np.mean(labels[city_lab == city] == c)), 3)
    metrics = {
        "k": k, "silhouette": sil, "holdoutAccuracy": round(acc, 4), "nTrain": int(len(Xtr)), "nTest": int(len(Xte)),
        "columns": pooled.columns, "clusterIds": cluster_ids, "shareByCity": share,
        "dataVersion": {c: cd.data_version for c, cd in cities.items()},
        "dataSource": {c: cd.source for c, cd in cities.items()},
    }
    log.info("archetypes: k=%d silhouette=%s holdout acc=%.3f", k, sil, acc)
    return {"scaler": pooled.scaler, "kmeans": km, "mlp": mlp, "columns": pooled.columns, "units": pooled.units,
            "cluster_ids": cluster_ids, "metrics": metrics}


def load_or_train(cities: dict[str, CityData], cfg: Config) -> tuple[dict, Pooled]:
    s = settings()
    path = s.models_dir / "archetypes.joblib"
    versions = {c: cd.data_version for c, cd in cities.items()}
    model = None
    if path.exists():
        try:
            m = joblib.load(path)
            if m["metrics"]["dataVersion"] == versions:
                model = m
        except Exception:  # noqa: BLE001 — stale/incompatible pickle → retrain
            log.exception("could not load %s; retraining", path)
    if model is not None:
        columns, units = model["columns"], model["units"]
        X = {c: _features(cd, columns, units) for c, cd in cities.items()}
        pooled = Pooled(columns, units, model["scaler"], {c: model["scaler"].transform(x) for c, x in X.items()})
    else:
        pooled = pool(cities)
        model = train(cities, cfg, pooled)
        try:
            s.models_dir.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, path, compress=3)
            (s.models_dir / "metrics.json").write_text(json.dumps(model["metrics"], ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            log.warning("models dir not writable; keeping the model in memory only")
    for c, cd in cities.items():
        proba = model["mlp"].predict_proba(pooled.Z[c])
        per_cluster = [model["cluster_ids"][int(k)] for k in model["mlp"].classes_]
        ids = list(dict.fromkeys(per_cluster))            # clusters sharing an id → summed probability
        agg = np.zeros((proba.shape[0], len(ids)))
        for col, aid in enumerate(per_cluster):
            agg[:, ids.index(aid)] += proba[:, col]
        cd.archetype_ids, cd.archetype_proba = ids, agg
    calibrate(pooled, cities)
    return model, pooled


# ───────────────────────────────────────── similarity
REF_PAIRS = 4000


def distance_sim(query: np.ndarray, Z: np.ndarray, d_ref: float) -> np.ndarray:
    """1 − d / d_ref, d = Euclidean distance in the pooled z-space: 1 = identical, 0 = as far apart as two random
    places, < 0 = further still. Rank on this value; clip to [0, 1] only for display. (Cosine ignored how strongly
    a place shows its profile, and (cos + 1) / 2 made an unrelated place look about 50 % similar.)"""
    return 1.0 - np.linalg.norm(np.atleast_2d(Z) - query, axis=1) / d_ref


def district_vectors(Z: np.ndarray, cd: CityData) -> np.ndarray:
    return np.array([group_vector(Z, cd, g.habitable) for g in cd.districts.values() if len(g.habitable)])


def calibrate(pooled: Pooled, cities: dict[str, CityData]) -> None:
    """Reference distances for distance_sim per (from, to) city pair: median over random habitable cell pairs, and
    separately over district pairs (district averages lie closer together than single cells)."""
    rng = np.random.default_rng(SEED)
    for a, ca in cities.items():
        for b, cb in cities.items():
            ia = rng.choice(np.flatnonzero(ca.habitable), REF_PAIRS)
            ib = rng.choice(np.flatnonzero(cb.habitable), REF_PAIRS)
            pooled.d_ref[(a, b)] = float(np.median(np.linalg.norm(pooled.Z[a][ia] - pooled.Z[b][ib], axis=1)))
            Ga, Gb = district_vectors(pooled.Z[a], ca), district_vectors(pooled.Z[b], cb)
            d = np.linalg.norm(Ga[:, None, :] - Gb[None, :, :], axis=2)
            pooled.d_ref_district[(a, b)] = float(np.median(d[~np.eye(len(Ga), dtype=bool)] if a == b else d))


def diverse_top(sim: np.ndarray, candidates: np.ndarray, groups: np.ndarray, limit: int, per_group: int = 1) -> list[int]:
    """Top by similarity, at most `per_group` per neighbourhood so results are not 5 adjacent hexes."""
    order = candidates[np.argsort(-sim[candidates], kind="stable")]
    seen: dict[object, int] = {}
    out = []
    for i in order:
        g = groups[i]
        if seen.get(g, 0) >= per_group:
            continue
        seen[g] = seen.get(g, 0) + 1
        out.append(int(i))
        if len(out) >= limit:
            break
    return out


def shared_traits(a: dict[str, float], b: dict[str, float], thr: float = 60.0) -> list[str]:
    common = [c for c in a if c in b and c != "commute" and a[c] >= thr and b[c] >= thr]
    return sorted(common, key=lambda c: -(a[c] + b[c]))[:4]


def group_vector(Z: np.ndarray, cd: CityData, idx: np.ndarray) -> np.ndarray:
    w = cd.population[idx].astype(float) + 1.0
    return np.average(Z[idx], axis=0, weights=w)
