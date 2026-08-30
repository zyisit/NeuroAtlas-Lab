# NeuroAtlas Lab

**Interactive Neuroscience Brain Atlas & Simulation Lab**

NeuroAtlas Lab is an evidence-aware, multiscale neuroscience education and visualization platform.

The long-term goal is to connect:

**whole brain → region → structure → circuit/pathway → neuron → synapse → receptor → neurotransmitter → molecular signaling → functional consequence → computational model**

The project is designed so that scientific facts, curated data, experimental evidence, computational models, and model-derived predictions remain explicitly distinguishable.

## Current status

**Phase:** Architecture / data-model foundation

This repository is intentionally pre-application. The current work focuses on:

- domain ontology
- machine-readable schemas
- scientific provenance
- dataset strategy
- validation rules
- architecture documentation

## Scientific principles

1. **Evidence before aesthetics.**
2. **Reference anatomy is not an individual human brain.**
3. **Correlation is not automatically causation.**
4. **Model output is not biological fact.**
5. **Species and experimental context matter.**
6. **External identifiers should be preserved.**
7. **Dataset licensing and provenance are first-class data.**
8. **Large datasets should not be copied into the source repository without an explicit data-management decision.**

## Initial repository structure

- `docs/` — architecture, scientific governance, dataset notes, ontology
- `schemas/` — JSON Schema definitions for the data model
- `data/` — curated project data and metadata
- `examples/` — small machine-readable example records
- `models/` — computational model definitions (future phases)
- `src/` — application source (future phases)
- `tests/` — validation and application tests
- `scripts/` — ingestion, validation, asset-processing, and build tooling

## Scope boundaries

NeuroAtlas Lab is an educational/research visualization project.

It is **not** intended to:

- reproduce the complete human brain
- provide clinical diagnosis
- predict an individual's response to treatment
- replace professional medical advice
- present simplified simulations as clinically validated predictions

## Next milestone

**Scientific Data Model Review (v0.5)**

The v0.5 review will test the current schema against representative real neuroscience datasets and refine:

- atlas relationships
- species/context handling
- evidence representation
- connectivity semantics
- spatial representations
- provenance
- future model compatibility

## Repository status

This repository is private during early architecture development. Public-release decisions will be made later.
