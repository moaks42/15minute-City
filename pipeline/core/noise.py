"""Noise from dB-band polygons (strategic noise maps): rasterize band values, max over sources, mean per cell."""
from __future__ import annotations

import geopandas as gpd
import numpy as np

from .common import log
from .context import Ctx
from .raster import Canvas


def band_value(lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    v = (lo + hi) / 2
    v = np.where((lo < 40) | ~np.isfinite(lo), hi - 5, v)  # open lower band "<55" → 50
    v = np.where((hi >= 99) | ~np.isfinite(hi), lo + 2.5, v)  # open upper band "≥75" → 77.5
    return v


def noise_db(ctx: Ctx, layers: list[gpd.GeoDataFrame], radius: float = 180.0, res: float = 10.0) -> np.ndarray:
    """Area mean (within ~one res-9 cell) of max-over-sources band value. NaN where no layer covers."""
    cv = Canvas(ctx.xy, margin=500, res=res)
    best = np.full((cv.h, cv.w), np.nan, dtype="float32")
    for g in layers:
        g = g.to_crs(ctx.crs)
        g = g.assign(v=band_value(g["lo"], g["hi"])).sort_values("v")  # later (louder) overwrite earlier
        r = cv.burn(g, g["v"].to_numpy(), fill=np.nan)
        best = np.fmax(best, r)
        log.info("[%s] noise layer burned: %d polygons, %.0f%% of canvas covered", ctx.city, len(g),
                 100 * np.isfinite(r).mean())
    valid = np.isfinite(best).astype("float32")
    return cv.mean_within(np.nan_to_num(best), ctx.xy, radius, valid=valid).round(1)
