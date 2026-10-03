"""Pooled cross-city feature table for archetypes / twins (README §5, §6.4; DATA_CONTRACT §7).

    uv run python ml_features.py   → data/processed/_shared/ml_features.parquet

Columns: city, h3, habitable + every `crossCity: true` indicator in config/indicators.yaml (absolute, comparable
units only; price is excluded because currencies differ). Fails loudly if a city lacks a crossCity column.
"""
from __future__ import annotations

import sys

import pandas as pd
import yaml

from core.common import CONFIG_DIR, PROCESSED_DIR, log


def cross_city_columns() -> list[str]:
    cfg = yaml.safe_load((CONFIG_DIR / "indicators.yaml").read_text(encoding="utf-8"))
    return [f"{c['id']}.{i['id']}" for c in cfg["criteria"] for i in c.get("indicators", [])
            if i.get("crossCity") and "column" not in i]


def main() -> int:
    cols = cross_city_columns()
    frames = []
    for city in ("krakow", "praha"):
        f = PROCESSED_DIR / city / "features.parquet"
        if not f.exists():
            log.error("missing %s", f)
            return 1
        df = pd.read_parquet(f)
        miss = [c for c in cols if c not in df.columns]
        if miss:
            log.error("[%s] crossCity columns missing from features.parquet: %s", city, miss)
            return 1
        frames.append(df[["h3", "habitable", *cols]].assign(city=city))
    out = pd.concat(frames, ignore_index=True)[["city", "h3", "habitable", *cols]]
    out["city"] = out["city"].astype("string")
    out["h3"] = out["h3"].astype("string")
    d = PROCESSED_DIR / "_shared"
    d.mkdir(parents=True, exist_ok=True)
    out.to_parquet(d / "ml_features.parquet", index=False, compression="snappy")
    nan = out[out["habitable"]].groupby("city")[cols].apply(lambda x: x.isna().mean()).T
    allnan = nan[(nan == 1).any(axis=1)]
    log.info("ml_features: %d rows × %d crossCity columns → %s", len(out), len(cols), d / "ml_features.parquet")
    if len(allnan):
        log.warning("crossCity columns all-NaN in a city (exclude them from pooled models): %s", allnan.index.tolist())
    return 0


if __name__ == "__main__":
    sys.exit(main())
