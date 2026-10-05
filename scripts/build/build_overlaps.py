#!/usr/bin/env python3
"""Compute spatial overlap between Julich-Brain 3.1 and Allen HRA 3D 2020 regions.

Usage:
    python scripts/build/build_overlaps.py               # writes data/anatomy/cross-atlas/
    python scripts/build/build_overlaps.py --min 0.05    # keep weaker overlaps (default 0.10)

Requires siibra (for the Julich labelled map) and the Allen import
(scripts/import/import_allen_hra_3d.py) to have run.

Why this exists
    The two atlases do not parcellate the brain the same way, so the project
    keeps atlas-scoped region ids and records where they overlap instead of
    inventing atlas-neutral ids. One `relationship` record per overlapping pair:

        subject   Julich map leaf (brain-region:julich-...)
        predicate overlaps
        object    Allen hemisphere/midline leaf (brain-region:allen-...)
        context   overlapFractionOfSubject  share of the Julich region's voxels inside the Allen region
                  overlapFractionOfObject   share of the Allen region's voxels inside the Julich region
                  overlapVolumeMm3          overlapping volume on the 1 mm grid

    A pair is kept when either fraction is >= --min (default 0.10).

How
    Every Julich voxel centre (1 mm, ICBM 2009c asym) is looked up in the Allen
    volume (0.5 mm, ICBM 2009b sym) by nearest neighbour, treating the two
    templates as the same millimetre space (see
    spatial-transformation:mni152-2009b-sym-to-2009c-asym-approx-identity).
    No registration is applied; expect errors of about a millimetre at
    boundaries. assertionType is `inferred`, never `observed`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_meshes import ATLASES, allen_label_volume, allen_leaves, julich_label_volumes, slug  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "anatomy" / "cross-atlas"
OUT_FILE = OUT_DIR / "julich31-allen2020-overlaps.json"
VALIDATE = ROOT / "scripts" / "validate.py"
TODAY = dt.date.today().isoformat()
TRANSFORM_ID = "spatial-transformation:mni152-2009b-sym-to-2009c-asym-approx-identity"
PROV = {
    "createdAt": f"{TODAY}T00:00:00Z",
    "createdBy": "scripts/build/build_overlaps.py",
    "method": "nearest-neighbour voxel overlap of the Julich labelled MPM (1 mm, ICBM 2009c asym) and the Allen annotation (0.5 mm, ICBM 2009b sym), templates treated as identical",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=float, default=0.10, help="keep a pair when either overlap fraction is >= this")
    args = ap.parse_args()

    print("loading Julich-Brain 3.1 labelled map ...", file=sys.stderr)
    _, jlabels, jaff, jleaves = julich_label_volumes()
    print("loading Allen annotation volume ...", file=sys.stderr)
    avol, aaff, left_cols = allen_label_volume()
    adata = ATLASES["allen"]["data_dir"]
    aregions = json.loads((adata / "regions.json").read_text(encoding="utf-8"))
    amaps = json.loads((adata / "mappings.json").read_text(encoding="utf-8"))
    aleaves = allen_leaves(aregions, amaps)
    aname = {r["id"]: r["name"] for r in aregions}
    jname = {r["id"]: r["name"] for r in json.loads((ATLASES["julich"]["data_dir"] / "regions.json").read_text(encoding="utf-8"))}

    # --- Allen leaf codes on the Allen grid: compact(label)*2 (+1 on the right) -----------------------
    # Allen structure ids go up to ~2.7e8, so labels are first compacted to 0..141 (0 stays background).
    uniq = np.unique(avol)
    compact = np.searchsorted(uniq, avol).astype(np.int32)
    comp_of = {int(l): int(i) for i, l in enumerate(uniq)}
    code_to_leaf: dict[int, tuple[str, str]] = {}
    midline = np.zeros(len(uniq), dtype=bool)
    for rid, key, lbl, side in aleaves:
        code_to_leaf[comp_of[lbl] * 2 + (1 if side == "right" else 0)] = (rid, key)
        if side == "midline":
            midline[comp_of[lbl]] = True
    side_bit = (~left_cols).astype(np.int32)  # 1 where x > 0
    acode = compact * 2 + np.where(midline[compact], 0, side_bit)
    acode[compact == 0] = 0
    del compact

    # --- resample Allen codes onto the Julich grid (nearest neighbour) --------------------------------
    shape = next(iter(jlabels.values())).shape
    ii, jj, kk = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), np.arange(shape[2]), indexing="ij")
    vox = np.stack([ii.ravel(), jj.ravel(), kk.ravel(), np.ones(ii.size)], axis=0).astype(np.float64)
    world = jaff @ vox
    aidx = np.rint(np.linalg.inv(aaff) @ world)[:3].astype(np.int64)
    inside = np.all((aidx >= 0) & (aidx < np.array(avol.shape)[:, None]), axis=0)
    acode_j = np.zeros(ii.size, dtype=np.int64)
    acode_j[inside] = acode[aidx[0, inside], aidx[1, inside], aidx[2, inside]]
    acode_j = acode_j.reshape(shape)
    allen_total = np.bincount(acode_j.ravel(), minlength=acode.max() + 1)  # Allen leaf sizes on the Julich grid
    voxel_mm3 = float(abs(np.linalg.det(jaff[:3, :3])))

    # --- per Julich leaf ----------------------------------------------------------------------------
    records = []
    n_pairs_all = 0
    for rid, key, frag, lbl in jleaves:
        mask = jlabels[frag] == lbl
        n_j = int(mask.sum())
        if n_j == 0:
            continue
        counts = np.bincount(acode_j[mask], minlength=acode.max() + 1)
        for code in np.nonzero(counts)[0]:
            if code == 0 or int(code) not in code_to_leaf:
                continue
            n_ov = int(counts[code])
            n_pairs_all += 1
            frac_j = n_ov / n_j
            frac_a = n_ov / int(allen_total[code])
            if max(frac_j, frac_a) < args.min:
                continue
            arid, akey = code_to_leaf[int(code)]
            records.append({
                "id": f"relationship:overlap-julich31-{slug(key)}-allen2020-{akey}",
                "subjectId": rid,
                "predicate": "overlaps",
                "objectId": arid,
                "species": "Homo sapiens",
                "context": {
                    "preparation": "in_silico",
                    "overlapFractionOfSubject": round(frac_j, 3),
                    "overlapFractionOfObject": round(frac_a, 3),
                    "overlapVolumeMm3": round(n_ov * voxel_mm3, 1),
                    "transformationId": TRANSFORM_ID,
                    "notes": f"{jname.get(rid, rid)} (Julich) vs {aname.get(arid, arid)} (Allen). Computed on the Julich 1 mm grid; the two MNI templates were treated as identical, so boundaries carry about a millimetre of uncertainty.",
                },
                "assertionType": "inferred",
                "status": "active",
                "provenance": PROV,
            })
    records.sort(key=lambda r: r["id"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("validating ...", file=sys.stderr)
    result = subprocess.run([sys.executable, str(VALIDATE), str(ROOT / "data" / "anatomy")], capture_output=True, text=True)
    print(result.stdout, file=sys.stderr)
    if result.returncode != 0:
        OUT_FILE.unlink(missing_ok=True)
        print("validation failed; output removed", file=sys.stderr)
        return 1
    n_j = len({r["subjectId"] for r in records})
    n_a = len({r["objectId"] for r in records})
    print(f"wrote {len(records)} overlap relationships ({n_pairs_all} raw pairs, kept where either fraction >= {args.min}) "
          f"covering {n_j} of {len(jleaves)} Julich leaves and {n_a} of {len(aleaves)} Allen leaves to {OUT_FILE.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
