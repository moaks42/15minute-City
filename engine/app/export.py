"""Static fallback export (README §8): engine/export/criteria_scores_{city}.json, schema StaticCriteriaScores.

    uv run python -m app.export          # both cities, from whatever data the engine loads
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import Config, load_config, settings
from .data import CityData, load_all
from .models import ScoreRequest
from .scoring import compute


def city_export(cd: CityData, cfg: Config) -> dict:
    personas = [p["id"] for p in cfg.raw["personas"]]
    per: dict[str, dict[str, np.ndarray]] = {}
    for pid in personas:
        p = cfg.persona(pid)
        per[pid] = compute(cd, cfg, ScoreRequest(persona=pid, weights=p["weights"])).crit
    crit_ids = [c for c in cfg.criterion_ids if c in per["custom"]]

    def rows(crit):
        M = np.column_stack([np.rint(crit[c]).astype(int) if c in crit else np.full(cd.n, -1) for c in crit_ids])
        return [[None if v < 0 else int(v) for v in r] for r in M.tolist()]

    base = rows(per["custom"])
    hab = cd.habitable
    return {
        "city": cd.city, "dataVersion": cd.data_version,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "criteria": crit_ids, "levels": {str(k): v for k, v in cfg.raw["levels"].items()},
        "cells": [[h, int(bool(hb)), *r] for h, hb, r in zip(cd.cells, hab.tolist(), base)],
        "byPersona": {pid: rows(per[pid]) for pid in personas if pid != "custom"},
        "cityMedian": {c: int(round(float(np.median(per["custom"][c][hab])))) for c in crit_ids},
    }


def export_all(out_dir: Path | None = None, cities: dict[str, CityData] | None = None, cfg: Config | None = None) -> list[Path]:
    cfg = cfg or load_config()
    cities = cities or load_all(cfg)
    out_dir = out_dir or settings().export_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for city, cd in cities.items():
        p = out_dir / f"criteria_scores_{city}.json"
        p.write_text(json.dumps(city_export(cd, cfg), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        paths.append(p)
    return paths


if __name__ == "__main__":
    for p in export_all():
        print("wrote", p, f"{p.stat().st_size / 1e6:.2f} MB")
