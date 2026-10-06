#!/usr/bin/env python3
"""Import HCP connectivity for Julich-Brain 3.1 into NeuroAtlas records.

Usage:
    python scripts/import/import_connectivity.py                      # everything, all 200 subjects
    python scripts/import/import_connectivity.py --subjects 20        # smoke test on the first 20 subjects
    python scripts/import/import_connectivity.py --min-mean 10 --min-subject-fraction 0.75   # looser structural cut
    python scripts/import/import_connectivity.py --fc-min-abs-r 0.2   # looser functional cut
    python scripts/import/import_connectivity.py --skip-fc            # structural only (counts + lengths)
    python scripts/import/import_connectivity.py --fc-reliability     # also print REST1-vs-REST2 agreement (~5 min more)

Requires:  pip install -r requirements-import.txt   (siibra, numpy)

Source dataset (read via siibra):
    "Parcellation-based structural and resting-state functional brain connectomes
     of a healthy cohort (v1.2)" — Domhof, Jung, Eickhoff, Popovych; EBRAINS,
     doi:10.25493/3PMM-FPW, CC BY 4.0. 200 HCP subjects, 414 mapped leaf regions
     of Julich-Brain 3.1.

Output (all under data/connectivity/hcp-julich-3.1/):
    provenance.json              dataset, dataset-version, source records for the connectivity dataset
    connections.json             one structural `connection` per retained region pair (streamline count)
    streamline-lengths.json      one `observation` per structural connection: group-mean streamline length (added 0.12.0)
    functional-connections.json  one `functional_connectivity` connection per retained pair (resting-state r) (added 0.12.0)

What the script does
1. Structural: reads the per-subject streamline-count and streamline-length
   matrices, averages counts across subjects and counts, for every pair, the
   fraction of subjects with at least one streamline. Keeps a pair if
   mean count >= --min-mean AND subject fraction >= --min-subject-fraction.
2. Lengths: for every retained structural pair, the mean streamline length
   over the subjects in which the pair has >= 1 streamline (a subject with no
   streamlines has length 0 in the source, which is "no measurement", not 0 mm).
   Written as an `observation` whose subjectId is the connection.
3. Functional: reads the per-subject resting-state correlation matrices for
   one paradigm (default: the four HCP runs concatenated), averages them in
   Fisher-z space and back-transforms to r. Keeps a pair if |r| >= --fc-min-abs-r
   and the pair has a value in >= --fc-min-valid-fraction of subjects.
4. Self-connections (matrix diagonal) are always dropped; each symmetric pair is
   written once, ordered by the matrix index.
5. Records whose id already exists in the output files keep their original
   provenance.createdAt, so a re-run does not rewrite every date.

Design notes
- direction is `undirected` for both kinds: tractography cannot resolve which
  way a bundle carries signals, and a correlation has no direction at all.
  The viewer must not render either as "projects to".
- One `strength` per connection, so lengths are observations about the
  structural edge rather than a second structural edge set (validator rule 7
  would also reject a second undirected edge for the same pair and dataset
  version). The observation schema's subjectId is "entity the observation is
  about"; a connection is such an entity.
- Functional edges share the dataset version with the structural edges; rule 7
  keys on connectionType as well, so the two sets do not collide. Only one
  paradigm is imported so there is exactly one functional edge per pair.
- assertionType is `observed`, status `active`: published group data, nothing
  hand-typed.
- Structural strength is the group-mean streamline count (scales with region
  volume and seeding; comparable within this dataset only). Functional strength
  is a signed Pearson r. Functional connectivity is correlation of slow BOLD
  fluctuations at rest, not a pathway: strongly correlated regions need not be
  directly wired.
- context.subjectFraction (structural) and context.subjectSignFraction
  (functional: share of subjects whose r has the same sign as the group mean)
  are stored per edge so stricter cuts can be applied without re-importing.
- Small deep nuclei get few or no structural edges (tractography) and almost no
  functional edges (low fMRI signal-to-noise in small parcels; three parcels
  have no fMRI values at all). The viewer says so rather than implying isolation.
- Region identity comes from the matrix row labels, matched by name to the
  brain-region records already imported by import_julich_brain.py. The
  script refuses to run if any label does not match exactly, or if the
  matrices of the three modalities are not in the same region order.
- License CC BY 4.0 (commercialUseAllowed: true) is the license of the derived
  connectomes on EBRAINS; the raw HCP images are under separate HCP terms and
  are not redistributed here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANATOMY_DIR = ROOT / "data" / "anatomy" / "julich-brain-3.1"
OUT_DIR = ROOT / "data" / "connectivity" / "hcp-julich-3.1"
VALIDATE = ROOT / "scripts" / "validate.py"

PARCELLATION_SPEC = "julich 3.1"
COUNT_FEATURE = "StreamlineCounts"
LENGTH_FEATURE = "StreamlineLengths"
FC_FEATURE = "FunctionalConnectivity"
TODAY = dt.date.today().isoformat()

DATASET_ID = "dataset:hcp-julich-brain-connectomes"
DATASET_VERSION_ID = "dataset-version:hcp-julich-brain-connectomes-1.2"
SOURCE_DATASET_ID = "source:domhof-2022-hcp-julich-connectomes-dataset"
SOURCE_PAPER_ID = "source:domhof-2021-parcellation-induced-variation"
ATLAS_DATASET_VERSION_ID = "dataset-version:julich-brain-3.1"  # must already exist in data/anatomy

# Full pipeline descriptions live once, on the dataset-version record; each edge carries the short form.
METHOD_FULL = "Diffusion MRI whole-brain probabilistic tractography (MRtrix3, multi-shell multi-tissue constrained spherical deconvolution) on HCP data; streamline count between Julich-Brain 3.1 parcels, averaged across subjects."
METHOD = "dwMRI probabilistic tractography, HCP group mean"
LENGTH_METHOD = "mean streamline length, dwMRI probabilistic tractography, HCP group mean over subjects with >= 1 streamline"
FC_METHOD = "resting-state fMRI, Pearson correlation, HCP group mean (Fisher z)"

PROV = {"createdAt": f"{TODAY}T00:00:00Z", "createdBy": "scripts/import/import_connectivity.py", "method": "siibra-python import, group mean"}
EDGE_PROV = {"createdAt": PROV["createdAt"], "createdBy": PROV["createdBy"]}

FILES = {"provenance": "provenance.json", "sc": "connections.json", "lengths": "streamline-lengths.json", "fc": "functional-connections.json"}


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


def transformations(n_subjects: int, args, fc_paradigm: str | None) -> list[str]:
    t = [
        METHOD_FULL,
        f"Per-subject streamline-count matrices for Julich-Brain 3.1 (414 mapped leaf regions) read via siibra-python for {n_subjects} HCP subjects.",
        "Group mean of streamline counts computed per region pair; matrix diagonal (self-connections) dropped.",
        f"Pairs retained only if mean count >= {args.min_mean} and present (>= 1 streamline) in >= {args.min_subject_fraction:.0%} of subjects.",
        "Each symmetric pair written once as an undirected connection; strength = group-mean streamline count.",
    ]
    if not args.skip_lengths:
        t.append("Streamline lengths: per-subject mean streamline length matrices read for the same subjects; for each retained structural "
                 "pair, the mean over subjects with >= 1 streamline (a length of 0 marks a missing measurement), in mm; one observation per "
                 "structural connection.")
    if fc_paradigm:
        t.append(f"Functional connectivity: per-subject resting-state Pearson correlation matrices, paradigm '{fc_paradigm}', read for the same "
                 "subjects; averaged in Fisher-z space (arctanh, mean over subjects with a value, tanh); diagonal dropped.")
        t.append(f"Functional pairs retained only if |r| >= {args.fc_min_abs_r} and a value exists in >= {args.fc_min_valid_fraction:.0%} of "
                 "subjects; strength = signed group-mean r; context.subjectSignFraction = share of subjects whose r has the group-mean sign.")
    else:
        t.append("Functional-connectivity matrices in the same dataset are not imported in this run.")
    return t


def build_provenance(feature, n_subjects: int, args, fc_paradigm: str | None) -> list[dict]:
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
                            "NeuroAtlas uses the Julich-Brain 3.1 streamline-count, streamline-length and one resting-state "
                            "functional-connectivity set."),
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
            "transformations": transformations(n_subjects, args, fc_paradigm),
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


def read_feature(feature, indices, labels_ref, what, on_matrix):
    """Read every subject's matrix of `feature`, check the region order, and hand the values to `on_matrix`."""
    labels = labels_ref[0]
    for i, subj in enumerate(indices, 1):
        m = feature.get_element(subj).data
        names = [getattr(r, "name", r) for r in m.index]
        if labels is None:
            labels = labels_ref[0] = names
        elif names != labels:
            sys.exit(f"{what}, subject {subj}: region order differs from the streamline-count matrices")
        on_matrix(m.values.astype(float))
        if i % 50 == 0 or i == len(indices):
            print(f"  {what}: [{i}/{len(indices)}] subjects read", file=sys.stderr)
    return labels


def single_feature(parcellation, feature_type, siibra):
    fs = siibra.features.get(parcellation, feature_type)
    if len(fs) != 1:
        sys.exit(f"expected exactly one {feature_type} feature for {parcellation.name}, got {len(fs)}: {[f.name for f in fs]}")
    return fs[0]


def fc_feature(parcellation, paradigm_hint: str, siibra):
    fs = siibra.features.get(parcellation, FC_FEATURE)
    match = [f for f in fs if paradigm_hint.lower() in str(getattr(f, "paradigm", "")).lower()]
    if len(match) != 1:
        sys.exit(f"--fc-paradigm '{paradigm_hint}' matches {len(match)} of the {FC_FEATURE} features; available: "
                 f"{[getattr(f, 'paradigm', f.name) for f in fs]}")
    return match[0], fs


def keep_created(records: list[dict], path: Path) -> None:
    """Records already present in `path` keep their original createdAt."""
    if not path.exists():
        return
    try:
        old = {r["id"]: r.get("provenance", {}).get("createdAt") for r in json.loads(path.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, KeyError, TypeError):
        return
    for r in records:
        was = old.get(r["id"])
        if was and "provenance" in r:
            r["provenance"] = {**r["provenance"], "createdAt": was}


def write_lines(path: Path, records: list[dict]) -> None:
    """One record per line: diff-friendly and compact."""
    lines = ",\n".join(json.dumps(r, separators=(",", ":"), ensure_ascii=False) for r in records)
    path.write_text("[\n" + lines + "\n]\n", encoding="utf-8")


def fc_reliability(fc_all, indices, labels_ref, np, keep_mask):
    """Agreement of the group-mean FC between the two HCP sessions (REST1 vs REST2), printed only."""
    sess = {}
    for f in fc_all:
        par = str(getattr(f, "paradigm", ""))
        m = re.search(r"REST(\d)", par)
        if not m:
            continue
        k = len(labels_ref[0])
        acc = {"z": np.zeros((k, k)), "n": np.zeros((k, k))}

        def add(v, acc=acc):
            z = np.arctanh(np.clip(v, -0.999999, 0.999999))
            ok = ~np.isnan(z)
            acc["z"][ok] += z[ok]
            acc["n"] += ok
        read_feature(f, indices, labels_ref, par, add)
        s = sess.setdefault(m.group(1), {"z": 0, "n": 0})
        s["z"] = s["z"] + acc["z"]
        s["n"] = s["n"] + acc["n"]
    if set(sess) != {"1", "2"}:
        print("reliability: REST1/REST2 runs not found; skipped", file=sys.stderr)
        return
    k = len(labels_ref[0])
    iu = np.triu_indices(k, 1)
    r1 = np.tanh(sess["1"]["z"] / np.maximum(sess["1"]["n"], 1))[iu]
    r2 = np.tanh(sess["2"]["z"] / np.maximum(sess["2"]["n"], 1))[iu]
    ok = (sess["1"]["n"][iu] > 0) & (sess["2"]["n"][iu] > 0)
    print(f"reliability: correlation of group-mean r between REST1 and REST2 over all pairs = {np.corrcoef(r1[ok], r2[ok])[0, 1]:.3f}", file=sys.stderr)
    kept = keep_mask[iu] & ok
    print(f"reliability: of {int(kept.sum())} retained edges, median |r1 - r2| = {np.median(np.abs(r1[kept] - r2[kept])):.3f}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=0, help="only use the first N subjects (smoke test); 0 = all")
    ap.add_argument("--min-mean", type=float, default=20.0, help="structural: minimum group-mean streamline count to keep a pair")
    ap.add_argument("--min-subject-fraction", type=float, default=0.9, help="structural: minimum fraction of subjects in which the pair has >= 1 streamline")
    ap.add_argument("--skip-lengths", action="store_true", help="do not import streamline lengths")
    ap.add_argument("--skip-fc", action="store_true", help="do not import functional connectivity")
    ap.add_argument("--fc-paradigm", default="concatenated", help="functional: text that picks exactly one paradigm (default: the four runs concatenated)")
    ap.add_argument("--fc-min-abs-r", type=float, default=0.3, help="functional: minimum |group-mean r| to keep a pair")
    ap.add_argument("--fc-min-valid-fraction", type=float, default=0.9, help="functional: minimum fraction of subjects with a value for the pair")
    ap.add_argument("--fc-reliability", action="store_true", help="also read the four single-run paradigms and print REST1-vs-REST2 agreement")
    args = ap.parse_args()

    import logging

    import numpy as np
    import siibra

    logging.getLogger("siibra").setLevel(logging.ERROR)
    by_name, key_of = load_region_index()

    print(f"siibra {siibra.__version__}; loading {PARCELLATION_SPEC} connectivity features ...", file=sys.stderr)
    parcellation = siibra.parcellations.get(PARCELLATION_SPEC)
    counts = single_feature(parcellation, COUNT_FEATURE, siibra)
    indices = list(counts.indices)
    if args.subjects:
        indices = indices[: args.subjects]
    n = len(indices)
    print(f"{counts.name}: using {n} of {len(counts.indices)} subjects", file=sys.stderr)

    labels_ref: list = [None]
    acc: dict = {}

    def k_shape():
        k = len(labels_ref[0])
        return (k, k)

    # structural: counts --------------------------------------------------------
    def add_count(v):
        if "total" not in acc:
            acc["total"], acc["present"] = np.zeros(k_shape()), np.zeros(k_shape())
        acc["total"] += v
        acc["present"] += (v > 0)
    read_feature(counts, indices, labels_ref, "streamline counts", add_count)
    labels = labels_ref[0]
    k = len(labels)
    mean, frac = acc["total"] / n, acc["present"] / n

    missing = [l for l in labels if l not in by_name]
    if missing:
        sys.exit(f"{len(missing)} matrix labels do not match any brain-region name, e.g. {missing[:5]}. Re-run import_julich_brain.py or fix the mapping.")
    region_ids = [by_name[l] for l in labels]
    key = lambda a, b: f"{key_of[region_ids[a]]}--{key_of[region_ids[b]]}"  # noqa: E731

    # structural: lengths -------------------------------------------------------
    mean_len = None
    if not args.skip_lengths:
        lengths = single_feature(parcellation, LENGTH_FEATURE, siibra)
        acc["len_sum"], acc["len_n"] = np.zeros((k, k)), np.zeros((k, k))

        def add_len(v):
            ok = v > 0  # 0 = no streamline in this subject, i.e. no measurement
            acc["len_sum"][ok] += v[ok]
            acc["len_n"] += ok
        read_feature(lengths, indices, labels_ref, "streamline lengths", add_len)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_len = acc["len_sum"] / acc["len_n"]

    # functional ----------------------------------------------------------------
    fc_r = fc_valid = fc_signfrac = None
    fc_paradigm = None
    fc_all = []
    if not args.skip_fc:
        fc, fc_all = fc_feature(parcellation, args.fc_paradigm, siibra)
        fc_paradigm = str(fc.paradigm)
        z_list = []

        def add_fc(v):
            z_list.append(np.arctanh(np.clip(v, -0.999999, 0.999999)).astype(np.float32))
        read_feature(fc, indices, labels_ref, fc_paradigm, add_fc)
        z = np.stack(z_list)  # subjects x k x k, float32 (~140 MB for 200 subjects)
        del z_list
        valid = ~np.isnan(z)
        fc_valid = valid.mean(axis=0)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # pairs with no value in any subject (3 parcels have no fMRI data) give NaN
            fc_r = np.tanh(np.nanmean(z, axis=0))
            same_sign = (np.sign(z) == np.sign(fc_r)[None]) & valid
            fc_signfrac = same_sign.sum(axis=0) / np.maximum(valid.sum(axis=0), 1)
        del z, valid, same_sign

    # records -------------------------------------------------------------------
    provenance = build_provenance(counts, n, args, fc_paradigm)
    strength_unit = f"streamlines (mean of {n} subjects)"
    sc: list[dict] = []
    obs: list[dict] = []
    for a in range(k):
        for b in range(a + 1, k):
            if mean[a, b] < args.min_mean or frac[a, b] < args.min_subject_fraction:
                continue
            cid = f"connection:hcp-sc-{key(a, b)}"
            sc.append({
                "id": cid,
                "sourceId": region_ids[a],
                "targetId": region_ids[b],
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
                "provenance": dict(EDGE_PROV),
            })
            if mean_len is not None and np.isfinite(mean_len[a, b]):
                obs.append({
                    "id": f"observation:hcp-sl-{key(a, b)}",
                    "observationType": "measurement",
                    "datasetVersionId": DATASET_VERSION_ID,
                    "sourceId": SOURCE_DATASET_ID,
                    "subjectId": cid,
                    "species": "Homo sapiens",
                    "context": {"preparation": "in_vivo", "subjectCount": int(acc["len_n"][a, b])},
                    "value": round(float(mean_len[a, b]), 1),
                    "unit": "mm",
                    "method": LENGTH_METHOD,
                    "provenance": dict(EDGE_PROV),
                })
    print(f"structural: {len(sc)} connections retained of {k * (k - 1) // 2} possible pairs "
          f"(mean >= {args.min_mean}, subject fraction >= {args.min_subject_fraction})", file=sys.stderr)
    if not sc:
        sys.exit("no structural connections retained; thresholds too strict")
    if mean_len is not None:
        print(f"lengths: {len(obs)} observations (median {np.median([o['value'] for o in obs]):.1f} mm)", file=sys.stderr)

    fcs: list[dict] = []
    if fc_r is not None:
        fc_unit = f"Pearson r (Fisher-z mean of {n} subjects)"
        keep_mask = np.zeros((k, k), dtype=bool)
        for a in range(k):
            for b in range(a + 1, k):
                r = fc_r[a, b]
                if not np.isfinite(r) or abs(r) < args.fc_min_abs_r or fc_valid[a, b] < args.fc_min_valid_fraction:
                    continue
                keep_mask[a, b] = True
                fcs.append({
                    "id": f"connection:hcp-fc-{key(a, b)}",
                    "sourceId": region_ids[a],
                    "targetId": region_ids[b],
                    "direction": "undirected",
                    "connectionType": "functional_connectivity",
                    "species": "Homo sapiens",
                    "context": {"preparation": "in_vivo", "condition": "healthy, eyes-open rest", "paradigm": fc_paradigm,
                                "subjectSignFraction": round(float(fc_signfrac[a, b]), 3)},
                    "assertionType": "observed",
                    "method": FC_METHOD,
                    "strength": round(float(r), 3),
                    "strengthUnit": fc_unit,
                    "datasetVersionId": DATASET_VERSION_ID,
                    "status": "active",
                    "provenance": dict(EDGE_PROV),
                })
        neg = sum(1 for c in fcs if c["strength"] < 0)
        iu = np.triu_indices(k, 1)
        print(f"functional: {len(fcs)} connections retained ({neg} negative) of {k * (k - 1) // 2} possible pairs "
              f"(|r| >= {args.fc_min_abs_r}, valid in >= {args.fc_min_valid_fraction:.0%} of subjects); "
              f"strongest negative group-mean r anywhere = {np.nanmin(fc_r[iu]):.3f}", file=sys.stderr)
        if args.fc_reliability:
            fc_reliability(fc_all, indices, labels_ref, np, keep_mask)

    # write + validate ----------------------------------------------------------
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {"sc": sc, "lengths": obs, "fc": fcs}
    for name, recs in {"provenance": provenance, **out}.items():
        keep_created(recs, OUT_DIR / FILES[name])
    backups = {name: (OUT_DIR / f).read_bytes() for name, f in FILES.items() if (OUT_DIR / f).exists()}
    (OUT_DIR / FILES["provenance"]).write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for name, recs in out.items():
        path = OUT_DIR / FILES[name]
        if recs:
            write_lines(path, recs)
        elif name == "lengths" and args.skip_lengths or name == "fc" and args.skip_fc:
            path.unlink(missing_ok=True)

    print("validating (connections reference data/anatomy, so the whole data/ tree is checked) ...", file=sys.stderr)
    result = subprocess.run([sys.executable, str(VALIDATE), str(ROOT / "data")], capture_output=True, text=True)
    print(result.stdout, file=sys.stderr)
    if result.returncode != 0:
        for name, f in FILES.items():
            path = OUT_DIR / f
            if name in backups:
                path.write_bytes(backups[name])
            else:
                path.unlink(missing_ok=True)
        print("validation failed; previous files restored", file=sys.stderr)
        return 1
    total = len(provenance) + len(sc) + len(obs) + len(fcs)
    print(f"wrote {total} records to {OUT_DIR.relative_to(ROOT)} "
          f"({len(sc)} structural, {len(obs)} lengths, {len(fcs)} functional)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
