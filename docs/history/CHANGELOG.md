# Changelog

## 0.7 — 2026-09-14
- Single canonical schema replacing the parallel v0.4 and v0.6 packages
- Schemas are generated from `scripts/gen_schemas.py`; CI fails on drift
- Restored from v0.4: `species`, `hemisphere`, `context`, `externalIdentifiers`, `license`, `Source`, `Atlas`, `Connection`, `BrainFunction`, record `status`
- Kept from v0.6: camelCase, `common.json` shared defs, `ReferenceSpace`, `SpatialTransformation`, `AtlasMapping`, `DatasetVersion`, `Observation`, `assertionType`
- New: `evidenceStatus` on claims (previously only in governance prose), `polarity` on evidence records, `license` object with `commercialUseAllowed`, `retrievedAt` required on dataset versions, `<type>:<slug>` ID convention enforced by pattern
- Predicate vocabulary v0.4: added connectivity, chemistry, and pathology/intervention terms; `causes` rejected by validator
- Validator: referential integrity, type-checked references, vocabulary, duplicate dataset versions, weak-assertion-vs-strong-claim rule
- Dropped: `Brain` (no use case before Phase 9), `Entity` base schema (each type is concrete), `ProvenanceRecord` (folded into `provenance` block and `dataset-version.transformations`)
- License set to Apache-2.0; NOTICE added for data-license passthrough

## 0.6 — 2026-08-30
- Spatial and provenance layer: ReferenceSpace, SpatialTransformation, AtlasMapping, DatasetVersion, Observation
- Dropped species/context/license fields (restored in 0.7)

## 0.4 — 2026-08-30
- First machine-readable MVP contract, 14 types, snake_case
