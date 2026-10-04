"""Rasterize polygons in the metric CRS and sample neighbourhood statistics at cell centroids."""
from __future__ import annotations

import geopandas as gpd
import numpy as np
from rasterio import features
from rasterio.enums import MergeAlg
from rasterio.transform import from_origin
from scipy.signal import fftconvolve


class Canvas:
    def __init__(self, xy: np.ndarray, margin: float = 1500.0, res: float = 20.0):
        self.res = res
        self.x0, self.y1 = xy[:, 0].min() - margin, xy[:, 1].max() + margin
        x1, y0 = xy[:, 0].max() + margin, xy[:, 1].min() - margin
        self.w = int(np.ceil((x1 - self.x0) / res))
        self.h = int(np.ceil((self.y1 - y0) / res))
        self.transform = from_origin(self.x0, self.y1, res, res)

    def burn(self, gdf: gpd.GeoDataFrame, values=None, fill: float = 0.0, dtype="float32") -> np.ndarray:
        if gdf is None or gdf.empty:
            return np.full((self.h, self.w), fill, dtype=dtype)
        vals = values if values is not None else np.ones(len(gdf))
        shapes = ((g, float(v)) for g, v in zip(gdf.geometry, vals) if g is not None and not g.is_empty)
        return features.rasterize(shapes, out_shape=(self.h, self.w), transform=self.transform, fill=fill,
                                  dtype=dtype, merge_alg=MergeAlg.replace, all_touched=False)

    def rc(self, xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        c = ((xy[:, 0] - self.x0) / self.res).astype(int).clip(0, self.w - 1)
        r = ((self.y1 - xy[:, 1]) / self.res).astype(int).clip(0, self.h - 1)
        return r, c

    def disk(self, radius: float) -> np.ndarray:
        k = int(np.ceil(radius / self.res))
        yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
        return ((xx ** 2 + yy ** 2) * self.res ** 2 <= radius ** 2).astype("float32")

    def mean_within(self, grid: np.ndarray, xy: np.ndarray, radius: float, valid: np.ndarray | None = None,
                    min_valid: float = 0.05) -> np.ndarray:
        """Mean of `grid` within radius of each point (ignoring cells where valid==0).

        With `valid`, points whose disk is less than `min_valid` covered get NaN: there the FFT round-off
        (~1e-7) in both sums would otherwise make the ratio arbitrary (e.g. 0 or 175 dB at a noise-map edge)."""
        k = self.disk(radius)
        if valid is None:
            num = fftconvolve(grid, k, mode="same")
            den = k.sum()
        else:
            num = fftconvolve(grid * valid, k, mode="same")
            den = fftconvolve(valid.astype("float32"), k, mode="same")
        r, c = self.rc(xy)
        with np.errstate(invalid="ignore", divide="ignore"):
            out = num[r, c] / (den[r, c] if np.ndim(den) else den)
        if valid is None:
            return np.clip(out, 0, None)  # FFT round-off can give -1e-7
        out = np.where(den[r, c] >= min_valid * k.sum(), out, np.nan)
        vals = grid[valid > 0]
        return np.clip(out, vals.min(), vals.max()) if vals.size else out  # a mean never leaves the value range
