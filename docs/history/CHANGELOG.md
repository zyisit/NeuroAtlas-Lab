# Changelog

## 0.9.0 — 2026-09-14
- Sprint 3: first curated claims — 12 claims, 23 sources (DOIs verified), 28 evidence records (5 `contradicts`), 8 relationships, 6 brain-function records, in `data/function/curated-claims-v1.json`; `docs/curation.md` documents the rules and review lifecycle
- Viewer: evidence records show polarity, species, preparation, method, locator and notes with DOI links; claims about containing regions are shown for sub-regions; region colour falls back to the nearest coloured relative; selecting a region swings the camera to its side
- Meshes and centroids now cover *map* leaves (regions with a label and no labelled descendant) rather than tree leaves, so amygdala nuclear groups and other parent-mapped structures get surfaces (406 meshes, up from 386)

## 0.8.0 — 2026-09-14
- Sprint 2: viewer MVP in `viewer/` (React 19, three.js, Vite) — region tree with search, 3D region surfaces, evidence/detail panel, attribution footer
- `scripts/build/build_meshes.py`: whole-brain hull and 386 per-region GLB meshes from the Julich labelled MPM, with spatial-representation records (`data/anatomy/julich-brain-3.1/meshes.json`)
- `scripts/build/build_viewer_bundle.py`: validates `data/` and emits the viewer bundle
- `.github/workflows/viewer.yml`: builds the site on every push; deploys to GitHub Pages from `main`
- `.gitattributes` normalises line endings; `src/` placeholder removed in favour of `viewer/`

## 0.7.1 — 2026-09-14
- Sprint 1: Julich-Brain 3.1 imported via `scripts/import/import_julich_brain.py` — 771 brain-region records, 771 atlas-mapping records, dataset / dataset-version / source / reference-space / atlas provenance
- `atlas-mapping.displayColor` added (atlas-supplied region colour for the viewer)
- `requirements-import.txt` for importer-only dependencies
- Julich-Brain license (CC BY-NC-SA 4.0) recorded with `commercialUseAllowed: false`

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
