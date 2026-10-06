# Changelog

## 0.12.0 — 2026-10-05
- Sprint 6, connectivity follow-ups from the same HCP dataset (Domhof et al., EBRAINS v1.2, CC BY 4.0), all written by `scripts/import/import_connectivity.py` (one run imports everything; `--skip-lengths`, `--skip-fc`, `--fc-*` flags):
  - Streamline lengths: 10,990 `observation` records, one per structural connection (`subjectId` = the connection), group-mean path length in mm over subjects with ≥ 1 streamline, in `streamline-lengths.json`
  - Resting-state functional connectivity: 6,768 undirected `functional_connectivity` edges (paradigm "EmpCorrFC concatenated", Fisher-z group mean of 200 subjects, |r| ≥ 0.3, value present in ≥ 90% of subjects, signed r as strength, per-edge `subjectSignFraction`) in `functional-connections.json`. No pair has a negative group-mean r at that cut (strongest negative anywhere: −0.175). REST1-vs-REST2 group means agree at r = 0.998 (`--fc-reliability`)
  - Re-running the importer keeps each existing record's `createdAt`; the 10,990 structural edges are reproduced byte-for-byte
- Schema unchanged (v0.7): lengths use the existing `observation` type, functional edges the existing `connectionType`
- Viewer: Structural / Functional switch in the Connections section (count per type), |r| slider for functional edges, functional tubes coloured by sign, mean streamline length on every structural edge, explicit "correlation is not a pathway" note, and a reasoned empty state for the 183 regions without functional edges (small deep nuclei and low-signal cortex). Masthead shows both connection counts
- Viewer: the stage background is now soft pastel pink instead of dark slate, with a Pink / White switch in its corner (remembered per browser); the whole-brain shell is a faint grey so it still reads on a light background
- `scripts/build/build_viewer_bundle.py` packs fields that repeat across a data file once (`_shared` / `_items`); `viewer/src/data.ts` re-expands them. Lossless; the bundle is smaller than in 0.11.0 despite ~17,800 more records
- `tests/test_connectivity.py`: five tests (lengths ↔ structural edges, functional edge invariants against the recorded threshold, region scope, packing round-trips) — 19 tests total
- `docs/data-sources/hcp-connectivity.md`: decision records for lengths and functional connectivity, threshold sweep, reliability, regions without edges
- Total 34,547 validated records (34,527 in `data/`)

## 0.11.0 — 2026-09-17
- Sprint 5: second atlas — the Allen Human Reference Atlas – 3D, 2020 (Ding et al., RRID:SCR_017764, CC BY 4.0) imported by `scripts/import/import_allen_hra_3d.py` directly from the Allen release directory (siibra has no Allen human parcellation): 473 brain-region records (205 ontology nodes, 268 hemisphere leaves split at x = 0, 7 midline leaves), 473 atlas-mappings with Allen colours, 275 centroids and volumes, plus dataset / dataset-version / source / reference-space / atlas records in `data/anatomy/allen-hra-3d-2020/`. First anatomy dataset with `commercialUseAllowed: true`
- The Allen template (ICBM 2009b symmetric) gets its own reference-space and an explicit approximate-identity `spatial-transformation` to the Julich space (2009c asymmetric); the importer verifies that the release volume is a left→right mirror and records it
- Decision: atlas-neutral region ids dropped; the atlases are joined by 1,137 computed `overlaps` relationships (`assertionType: inferred`, both overlap fractions and shared volume in context) from the new `scripts/build/build_overlaps.py`, in `data/anatomy/cross-atlas/`
- `scripts/build/build_meshes.py` takes `--atlas julich|allen|all`; 275 Allen surfaces in `viewer/public/assets/allen-hra-3d-2020/` (smoothing halved for structures under 500 mm³ so thin tracts survive)
- Viewer: atlas switch, per-atlas surfaces loaded without resetting the camera, "In <other atlas>" panel on every leaf with the template caveat (clicking an overlap switches atlas), mapping notes shown (hemisphere split / mirror), Allen regions state that connectivity is Julich-only, masthead and centroid label name the current atlas and its space
- `tests/test_cross_atlas.py`: six invariants of the second atlas and the overlap records (14 tests total)
- `docs/data-sources/allen-human-reference-atlas-3d-2020.md` (includes the atlas decision record); data-sources table, Julich notes and roadmap updated
- Total 16,789 validated records

## 0.10.0 — 2026-09-15
- Sprint 4, Phase 2 begins: HCP structural connectivity for Julich-Brain 3.1 — `scripts/import/import_connectivity.py` reads the 200-subject streamline-count matrices (Domhof et al., EBRAINS v1.2, CC BY 4.0) via siibra, averages them, and writes 10,990 undirected `connection` records (pairs with mean ≥ 20 streamlines present in ≥ 90% of subjects) plus dataset / dataset-version / source records to `data/connectivity/hcp-julich-3.1/`
- Schema (additive, still v0.7): optional `datasetVersionId` on `connection`
- Validator rule 7: no self-loop connections; an undirected or bidirectional pair is stored once per dataset version. Three new tests
- Viewer: "Connections" section in the detail panel (strongest first, subject-consistency per edge, threshold slider, dataset and method stated, explicit note that tractography edges are undirected) and bowed tubes in 3D from the selected region to its connected regions, tube width and opacity ∝ strength, connected regions half-lit. Grouping nodes point to their mapped leaves; the 50 small nuclei with no retained edges say why
- `docs/data-sources/hcp-connectivity.md`; data-sources table and roadmap updated
- CI: `workflow_dispatch` on viewer.yml; actions moved to their Node 24 majors (checkout v5, setup-python v6, setup-node v5, upload-pages-artifact v5, deploy-pages v5)

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
