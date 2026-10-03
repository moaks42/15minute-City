"""Validate data/processed/{city}/ against the contract and run README §5 sanity checks.

    uv run python validate.py --city krakow|praha|all [--write-docs]

1. contracts/tools/validate_data.py (B's validator, the same one the engine runs at startup) → errors fail.
2. Soft sanity checks (README §5) → printed as PASS/FAIL with numbers; failures are findings, not errors.
3. --write-docs: refresh the coverage / NaN section in docs/DATA_SOURCES.md.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys

import numpy as np
import pandas as pd

from core.common import PROCESSED_DIR, REPO_DIR

spec = importlib.util.spec_from_file_location("validate_data", REPO_DIR / "contracts/tools/validate_data.py")
vd = importlib.util.module_from_spec(spec)
sys.modules["validate_data"] = vd
spec.loader.exec_module(vd)

# named places for sanity checks only (lat, lon) — never used to compute features
PLACES = {
    "las_wolski": (50.0600, 19.8550), "bielany": (50.0430, 19.8460), "wola_justowska": (50.0640, 19.8800),
    "nowa_huta_steelworks": (50.0700, 20.0870),
    "ruzyne_airport": (50.1008, 14.2600), "stromovka": (50.1060, 14.4220), "divoka_sarka": (50.0960, 14.3250),
    "hostivar_forest": (50.0505, 14.5285),
}


def load(city: str) -> pd.DataFrame:
    f = pd.read_parquet(PROCESSED_DIR / city / "features.parquet")
    return f


def near(df: pd.DataFrame, place: str, km: float) -> pd.Series:
    lat, lon = PLACES[place]
    d = np.hypot((df["lat"] - lat) * 111.2, (df["lon"] - lon) * 111.2 * np.cos(np.radians(lat)))
    return d <= km


def rank_of(df: pd.DataFrame, col: str, district: str, ascending: bool = False) -> tuple[int, int]:
    med = df[df["habitable"]].groupby("district_name")[col].median().sort_values(ascending=ascending)
    return int(list(med.index).index(district)) + 1, len(med)


def pct_rank(df: pd.DataFrame, mask: pd.Series, col: str, habitable_only: bool = True) -> float:
    h = df[df["habitable"]] if habitable_only else df
    p = h[col].rank(pct=True)
    m = mask[h.index]
    return float(p[m.to_numpy()].median()) if m.any() else float("nan")


def sanity(city: str, df: pd.DataFrame) -> list[tuple[str, bool, str]]:
    out = []

    def check(name, ok, detail):
        out.append((name, bool(ok), detail))

    if city == "krakow":
        r, n = rank_of(df, "transit.departures_per_h_500m", "Stare Miasto")
        check("Stare Miasto top for transit", r <= 2, f"rank {r}/{n} by median departures/h")
        r, n = rank_of(df, "leisure.food_10min", "Stare Miasto")
        check("Stare Miasto top for leisure", r <= 2, f"rank {r}/{n} by median food venues within 10 min")
        r, n = rank_of(df, "environment.noise_db", "Stare Miasto")
        check("Stare Miasto low for quiet (loud)", r <= n // 2, f"rank {r}/{n} loudest by median noise")
        r, n = rank_of(df, "price.buy_per_m2", "Stare Miasto")
        check("Stare Miasto low for price (expensive)", r <= 2, f"rank {r}/{n} most expensive by median zł/m²")
        p = pct_rank(df, near(df, "nowa_huta_steelworks", 3.0), "environment.pm10")
        check("Nowa Huta steelworks area worse for air", p >= 0.5, f"median PM10 percentile within 3 km = {p:.2f}")
        p = pct_rank(df, near(df, "las_wolski", 1.0) | near(df, "bielany", 0.7) | near(df, "wola_justowska", 0.7),
                     "green.green_share_500m", habitable_only=False)
        check("Las Wolski / Bielany / Wola Justowska top for green", p >= 0.75, f"median green-share percentile = {p:.2f}")
    else:
        r, n = rank_of(df, "transit.departures_per_h_500m", "Praha 1")
        check("Praha 1 top for transit", r <= 3, f"rank {r}/{n} by median departures/h")
        r, n = rank_of(df, "leisure.food_10min", "Praha 1")
        check("Praha 1 top for leisure", r <= 2, f"rank {r}/{n} by median food venues within 10 min")
        r, n = rank_of(df, "environment.noise_db", "Praha 1")
        check("Praha 1 low for quiet (loud)", r <= n // 2, f"rank {r}/{n} loudest by median noise")
        m = df["poi.metro_station_walk_min"] <= 3
        v = df.loc[m & df["habitable"], "transit.rail_station_walk_min"]
        check("cells next to metro top for rail indicator", (v <= 5).mean() > 0.9 if len(v) else False,
              f"{len(v)} cells ≤3 min from metro, {100 * (v <= 5).mean():.0f}% have rail_station_walk_min ≤ 5")
        p = pct_rank(df, near(df, "ruzyne_airport", 2.5), "environment.noise_db")
        check("Ruzyně airport zone worse for noise", p >= 0.5, f"median noise percentile within 2.5 km = {p:.2f}")
        p = pct_rank(df, near(df, "stromovka", 0.7) | near(df, "divoka_sarka", 0.7) | near(df, "hostivar_forest", 0.7),
                     "green.green_share_500m", habitable_only=False)
        check("Stromovka / Divoká Šárka / Hostivař top for green", p >= 0.75, f"median green-share percentile = {p:.2f}")
    return out


def coverage_md(city: str, rep) -> str:
    cfg = vd.load_config(REPO_DIR / "config")
    exp = vd.expected_indicators(cfg, city)
    man = json.loads((PROCESSED_DIR / city / "manifest.json").read_text())
    lines = [f"#### {city} — built {man.get('builtAt', '?')}", "",
             "| criterion | coverage (weighted) | indicators with data / total |", "|---|---|---|"]
    for crit, cov in rep.coverage.items():
        cols = [c for c, s in exp.items() if s["criterion"] == crit and s.get("weight", 0) > 0]
        have = sum(1 for c in cols if rep.nan_share.get(c, 1.0) < 1.0)
        lines.append(f"| {crit} | {cov:.0%} | {have}/{len(cols)} |")
    lines += ["", "<details><summary>NaN share per column (habitable cells)</summary>", "",
              "| column | NaN share |", "|---|---|"]
    lines += [f"| `{c}` | {v:.1%} |" for c, v in sorted(rep.nan_share.items())]
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def write_docs(blocks: dict[str, str]) -> None:
    p = REPO_DIR / "docs" / "DATA_SOURCES.md"
    s = p.read_text(encoding="utf-8") if p.exists() else ""
    for city, md in blocks.items():
        a, b = f"<!-- coverage:{city}:start -->", f"<!-- coverage:{city}:end -->"
        block = f"{a}\n{md}\n{b}"
        s = re.sub(re.escape(a) + r".*?" + re.escape(b), lambda _: block, s, flags=re.S) if a in s else s + "\n" + block + "\n"
    p.write_text(s, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="all")
    ap.add_argument("--write-docs", action="store_true")
    a = ap.parse_args()
    cities = ["krakow", "praha"] if a.city == "all" else [a.city]
    failed, blocks = False, {}
    for city in cities:
        rep = vd.validate_city(PROCESSED_DIR, city, REPO_DIR / "config")
        print(f"\n== {city}: {len(rep.errors)} contract errors, {len(rep.warnings)} warnings")
        for e in rep.errors:
            print("  ERROR  ", e)
        for w in rep.warnings:
            print("  warn   ", w)
        print("  coverage:", json.dumps(rep.coverage))
        failed |= bool(rep.errors)
        if rep.errors:
            continue
        df = load(city)
        print("  sanity checks (README §5):")
        res = sanity(city, df)
        for name, ok, detail in res:
            print(f"    {'PASS' if ok else 'FAIL'}  {name}: {detail}")
        md = coverage_md(city, rep)
        md += "\n| sanity check (README §5) | result | detail |\n|---|---|---|\n"
        md += "\n".join(f"| {n} | {'✅ pass' if ok else '⚠️ fail'} | {d} |" for n, ok, d in res) + "\n"
        blocks[city] = md
    if a.write_docs and blocks:
        write_docs(blocks)
        print("\nupdated docs/DATA_SOURCES.md")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
