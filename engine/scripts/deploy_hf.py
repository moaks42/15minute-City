# /// script
# requires-python = ">=3.11"
# dependencies = ["huggingface_hub>=0.25"]
# ///
"""Deploy the engine as a Hugging Face Docker Space. NOTE (2026-10-03): Docker Spaces on cpu-basic need HF PRO (API → 402).

    uv run engine/scripts/deploy_hf.py [--space kompas-engine] [--wait]

Uploads exactly the files of /.dockerignore's whitelist + engine/Dockerfile (as /Dockerfile) + a Space README.
Uses the HF HTTP API (no git). HF_TOKEN comes from the environment or the repo's .env and is never printed.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
INCLUDE = ["engine/pyproject.toml", "engine/uv.lock", "engine/app", "engine/models", "config",
           "contracts/openapi.yaml", "contracts/tools/validate_data.py", "contracts/tools/validate_fixtures.py",
           "data/processed"]
README = """---
title: Kompas engine
emoji: 🧭
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
short_description: Kompas scoring engine API (Kraków + Praha), HackYeah 2026
---

Scoring engine API for **Kompas**: find the part of the city that fits your life (Kraków + Praha).
API docs: `/docs` · health: `/api/health` · source: https://github.com/moaks42/15minute-City (deployed from `{ref}`).
"""


def token() -> str:
    if os.environ.get("HF_TOKEN"):
        return os.environ["HF_TOKEN"]
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("HF_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("HF_TOKEN missing (env or .env)")


def stage(dst: Path, ref: str) -> None:
    for rel in INCLUDE:
        src = ROOT / rel
        if not src.exists():
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, out, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        else:
            shutil.copy2(src, out)
    shutil.copy2(ROOT / "engine/Dockerfile", dst / "Dockerfile")
    (dst / "README.md").write_text(README.replace("{ref}", ref), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--space", default="kompas-engine")
    ap.add_argument("--wait", action="store_true", help="poll until the Space is running and /api/health answers")
    a = ap.parse_args()
    api = HfApi(token=token())
    user = api.whoami()["name"]
    repo_id = f"{user}/{a.space}"
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    ref = f"{branch}@{sha}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True, private=False)
    with tempfile.TemporaryDirectory() as tmp:
        stage(Path(tmp), ref)
        api.upload_folder(folder_path=tmp, repo_id=repo_id, repo_type="space", commit_message=f"deploy engine {ref}")
    host = f"https://{user.lower()}-{a.space.lower()}.hf.space".replace("_", "-")
    print(f"space: https://huggingface.co/spaces/{repo_id}\nurl:   {host}")
    if not a.wait:
        return
    t0 = time.time()
    while time.time() - t0 < 1800:
        stage_ = api.get_space_runtime(repo_id).stage
        print(f"  {int(time.time() - t0):4d}s  {stage_}", flush=True)
        if stage_ in ("BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR"):
            raise SystemExit(f"space failed: {stage_} (see build logs on the Space page)")
        if stage_ == "RUNNING":
            try:
                with urllib.request.urlopen(f"{host}/api/health", timeout=20) as r:
                    print("health:", r.read().decode())
                    return
            except Exception as e:  # noqa: BLE001
                print("  health not ready:", e)
        time.sleep(20)
    raise SystemExit("timed out waiting for the Space")


if __name__ == "__main__":
    main()
