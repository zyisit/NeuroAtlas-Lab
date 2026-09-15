#!/usr/bin/env python3
"""NeuroAtlas Lab record validator.

Usage:
    python scripts/validate.py                # validates examples/ and data/
    python scripts/validate.py path [path...] # validates the given files/dirs

Every *.json file under the given paths is loaded. A file may contain one
record or an array of records. Each record's type is taken from the prefix of
its `id` (e.g. "brain-region:hippocampus" -> schemas/brain-region.json).

Checks performed:
  1. JSON Schema (Draft 2020-12) shape validation.
  2. Referential integrity: every *Id / *Ids field must resolve to a record in
     the validated bundle, and to a record of the expected type.
  3. Relationship predicates must appear in docs/ontology/predicate-vocabulary.md.
  4. The predicate `causes` is rejected outright (governance rule).
  5. Dataset versions must not be duplicated (same datasetId + version).
  6. Records whose assertionType is model_derived or hypothetical must not
     carry evidenceStatus established/well_supported (via linked claims).
  7. Connections must not be self-loops, and undirected/bidirectional
     connections must not repeat the same unordered pair within one dataset
     version (each symmetric edge is stored once).

Exit code 0 on success, 1 on any failure.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schemas"
VOCAB_FILE = ROOT / "docs" / "ontology" / "predicate-vocabulary.md"
DEFAULT_PATHS = [ROOT / "examples", ROOT / "data"]

# field name -> expected record type prefix (None = any type)
REF_FIELDS = {
    "datasetId": "dataset",
    "datasetVersionId": "dataset-version",
    "sourceReferenceSpaceId": "reference-space",
    "targetReferenceSpaceId": "reference-space",
    "referenceSpaceId": "reference-space",
    "brainRegionId": "brain-region",
    "atlasId": "atlas",
    "atlasMappingIds": "atlas-mapping",
    "spatialRepresentationIds": "spatial-representation",
    "spatialRepresentationId": "spatial-representation",
    "transformationIds": "spatial-transformation",
    "parentRegionIds": "brain-region",
    "claimId": "claim",
    "claimIds": "claim",
    "supersededByClaimId": "claim",
    "sourceId": None,  # Source on evidence/observation; entity on connection
    "evidenceRecordIds": "evidence-record",
    "observationIds": "observation",
    "subjectId": None,
    "subjectIds": None,
    "objectId": None,
    "targetId": None,
    "neurotransmitterIds": None,
}
STRONG_EVIDENCE = {"established", "well_supported"}
WEAK_ASSERTIONS = {"model_derived", "hypothetical"}


def load_vocabulary() -> set[str]:
    text = VOCAB_FILE.read_text()
    terms: set[str] = set()
    section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        # A predicate line is ONLY a comma-separated list of snake_case tokens.
        if section != "excluded" and re.fullmatch(r"[a-z_]+(\s*,\s*[a-z_]+)*", line.strip()):
            terms.update(t.strip() for t in line.split(","))
    terms.discard("causes")
    return terms


def load_schemas():
    registry = Registry()
    validators = {}
    for path in SCHEMA_DIR.glob("*.json"):
        doc = json.loads(path.read_text())
        if "$id" not in doc:
            continue
        registry = registry.with_resource(doc["$id"], Resource.from_contents(doc, default_specification=DRAFT202012))
    for path in SCHEMA_DIR.glob("*.json"):
        doc = json.loads(path.read_text())
        if path.name in ("common.json", "index.json"):
            continue
        validators[path.stem] = Draft202012Validator(doc, registry=registry, format_checker=FormatChecker())
    return validators


def iter_records(paths):
    for p in paths:
        p = Path(p)
        if not p.exists():
            if p in DEFAULT_PATHS:
                continue  # data/ is empty until Sprint 1; that's fine
            yield p, None, "path does not exist"
            continue
        files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
        for f in files:
            try:
                doc = json.loads(f.read_text())
            except json.JSONDecodeError as e:
                yield f, None, f"invalid JSON: {e}"
                continue
            records = doc if isinstance(doc, list) else [doc]
            for r in records:
                yield f, r, None


def main(argv):
    paths = [Path(a) for a in argv] or DEFAULT_PATHS
    validators = load_schemas()
    vocab = load_vocabulary()
    errors: list[str] = []
    records: dict[str, dict] = {}
    origin: dict[str, Path] = {}

    # pass 1: shape + collect
    for f, rec, err in iter_records(paths):
        if err:
            errors.append(f"{f}: {err}")
            continue
        rid = rec.get("id") if isinstance(rec, dict) else None
        if not rid or ":" not in str(rid):
            errors.append(f"{f}: record without a typed id: {json.dumps(rec)[:80]}")
            continue
        rtype = rid.split(":", 1)[0]
        v = validators.get(rtype)
        if v is None:
            errors.append(f"{f}: {rid}: unknown record type '{rtype}'")
            continue
        for e in sorted(v.iter_errors(rec), key=lambda e: e.path):
            loc = "/".join(str(x) for x in e.path) or "<root>"
            errors.append(f"{f}: {rid}: {loc}: {e.message}")
        if rid in records:
            errors.append(f"{f}: duplicate id {rid} (also in {origin[rid]})")
        records[rid] = rec
        origin[rid] = f

    # pass 2: cross-record checks
    dv_keys = defaultdict(list)
    pair_keys = defaultdict(list)
    for rid, rec in records.items():
        rtype = rid.split(":", 1)[0]
        for field, expected in REF_FIELDS.items():
            if field not in rec:
                continue
            vals = rec[field] if isinstance(rec[field], list) else [rec[field]]
            for target in vals:
                if target not in records:
                    errors.append(f"{origin[rid]}: {rid}: {field} -> {target} does not resolve")
                    continue
                exp = expected
                if field == "sourceId" and rtype in ("evidence-record", "observation"):
                    exp = "source"
                if exp and not target.startswith(exp + ":"):
                    errors.append(f"{origin[rid]}: {rid}: {field} -> {target} should be a {exp} record")
        if rtype == "relationship":
            pred = rec.get("predicate")
            if pred == "causes":
                errors.append(f"{origin[rid]}: {rid}: predicate 'causes' is excluded pending governance review")
            elif pred not in vocab:
                errors.append(f"{origin[rid]}: {rid}: predicate '{pred}' not in predicate vocabulary")
        if rtype == "dataset-version":
            dv_keys[(rec.get("datasetId"), rec.get("version"))].append(rid)
        if rtype == "connection":
            a, b = rec.get("sourceId"), rec.get("targetId")
            if a == b:
                errors.append(f"{origin[rid]}: {rid}: connection is a self-loop ({a})")
            elif rec.get("direction") in ("undirected", "bidirectional"):
                pair_keys[(rec.get("datasetVersionId"), rec.get("connectionType"), *sorted((str(a), str(b))))].append(rid)
        if rtype in ("relationship", "connection") and rec.get("assertionType") in WEAK_ASSERTIONS:
            for cid in rec.get("claimIds", []):
                c = records.get(cid, {})
                if c.get("evidenceStatus") in STRONG_EVIDENCE:
                    errors.append(f"{origin[rid]}: {rid}: {rec['assertionType']} assertion linked to claim {cid} marked {c['evidenceStatus']}")
    for key, ids in dv_keys.items():
        if len(ids) > 1:
            errors.append(f"duplicate DatasetVersion for {key}: {ids}")
    for key, ids in pair_keys.items():
        if len(ids) > 1:
            errors.append(f"duplicate undirected connection for {key[2]} <-> {key[3]} ({key[1]}, {key[0]}): {ids}")

    if errors:
        print(f"FAILED: {len(errors)} problem(s) across {len(records)} record(s)")
        for e in errors:
            print("  -", e)
        return 1
    print(f"OK: {len(records)} record(s) valid, all references resolve, {len(vocab)} predicates loaded")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
