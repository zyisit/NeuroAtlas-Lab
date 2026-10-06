"""Invariants of the HCP connectivity records (structural edges, streamline lengths, functional edges)
and of the viewer-bundle packing.

Data tests read the committed files and are skipped when they are absent
(a fresh clone before the import script has been run).
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HCP = ROOT / "data" / "connectivity" / "hcp-julich-3.1"
DV = "dataset-version:hcp-julich-brain-connectomes-1.2"


def load(path: Path):
    if not path.exists():
        pytest.skip(f"{path.relative_to(ROOT)} not present")
    return json.loads(path.read_text(encoding="utf-8"))


def bundle_module():
    spec = importlib.util.spec_from_file_location("build_viewer_bundle", ROOT / "scripts" / "build" / "build_viewer_bundle.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_streamline_length_describes_one_structural_connection():
    sc = {c["id"]: c for c in load(HCP / "connections.json")}
    lengths = load(HCP / "streamline-lengths.json")
    subjects = [o["subjectId"] for o in lengths]
    assert len(subjects) == len(set(subjects)), "more than one length per connection"
    assert set(subjects) <= set(sc), "a length points at something that is not a structural connection"
    assert len(lengths) == len(sc), "a structural connection has no length"
    for o in lengths:
        assert o["observationType"] == "measurement" and o["unit"] == "mm" and o["datasetVersionId"] == DV
        assert 0 < o["value"] < 300, o  # a human brain is ~170 mm long; tractography paths curve, but not that much
        assert sc[o["subjectId"]]["connectionType"] == "structural_connectivity"


def test_functional_edges_are_undirected_bounded_correlations_above_the_recorded_threshold():
    fc = load(HCP / "functional-connections.json")
    dv = next(r for r in load(HCP / "provenance.json") if r["id"] == DV)
    m = next((re.search(r"\|r\| >= ([0-9.]+)", t) for t in dv["transformations"] if "|r| >=" in t), None)
    assert m, "the dataset version must record the functional threshold"
    floor = float(m.group(1))
    assert fc
    for c in fc:
        assert c["connectionType"] == "functional_connectivity" and c["direction"] == "undirected"
        assert c["assertionType"] == "observed" and c["datasetVersionId"] == DV
        assert -1 <= c["strength"] <= 1 and abs(c["strength"]) >= floor - 1e-9, c
        assert 0 <= c["context"]["subjectSignFraction"] <= 1
        assert c["id"].startswith("connection:hcp-fc-")


def test_structural_and_functional_sets_cover_the_same_julich_regions_only():
    sc = load(HCP / "connections.json")
    fc = load(HCP / "functional-connections.json")
    ends = {c[k] for c in sc + fc for k in ("sourceId", "targetId")}
    assert all(e.startswith("brain-region:julich-") for e in ends)


def test_bundle_packing_is_lossless():
    mod = bundle_module()
    recs = [
        {"id": f"connection:x{i}", "sourceId": "brain-region:a", "targetId": f"brain-region:b{i}", "species": "Homo sapiens",
         "context": {"preparation": "in_vivo", "subjectFraction": i / 100}, "strength": float(i), "provenance": {"createdBy": "t"}}
        for i in range(mod.PACK_MIN)
    ]
    recs[3]["status"] = "active"  # a field only some records carry stays per record
    recs[4]["context"] = {"preparation": "in_vivo"}
    packed = mod.pack(recs)
    assert len(packed) == 1 and "_items" in packed[0]
    assert packed[0]["_shared"]["species"] == "Homo sapiens" and packed[0]["_shared"]["context"] == {"preparation": "in_vivo"}
    assert "status" not in packed[0]["_shared"]
    assert mod.unpack(packed) == recs
    small = recs[: mod.PACK_MIN - 1]
    assert mod.pack(small) == small


def test_bundle_packing_round_trips_the_real_connections():
    mod = bundle_module()
    fc = load(HCP / "functional-connections.json")
    assert mod.unpack(mod.pack(fc)) == fc
