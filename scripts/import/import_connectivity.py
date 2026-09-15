#!/usr/bin/env python3
"""Import HCP structural connectivity for Julich-Brain 3.1 into NeuroAtlas records.

Usage:
    python scripts/import/import_connectivity.py                      # all 200 subjects, default thresholds
    python scripts/import/import_connectivity.py --subjects 20        # smoke test on the first 20 subjects
    python scripts/import/import_connectivity.py --min-mean 10 --min-subject-fraction 0.75   # looser

Requires:  pip install -r requirements-import.txt   (siibra, numpy)

Source dataset (read via siibra):
    "Parcellation-based structural and resting-state functional brain connectomes
     of a healthy cohort (v1.2)" — Domhof, Jung, Eickhoff, Popovych; EBRAINS,
     doi:10.25493/3PMM-FPW, CC BY 4.0. 200 HCP subjects, streamline counts
     between the 414 mapped leaf regions of Julich-Brain 3.1.

Output (all under data/connectivity/hcp-julich-3.1/):
    provenance.json   dataset, dataset-version, source records for the connectivity dataset
    connections.json  one `connection` record per retained region pair

What the script does
1. Fetches the per-subject streamline-count matrix for every subject (~0.3 s each
   once cached).
2. Averages across subjects and, for every region pair, counts the fraction of
   subjects in which the pair has at least one streamline.
3. Keeps a pair if mean count >= --min-mean AND subject fraction >= --min-subject-fraction.
   Self-connections (matrix diagonal) are always dropped.
4. Writes one undirected `connection` record per retained pair. The matrix is
   symmetric, so each pair is written once, ordered by the matrix index.

Design notes
- direction is `undirected`: diffusion tractography cannot resolve the direction
  of a fibre bundle. The viewer must not render these as "projects to".
- assertionType is `observed` (empirical dwMRI), status `active`: this is a
  published group dataset, not a curated claim. Nothing here is hand-typed.
- strength is the group-mean streamline count. It scales with region volume
  and with the tractography seeding scheme, so it is comparable within this
  dataset only. strengthUnit records that.
- context.subjectFraction (fraction of subjects with >= 1 streamline) is the
  consistency measure; it is stored per edge so a stricter threshold can be
  applied downstream without re-importing.
- 50 of the 414 regions (small thalamic, amygdalar, cerebellar and midbrain
  nuclei) receive fewer than 10 streamlines to any region in this dataset and
  end up with no connections. That is a limitation of dwMRI tractography at
  this scale, not evidence of isolation; the viewer says so.
- Region identity comes from the matrix row labels, matched by name to the
  brain-region records already imported by import_julich_brain.py. The
  script refuses to run if any label does not match exactly.
- The dataset license is CC BY 4.0 (commercialUseAllowed: true). Note that
  this is the license of the *derived connectomes* on EBRAINS; the raw HCP
  images they were computed from are under separate HCP terms and are not
  redistributed here.
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
ANATOMY_DIR = ROOT / "data" / "anatomy" / "julich-brain-3.1"
OUT_DIR = ROOT / "data" / "connectivity" / "hcp-julich-3.1"
VALIDATE = ROOT / "scripts" / "validate.py"

PARCELLATION_SPEC = "julich 3.1"
FEATURE_TYPE = "StreamlineCounts"
TODAY = dt.date.today().isoformat()

DATASET_ID = "dataset:hcp-julich-brain-connectomes"
DATASET_VERSION_ID = "dataset-version:hcp-julich-brain-connectomes-1.2"
SOURCE_DATASET_ID = "source:domhof-2022-hcp-julich-connectomes-dataset"
SOURCE_PAPER_ID = "source:domhof-2021-parcellation-induced-variation"
ATLAS_DATASET_VERSION_ID = "dataset-version:julich-brain-3.1"  # must already exist in data/anatomy

# Full pipeline description lives once, on the dataset-version record; each edge carries the short form.
METHOD_FULL = "Diffusion MRI whole-brain probabilistic tractography (MRtrix3, multi-shell multi-tissue constrained spherical deconvolution) on HCP data; streamline count between Julich-Brain 3.1 parcels, averaged across subjects."
METHOD = "dwMRI probabilistic tractography, HCP group mean"

PROV = {"createdAt": f"{TODAY}T00:00:00Z", "createdBy": "scripts/import/import_connectivity.py", "method": "siibra-python import, group mean"}


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def load_region_index() -> tuple[dict[str, str], dict[str, str]]:
    """name -> brain-region id, and brain-region id -> julich key slug."""
    regions_file = ANATOMY_DIR / "regions.json"
    if not regions_file.exists():
        sys.exit(f"{regions_file} not found. Run scripts/import/import_julich_brain.py first.")
    regions = json.loads(regions_file.read_text(encoding="utf-8"))
    by_name, key_of = {}, {}
    for r in regions:
        by_name[r["name"]] = r["id"]
        key = next((e["identifier"] for e in r.get("externalIdentifiers", []) if e["namespace"] == "siibra-key"), None)
        key_of[r["id"]] = slug(key) if key else r["id"].split(":", 1)[1].removeprefix("julich-")
    return by_name, key_of


def build_provenance(feature, n_subjects: int, args) -> list[dict]:
    dsv = next((d for d in feature.datasets if type(d).__name__ == "EbrainsV3DatasetVersion"), None)
    ds = next((d for d in feature.datasets if type(d).__name__ == "EbrainsV3Dataset"), None)
    license_name = (dsv and getattr(dsv, "LICENSE", None)) or "Creative Commons Attribution 4.0 International"
    access_url = (dsv.urls[0]["url"] if dsv and dsv.urls else "https://doi.org/10.25493/3PMM-FPW")
    citation_dataset = ("Domhof JWM, Jung K, Eickhoff SB, Popovych OV (2022). Parcellation-based structural and resting-state "
                        "functional brain connectomes of a healthy cohort (v1.2) [Data set]. EBRAINS. https://doi.org/10.25493/3PMM-FPW")
    citation_paper = ("Domhof JWM, Jung K, Eickhoff SB, Popovych OV (2021). Parcellation-induced variation of empirical and "
                      "simulated brain connectomes at group and subject levels. Network Neuroscience 5(3):798-830. "
                      "https://doi.org/10.1162/netn_a_00202")
    return [
        {
            "id": DATASET_ID,
            "name": "Parcellation-based structural and resting-state functional brain connectomes of a healthy cohort",
            "description": ("Individual structural (dwMRI tractography) and functional (resting-state fMRI) connectomes for 200 "
                            "Human Connectome Project subjects, computed for 20 parcellations including Julich-Brain. "
                            "NeuroAtlas uses the Julich-Brain 3.1 streamline-count matrices only."),
            "publisher": "Forschungszentrum Jülich (INM-7) / EBRAINS",
            "homepage": "https://doi.org/10.25493/3PMM-FPW",
            "license": {
                "spdx": "CC-BY-4.0",
                "url": "https://creativecommons.org/licenses/by/4.0/",
                "attributionText": f"{citation_dataset} Licensed {license_name}.",
                "commercialUseAllowed": True,
                "notes": ("License applies to the derived connectome matrices published on EBRAINS. The underlying HCP images "
                          "are governed by HCP Open Access terms and are not redistributed by this project."),
            },
            "externalIdentifiers": [
                {"namespace": "EBRAINS", "identifier": getattr(ds, "id", None) or "0f1ccc4a-9a11-4697-b43f-9c9c8ac543e6"},
                {"namespace": "DOI", "identifier": "10.25493/3PMM-FPW", "url": "https://doi.org/10.25493/3PMM-FPW"},
            ],
            "provenance": PROV,
        },
        {
            "id": DATASET_VERSION_ID,
            "datasetId": DATASET_ID,
            "version": "1.2",
            "retrievedAt": TODAY,
            "accessUrl": access_url,
            "transformations": [
                METHOD_FULL,
                f"Per-subject streamline-count matrices for Julich-Brain 3.1 (414 mapped leaf regions) read via siibra-python for {n_subjects} HCP subjects.",
                "Group mean of streamline counts computed per region pair; matrix diagonal (self-connections) dropped.",
                f"Pairs retained only if mean count >= {args.min_mean} and present (>= 1 streamline) in >= {args.min_subject_fraction:.0%} of subjects.",
                "Each symmetric pair written once as an undirected connection; strength = group-mean streamline count.",
                "Streamline lengths and functional-connectivity matrices in the same dataset are not imported.",
            ],
            "notes": f"Imported with siibra-python {__import__('siibra').__version__}. EBRAINS dataset version id {getattr(dsv, 'id', '2a52e7c3-9aad-49db-bb71-4ed0208ae7cb')}.",
            "provenance": PROV,
        },
        {
            "id": SOURCE_DATASET_ID,
            "sourceType": "experimental_dataset",
            "title": "Parcellation-based structural and resting-state functional brain connectomes of a healthy cohort (v1.2)",
            "authors": ["Domhof JWM", "Jung K", "Eickhoff SB", "Popovych OV"],
            "year": 2022,
            "citation": citation_dataset,
            "url": "https://doi.org/10.25493/3PMM-FPW",
            "datasetVersionId": DATASET_VERSION_ID,
            "externalIdentifiers": [{"namespace": "DOI", "identifier": "10.25493/3PMM-FPW"}],
            "provenance": PROV,
        },
        {
            "id": SOURCE_PAPER_ID,
            "sourceType": "primary_research",
            "title": "Parcellation-induced variation of empirical and simulated brain connectomes at group and subject levels",
            "authors": ["Domhof JWM", "Jung K", "Eickhoff SB", "Popovych OV"],
            "year": 2021,
            "citation": citation_paper,
            "url": "https://doi.org/10.1162/netn_a_00202",
            "externalIdentifiers": [{"namespace": "DOI", "identifier": "10.1162/netn_a_00202"}, {"namespace": "PMID", "identifier": "34746628"}],
            "provenance": PROV,
        },
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=0, help="only use the first N subjects (smoke test); 0 = all")
    ap.add_argument("--min-mean", type=float, default=20.0, help="minimum group-mean streamline count to keep a pair")
    ap.add_argument("--min-subject-fraction", type=float, default=0.9, help="minimum fraction of subjects in which the pair has >= 1 streamline")
    args = ap.parse_args()

    import logging

    import numpy as np
    import siibra

    logging.getLogger("siibra").setLevel(logging.ERROR)
    by_name, key_of = load_region_index()

    print(f"siibra {siibra.__version__}; loading {PARCELLATION_SPEC} {FEATURE_TYPE} ...", file=sys.stderr)
    parcellation = siibra.parcellations.get(PARCELLATION_SPEC)
    features = siibra.features.get(parcellation, FEATURE_TYPE)
    if len(features) != 1:
        sys.exit(f"expected exactly one {FEATURE_TYPE} feature for {parcellation.name}, got {len(features)}: {[f.name for f in features]}")
    feature = features[0]
    indices = list(feature.indices)
    if args.subjects:
        indices = indices[: args.subjects]
    print(f"{feature.name}: using {len(indices)} of {len(feature.indices)} subjects", file=sys.stderr)

    # matrices ---------------------------------------------------------------
    labels: list[str] | None = None
    total = None
    present = None
    for i, subj in enumerate(indices, 1):
        elem = feature.get_element(subj)
        m = elem.data
        names = [getattr(r, "name", r) for r in m.index]
        if labels is None:
            labels = names
            total = np.zeros((len(labels), len(labels)))
            present = np.zeros_like(total)
        elif names != labels:
            sys.exit(f"subject {subj}: region order differs from subject {indices[0]}")
        v = m.values.astype(float)
        total += v
        present += (v > 0)
        if i % 25 == 0 or i == len(indices):
            print(f"  [{i}/{len(indices)}] subjects read", file=sys.stderr)
    assert labels is not None and total is not None and present is not None

    n = len(indices)
    mean = total / n
    frac = present / n

    # region identity --------------------------------------------------------
    missing = [l for l in labels if l not in by_name]
    if missing:
        sys.exit(f"{len(missing)} matrix labels do not match any brain-region name, e.g. {missing[:5]}. Re-run import_julich_brain.py or fix the mapping.")
    region_ids = [by_name[l] for l in labels]

    # connections ------------------------------------------------------------
    provenance = build_provenance(feature, n, args)
    strength_unit = f"streamlines (mean of {n} subjects)"
    edge_prov = {"createdAt": PROV["createdAt"], "createdBy": PROV["createdBy"]}
    connections: list[dict] = []
    k = len(labels)
    for a in range(k):
        for b in range(a + 1, k):
            if mean[a, b] < args.min_mean or frac[a, b] < args.min_subject_fraction:
                continue
            ra, rb = region_ids[a], region_ids[b]
            connections.append({
                "id": f"connection:hcp-sc-{key_of[ra]}--{key_of[rb]}",
                "sourceId": ra,
                "targetId": rb,
                "direction": "undirected",
                "connectionType": "structural_connectivity",
                "species": "Homo sapiens",
                "context": {"preparation": "in_vivo", "subjectFraction": round(float(frac[a, b]), 3)},
                "assertionType": "observed",
                "method": METHOD,
                "strength": round(float(mean[a, b]), 1),
                "strengthUnit": strength_unit,
                "datasetVersionId": DATASET_VERSION_ID,
                "status": "active",
                "provenance": edge_prov,
            })
    print(f"{len(connections)} connections retained of {k * (k - 1) // 2} possible pairs "
          f"(mean >= {args.min_mean}, subject fraction >= {args.min_subject_fraction})", file=sys.stderr)
    if not connections:
        sys.exit("no connections retained; thresholds too strict")

    # write + validate -------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {"provenance.json": provenance, "connections.json": connections}
    # provenance.json is small and pretty-printed; connections.json is one record per line (diff-friendly, ~5 MB).
    (OUT_DIR / "provenance.json").write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ",\n".join(json.dumps(c, separators=(",", ":"), ensure_ascii=False) for c in connections)
    (OUT_DIR / "connections.json").write_text("[\n" + lines + "\n]\n", encoding="utf-8")

    print("validating (connections reference data/anatomy, so the whole data/ tree is checked) ...", file=sys.stderr)
    result = subprocess.run([sys.executable, str(VALIDATE), str(ROOT / "data")], capture_output=True, text=True)
    print(result.stdout, file=sys.stderr)
    if result.returncode != 0:
        for name in files:
            (OUT_DIR / name).unlink(missing_ok=True)
        print("validation failed; output removed", file=sys.stderr)
        return 1
    print(f"wrote {len(provenance) + len(connections)} records to {OUT_DIR.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
