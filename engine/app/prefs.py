"""Preference learning (README §6.4.4, P2): pairwise choices → Bradley–Terry logistic regression → emoji levels."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression

from .data import CityData
from .models import PrefFitRequest

SEED = 7


def pairs(cd: CityData, crit: dict[str, np.ndarray], n: int) -> list[dict]:
    """Contrasting pairs: each pair differs strongly on a different criterion."""
    rng = np.random.default_rng(SEED)
    ids = list(crit)
    hab = np.flatnonzero(cd.habitable)
    M = np.column_stack([crit[c][hab] for c in ids])
    out = []
    for p in range(n):
        focus = p % len(ids)
        hi = hab[rng.choice(np.flatnonzero(M[:, focus] >= np.percentile(M[:, focus], 80)))]
        lo = hab[rng.choice(np.flatnonzero(M[:, focus] <= np.percentile(M[:, focus], 20)))]
        a, b = (hi, lo) if p % 2 == 0 else (lo, hi)
        out.append({"id": f"p{p + 1}",
                    "a": {c: int(round(float(crit[c][a]))) for c in ids},
                    "b": {c: int(round(float(crit[c][b]))) for c in ids}})
    return out


def fit(req: PrefFitRequest, criteria: list[str]) -> dict:
    ids = [c for c in criteria if c != "commute"]
    X, y = [], []
    for ch in req.choices:
        d = np.array([ch.a.get(c, 50.0) - ch.b.get(c, 50.0) for c in ids]) / 100.0
        win = 1 if ch.choice == "a" else 0
        X += [d, -d]          # symmetric augmentation: P(a≻b) = σ(w·(a−b))
        y += [win, 1 - win]
    clf = LogisticRegression(C=1.0, fit_intercept=False, max_iter=1000).fit(np.array(X), np.array(y))
    w = clf.coef_[0]
    top = float(w.max()) if w.max() > 0 else 1.0
    levels = {c: int(np.clip(np.rint(1 + 4 * wi / top), 1, 5)) if wi > 0 else 0 for c, wi in zip(ids, w)}
    acc = float(clf.score(np.array(X), np.array(y)))
    return {"weights": levels, "confidence": round(acc, 3)}
