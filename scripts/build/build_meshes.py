#!/usr/bin/env python3
"""Build viewer meshes from the Julich-Brain 3.1 labelled maximum-probability map.

Usage:
    python scripts/build/build_meshes.py            # all mapped leaf regions + hull

Requires the import dependencies plus trimesh and fast-simplification:
    python -m pip install -r requirements-import.txt

Outputs
    viewer/public/assets/julich-3.1/hull.glb      smoothed whole-brain hull (one mesh)
    viewer/public/assets/julich-3.1/regions.glb   one named mesh per mapped leaf region
    data/anatomy/julich-brain-3.1/meshes.json     spatial-representation records for the above

All geometry is in MNI152 ICBM 2009c asym millimetre coordinates, RAS. The viewer
rotates to its own y-up convention at load time; the files are not rotated.

Meshes are derived from a 1 mm labelled map, smoothed and decimated for display.
They are illustrations of the atlas, not measurement-grade surfaces; the records
say so in their provenance.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "anatomy" / "julich-brain-3.1"
ASSET_DIR = ROOT / "viewer" / "public" / "assets" / "julich-3.1"
TODAY = dt.date.today().isoformat()
PROV = {"createdAt": f"{TODAY}T00:00:00Z", "createdBy": "scripts/build/build_meshes.py", "method": "marching cubes on siibra labelled MPM, gaussian-smoothed, quadric-decimated"}

SPACE_ID = "reference-space:mni152-icbm-2009c-nonlin-asym"
DATASET_VERSION_ID = "dataset-version:julich-brain-3.1"
ATLAS_ID = "atlas:julich-brain-3.1"


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def mapped_leaves(parc, lmap):
    """Regions that have a label in the map and none of whose descendants do.

    Julich defines some sub-areas (e.g. amygdala subnuclei) in the hierarchy but
    maps only their parent, so 'leaf' must mean leaf-of-the-map, not leaf-of-the-tree.
    """
    import logging
    logging.getLogger("siibra").setLevel(logging.ERROR)
    mapped = []
    for r in parc:
        if r is parc:
            continue
        try:
            lmap.get_index(r)
            mapped.append(r)
        except Exception:
            pass
    mapped_set = set(mapped)
    return [r for r in mapped if not any(d in mapped_set for d in r.descendants)]


def to_mm(verts_vox: np.ndarray, affine: np.ndarray) -> np.ndarray:
    homog = np.c_[verts_vox, np.ones(len(verts_vox))]
    return (affine @ homog.T).T[:, :3].astype(np.float32)


def mesh_from_mask(mask: np.ndarray, affine, sigma: float, level: float, step: int, target_faces: int):
    from scipy import ndimage
    from skimage import measure
    import trimesh

    sm = ndimage.gaussian_filter(mask.astype(np.float32), sigma)
    if sm.max() < level:
        return None
    v, f, _, _ = measure.marching_cubes(sm, level, step_size=step)
    m = trimesh.Trimesh(to_mm(v, affine), f, process=True)
    if len(m.faces) > target_faces:
        m = m.simplify_quadric_decimation(face_count=target_faces)
    m.fix_normals()
    return m


def main():
    import siibra
    import trimesh

    print("loading Julich-Brain 3.1 labelled map in MNI152 ...", file=sys.stderr)
    parc = siibra.parcellations.get("julich 3.1")
    space = siibra.spaces.get("mni152")
    lmap = parc.get_map(space=space, maptype="labelled")
    frags = sorted(lmap.fragments) if lmap.fragments else [None]
    vols = {f: lmap.fetch(fragment=f) if f else lmap.fetch() for f in frags}
    affine = next(iter(vols.values())).affine
    labels = {f: np.asanyarray(v.dataobj).astype(np.int32) for f, v in vols.items()}

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    # --- hull ---------------------------------------------------------------
    mask = np.zeros_like(next(iter(labels.values())), dtype=bool)
    for a in labels.values():
        mask |= a > 0
    hull = mesh_from_mask(mask, affine, sigma=2.0, level=0.4, step=1, target_faces=30000)
    hull.export(ASSET_DIR / "hull.glb")
    print(f"hull: {len(hull.faces)} faces", file=sys.stderr)
    records.append({
        "id": "spatial-representation:julich31-whole-brain-hull",
        "subjectId": ATLAS_ID,
        "referenceSpaceId": SPACE_ID,
        "datasetVersionId": DATASET_VERSION_ID,
        "geometry": {"type": "surface", "uri": "viewer/public/assets/julich-3.1/hull.glb", "format": "glb", "resolutionUm": 1000,
                     "note": "Union of all labelled voxels, smoothed (sigma 2 mm) and decimated to ~30k faces. Display-only."},
        "provenance": PROV,
    })

    # --- per-region ---------------------------------------------------------
    regions_json = json.loads((DATA_DIR / "regions.json").read_text(encoding="utf-8"))
    by_key = {}
    for r in regions_json:
        for e in r.get("externalIdentifiers", []):
            if e["namespace"] == "siibra-key":
                by_key[e["identifier"]] = r

    scene = trimesh.Scene()
    leaves = mapped_leaves(parc, lmap)
    print(f"{len(leaves)} mapped leaf regions (regions with a label and no labelled descendant)", file=sys.stderr)
    n_ok = 0
    for i, r in enumerate(leaves, 1):
        idx = lmap.get_index(r)
        frag = idx.fragment if idx.fragment in labels else next(iter(labels))
        m = mesh_from_mask(labels[frag] == idx.label, affine, sigma=1.0, level=0.5, step=1, target_faces=700)
        if m is None or len(m.faces) < 12:
            continue
        rec = by_key.get(r.key)
        if rec is None:
            continue
        rid = rec["id"]
        node_name = rid  # the viewer looks meshes up by record id
        scene.add_geometry(m, node_name=node_name, geom_name=node_name)
        sid = f"spatial-representation:julich31-{slug(r.key)}-mesh"
        records.append({
            "id": sid,
            "subjectId": rid,
            "referenceSpaceId": SPACE_ID,
            "datasetVersionId": DATASET_VERSION_ID,
            "geometry": {"type": "surface", "uri": "viewer/public/assets/julich-3.1/regions.glb", "format": "glb", "resolutionUm": 1000,
                         "note": f"Named node '{node_name}' inside regions.glb. Labelled-map isosurface, smoothed (sigma 1 mm), decimated to <=700 faces. Display-only."},
            "provenance": PROV,
        })
        rec.setdefault("spatialRepresentationIds", [])
        if sid not in rec["spatialRepresentationIds"]:
            rec["spatialRepresentationIds"].append(sid)
        n_ok += 1
        if i % 50 == 0:
            print(f"  {i}/{len(leaves)} ...", file=sys.stderr)

    scene.export(ASSET_DIR / "regions.glb")
    print(f"regions: {n_ok} meshes", file=sys.stderr)

    (DATA_DIR / "meshes.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DATA_DIR / "regions.json").write_text(json.dumps(regions_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for f in sorted(ASSET_DIR.glob("*.glb")):
        print(f"  {f.relative_to(ROOT)}  {f.stat().st_size/1e6:.1f} MB", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
