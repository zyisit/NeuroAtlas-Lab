# NeuroAtlas Lab

**An evidence-aware, multiscale interactive brain atlas.**

NeuroAtlas Lab is an educational neuroscience platform being built to connect

> whole brain → region → circuit → neuron → synapse → receptor → neurotransmitter → molecular signaling → function → pathology → intervention

in a single navigable 3D model, where every statement carries its species, its
experimental context, its source, and an honest label for how well it is
supported. Established anatomy, curated data, inference, model output, and
hypotheses are never silently mixed.

## Status

**Schema v0.7 · Phase 0 (foundation) · pre-application**

What exists today:

- A JSON Schema (Draft 2020-12) data contract for 15 record types (`schemas/`)
- A controlled predicate vocabulary (`docs/ontology/`)
- A validator that enforces schema shape, referential integrity, vocabulary,
  and governance rules (`scripts/validate.py`), run in CI on every push
- Scientific-governance principles the data model is designed to uphold
- A synthetic example bundle exercising the full record chain (`examples/`)

What does not exist yet: real data, and the viewer. Those are Sprints 1 and 2.
See `docs/roadmap.md`.

## Quick start

```bash
pip install -r requirements.txt
python scripts/validate.py        # validates examples/ and data/
pytest -q
```

To change the schemas, edit `scripts/gen_schemas.py` and re-run it; `schemas/`
is generated output and CI fails if it drifts.

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
| `scripts/` | `gen_schemas.py` (schema source of truth), `validate.py` |
| `docs/` | Data model, ontology, governance, architecture, data-source policy, roadmap |
| `examples/` | Synthetic placeholder records. **Not scientific content.** |
| `data/` | Curated project records, by domain. Empty until Sprint 1. |
| `tests/` | Validator tests |
| `archive/` | Schema v0.4 and v0.6 packages, retained for history |
| `src/`, `models/` | Reserved for the viewer (Phase 1) and computational models (Phase 5+) |

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
