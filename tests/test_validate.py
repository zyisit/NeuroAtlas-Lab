"""Smoke tests for the record validator."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATE = ROOT / "scripts" / "validate.py"


def run(*paths):
    return subprocess.run([sys.executable, str(VALIDATE), *map(str, paths)], capture_output=True, text=True)


def test_examples_are_valid():
    r = run(ROOT / "examples")
    assert r.returncode == 0, r.stdout


def test_schemas_are_generated_from_script():
    before = {p.name: p.read_text() for p in (ROOT / "schemas").glob("*.json")}
    subprocess.run([sys.executable, str(ROOT / "scripts" / "gen_schemas.py")], check=True, capture_output=True)
    after = {p.name: p.read_text() for p in (ROOT / "schemas").glob("*.json")}
    assert before == after, "schemas/ is out of sync with scripts/gen_schemas.py"


def test_causes_is_rejected(tmp_path):
    bundle = [
        {"id": "brain-region:a", "name": "A", "species": "Homo sapiens", "status": "draft"},
        {"id": "brain-function:f", "name": "F", "status": "draft"},
        {"id": "relationship:r", "subjectId": "brain-region:a", "predicate": "causes", "objectId": "brain-function:f",
         "assertionType": "observed", "status": "draft"},
    ]
    f = tmp_path / "b.json"
    f.write_text(json.dumps(bundle))
    r = run(f)
    assert r.returncode == 1 and "causes" in r.stdout


def test_dangling_reference_is_rejected(tmp_path):
    bundle = [{"id": "atlas-mapping:m", "brainRegionId": "brain-region:missing", "atlasId": "atlas:missing", "mappingType": "exact"}]
    f = tmp_path / "b.json"
    f.write_text(json.dumps(bundle))
    r = run(f)
    assert r.returncode == 1 and "does not resolve" in r.stdout


def test_model_derived_cannot_back_established_claim(tmp_path):
    bundle = [
        {"id": "brain-region:a", "name": "A", "species": "Homo sapiens", "status": "draft"},
        {"id": "brain-function:f", "name": "F", "status": "draft"},
        {"id": "claim:c", "statement": "A does F.", "evidenceStatus": "established", "status": "active"},
        {"id": "relationship:r", "subjectId": "brain-region:a", "predicate": "contributes_to", "objectId": "brain-function:f",
         "assertionType": "model_derived", "claimIds": ["claim:c"], "status": "draft"},
    ]
    f = tmp_path / "b.json"
    f.write_text(json.dumps(bundle))
    r = run(f)
    assert r.returncode == 1 and "model_derived" in r.stdout


CONN_BASE = [
    {"id": "brain-region:a", "name": "A", "species": "Homo sapiens", "status": "draft"},
    {"id": "brain-region:b", "name": "B", "species": "Homo sapiens", "status": "draft"},
]


def conn(cid, a, b, direction="undirected"):
    return {"id": cid, "sourceId": a, "targetId": b, "direction": direction, "connectionType": "structural_connectivity",
            "species": "Homo sapiens", "assertionType": "observed", "status": "draft"}


def test_self_loop_connection_is_rejected(tmp_path):
    f = tmp_path / "b.json"
    f.write_text(json.dumps(CONN_BASE + [conn("connection:aa", "brain-region:a", "brain-region:a")]))
    r = run(f)
    assert r.returncode == 1 and "self-loop" in r.stdout


def test_duplicate_undirected_pair_is_rejected(tmp_path):
    f = tmp_path / "b.json"
    f.write_text(json.dumps(CONN_BASE + [conn("connection:ab", "brain-region:a", "brain-region:b"), conn("connection:ba", "brain-region:b", "brain-region:a")]))
    r = run(f)
    assert r.returncode == 1 and "duplicate undirected connection" in r.stdout


def test_directed_pair_both_ways_is_allowed(tmp_path):
    f = tmp_path / "b.json"
    f.write_text(json.dumps(CONN_BASE + [conn("connection:ab", "brain-region:a", "brain-region:b", "directed"), conn("connection:ba", "brain-region:b", "brain-region:a", "directed")]))
    r = run(f)
    assert r.returncode == 0, r.stdout
