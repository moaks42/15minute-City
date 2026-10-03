"""Align feature columns with config/indicators.yaml + contracts/DATA_CONTRACT.md (column set, dtypes, NaN columns)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import yaml

from .common import CONFIG_DIR, log

ID_COLUMNS = ["h3", "lat", "lon", "habitable", "district_id", "district_name", "neighborhood", "population_est"]
AUX = {"poi.metro_station_walk_min", "price.buy_n_transactions"}


def expected_columns(city: str) -> list[str]:
    cfg = yaml.safe_load((CONFIG_DIR / "indicators.yaml").read_text(encoding="utf-8"))
    out = []
    for crit in cfg["criteria"]:
        for ind in crit.get("indicators", []):
            if "column" in ind or city not in ind.get("cities", [city]):
                continue
            out.append(f"{crit['id']}.{ind['id']}")
    return out


def align(city: str, feats: pd.DataFrame) -> pd.DataFrame:
    exp = expected_columns(city)
    df = feats.copy()
    for c in exp:
        if c not in df.columns:
            log.warning("[%s] %s not produced → all-NaN column", city, c)
            df[c] = np.nan
    extra = [c for c in df.columns if c not in exp and c not in ID_COLUMNS and c not in AUX and not c.startswith("aux.")]
    # keep anything else for QA under aux.* (the engine ignores aux.*)
    df = df.rename(columns={c: "aux." + c.replace(".", "_") for c in extra})
    # drop an aux column that is entirely NaN (e.g. metro minutes in a city without metro)
    for c in [c for c in df.columns if (c in AUX or c.startswith("aux.")) and df[c].isna().all()]:
        df = df.drop(columns=c)
    for c in df.columns:
        if c not in ID_COLUMNS:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df["population_est"] = df["population_est"].astype("int32")
    df["habitable"] = df["habitable"].astype(bool)
    for c in ("h3", "district_id", "district_name", "neighborhood"):
        df[c] = df[c].astype("string")
    rest = [c for c in df.columns if c not in ID_COLUMNS]
    order = {c: i for i, c in enumerate(exp)}
    rest.sort(key=lambda c: (order.get(c, 10_000), c))
    if extra:
        log.info("[%s] non-contract columns kept as aux.*: %s", city, extra)
    return df[ID_COLUMNS + rest]
