#!/usr/bin/env python3
"""Import the Julich-Brain cytoarchitectonic atlas into NeuroAtlas records.

Usage:
    python scripts/import/import_julich_brain.py                # regions, hierarchy, mappings
    python scripts/import/import_julich_brain.py --spatial      # also centroids + volumes (slow, ~30 min first run)
    python scripts/import/import_julich_brain.py --limit 20     # smoke test on a few regions

Requires:  pip install siibra   (see docs/data-sources/README.md for license)

Output (all under data/anatomy/julich-brain-3.1/):
    provenance.json   dataset, dataset-version, source, reference-space, atlas
    regions.json      one brain-region per Julich region (root node excluded)
    mappings.json     one atlas-mapping per region, with Julich label, id, colour
    spatial.json      (--spatial only) centroid spatial-representations + volume observations

Every record is validated by scripts/validate.py before being written; the
script refuses to write anything if validation fails.

Design notes
- brain-region ids are prefixed `julich-` because these identities were
  derived from one atlas. A later curation pass will merge regions that
  appear in several atlases into atlas-neutral ids and keep these as mappings.
- Julich is a post-mortem, ten-brain probabilistic atlas of Homo sapiens.
  species is set accordingly on every record.
- The Julich-Brain license is CC BY-NC-SA 4.0. commercialUseAllowed is
  recorded as false. Do not build a commercial tier on these records.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "anatomy" / "julich-brain-3.1"
VALIDATE = ROOT / "scripts" / "validate.py"

PARCELLATION_SPEC = "julich 3.1"
SPACE_SPEC = "mni152"
TODAY = dt.date.today().isoformat()

DATASET_ID = "dataset:julich-brain"
DATASET_VERSION_ID = "dataset-version:julich-brain-3.1"
SOURCE_ID = "source:amunts-2020-julich-brain"
SPACE_ID = "reference-space:mni152-icbm-2009c-nonlin-asym"
ATLAS_ID = "atlas:julich-brain-3.1"

PROV = {"createdAt": f"{TODAY}T00:00:00Z", "createdBy": "scripts/import/import_julich_brain.py", "method": "siibra-python import"}


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def region_id(region) -> str:
    return f"brain-region:julich-{slug(region.key)}"


def hemisphere(region) -> str:
    n = region.name.lower()
    if n.endswith(" left"):
        return "left"
    if n.endswith(" right"):
        return "right"
    return "bilateral"


CLASS_MAP = {
    "cerebral cortex": "cortex",
    "cerebral nuclei": "subcortex",
    "diencephalon": "subcortex",
    "cerebellum": "cerebellum",
    "brainstem": "brainstem",
    "mesencephalon": "brainstem",
    "metencephalon": "brainstem",
    "myelencephalon": "brainstem",
    "white matter": "white_matter",
}


def anatomical_class(region) -> str:
    names = [a.name.lower() for a in region.ancestors] + [region.name.lower()]
    for key, cls in CLASS_MAP.items():
        if any(key in n for n in names):
            return cls
    # fall back to the top-level division (telencephalon, etc.)
    return slug(names[1]).replace("-", "_") if len(names) > 1 else "unspecified"


def rgb_hex(rgb) -> str | None:
    if not rgb or len(rgb) != 3:
        return None
    return "#{:02x}{:02x}{:02x}".format(*[int(v) for v in rgb])


def build_provenance(parcellation, space, dataset_version) -> list[dict]:
    citation = parcellation.publications[0]["citation"] if parcellation.publications else "Amunts K, Mohlberg H, Bludau S, Zilles K (2020). Julich-Brain: A 3D probabilistic atlas of the human brain's cytoarchitecture. Science 369(6506):988-992."
    pub_url = parcellation.publications[0]["url"] if parcellation.publications else "https://doi.org/10.1126/science.abb4588"
    access_url = (dataset_version.urls[0]["url"] if dataset_version and dataset_version.urls else "https://doi.org/10.25493/KNSN-XB4")
    license_name = getattr(dataset_version, "LICENSE", None) or parcellation.LICENSE

    return [
        {
            "id": DATASET_ID,
            "name": "Julich-Brain Atlas, cytoarchitectonic maps",
            "description": "Probabilistic cytoarchitectonic maps of the human brain derived from ten post-mortem brains, published via EBRAINS.",
            "publisher": "Forschungszentrum Jülich / EBRAINS",
            "homepage": "https://julich-brain-atlas.de/",
            "license": {
                "spdx": "CC-BY-NC-SA-4.0",
                "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                "attributionText": f"Julich-Brain Atlas, {license_name}. {citation}",
                "commercialUseAllowed": False,
                "notes": "Non-commercial and share-alike. Any commercial use requires a separate agreement with the licensor.",
            },
            "externalIdentifiers": [
                {"namespace": "RRID", "identifier": "SCR_023277"},
                {"namespace": "EBRAINS", "identifier": getattr(getattr(dataset_version, "is_version_of", None), "id", "") or "5a16d948-8d1c-400c-b797-8a7ad29944b2"},
            ],
            "provenance": PROV,
        },
        {
            "id": DATASET_VERSION_ID,
            "datasetId": DATASET_ID,
            "version": parcellation.version.__str__() if getattr(parcellation, "version", None) else "3.1",
            "retrievedAt": TODAY,
            "accessUrl": access_url,
            "transformations": [
                "Region hierarchy, names, keys, and colours read via siibra-python; no geometry altered.",
                "Centroids and volumes (if present) computed from siibra labelled masks in MNI152 ICBM 2009c asym space.",
            ],
            "notes": f"Imported with siibra-python {__import__('siibra').__version__}.",
            "provenance": PROV,
        },
        {
            "id": SOURCE_ID,
            "sourceType": "atlas",
            "title": "Julich-Brain: A 3D probabilistic atlas of the human brain's cytoarchitecture",
            "authors": ["Amunts K", "Mohlberg H", "Bludau S", "Zilles K"],
            "year": 2020,
            "citation": citation,
            "url": pub_url,
            "datasetVersionId": DATASET_VERSION_ID,
            "externalIdentifiers": [{"namespace": "DOI", "identifier": "10.1126/science.abb4588"}],
            "provenance": PROV,
        },
        {
            "id": SPACE_ID,
            "name": space.name,
            "coordinateSystem": "MNI152 ICBM 2009c Nonlinear Asymmetric, RAS, mm",
            "species": "Homo sapiens",
            "unit": "mm",
            "description": "Template space used for the Julich-Brain maximum probability maps.",
            "externalIdentifiers": [{"namespace": "EBRAINS", "identifier": space.id, "url": (space.urls[0] if space.urls else None)}],
            "provenance": PROV,
        },
        {
            "id": ATLAS_ID,
            "name": parcellation.name,
            "species": "Homo sapiens",
            "referenceSpaceId": SPACE_ID,
            "datasetVersionId": DATASET_VERSION_ID,
            "parcellationVersion": str(parcellation.version),
            "description": (parcellation.description or "")[:600],
            "externalIdentifiers": [{"namespace": "EBRAINS", "identifier": parcellation.id}],
            "provenance": PROV,
        },
    ]


def build_regions(parcellation, regions) -> tuple[list[dict], list[dict]]:
    region_recs, mapping_recs = [], []
    for r in regions:
        rid = region_id(r)
        parent_ids = []
        if r.parent is not None and r.parent is not parcellation:
            parent_ids = [region_id(r.parent)]
        rec = {
            "id": rid,
            "name": r.name,
            "species": "Homo sapiens",
            "hemisphere": hemisphere(r),
            "anatomicalClass": anatomical_class(r),
            "atlasMappingIds": [f"atlas-mapping:julich31-{slug(r.key)}"],
            "externalIdentifiers": [
                {"namespace": "siibra-id", "identifier": r.id},
                {"namespace": "siibra-key", "identifier": r.key},
            ],
            "status": "active",
            "provenance": PROV,
        }
        if parent_ids:
            rec["parentRegionIds"] = parent_ids
        if r.description:
            rec["description"] = r.description[:600]
        region_recs.append(rec)

        m = {
            "id": f"atlas-mapping:julich31-{slug(r.key)}",
            "brainRegionId": rid,
            "atlasId": ATLAS_ID,
            "atlasRegionId": r.key,
            "label": r.name,
            "mappingType": "exact",
            "datasetVersionId": DATASET_VERSION_ID,
            "provenance": PROV,
        }
        if r.parent is not None and r.parent is not parcellation:
            m["atlasParentRegionId"] = r.parent.key
        color = rgb_hex(getattr(r, "rgb", None))
        if color:
            m["displayColor"] = color
        mapping_recs.append(m)
    return region_recs, mapping_recs


def build_spatial(space, regions, region_recs_by_id) -> list[dict]:
    recs = []
    leaves = [r for r in regions if r.is_leaf]
    for i, r in enumerate(leaves, 1):
        try:
            props = r.spatial_props(space)
        except Exception as e:  # region not mapped in this space
            print(f"  [{i}/{len(leaves)}] skip {r.name}: {e.__class__.__name__}", file=sys.stderr)
            continue
        if not props:
            continue
        main = props[0]  # largest connected component
        rid = region_id(r)
        sid = f"spatial-representation:julich31-{slug(r.key)}-centroid"
        recs.append({
            "id": sid,
            "subjectId": rid,
            "referenceSpaceId": SPACE_ID,
            "datasetVersionId": DATASET_VERSION_ID,
            "geometry": {
                "type": "point",
                "coordinates": [round(float(v), 2) for v in main.centroid.coordinate],
                "format": "xyz-mm",
                "note": "Centroid of the largest connected component of the labelled (maximum-probability) mask.",
            },
            "provenance": PROV,
        })
        recs.append({
            "id": f"observation:julich31-{slug(r.key)}-volume",
            "observationType": "derived",
            "datasetVersionId": DATASET_VERSION_ID,
            "sourceId": SOURCE_ID,
            "subjectId": rid,
            "species": "Homo sapiens",
            "context": {"preparation": "post_mortem", "notes": "Maximum probability map volume in template space; not an individual-brain measurement."},
            "value": round(float(sum(c.volume for c in props)), 1),
            "unit": "mm3",
            "method": "voxel count of labelled mask x voxel volume (siibra spatial_props)",
            "spatialRepresentationId": sid,
            "provenance": PROV,
        })
        region_recs_by_id[rid].setdefault("spatialRepresentationIds", []).append(sid)
        print(f"  [{i}/{len(leaves)}] {r.name}", file=sys.stderr)
    return recs


def write(path: Path, records: list[dict]):
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spatial", action="store_true", help="compute centroids and volumes for leaf regions (slow)")
    ap.add_argument("--limit", type=int, default=0, help="only import the first N regions (smoke test)")
    args = ap.parse_args()

    import siibra

    print(f"siibra {siibra.__version__}; loading {PARCELLATION_SPEC} ...", file=sys.stderr)
    parcellation = siibra.parcellations.get(PARCELLATION_SPEC)
    space = siibra.spaces.get(SPACE_SPEC)
    dataset_version = next((d for d in parcellation.datasets if type(d).__name__ == "EbrainsV3DatasetVersion"), None)

    regions = [r for r in parcellation if r is not parcellation]
    if args.limit:
        regions = regions[: args.limit]
        # keep parents inside the limited set consistent
        keep = {r.key for r in regions}
        regions = [r for r in regions if r.parent is parcellation or r.parent.key in keep]
    print(f"{len(regions)} regions", file=sys.stderr)

    provenance = build_provenance(parcellation, space, dataset_version)
    region_recs, mapping_recs = build_regions(parcellation, regions)
    by_id = {r["id"]: r for r in region_recs}

    spatial_recs = []
    if args.spatial:
        print("computing spatial properties (this fetches one mask per leaf region) ...", file=sys.stderr)
        spatial_recs = build_spatial(space, regions, by_id)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()
    write(OUT_DIR / "provenance.json", provenance)
    write(OUT_DIR / "regions.json", region_recs)
    write(OUT_DIR / "mappings.json", mapping_recs)
    if spatial_recs:
        write(OUT_DIR / "spatial.json", spatial_recs)

    print("validating ...", file=sys.stderr)
    result = subprocess.run([sys.executable, str(VALIDATE), str(OUT_DIR)], capture_output=True, text=True)
    print(result.stdout, file=sys.stderr)
    if result.returncode != 0:
        for f in OUT_DIR.glob("*.json"):
            f.unlink()
        print("validation failed; output removed", file=sys.stderr)
        return 1
    total = len(provenance) + len(region_recs) + len(mapping_recs) + len(spatial_recs)
    print(f"wrote {total} records to {OUT_DIR.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
