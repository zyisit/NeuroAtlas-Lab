#!/usr/bin/env python3
"""Import the Allen Human Reference Atlas - 3D, 2020 into NeuroAtlas records.

Usage:
    python scripts/import/import_allen_hra_3d.py            # downloads (once), writes regions, mappings, spatial

Requires:  python -m pip install -r requirements-import.txt   (nibabel, numpy)
This importer does NOT use siibra. siibra has no Allen *human* parcellation
(only Allen Mouse CCF v3), so the atlas is read directly from the Allen
Institute's release directory.

Input (downloaded once into data/anatomy/allen-hra-3d-2020/raw/, gitignored):
    annotation_full.nii.gz   0.5 mm label volume, both hemispheres, 141 structures
    voxel_count.csv          the structure ontology (id, acronym, name, colour,
                             parent, id path) plus voxel counts, shipped inside
                             the same CC BY 4.0 release directory

Output (all under data/anatomy/allen-hra-3d-2020/):
    provenance.json   dataset, dataset-version, 2 sources, reference-space,
                      spatial-transformation (to the Julich MNI space), atlas
    regions.json      hierarchy nodes + annotated structures + hemisphere leaves
    mappings.json     one atlas-mapping per region, with Allen id, acronym, colour
    spatial.json      centroid + volume for every hemisphere/midline leaf

Every record is validated by scripts/validate.py before being written; the
script refuses to write anything if validation fails.

Design notes
- Region ids are `brain-region:allen-<acronym>`; hemisphere leaves add
  `-left` / `-right`. Ids stay atlas-scoped on purpose: Julich and Allen do
  not parcellate the same way (Allen splits the hippocampus head/body/tail,
  Julich splits it CA1/CA2/CA3), so there is no honest atlas-neutral id for
  both. Cross-atlas navigation is provided by computed `overlaps`
  relationships (scripts/build/build_overlaps.py), not by shared ids.
- Allen assigns ONE label to both hemispheres. The published
  annotation_full.nii.gz is the left-hemisphere drawing mirrored across
  x = 0 (verified voxel-for-voxel at import). This script splits each
  bilateral structure into a left and a right leaf at x = 0 and records the
  mirroring on the dataset-version. Ventricles, commissures and the pineal
  body are kept as single `midline` leaves (see MIDLINE_ACRONYMS).
- The atlas is drawn on ICBM 2009b Nonlinear *Symmetric*. Julich-Brain is on
  ICBM 2009c Nonlinear *Asymmetric*. They are different templates, so the
  Allen records get their own reference-space record and an explicit
  approximate identity spatial-transformation to the Julich space.
- License: CC BY 4.0 (the release page states the materials moved to
  CC BY 4.0 on 2022-09-01, overriding the general Allen Terms of Use).
  commercialUseAllowed is recorded as true.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "anatomy" / "allen-hra-3d-2020"
RAW_DIR = OUT_DIR / "raw"
VALIDATE = ROOT / "scripts" / "validate.py"
TODAY = dt.date.today().isoformat()

BASE_URL = "https://download.alleninstitute.org/informatics-archive/allen_human_reference_atlas_3d_2020/version_1"
FILES = {
    "annotation_full.nii.gz": f"{BASE_URL}/annotation_full.nii.gz",
    "voxel_count.csv": f"{BASE_URL}/examples/voxel_count/voxel_count.csv",
}

DATASET_ID = "dataset:allen-human-reference-atlas-3d"
DATASET_VERSION_ID = "dataset-version:allen-hra-3d-2020-1.0.0"
SOURCE_DATASET_ID = "source:ding-2020-allen-hra-3d"
SOURCE_ONTOLOGY_ID = "source:ding-2016-allen-human-atlas"
SPACE_ID = "reference-space:mni152-icbm-2009b-nonlin-sym"
JULICH_SPACE_ID = "reference-space:mni152-icbm-2009c-nonlin-asym"
TRANSFORM_ID = "spatial-transformation:mni152-2009b-sym-to-2009c-asym-approx-identity"
ATLAS_ID = "atlas:allen-hra-3d-2020"

PROV = {"createdAt": f"{TODAY}T00:00:00Z", "createdBy": "scripts/import/import_allen_hra_3d.py", "method": "direct import of the Allen release files (NIfTI label volume + voxel_count.csv ontology)"}

# Structures that sit on the midline and are not split into hemispheres:
# the ventricular system, the commissures and the pineal body.
MIDLINE_ACRONYMS = {"3V", "Aq", "4V", "cec", "ac", "cc", "Pin"}
# Developmental scaffolding above the brain node; not imported as regions.
SKIP_ACRONYMS = {"NP", "NT", "Br"}

VOXEL_MM3 = 0.5 ** 3


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


# acronym -> id slug. Allen acronyms are unique but only case-sensitively (MTG = middle temporal
# gyrus, MTg = midbrain tegmentum), so colliding ones get the Allen structure id appended.
SLUGS: dict[str, str] = {}


def build_slugs(by_id: dict[int, dict], ordered: list[int]):
    groups: dict[str, list[int]] = {}
    for sid in ordered:
        groups.setdefault(slug(by_id[sid]["acronym"]), []).append(sid)
    for base, sids in groups.items():
        for sid in sids:
            SLUGS[by_id[sid]["acronym"]] = base if len(sids) == 1 else f"{base}-{sid}"


def region_id(acronym: str, side: str | None = None) -> str:
    return f"brain-region:allen-{SLUGS[acronym]}" + (f"-{side}" if side else "")


def mapping_id(acronym: str, side: str | None = None) -> str:
    return f"atlas-mapping:allen2020-{SLUGS[acronym]}" + (f"-{side}" if side else "")


def download(force: bool = False) -> dict[str, Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, url in FILES.items():
        p = RAW_DIR / name
        if force or not p.exists():
            print(f"downloading {name} ...", file=sys.stderr)
            urllib.request.urlretrieve(url, p)
        paths[name] = p
    return paths


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_ontology(csv_path: Path) -> tuple[dict[int, dict], list[int]]:
    """All rows by id, and the ordered list of ids that are annotated or an ancestor of one."""
    rows = list(csv.DictReader(csv_path.open(newline="", encoding="utf-8")))
    by_id = {int(r["id"]): r for r in rows}
    keep: set[int] = set()
    for r in rows:
        if r["annotated"] == "True":
            for pid in r["structure_id_path"].strip("/").split("/"):
                keep.add(int(pid))
    ordered = [int(r["id"]) for r in rows if int(r["id"]) in keep]  # csv is in graph order (parents first)
    return by_id, ordered


CLASS_RULES = [  # (acronym of an ancestor or self, anatomicalClass); first match wins, checked from self upward
    ("Cx", "cortex"), ("CeG", "cortex"), ("LI", "cortex"),
    ("CN", "subcortex"), ("Die", "subcortex"),
    ("CB", "cerebellum"),
    ("M", "brainstem"), ("Pn", "brainstem"), ("Mo", "brainstem"),
    ("FWM", "white_matter"), ("MWM", "white_matter"), ("HWM", "white_matter"),
    ("FV", "ventricle"), ("MV", "ventricle"), ("HV", "ventricle"),
    ("FGM", "subcortex"), ("HGM", "brainstem"), ("FSS", "cortex"),
]


def anatomical_class(path_ids: list[int], by_id: dict[int, dict]) -> str:
    acrs = [by_id[i]["acronym"] for i in reversed(path_ids)]  # self first, then parents
    for a in acrs:
        for key, cls in CLASS_RULES:
            if a == key:
                return cls
    # top-level division keeps its own name (forebrain, hindbrain), as the Julich importer does
    return slug(by_id[path_ids[3]]["name"].split(" ")[0]).replace("-", "_") if len(path_ids) > 3 else "unspecified"


def build_provenance(hashes: dict[str, str]) -> list[dict]:
    dataset_citation = ('Ding S-L, Royall JJ, Sunkin SM, Facer BAC, Lesnar P, Bernard A, Ng L, Lein ES (2020). '
                        '"Allen Human Reference Atlas - 3D, 2020", RRID:SCR_017764, version 1.0.0.')
    ontology_citation = ('Ding S-L, Royall JJ, Sunkin SM, Ng L, Facer BAC, Lesnar P, et al. (2016). Comprehensive cellular-resolution '
                         'atlas of the adult human brain. Journal of Comparative Neurology 524(16):3127-3481. doi:10.1002/cne.24080')
    return [
        {
            "id": DATASET_ID,
            "name": "Allen Human Reference Atlas - 3D",
            "description": "A voxel-level parcellation of the adult human brain into 141 structures, drawn by Song-Lin Ding on the ICBM 2009b Nonlinear Symmetric template at 0.5 mm, using the anatomic ontology of the 2016 Allen adult human brain atlas.",
            "publisher": "Allen Institute for Brain Science",
            "homepage": "https://community.brain-map.org/t/allen-human-reference-atlas-3d-2020-new/405",
            "license": {
                "spdx": "CC-BY-4.0",
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "attributionText": f"{dataset_citation} Available from {BASE_URL}/ . (c) 2019 Allen Institute for Brain Science.",
                "commercialUseAllowed": True,
                "notes": "The release page states these materials are provided under CC BY 4.0 as of 2022-09-01, which overrides the non-commercial clause of the general Allen Institute Terms of Use for this resource. Citation must follow the Allen Institute Citation Policy.",
            },
            "externalIdentifiers": [
                {"namespace": "RRID", "identifier": "SCR_017764", "url": "https://scicrunch.org/resolver/RRID:SCR_017764"},
            ],
            "provenance": PROV,
        },
        {
            "id": DATASET_VERSION_ID,
            "datasetId": DATASET_ID,
            "version": "1.0.0",
            "releaseDate": "2020-01-11",
            "retrievedAt": TODAY,
            "accessUrl": f"{BASE_URL}/",
            "contentHash": "sha256:" + hashes["annotation_full.nii.gz"],
            "transformations": [
                "Structure names, acronyms, colours and hierarchy read from examples/voxel_count/voxel_count.csv in the release directory; no Allen API call.",
                "annotation_full.nii.gz is Allen's left-hemisphere drawing mirrored across x = 0 (verified voxel-for-voxel at import); the right-hemisphere geometry in this project is therefore a mirror image, not an independent drawing.",
                "Each bilateral structure split at x = 0 (RAS) into a left and a right leaf region; voxels at x = 0 assigned to the left. Ventricles, commissures and the pineal body kept as single midline regions.",
                "Centroids and volumes computed from the label volume in template voxel space (0.5 mm isotropic).",
            ],
            "notes": f"voxel_count.csv sha256: {hashes['voxel_count.csv']}. Developmental scaffolding nodes above 'brain' (neural plate, neural tube, brain) are not imported.",
            "provenance": PROV,
        },
        {
            "id": SOURCE_DATASET_ID,
            "sourceType": "atlas",
            "title": "Allen Human Reference Atlas - 3D, 2020",
            "authors": ["Ding S-L", "Royall JJ", "Sunkin SM", "Facer BAC", "Lesnar P", "Bernard A", "Ng L", "Lein ES"],
            "year": 2020,
            "citation": dataset_citation,
            "url": "https://community.brain-map.org/t/allen-human-reference-atlas-3d-2020-new/405",
            "datasetVersionId": DATASET_VERSION_ID,
            "externalIdentifiers": [{"namespace": "RRID", "identifier": "SCR_017764"}],
            "provenance": PROV,
        },
        {
            "id": SOURCE_ONTOLOGY_ID,
            "sourceType": "primary_research",
            "title": "Comprehensive cellular-resolution atlas of the adult human brain",
            "authors": ["Ding S-L", "Royall JJ", "Sunkin SM", "Ng L", "Facer BAC", "Lesnar P", "Guillozet-Bongaarts A", "McMurray B", "Szafer A", "Dolbeare TA", "Stevens A", "Tirrell L", "Benner T", "Caldejon S", "Dalley RA", "Dee N", "Lau C", "Nyhus J", "Reding M", "Riley ZL", "Sandman D", "Shen E", "van der Kouwe A", "Varjabedian A", "Write M", "Zollei L", "Dang C", "Knowles JA", "Koch C", "Phillips JW", "Sestan N", "Wohnoutka P", "Zielke HR", "Hohmann JG", "Jones AR", "Bernard A", "Hawrylycz MJ", "Hof PR", "Fischl B", "Lein ES"],
            "year": 2016,
            "citation": ontology_citation,
            "url": "https://doi.org/10.1002/cne.24080",
            "externalIdentifiers": [{"namespace": "DOI", "identifier": "10.1002/cne.24080"}],
            "provenance": PROV,
        },
        {
            "id": SPACE_ID,
            "name": "MNI 152 ICBM 2009b Nonlinear Symmetric",
            "coordinateSystem": "MNI152 ICBM 2009b Nonlinear Symmetric, RAS, mm",
            "species": "Homo sapiens",
            "unit": "mm",
            "description": "Symmetric non-linear average of 152 adult brains (McConnell Brain Imaging Centre, MNI). Template space of the Allen Human Reference Atlas - 3D. Not the same template as the Julich-Brain maps (2009c asymmetric).",
            "externalIdentifiers": [{"namespace": "MNI", "identifier": "ICBM 152 Nonlinear atlases 2009", "url": "http://www.bic.mni.mcgill.ca/ServicesAtlases/ICBM152NLin2009"}],
            "provenance": PROV,
        },
        {
            "id": TRANSFORM_ID,
            "sourceReferenceSpaceId": SPACE_ID,
            "targetReferenceSpaceId": JULICH_SPACE_ID,
            "method": "identity (approximate)",
            "invertible": True,
            "notes": "The 2009b symmetric and 2009c asymmetric ICBM templates are both non-linear averages of the same 152 subjects and are treated as the same millimetre space in this project. No registration was computed. Expect discrepancies of the order of a millimetre at structure boundaries; the viewer says so wherever the two atlases are compared.",
            "provenance": PROV,
        },
        {
            "id": ATLAS_ID,
            "name": "Allen Human Reference Atlas - 3D, 2020",
            "species": "Homo sapiens",
            "referenceSpaceId": SPACE_ID,
            "datasetVersionId": DATASET_VERSION_ID,
            "parcellationVersion": "1.0.0",
            "description": "141 annotated structures covering cortex (gyral level), cerebral nuclei, diencephalon, brainstem, cerebellum, white-matter tracts and ventricles, with the 2016 Allen adult human structural ontology as hierarchy.",
            "externalIdentifiers": [{"namespace": "RRID", "identifier": "SCR_017764"}],
            "provenance": PROV,
        },
    ]


def build_regions(by_id: dict[int, dict], ordered: list[int], side_info: dict[int, str]):
    """side_info: annotated structure id -> 'split' or 'midline'."""
    region_recs, mapping_recs = [], []
    kept = set(ordered)

    def parent_of(sid: int) -> int | None:
        p = by_id[sid]["parent_structure_id"]
        if not p:
            return None
        pid = int(float(p))
        return pid if pid in kept and by_id[pid]["acronym"] not in SKIP_ACRONYMS else None

    for sid in ordered:
        row = by_id[sid]
        acr = row["acronym"]
        if acr in SKIP_ACRONYMS:
            continue
        path_ids = [int(x) for x in row["structure_id_path"].strip("/").split("/")]
        annotated = row["annotated"] == "True"
        cls = anatomical_class(path_ids, by_id)
        color = "#" + row["color_hex_triplet"].lower() if row["color_hex_triplet"] else None
        pid = parent_of(sid)

        base = {
            "species": "Homo sapiens",
            "anatomicalClass": cls,
            "status": "active",
            "provenance": PROV,
        }
        ext = [
            {"namespace": "Allen", "identifier": str(sid), "url": f"http://api.brain-map.org/api/v2/data/Structure/{sid}.json"},
            {"namespace": "Allen-acronym", "identifier": acr},
        ]
        node_id = region_id(acr)
        mode = side_info.get(sid)
        node = {
            "id": node_id, "name": row["name"], "aliases": [acr], **base,
            "hemisphere": "midline" if mode == "midline" else "bilateral",
            "atlasMappingIds": [mapping_id(acr)],
            "externalIdentifiers": ext,
        }
        if pid is not None:
            node["parentRegionIds"] = [region_id(by_id[pid]["acronym"])]
        region_recs.append(node)
        m = {
            "id": mapping_id(acr), "brainRegionId": node_id, "atlasId": ATLAS_ID,
            "atlasRegionId": str(sid), "label": row["name"], "mappingType": "exact",
            "datasetVersionId": DATASET_VERSION_ID, "provenance": PROV,
        }
        if pid is not None:
            m["atlasParentRegionId"] = str(pid)
        if color:
            m["displayColor"] = color
        if not annotated:
            m["notes"] = "Hierarchy node from the Allen ontology; it has no voxels of its own in the 3D annotation."
        mapping_recs.append(m)

        if mode == "split":
            for side in ("left", "right"):
                leaf_id = region_id(acr, side)
                region_recs.append({
                    "id": leaf_id, "name": f"{row['name']} {side}", "aliases": [f"{acr} {side}"], **base,
                    "hemisphere": side, "parentRegionIds": [node_id],
                    "atlasMappingIds": [mapping_id(acr, side)],
                    "externalIdentifiers": ext,
                })
                mapping_recs.append({
                    "id": mapping_id(acr, side), "brainRegionId": leaf_id, "atlasId": ATLAS_ID,
                    "atlasRegionId": str(sid), "atlasParentRegionId": str(sid), "label": row["name"],
                    "mappingType": "approximate", "datasetVersionId": DATASET_VERSION_ID,
                    "notes": f"The {side} half (x {'< 0' if side == 'left' else '> 0'} RAS) of Allen structure {acr}, which carries one label for both hemispheres. Split by NeuroAtlas at import; the right side of the Allen volume is a mirror of the left.",
                    "provenance": PROV, **({"displayColor": color} if color else {}),
                })
    return region_recs, mapping_recs


def build_spatial(vol: np.ndarray, affine: np.ndarray, by_id: dict[int, dict], side_info: dict[int, str], region_by_id: dict[str, dict]) -> list[dict]:
    recs = []
    xs = affine[0, 0] * np.arange(vol.shape[0]) + affine[0, 3]
    left_cols = xs <= 0
    for sid, mode in side_info.items():
        acr = by_id[sid]["acronym"]
        mask_all = vol == sid
        parts = [(None, mask_all)] if mode == "midline" else [("left", mask_all & left_cols[:, None, None]), ("right", mask_all & ~left_cols[:, None, None])]
        for side, mask in parts:
            n = int(mask.sum())
            if n == 0:
                continue
            idx = np.argwhere(mask)
            centroid_vox = idx.mean(axis=0)
            centroid = (affine @ np.append(centroid_vox, 1.0))[:3]
            rid = region_id(acr, side)
            spid = f"spatial-representation:allen2020-{SLUGS[acr]}{'-' + side if side else ''}-centroid"
            recs.append({
                "id": spid, "subjectId": rid, "referenceSpaceId": SPACE_ID, "datasetVersionId": DATASET_VERSION_ID,
                "transformationIds": [TRANSFORM_ID],
                "geometry": {"type": "point", "coordinates": [round(float(v), 2) for v in centroid], "format": "xyz-mm",
                             "note": "Mean voxel position of the label (all voxels, not the largest component) in ICBM 2009b symmetric space."},
                "provenance": PROV,
            })
            recs.append({
                "id": f"observation:allen2020-{SLUGS[acr]}{'-' + side if side else ''}-volume",
                "observationType": "derived", "datasetVersionId": DATASET_VERSION_ID, "sourceId": SOURCE_DATASET_ID,
                "subjectId": rid, "species": "Homo sapiens",
                "context": {"preparation": "in_vivo", "notes": "Volume of the annotation label on the ICBM 2009b symmetric population template; not an individual-brain measurement. Right-hemisphere values equal the left because the Allen volume is mirrored."},
                "value": round(n * VOXEL_MM3, 1), "unit": "mm3",
                "method": "voxel count of the label x 0.125 mm3",
                "spatialRepresentationId": spid, "provenance": PROV,
            })
            region_by_id[rid].setdefault("spatialRepresentationIds", []).append(spid)
    return recs


def classify_sides(by_id: dict[int, dict], vol: np.ndarray) -> dict[int, str]:
    labels = [int(l) for l in np.unique(vol) if l != 0]
    out = {}
    for l in labels:
        out[l] = "midline" if by_id[l]["acronym"] in MIDLINE_ACRONYMS else "split"
    return out


def write(path: Path, records: list[dict]):
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-download", action="store_true", help="re-download the release files even if cached")
    args = ap.parse_args()

    import nibabel as nib

    paths = download(args.force_download)
    hashes = {name: sha256(p) for name, p in paths.items()}
    by_id, ordered = load_ontology(paths["voxel_count.csv"])
    build_slugs(by_id, ordered)
    img = nib.load(paths["annotation_full.nii.gz"])
    vol = np.asanyarray(img.dataobj).astype(np.int64)
    affine = img.affine
    labels = {int(l) for l in np.unique(vol) if l != 0}
    missing = labels - set(by_id)
    if missing:
        print(f"ERROR: {len(missing)} labels in the volume are not in voxel_count.csv: {sorted(missing)[:10]}", file=sys.stderr)
        return 1
    # mirror check: right half must equal the flipped left half
    xs = affine[0, 0] * np.arange(vol.shape[0]) + affine[0, 3]
    i0 = int(np.argmin(np.abs(xs)))
    left, right = vol[:i0], vol[i0 + 1:i0 + 1 + i0][::-1]
    mirrored = right.shape == left.shape and np.array_equal(left, right)
    print(f"{len(labels)} labels, {len(ordered)} ontology nodes kept; volume {vol.shape}; right hemisphere is {'an exact' if mirrored else 'NOT a'} mirror of the left", file=sys.stderr)
    if not mirrored:
        print("ERROR: the release volume is no longer a mirror; the hemisphere-split notes in this script would be wrong. Stop and review.", file=sys.stderr)
        return 1

    side_info = classify_sides(by_id, vol)
    provenance = build_provenance(hashes)
    region_recs, mapping_recs = build_regions(by_id, ordered, side_info)
    by_rid = {r["id"]: r for r in region_recs}
    spatial_recs = build_spatial(vol, affine, by_id, side_info, by_rid)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("provenance.json", "regions.json", "mappings.json", "spatial.json"):
        (OUT_DIR / name).unlink(missing_ok=True)  # meshes.json belongs to scripts/build/build_meshes.py
    write(OUT_DIR / "provenance.json", provenance)
    write(OUT_DIR / "regions.json", region_recs)
    write(OUT_DIR / "mappings.json", mapping_recs)
    write(OUT_DIR / "spatial.json", spatial_recs)

    print("validating ...", file=sys.stderr)
    # The transformation points at the Julich reference space, so validate together with the Julich records.
    result = subprocess.run([sys.executable, str(VALIDATE), str(OUT_DIR), str(ROOT / "data" / "anatomy" / "julich-brain-3.1")], capture_output=True, text=True)
    print(result.stdout, file=sys.stderr)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        for name in ("provenance.json", "regions.json", "mappings.json", "spatial.json"):
            (OUT_DIR / name).unlink(missing_ok=True)
        print("validation failed; output removed", file=sys.stderr)
        return 1
    n_leaves = sum(1 for r in region_recs if r.get("hemisphere") in ("left", "right", "midline"))
    total = len(provenance) + len(region_recs) + len(mapping_recs) + len(spatial_recs)
    print(f"wrote {total} records to {OUT_DIR.relative_to(ROOT)}: {len(region_recs)} regions ({n_leaves} hemisphere/midline leaves), {len(mapping_recs)} mappings, {len(spatial_recs)} spatial/volume records", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
