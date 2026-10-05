"""Invariants of the second atlas (Allen HRA 3D 2020) and the cross-atlas overlap records.

These tests read the committed data; they are skipped when the files are absent
(a fresh clone before the import scripts have been run).
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ALLEN = ROOT / "data" / "anatomy" / "allen-hra-3d-2020"
JULICH = ROOT / "data" / "anatomy" / "julich-brain-3.1"
OVERLAPS = ROOT / "data" / "anatomy" / "cross-atlas" / "julich31-allen2020-overlaps.json"


def load(path: Path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(ROOT)} not present")
    return json.loads(path.read_text(encoding="utf-8"))


def test_allen_regions_map_to_the_allen_atlas_only():
    mappings = load(ALLEN / "mappings.json")
    assert mappings and all(m["atlasId"] == "atlas:allen-hra-3d-2020" for m in mappings)
    regions = load(ALLEN / "regions.json")
    ids = {r["id"] for r in regions}
    assert all(r["id"].startswith("brain-region:allen-") for r in regions)
    assert {m["brainRegionId"] for m in mappings} == ids


def test_allen_hemisphere_leaves_are_split_from_a_bilateral_parent():
    regions = {r["id"]: r for r in load(ALLEN / "regions.json")}
    leaves = [r for r in regions.values() if r.get("hemisphere") in ("left", "right")]
    assert leaves
    for r in leaves:
        parent = regions[r["parentRegionIds"][0]]
        assert parent["hemisphere"] == "bilateral"
        assert r["name"].endswith(" " + r["hemisphere"])
    midline = [r for r in regions.values() if r.get("hemisphere") == "midline"]
    assert midline and all(not [c for c in regions.values() if c.get("parentRegionIds") == [m["id"]] and c.get("hemisphere") in ("left", "right")] for m in midline)


def test_allen_license_allows_commercial_use_and_julich_does_not():
    allen = {r["id"]: r for r in load(ALLEN / "provenance.json")}
    julich = {r["id"]: r for r in load(JULICH / "provenance.json")}
    assert allen["dataset:allen-human-reference-atlas-3d"]["license"]["spdx"] == "CC-BY-4.0"
    assert allen["dataset:allen-human-reference-atlas-3d"]["license"]["commercialUseAllowed"] is True
    assert julich["dataset:julich-brain"]["license"]["commercialUseAllowed"] is False


def test_allen_space_differs_from_julich_and_is_linked_by_an_approximate_transformation():
    prov = {r["id"]: r for r in load(ALLEN / "provenance.json")}
    tx = prov["spatial-transformation:mni152-2009b-sym-to-2009c-asym-approx-identity"]
    assert tx["sourceReferenceSpaceId"] == "reference-space:mni152-icbm-2009b-nonlin-sym"
    assert tx["targetReferenceSpaceId"] == "reference-space:mni152-icbm-2009c-nonlin-asym"
    assert "approximate" in tx["method"]


def test_overlaps_join_the_two_atlases_and_are_inferred():
    rels = load(OVERLAPS)
    allen_ids = {r["id"] for r in load(ALLEN / "regions.json")}
    julich_ids = {r["id"] for r in load(JULICH / "regions.json")}
    assert rels
    seen = set()
    for r in rels:
        assert r["predicate"] == "overlaps"
        assert r["assertionType"] == "inferred", "voxel overlap on unregistered templates is inference, not observation"
        assert r["subjectId"] in julich_ids and r["objectId"] in allen_ids
        c = r["context"]
        assert 0 <= c["overlapFractionOfSubject"] <= 1 and 0 <= c["overlapFractionOfObject"] <= 1  # a tiny share of a huge region rounds to 0.0
        assert max(c["overlapFractionOfSubject"], c["overlapFractionOfObject"]) >= 0.1
        assert c["overlapVolumeMm3"] > 0
        pair = (r["subjectId"], r["objectId"])
        assert pair not in seen, f"duplicate overlap pair {pair}"
        seen.add(pair)


def test_overlap_fractions_of_a_julich_region_do_not_exceed_one_in_total():
    rels = load(OVERLAPS)
    totals = {}
    for r in rels:
        totals[r["subjectId"]] = totals.get(r["subjectId"], 0.0) + r["context"]["overlapFractionOfSubject"]
    assert max(totals.values()) <= 1.001
