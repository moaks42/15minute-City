"""Load test POST /api/{city}/score for both cities (README §9 H16–H20).

    uv run python scripts/loadtest.py --url http://localhost:8000 --n 300 --concurrency 16
"""
from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import time

import httpx

PERSONAS = {
    "student": {"commute": 5, "transit": 5, "active": 3, "green": 2, "education": 1, "family": 0, "safety": 3,
                "price": 5, "shops": 3, "health": 1, "environment": 2, "leisure": 5, "accessibility": 0},
    "parent": {"commute": 3, "transit": 3, "active": 2, "green": 5, "education": 5, "family": 5, "safety": 5,
               "price": 3, "shops": 4, "health": 4, "environment": 4, "leisure": 1, "accessibility": 2},
    "senior": {"commute": 1, "transit": 4, "active": 3, "green": 4, "education": 0, "family": 0, "safety": 5,
               "price": 3, "shops": 5, "health": 5, "environment": 4, "leisure": 3, "accessibility": 5},
}
ANCHORS = {"krakow": (50.0487, 19.9625), "praha": (50.0925, 14.4520)}


def request(city: str) -> dict:
    p = random.choice(list(PERSONAS))
    la, lo = ANCHORS[city]
    return {"v": 1, "persona": p, "weights": {k: max(0, min(5, v + random.randint(-1, 1))) for k, v in PERSONAS[p].items()},
            "anchors": [{"id": "a1", "lat": la + random.uniform(-0.02, 0.02), "lon": lo + random.uniform(-0.03, 0.03),
                         "mode": random.choice(["transit", "bike"]), "level": 5, "maxMinutes": random.choice([None, 30, 45])}],
            "filters": {"mustHave": [{"category": "pharmacy", "maxWalkMin": 10}] if random.random() < 0.5 else []},
            "aggregate": random.choice(["hex", "hex", "district"])}


async def main(url: str, n: int, concurrency: int) -> None:
    sem = asyncio.Semaphore(concurrency)
    lat: dict[str, list[float]] = {"krakow": [], "praha": []}
    server: dict[str, list[float]] = {"krakow": [], "praha": []}
    errors = 0
    async with httpx.AsyncClient(base_url=url, timeout=30, headers={"Accept-Encoding": "gzip"}) as c:
        async def one(i: int):
            nonlocal errors
            city = "krakow" if i % 2 else "praha"
            async with sem:
                t = time.perf_counter()
                r = await c.post(f"/api/{city}/score", json=request(city))
                dt = (time.perf_counter() - t) * 1000
            if r.status_code != 200:
                errors += 1
                return
            lat[city].append(dt)
            server[city].append(r.json()["computeMs"])
        t0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(n)))
        wall = time.perf_counter() - t0
    print(f"{n} requests, concurrency {concurrency}, {errors} errors, {n / wall:.1f} req/s")
    for city in lat:
        if lat[city]:
            q = statistics.quantiles(lat[city], n=20)
            s = statistics.quantiles(server[city], n=20)
            print(f"  {city:7s} client p50 {q[9]:.0f} ms · p95 {q[18]:.0f} ms | server computeMs p50 {s[9]:.1f} · p95 {s[18]:.1f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=8)
    a = ap.parse_args()
    asyncio.run(main(a.url, a.n, a.concurrency))
