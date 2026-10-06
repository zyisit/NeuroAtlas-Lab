#!/usr/bin/env python3
"""Bundle validated records into one JSON file for the viewer.

Usage:  python scripts/build/build_viewer_bundle.py

Reads every record under data/ (after validating it), groups records by type,
and writes viewer/public/data/bundle.json. The viewer never reads data/ directly;
it reads this bundle, which is the only thing the build step produces.

Packing (added 0.12.0)
Imported files repeat the same values on every record (species, method, unit,
dataset version, provenance ...). For every data file with at least
PACK_MIN records of one type, fields whose value is identical on all of them
are written once:

    {"_shared": {<identical fields>}, "_items": [<the remaining fields per record>]}

`context` is treated the same way one level down (identical context keys move to
_shared.context). The viewer re-expands packs on load (viewer/src/data.ts,
unpackRecords) so every record it sees is complete. Packing changes the bundle
only; data/ is untouched and stays one full record per entry.
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
PACK_MIN = 50
_MISSING = object()


def _same(values) -> object:
    """The common value if every entry is present and identical, else _MISSING."""
    first = _MISSING
    for v in values:
        if v is _MISSING:
            return _MISSING
        if first is _MISSING:
            first = v
        elif v != first:
            return _MISSING
    return first


def pack(records: list[dict]) -> list[dict]:
    """Return [records...] unchanged if small, else [one pack]. Lossless: unpack(pack(x)) == x."""
    if len(records) < PACK_MIN:
        return records
    keys = {k for r in records for k in r}
    shared: dict = {}
    for k in sorted(keys):
        if k in ("id", "context"):
            continue
        v = _same(r.get(k, _MISSING) for r in records)
        if v is not _MISSING:
            shared[k] = v
    ctx_shared: dict = {}
    if all(isinstance(r.get("context"), dict) for r in records):
        ckeys = {k for r in records for k in r["context"]}
        for k in sorted(ckeys):
            v = _same(r["context"].get(k, _MISSING) for r in records)
            if v is not _MISSING:
                ctx_shared[k] = v
        if ctx_shared:
            shared["context"] = ctx_shared
    items = []
    for r in records:
        it = {k: v for k, v in r.items() if k not in shared or k == "context"}
        if "context" in it and ctx_shared:
            rest = {k: v for k, v in it["context"].items() if k not in ctx_shared}
            if rest:
                it["context"] = rest
            else:
                del it["context"]
        items.append(it)
    return [{"_shared": shared, "_items": items}]


def unpack(entries: list[dict]) -> list[dict]:
    """Python twin of viewer/src/data.ts unpackRecords; used by the tests."""
    out = []
    for e in entries:
        if "_items" not in e:
            out.append(e)
            continue
        sh = e["_shared"]
        for it in e["_items"]:
            r = {**sh, **it}
            if "context" in sh:
                r["context"] = {**sh["context"], **it.get("context", {})}
            out.append(r)
    return out


def main():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py"), str(DATA)], capture_output=True, text=True)
    print(r.stdout.strip(), file=sys.stderr)
    if r.returncode != 0:
        return 1
    groups: dict[str, list] = defaultdict(list)
    counts: dict[str, int] = defaultdict(int)
    for f in sorted(DATA.rglob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        by_type: dict[str, list] = defaultdict(list)
        for rec in (doc if isinstance(doc, list) else [doc]):
            by_type[rec["id"].split(":", 1)[0]].append(rec)
        for t, recs in by_type.items():
            groups[t].extend(pack(recs))
            counts[t] += len(recs)
    bundle = {"generatedFrom": "data/", "schemaVersion": json.loads((ROOT / "schemas" / "index.json").read_text())["version"],
              "packed": True, "records": dict(groups)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(bundle, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1e6:.1f} MB): " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
