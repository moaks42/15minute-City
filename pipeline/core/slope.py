"""accessibility.slope_pct from the Copernicus GLO-30 DEM (public AWS bucket, no key).

GLO-30 is a surface model (buildings, trees), so the DEM is Gaussian-smoothed (σ = 60 m) before the gradient to keep
terrain-scale slopes and suppress building edges. Value = mean slope (%) within 180 m of the cell centroid.
"""
from __future__ import annotations

import math

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve

from .common import RAW_DIR, USER_AGENT, log, now_iso
from .context import Ctx

URL = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_{t}_DEM/Copernicus_DSM_COG_10_{t}_DEM.tif"
LICENCE = ("Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under "
           "COPERNICUS by the European Union and ESA")


def tiles(bounds) -> list[str]:
    w, s, e, n = bounds
    out = []
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            out.append(f"N{lat:02d}_00_E{lon:03d}_00")
    return out


def fetch(names: list[str]) -> list:
    import requests

    d = RAW_DIR / "_common" / "dem"
    d.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in names:
        p = d / f"cop30_{t}.tif"
        if not p.exists():
            r = requests.get(URL.format(t=t), timeout=600, headers={"User-Agent": USER_AGENT})
            r.raise_for_status()
            p.write_bytes(r.content)
            log.info("DEM tile %s downloaded (%.0f MB)", t, p.stat().st_size / 1e6)
        paths.append(p)
    return paths


def compute(ctx: Ctx, res: float = 30.0, radius: float = 180.0) -> np.ndarray:
    b = ctx.boundary.to_crs(4326).total_bounds
    pad = 0.02
    bounds = (b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad)
    paths = fetch(tiles(bounds))
    srcs = [rasterio.open(p) for p in paths]
    mosaic, mtr = merge(srcs, bounds=bounds)
    src_crs = srcs[0].crs
    for s in srcs:
        s.close()
    xy = ctx.xy
    x0, y1 = xy[:, 0].min() - 1000, xy[:, 1].max() + 1000
    w = int(np.ceil((xy[:, 0].max() + 1000 - x0) / res))
    h = int(np.ceil((y1 - (xy[:, 1].min() - 1000)) / res))
    dst = np.full((h, w), np.nan, dtype="float32")
    dtr = from_origin(x0, y1, res, res)
    reproject(mosaic[0].astype("float32"), dst, src_transform=mtr, src_crs=src_crs, dst_transform=dtr,
              dst_crs=ctx.crs, resampling=Resampling.bilinear, src_nodata=-32767, dst_nodata=np.nan)
    z = np.where(np.isfinite(dst), dst, np.nanmedian(dst))
    z = gaussian_filter(z, sigma=60 / res)
    gy, gx = np.gradient(z, res)
    slope = 100 * np.hypot(gx, gy)
    k = int(np.ceil(radius / res))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    disk = ((xx ** 2 + yy ** 2) * res ** 2 <= radius ** 2).astype("float32")
    mean = fftconvolve(slope, disk, mode="same") / disk.sum()
    c = ((xy[:, 0] - x0) / res).astype(int).clip(0, w - 1)
    r = ((y1 - xy[:, 1]) / res).astype(int).clip(0, h - 1)
    out = np.clip(mean[r, c], 0, 100).round(2)
    ctx.man.record("copernicus_dem", url=URL.format(t="{tile}"), fetchedAt=now_iso(), licence=LICENCE,
                   rows=len(paths), status="ok",
                   note=f"GLO-30 tiles {', '.join(tiles(bounds))}; reprojected to {ctx.crs} at {res:.0f} m, "
                        "Gaussian σ=60 m (DSM → terrain-scale), slope % mean within 180 m")
    log.info("[%s] slope_pct: median %.1f%%, p95 %.1f%%", ctx.city, np.median(out), np.percentile(out, 95))
    return out
