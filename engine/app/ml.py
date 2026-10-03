"""ML layer (README §6.4): pooled archetypes (KMeans → MLP), similar places, twin neighbourhoods.

Pooled across cities on the ABSOLUTE cross-city indicators (crossCity: true, present in every city).
Model + metrics are saved to engine/models/ (B never writes into data/). Retrained when the data version changes.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import joblib
import numpy as np
from scipy.optimize import linear_sum_assignment
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

# Archetype prototypes: signed z-score directions on cross-city columns (cluster → id by Hungarian matching).
PROTOTYPES: dict[str, dict[str, float]] = {
    "historic_core": {"transit.departures_per_h_500m": 1, "leisure.food_10min": 1.2, "leisure.nightlife_10min": 1,
                      "leisure.culture_walk_min": -1, "environment.noise_db": 0.8, "green.green_share_500m": -0.8,
                      "active.intersection_density": 1},
    "urban_mix": {"transit.departures_per_h_500m": 0.8, "shops.shops_10min": 0.8, "leisure.food_10min": 0.5,
                  "transit.stop_walk_min": -0.6, "shops.supermarket_walk_min": -0.6},
    "student_buzz": {"education.university_walk_min": -1.2, "leisure.nightlife_10min": 0.8, "leisure.food_10min": 0.6,
                     "transit.departures_per_h_500m": 0.5},
    "estate_blocks": {"family.playgrounds_500m": 0.8, "accessibility.benches_300m": 0.6, "transit.stop_walk_min": -0.5,
                      "shops.supermarket_walk_min": -0.5, "leisure.nightlife_10min": -0.5, "leisure.food_10min": -0.4},
    "green_residential": {"green.green_share_500m": 1.2, "green.park_walk_min": -1, "environment.noise_db": -0.8,
                          "green.forest_meadow_ha_1km": 0.5},
    "family_suburb": {"family.playgrounds_500m": 0.6, "education.primary_school_walk_min": -0.4,
                      "transit.departures_per_h_500m": -0.7, "leisure.food_10min": -0.6, "green.green_share_500m": 0.5},
    "quiet_outskirts": {"green.forest_meadow_ha_1km": 1.2, "transit.stop_walk_min": 1, "shops.shops_10min": -1,
                        "environment.noise_db": -1, "active.intersection_density": -0.8},
    "industrial_edge": {"environment.industrial_ha_1km": 1.4, "environment.major_road_m": -1, "environment.noise_db": 0.6,
                        "green.green_share_500m": -0.6},
}


@dataclass
class Pooled:
    columns: list[str]
    units: list[str]
    scaler: StandardScaler
    Z: dict[str, np.ndarray]     # city → (n, d) standardized vectors (all cells; NaN → city median)


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
    col = {c: i for i, c in enumerate(columns)}
    P = np.zeros((len(ids), len(columns)))
    for a, aid in enumerate(ids):
        for c, w in PROTOTYPES[aid].items():
            if c in col:
                P[a, col[c]] = w
    P /= np.linalg.norm(P, axis=1, keepdims=True) + 1e-9
    C = centroids / (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-9)
    rows, cols = linear_sum_assignment(-(C @ P.T))
    out = [""] * len(centroids)
    for r, c in zip(rows, cols):
        out[r] = ids[c]
    return out


def train(cities: dict[str, CityData], cfg: Config, pooled: Pooled) -> dict:
    ids = [a["id"] for a in cfg.raw["archetypes"]]
    Xs = np.vstack([pooled.Z[c][cd.habitable] for c, cd in cities.items()])
    city_lab = np.concatenate([[c] * int(cd.habitable.sum()) for c, cd in cities.items()])
    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(Xs), size=min(4000, len(Xs)), replace=False)
    best = None
    sil = {}
    for k in range(6, min(8, len(ids)) + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Xs)
        s = float(silhouette_score(Xs[sample], km.labels_[sample]))
        sil[k] = round(s, 4)
        if best is None or s > best[0]:
            best = (s, k, km)
    _, k, km = best
    labels = km.labels_
    Xtr, Xte, ytr, yte = train_test_split(Xs, labels, test_size=0.2, random_state=SEED, stratify=labels)
    mlp = MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=600, early_stopping=True, random_state=SEED).fit(Xtr, ytr)
    acc = float(mlp.score(Xte, yte))
    cluster_ids = _assign_ids(km.cluster_centers_, pooled.columns, ids)
    share = {cluster_ids[c]: {city: round(float(np.mean(labels[city_lab == city] == c)), 3) for city in cities}
             for c in range(k)}
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
        ids = [model["cluster_ids"][int(k)] for k in model["mlp"].classes_]
        cd.archetype_ids, cd.archetype_proba = ids, proba
    return model, pooled


# ───────────────────────────────────────── similarity
def _unit(Z: np.ndarray) -> np.ndarray:
    return Z / (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-9)


def cosine_rank(query: np.ndarray, Z: np.ndarray) -> np.ndarray:
    q = query / (np.linalg.norm(query) + 1e-9)
    return (_unit(Z) @ q + 1.0) / 2.0   # map [-1, 1] → [0, 1]


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
