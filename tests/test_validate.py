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
