"""Download every source listed in settings/{city}.yaml into data/raw/{city}/ and record it in the manifest.

Idempotent: files already on disk are kept unless --force. Usage:
    uv run python fetch.py --city krakow [--force] [--only key1,key2]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

import requests

from core.common import USER_AGENT, Manifest, load_env, log, now_iso, raw_dir, settings

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


def _download(url: str, dest: Path, timeout: int = 300, headers: dict | None = None) -> int:
    tmp = dest.with_suffix(dest.suffix + ".part")
    with SESSION.get(url, stream=True, timeout=timeout, headers=headers or {}) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.replace(dest)
    return dest.stat().st_size


def fetch_http(src: dict, dest: Path) -> str:
    size = _download(src["url"], dest, timeout=src.get("timeout", 300))
    return f"{size} bytes"


def fetch_arcgis(src: dict, dest: Path) -> str:
    """Page through an ArcGIS FeatureServer layer and write one GeoJSON FeatureCollection (WGS84)."""
    base = src["url"].rstrip("/")
    meta = SESSION.get(base, params={"f": "json"}, timeout=60).json()
    page = min(int(meta.get("maxRecordCount") or 1000), 2000)
    feats, offset = [], 0
    while True:
        r = SESSION.get(f"{base}/query", timeout=300, params={
            "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
            "resultOffset": offset, "resultRecordCount": page})
        r.raise_for_status()
        fc = r.json()
        if "error" in fc:
            raise RuntimeError(fc["error"])
        batch = fc.get("features", [])
        feats.extend(batch)
        if len(batch) < page and not fc.get("properties", {}).get("exceededTransferLimit"):
            break
        if not batch:
            break
        offset += len(batch)
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False))
    return f"{len(feats)} features"


def fetch_golemio(src: dict, dest: Path) -> str:
    key = os.environ.get("GOLEMIO_API_KEY")
    if not key:
        raise RuntimeError("GOLEMIO_API_KEY not set")
    feats, offset, limit = [], 0, 1000
    while True:
        r = SESSION.get(src["url"], timeout=120, headers={"X-Access-Token": key},
                        params={"limit": limit, "offset": offset})
        r.raise_for_status()
        batch = r.json().get("features", [])
        feats.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    dest.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, ensure_ascii=False))
    return f"{len(feats)} features"


def fetch_police_months(src: dict, dest: Path) -> str:
    """Last N complete months of the Police ČR crime map (national monthly zips)."""
    dest.mkdir(parents=True, exist_ok=True)
    listing = SESSION.get("https://kriminalita.policie.gov.cz/api/v2/downloads", timeout=60).json()["data"]
    this_month = date.today().strftime("%Y%m")
    months = sorted([d["name"] for d in listing if d["name"].isdigit() and d["name"] < this_month],
                    reverse=True)[: src.get("months", 12)]
    for m in months:
        f = dest / f"{m}.zip"
        if not f.exists():
            _download(src["url"].format(month=m), f, timeout=300)
            time.sleep(0.5)
    return f"{len(months)} months {months[-1]}..{months[0]}"


FETCHERS = {"http": fetch_http, "arcgis": fetch_arcgis, "golemio": fetch_golemio,
            "police_months": fetch_police_months}


def run(city: str, force: bool = False, only: set[str] | None = None) -> dict:
    load_env()
    s = settings(city)
    rd = raw_dir(city)
    man = Manifest(city)
    log_path = rd / "_fetch_log.json"
    flog = json.loads(log_path.read_text()) if log_path.exists() else {}
    for src in s["sources"]:
        key = src["key"]
        if only and key not in only:
            continue
        dest = rd / src["file"]
        prev = man.get(key) or {}
        if dest.exists() and not force:
            log.info("[%s] %s cached (%s)", city, key, dest.name)
            fetched_at = flog.get(key, {}).get("fetchedAt") or prev.get("fetchedAt") \
                or now_iso()
            man.record(key, url=src["url"], licence=src.get("licence"), fetchedAt=fetched_at,
                       status=prev.get("status") if prev.get("status") in ("ok", "fallback") else "ok")
            flog.setdefault(key, {"fetchedAt": fetched_at, "result": "cached", "file": src["file"]})
            continue
        try:
            t0 = time.time()
            res = FETCHERS[src["kind"]](src, dest)
            log.info("[%s] %s OK %s in %.1fs", city, key, res, time.time() - t0)
            flog[key] = {"fetchedAt": now_iso(), "result": res, "file": src["file"]}
            note = prev.get("note") or ""
            man.record(key, url=src["url"], licence=src.get("licence"), fetchedAt=flog[key]["fetchedAt"],
                       status="ok", note="" if note.startswith("fetch failed") else note)
        except Exception as ex:  # noqa: BLE001 — record and continue, never block the pipeline
            log.warning("[%s] %s FAILED: %s", city, key, ex)
            flog[key] = {"fetchedAt": now_iso(), "result": f"error: {ex}", "file": src["file"]}
            man.record(key, url=src["url"], licence=src.get("licence"),
                       status="missing", note=f"fetch failed {now_iso()[:16]}: {str(ex)[:200]}"
                       + (" (optional)" if src.get("optional") else ""))
    log_path.write_text(json.dumps(flog, ensure_ascii=False, indent=2))
    man.save()
    return flog


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True, choices=["krakow", "praha"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    run(a.city, a.force, set(filter(None, a.only.split(","))) or None)
