#!/usr/bin/env python3
"""Bundle validated records into one JSON file for the viewer.

Usage:  python scripts/build/build_viewer_bundle.py

Reads every record under data/ (after validating it), groups records by type,
and writes viewer/public/data/bundle.json. The viewer never reads data/ directly;
it reads this bundle, which is the only thing the build step produces.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "viewer" / "public" / "data" / "bundle.json"


def main():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py"), str(DATA)], capture_output=True, text=True)
    print(r.stdout.strip(), file=sys.stderr)
    if r.returncode != 0:
        return 1
    groups = defaultdict(list)
    for f in sorted(DATA.rglob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        for rec in (doc if isinstance(doc, list) else [doc]):
            groups[rec["id"].split(":", 1)[0]].append(rec)
    bundle = {"generatedFrom": "data/", "schemaVersion": json.loads((ROOT / "schemas" / "index.json").read_text())["version"], "records": dict(groups)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1e6:.1f} MB): " + ", ".join(f"{k}={len(v)}" for k, v in sorted(groups.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
