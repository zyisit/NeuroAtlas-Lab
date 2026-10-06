# NeuroAtlas Lab

**An evidence-aware, multiscale interactive brain atlas.**

NeuroAtlas Lab is an educational neuroscience platform being built to connect

> whole brain → region → circuit → neuron → synapse → receptor → neurotransmitter → molecular signaling → function → pathology → intervention

in a single navigable 3D model, where every statement carries its species, its
experimental context, its source, and an honest label for how well it is
supported. Established anatomy, curated data, inference, model output, and
hypotheses are never silently mixed.

## Status

**v0.12.0 · Sprint 6 (connectivity follow-ups)**

What exists today:

- A JSON Schema (Draft 2020-12) data contract for 15 record types (`schemas/`)
- A controlled predicate vocabulary (`docs/ontology/`)
- A validator that enforces schema shape, referential integrity, vocabulary,
  and governance rules (`scripts/validate.py`), run in CI on every push
- Scientific-governance principles the data model is designed to uphold
- A synthetic example bundle exercising the full record chain (`examples/`)
- **Real data, two atlases:** the full Julich-Brain 3.1 cytoarchitectonic atlas — 771 regions
  with hierarchy, atlas mappings, display colours, and provenance
  (`data/anatomy/julich-brain-3.1/`, CC BY-NC-SA) — and the Allen Human Reference Atlas – 3D,
  2020 — 473 regions with hemisphere leaves (`data/anatomy/allen-hra-3d-2020/`, CC BY 4.0), each
  produced by a reproducible import script under `scripts/import/`. The atlases sit on different
  MNI templates; the records say so, and 1,137 computed overlap relationships
  (`data/anatomy/cross-atlas/`) join them without pretending they share regions
- **The viewer:** a React + three.js atlas browser (`viewer/`) — atlas switch, searchable region
  hierarchy, 3D surfaces for 406 Julich and 275 Allen regions, cross-atlas overlaps, and a detail
  panel that shows only what the records contain, with sources and license attached
- **First curated claims** (`data/function/`): twelve cited statements about the
  hippocampus, V1, M1 and amygdala, each with species, preparation, evidence status,
  and evidence for *and against* — see `docs/curation.md`
- **Connectivity** (`data/connectivity/`), from 200 HCP subjects (Domhof et al., CC BY 4.0):
  10,990 undirected structural edges (tractography streamline counts, each with its mean
  streamline length) and 6,768 resting-state functional edges (group-mean correlation,
  |r| ≥ 0.3) between Julich regions, with per-edge subject consistency. The viewer switches
  between the two and says plainly that a correlation is not a pathway

Run it: see `viewer/README.md`. Roadmap: `docs/roadmap.md`.

## Quick start

```bash
pip install -r requirements.txt
python scripts/validate.py        # validates examples/ and data/
pytest -q
```

To change the schemas, edit `scripts/gen_schemas.py` and re-run it; `schemas/`
is generated output and CI fails if it drifts.

To (re)build the Julich-Brain records:

```bash
pip install -r requirements-import.txt
python scripts/import/import_julich_brain.py            # regions + mappings, ~1 min
python scripts/import/import_julich_brain.py --spatial  # adds centroids + volumes, ~30 min first run
```

To (re)build the connectivity records (needs the Julich records above):

```bash
python scripts/import/import_connectivity.py            # 200 HCP subjects: counts, lengths, resting-state FC, ~4 min
```

To (re)build the Allen atlas, its meshes and the cross-atlas overlaps:

```bash
python scripts/import/import_allen_hra_3d.py            # downloads ~3 MB once, ~1 min
python scripts/build/build_meshes.py --atlas allen      # ~3 min
python scripts/build/build_overlaps.py                  # ~2 min, needs the Julich siibra cache
```

## Scientific principles

1. Evidence before aesthetics.
2. Reference anatomy is not an individual human brain.
3. Correlation is not causation. `causes` is not a valid predicate.
4. Model output is not biological fact. Every edge declares its `assertionType`.
5. Species and experimental context travel with every finding.
6. External identifiers (UBERON, Allen, Julich, ChEBI, IUPHAR, …) are preserved as mappings, never overwritten.
7. Dataset licensing, versioning, and provenance are first-class records.
8. Large datasets are referenced, not committed.

Full text: `docs/scientific-governance/principles.md`.

## Repository layout

| Path | Contents |
|---|---|
| `schemas/` | Generated JSON Schema files + `index.json` registry |
| `scripts/` | `gen_schemas.py` (schema source of truth), `validate.py`, `import/` (data ingestion), `build/` (meshes, viewer bundle) |
| `docs/` | Data model, ontology, governance, architecture, data-source policy, roadmap |
| `examples/` | Synthetic placeholder records. **Not scientific content.** |
| `data/` | Curated project records, by domain: `anatomy/` (Julich, Allen, cross-atlas overlaps), `connectivity/`, `function/` |
| `tests/` | Validator tests |
| `archive/` | Schema v0.4 and v0.6 packages, retained for history |
| `viewer/` | The web viewer (React, three.js). Reads `viewer/public/data/bundle.json` built from `data/` |
| `models/` | Reserved for computational models (Phase 7+) |

## Scope boundaries

NeuroAtlas Lab is an educational and research visualization project. It is
**not** a clinical tool. It does not diagnose, does not predict an individual's
response to treatment, and does not present simulations as clinically
validated. Model-derived output is labeled as such everywhere it appears.

## License

Code, schemas, and documentation: [Apache License 2.0](LICENSE).
Ingested scientific data retains its source license; see `NOTICE` and
`docs/data-sources/README.md`.

## Citing

See `CITATION.cff`. Please also cite the underlying datasets.
