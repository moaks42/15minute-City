"""Kraków indicator adapters: MSIP noise, Bezpieczny Kraków safety, RCN apartment prices, GIOŚ air."""
from __future__ import annotations

import io
import json
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import pyogrio
import requests

from core.common import USER_AGENT, log, now_iso
from core.context import Ctx
from core.noise import noise_db

from . import gios

NOISE_ZIP = "Mapa_Halasu_2022_JSON.zip"
NOISE_LAYERS = ["Mapa_imisyjna_2022_JSON/halas_2022_imisja_dr_LDWN.geojson",
                "Mapa_imisyjna_2022_JSON/halas_2022_imisja_szyn_LDWN.geojson"]


def noise(ctx: Ctx) -> np.ndarray:
    layers = []
    for f in NOISE_LAYERS:
        g = pyogrio.read_dataframe(f"/vsizip/{ctx.raw / NOISE_ZIP}/{f}", columns=["isov1", "isov2"])
        g = g.set_crs(2178, allow_override=True).rename(columns={"isov1": "lo", "isov2": "hi"})
        layers.append(g)
    v = noise_db(ctx, layers)
    ctx.ok("msip_noise", int(np.isfinite(v).sum()),
           "Mapa imisyjna 2022, LDWN (Lden) 5-dB bands; max(road, rail+tram) per pixel, mean per cell; "
           "industrial layer has no dB attribute → not used")
    return v


def safety(ctx: Ctx) -> np.ndarray:
    """Public-space offences 2023 (141 GMK polygons) → dzielnica totals per 1 000 residents (EMUiA proxy)."""
    pol = gpd.read_file(ctx.raw_file("safety_krk")).to_crs(ctx.crs)
    d = ctx.districts.to_crs(ctx.crs)
    pol["a"] = pol.area
    inter = gpd.overlay(pol[["przestepstwa", "a", "geometry"]], d[["district_id", "geometry"]], how="intersection")
    inter["n"] = inter["przestepstwa"] * inter.area / inter["a"]
    crimes = inter.groupby("district_id")["n"].sum()
    # residents: latest GUS BDL total for powiat m. Kraków split by EMUiA address share per district
    vals = json.loads(ctx.raw_file("gus_bdl").read_text())["results"][0]["values"]
    year, total = vals[-1]["year"], int(vals[-1]["val"])
    pop = ctx.grid.groupby("district_id")["population_est"].sum()
    residents = pop / pop.sum() * total
    ctx.ok("gus_bdl", 1, f"population {total} ({year}), var 72305, unit 011212161000")
    rate = (crimes / residents * 1000).round(2)
    log.info("[krakow] crimes per 1000 by district: %s", rate.to_dict())
    ctx.ok("safety_krk", int(len(pol)),
           f"'Przestępstwa w przestrzeni publicznej 2023' ({int(pol['przestepstwa'].sum())} offences, 141 units) "
           f"area-apportioned to dzielnice; residents = GUS {year} total split by EMUiA address share")
    return ctx.grid["district_id"].map(rate).to_numpy(dtype=float)


RCN_URL = "https://geodezja.eco.um.krakow.pl/cgi-bin/krakow-rcn"
NS = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml/3.2",
      "ms": "http://mapserver.gis.umn.edu/mapserver"}


def rcn_fetch(ctx: Ctx, months: int = 24) -> pd.DataFrame:
    cache = ctx.raw / "rcn_lokale_24m.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    since = (date.today() - timedelta(days=int(months * 30.44))).isoformat()
    flt = ("<fes:Filter xmlns:fes=\"http://www.opengis.net/fes/2.0\"><fes:PropertyIsGreaterThanOrEqualTo>"
           f"<fes:ValueReference>DOK_DATA</fes:ValueReference><fes:Literal>{since}</fes:Literal>"
           "</fes:PropertyIsGreaterThanOrEqualTo></fes:Filter>")
    ses = requests.Session()
    ses.headers["User-Agent"] = USER_AGENT
    rows, start, page = [], 0, 1000  # server caps COUNT at 1000
    while True:
        r = ses.get(RCN_URL, timeout=300, params={"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
                                                  "TYPENAMES": "ms:lokale", "COUNT": page, "STARTINDEX": start,
                                                  "FILTER": flt})
        r.raise_for_status()
        root = ET.parse(io.BytesIO(r.content)).getroot()
        if root.tag.endswith("ExceptionReport"):
            raise RuntimeError(r.text[:500])
        mem = root.findall("wfs:member", NS)
        for m in mem:
            f = m[0]
            pos = f.find(".//gml:pos", NS)
            rec = {c.tag.split("}")[1]: c.text for c in f if c.tag.startswith("{" + NS["ms"])}
            if pos is not None:
                n, e = map(float, pos.text.split())  # EPSG:2178 axis order: northing, easting
                rec["x"], rec["y"] = e, n
            rows.append(rec)
        log.info("[krakow] RCN page start=%d → %d rows (total %d)", start, len(mem), len(rows))
        if not mem or not root.get("next"):
            break
        start += page
        time.sleep(0.5)
    df = pd.DataFrame(rows).drop(columns=["msGeometry"], errors="ignore")
    df.to_parquet(cache)
    return df


def price(ctx: Ctx) -> tuple[np.ndarray, np.ndarray]:
    """Median zł/m² of residential apartment free-market sales, last 24 months, k-ring smoothing until n ≥ 5."""
    df = rcn_fetch(ctx)
    n0 = len(df)
    num = lambda c: pd.to_numeric(df[c], errors="coerce")  # noqa: E731
    df["price"] = num("TRAN_CENA_BRUTTO")
    df["area"] = num("LOK_POW_UZYT")
    # one transaction may contain several units: use the unit price when present, else the transaction price
    lok = num("LOK_CENA_BRUTTO")
    multi = df.groupby("TRAN_OZNACZENIE_TRANS")["LOK_ID_LOKALU"].transform("count") if "TRAN_OZNACZENIE_TRANS" in df else 1
    df["p"] = np.where(lok.notna() & (lok > 0), lok, np.where(multi == 1, df["price"], np.nan))
    df = df[(df.get("LOK_FUNKCJA") == "mieszkalna") & (df.get("TRAN_RODZAJ_TRANS") == "wolnyRynek")
            & (df["area"] >= 15) & (df["area"] <= 250) & df["p"].notna()]
    df["ppm2"] = df["p"] / df["area"]
    q1, q3 = df["ppm2"].quantile([0.25, 0.75])
    iqr = q3 - q1
    df = df[(df["ppm2"] >= max(q1 - 1.5 * iqr, 2000)) & (df["ppm2"] <= q3 + 1.5 * iqr)]
    pts = gpd.GeoSeries(gpd.points_from_xy(df["x"], df["y"]), crs=2178).to_crs(4326)
    df["h3"] = [h3.latlng_to_cell(y, x, 9) for x, y in zip(pts.x, pts.y)]
    by = df.groupby("h3")["ppm2"].apply(list).to_dict()
    med, nn = [], []
    for c in ctx.grid["h3"]:
        vals = []
        for k in range(0, 4):
            ring = h3.grid_disk(c, k)
            vals = [v for r in ring for v in by.get(r, [])]
            if len(vals) >= 5:
                break
        med.append(float(np.median(vals)) if len(vals) >= 5 else np.nan)
        nn.append(len(vals))
    med, nn = np.round(np.array(med), 0), np.array(nn)
    ctx.ok("rcn", int(len(df)),
           f"Kraków RCN WFS ms:lokale, DOK_DATA ≥ last 24 months: {n0} records → {len(df)} free-market apartment "
           "sales after IQR filter; median zł/m² over H3 k-ring (k=0..3 until n≥5)")
    ctx.man.record("rcn", fetchedAt=now_iso())
    return med, nn


def features(ctx: Ctx) -> pd.DataFrame:
    out = pd.DataFrame(index=range(len(ctx.grid)))
    out["environment.noise_db"] = noise(ctx)
    out["safety.crime_per_1000"] = safety(ctx)
    try:
        med, nn = price(ctx)
        out["price.buy_per_m2"] = med
        out["price.buy_n_transactions"] = nn
    except Exception as ex:  # noqa: BLE001
        log.warning("[krakow] RCN failed: %s", ex)
        ctx.missing("rcn", f"RCN WFS failed: {ex}")
        out["price.buy_per_m2"] = np.nan
    g = gios.features(ctx)
    for c in g.columns:
        out[c] = g[c].to_numpy()
    return out
