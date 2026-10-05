#!/usr/bin/env python3
"""Build viewer meshes from an atlas's labelled volume.

Usage:
    python scripts/build/build_meshes.py                 # both atlases
    python scripts/build/build_meshes.py --atlas julich  # Julich-Brain 3.1 only (needs siibra)
    python scripts/build/build_meshes.py --atlas allen   # Allen Human Reference Atlas 3D 2020 only

Requires the import dependencies plus trimesh and fast-simplification:
    python -m pip install -r requirements-import.txt

Outputs, per atlas
    viewer/public/assets/<atlas>/hull.glb      smoothed whole-brain hull (one mesh)
    viewer/public/assets/<atlas>/regions.glb   one named mesh per leaf region
    data/anatomy/<atlas>/meshes.json           spatial-representation records for the above
    data/anatomy/<atlas>/regions.json          spatialRepresentationIds appended

Julich geometry is in MNI152 ICBM 2009c asym; Allen geometry is in ICBM 2009b sym.
Both are RAS millimetres. The viewer rotates to its own y-up convention at load
time; the files are not rotated.

Meshes are derived from labelled maps (1 mm Julich, 0.5 mm Allen), smoothed
and decimated for display. They are illustrations of the atlas, not
measurement-grade surfaces; the records say so in their provenance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TODAY = dt.date.today().isoformat()

ATLASES = {
    "julich": {
        "data_dir": ROOT / "data" / "anatomy" / "julich-brain-3.1",
        "asset_dir": ROOT / "viewer" / "public" / "assets" / "julich-3.1",
        "asset_rel": "viewer/public/assets/julich-3.1",
        "space_id": "reference-space:mni152-icbm-2009c-nonlin-asym",
        "dataset_version_id": "dataset-version:julich-brain-3.1",
        "atlas_id": "atlas:julich-brain-3.1",
        "prefix": "julich31",
        "resolution_um": 1000,
        "method": "marching cubes on siibra labelled MPM, gaussian-smoothed, quadric-decimated",
    },
    "allen": {
        "data_dir": ROOT / "data" / "anatomy" / "allen-hra-3d-2020",
        "asset_dir": ROOT / "viewer" / "public" / "assets" / "allen-hra-3d-2020",
        "asset_rel": "viewer/public/assets/allen-hra-3d-2020",
        "space_id": "reference-space:mni152-icbm-2009b-nonlin-sym",
        "dataset_version_id": "dataset-version:allen-hra-3d-2020-1.0.0",
        "atlas_id": "atlas:allen-hra-3d-2020",
        "prefix": "allen2020",
        "resolution_um": 500,
        "method": "marching cubes on the Allen annotation volume, gaussian-smoothed, quadric-decimated",
    },
}


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


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


def crop(mask: np.ndarray, pad: int):
    """Bounding-box crop of a mask plus its voxel offset, so small regions don't cost a whole-volume filter."""
    idx = np.argwhere(mask)
    if len(idx) == 0:
        return None, None
    lo = np.maximum(idx.min(axis=0) - pad, 0)
    hi = np.minimum(idx.max(axis=0) + pad + 1, mask.shape)
    return mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]], lo


def shifted(affine: np.ndarray, lo: np.ndarray) -> np.ndarray:
    a = affine.copy()
    a[:3, 3] = (affine @ np.append(lo, 1.0))[:3]
    return a


# ---------------------------------------------------------------------------
# Julich: labelled maximum-probability map from siibra (one fragment per hemisphere)
# ---------------------------------------------------------------------------

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


def julich_label_volumes():
    """The Julich labelled MPM as {fragment: int32 array}, its affine, and (record id, key, fragment, label) per mapped leaf."""
    import siibra

    parc = siibra.parcellations.get("julich 3.1")
    space = siibra.spaces.get("mni152")
    lmap = parc.get_map(space=space, maptype="labelled")
    frags = sorted(lmap.fragments) if lmap.fragments else [None]
    vols = {f: lmap.fetch(fragment=f) if f else lmap.fetch() for f in frags}
    affine = next(iter(vols.values())).affine
    labels = {f: np.asanyarray(v.dataobj).astype(np.int32) for f, v in vols.items()}

    regions_json = json.loads((ATLASES["julich"]["data_dir"] / "regions.json").read_text(encoding="utf-8"))
    by_key = {}
    for r in regions_json:
        for e in r.get("externalIdentifiers", []):
            if e["namespace"] == "siibra-key":
                by_key[e["identifier"]] = r
    leaves = []
    for r in mapped_leaves(parc, lmap):
        rec = by_key.get(r.key)
        if rec is None:
            continue
        idx = lmap.get_index(r)
        frag = idx.fragment if idx.fragment in labels else next(iter(labels))
        leaves.append((rec["id"], r.key, frag, int(idx.label)))
    return regions_json, labels, affine, leaves


def julich_masks():
    print("loading Julich-Brain 3.1 labelled map in MNI152 ...", file=sys.stderr)
    regions_json, labels, affine, leaves = julich_label_volumes()
    union = np.zeros_like(next(iter(labels.values())), dtype=bool)
    for a in labels.values():
        union |= a > 0
    print(f"{len(leaves)} mapped leaf regions (regions with a label and no labelled descendant)", file=sys.stderr)
    items = [(rid, slug(key), (lambda f=frag, l=lbl: labels[f] == l)) for rid, key, frag, lbl in leaves]
    return regions_json, union, affine, items, dict(sigma=1.0, hull_sigma=2.0, step=1, faces=700)


# ---------------------------------------------------------------------------
# Allen: one label volume, hemispheres split at x = 0 exactly as the importer did
# ---------------------------------------------------------------------------

def allen_label_volume():
    """The Allen annotation volume (int64), its affine, and a left-hemisphere column mask (x <= 0)."""
    import nibabel as nib

    raw = ATLASES["allen"]["data_dir"] / "raw" / "annotation_full.nii.gz"
    if not raw.exists():
        sys.exit(f"{raw} missing; run scripts/import/import_allen_hra_3d.py first")
    img = nib.load(raw)
    vol = np.asanyarray(img.dataobj).astype(np.int32)
    affine = img.affine
    xs = affine[0, 0] * np.arange(vol.shape[0]) + affine[0, 3]
    return vol, affine, (xs <= 0)[:, None, None]


def allen_leaves(regions_json, mappings):
    """(record id, key, label, side) for every hemisphere/midline leaf region."""
    label_of = {m["brainRegionId"]: int(m["atlasRegionId"]) for m in mappings if m.get("atlasRegionId")}
    out = []
    for r in regions_json:
        side = r.get("hemisphere")
        if side in ("left", "right", "midline"):
            out.append((r["id"], r["id"].split(":", 1)[1].removeprefix("allen-"), label_of[r["id"]], side))
    return out


def allen_masks():
    print("loading Allen annotation volume ...", file=sys.stderr)
    data_dir = ATLASES["allen"]["data_dir"]
    vol, affine, left_cols = allen_label_volume()
    regions_json = json.loads((data_dir / "regions.json").read_text(encoding="utf-8"))
    mappings = json.loads((data_dir / "mappings.json").read_text(encoding="utf-8"))
    def mask_fn(lbl, side):
        def f():
            mask = vol == lbl
            if side == "left":
                mask &= left_cols
            elif side == "right":
                mask &= ~left_cols
            return mask
        return f

    items = [(rid, key, mask_fn(lbl, side)) for rid, key, lbl, side in allen_leaves(regions_json, mappings)]
    print(f"{len(items)} hemisphere/midline leaf regions", file=sys.stderr)
    # 0.5 mm voxels: sigma doubled to keep the same physical smoothing as Julich; step 2 keeps triangle counts sane
    return regions_json, vol > 0, affine, items, dict(sigma=2.0, hull_sigma=4.0, step=2, faces=1000)


# ---------------------------------------------------------------------------

def build(atlas: str) -> int:
    import trimesh

    cfg = ATLASES[atlas]
    prov = {"createdAt": f"{TODAY}T00:00:00Z", "createdBy": "scripts/build/build_meshes.py", "method": cfg["method"]}
    regions_json, union, affine, items, params = (julich_masks if atlas == "julich" else allen_masks)()
    by_id = {r["id"]: r for r in regions_json}
    mm = cfg["resolution_um"] / 1000
    pad = int(np.ceil(params["sigma"] * 3)) + 1

    cfg["asset_dir"].mkdir(parents=True, exist_ok=True)
    records = []

    # --- hull ---------------------------------------------------------------
    hull = mesh_from_mask(union, affine, sigma=params["hull_sigma"], level=0.4, step=params["step"], target_faces=30000)
    hull.export(cfg["asset_dir"] / "hull.glb")
    print(f"hull: {len(hull.faces)} faces", file=sys.stderr)
    records.append({
        "id": f"spatial-representation:{cfg['prefix']}-whole-brain-hull",
        "subjectId": cfg["atlas_id"],
        "referenceSpaceId": cfg["space_id"],
        "datasetVersionId": cfg["dataset_version_id"],
        "geometry": {"type": "surface", "uri": f"{cfg['asset_rel']}/hull.glb", "format": "glb", "resolutionUm": cfg["resolution_um"],
                     "note": f"Union of all labelled voxels, smoothed (sigma {params['hull_sigma'] * mm:g} mm) and decimated to ~30k faces. Display-only."},
        "provenance": prov,
    })

    # --- per-region ---------------------------------------------------------
    scene = trimesh.Scene()
    n_ok = 0
    for i, (rid, key, mask_of) in enumerate(items, 1):  # masks are built one at a time: a whole-volume mask per region would not fit in memory
        sub, lo = crop(mask_of(), pad)
        if sub is None:
            continue
        # thin tracts and tiny nuclei (< 500 mm3) vanish under full smoothing; halve it for them
        sigma = params["sigma"] if sub.sum() * mm ** 3 >= 500 else params["sigma"] / 2
        m = mesh_from_mask(sub, shifted(affine, lo), sigma=sigma, level=0.5, step=params["step"], target_faces=params["faces"])
        if m is None or len(m.faces) < 12:
            continue
        rec = by_id.get(rid)
        if rec is None:
            continue
        scene.add_geometry(m, node_name=rid, geom_name=rid)  # the viewer looks meshes up by record id
        sid = f"spatial-representation:{cfg['prefix']}-{key}-mesh"
        records.append({
            "id": sid,
            "subjectId": rid,
            "referenceSpaceId": cfg["space_id"],
            "datasetVersionId": cfg["dataset_version_id"],
            "geometry": {"type": "surface", "uri": f"{cfg['asset_rel']}/regions.glb", "format": "glb", "resolutionUm": cfg["resolution_um"],
                         "note": f"Named node '{rid}' inside regions.glb. Labelled-map isosurface, smoothed (sigma {sigma * mm:g} mm), decimated to <={params['faces']} faces. Display-only."},
            "provenance": prov,
        })
        rec.setdefault("spatialRepresentationIds", [])
        if sid not in rec["spatialRepresentationIds"]:
            rec["spatialRepresentationIds"].append(sid)
        n_ok += 1
        if i % 50 == 0:
            print(f"  {i}/{len(items)} ...", file=sys.stderr)

    scene.export(cfg["asset_dir"] / "regions.glb")
    print(f"regions: {n_ok} meshes", file=sys.stderr)

    (cfg["data_dir"] / "meshes.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (cfg["data_dir"] / "regions.json").write_text(json.dumps(regions_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for f in sorted(cfg["asset_dir"].glob("*.glb")):
        print(f"  {f.relative_to(ROOT)}  {f.stat().st_size/1e6:.1f} MB", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", choices=["julich", "allen", "all"], default="all")
    args = ap.parse_args()
    for atlas in (["julich", "allen"] if args.atlas == "all" else [args.atlas]):
        print(f"== {atlas} ==", file=sys.stderr)
        rc = build(atlas)
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
