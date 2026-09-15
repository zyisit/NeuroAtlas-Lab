# Roadmap

## Near-term sprints

### Sprint 0 — Foundation (this release, v0.7)
- Reconcile schema v0.4 and v0.6 into one contract
- Validator with referential integrity + governance rules, wired to CI
- License decision (Apache-2.0), citation, contribution policy

### Sprint 1 — First real data (v0.7.1, done)
- Julich-Brain 3.1 ingested via `siibra-python` into `data/anatomy/julich-brain-3.1/`
- Dataset, DatasetVersion, Source, ReferenceSpace, Atlas, and an AtlasMapping for every region
- Optional `--spatial` pass adds centroids and volumes for leaf regions
- Still to do in Sprint 1b: region meshes as external assets (`geometry.uri`) for the viewer; evaluate Allen Human atlas as a second source

### Sprint 2 — Viewer MVP
- React + TypeScript + Three.js, static build deployable to GitHub Pages
- Load reference mesh, click/search a region, show its evidence panel (claims, evidence status, sources, external IDs)
- Assertion-type and evidence-status badges visible on every fact

## Phases

| Phase | Scope |
|---|---|
| 0 | Ontology, schemas, provenance, licensing (done in v0.7) |
| 1 | Anatomical atlas MVP (Sprints 1–2) |
| 2 | Connectivity, pathways, functional associations |
| 3 | Cell types, morphology, synapses, electrophysiology |
| 4 | Neurochemistry: transmitters, receptors, channels, transporters, signaling |
| 5 | Pathology and injury: disease records, lesion → deficit chains, clinical presentation |
| 6 | Pharmacology: compound → target → region → function mechanism tracing |
| 7 | Transparent educational simulation (neuron / synapse / circuit models) |
| 8 | Procedural / surgical planning module |
| 9 | Integrated multiscale navigation; optional backend compute |

## Open-core boundary

This repository is and will remain Apache-2.0. Anything intended for a paid tier
(advanced pharmacology inference, surgical simulation, hosted accounts) is
developed in a separate private repository that depends on this one. Nothing
paid is ever committed here.

## Explicit non-goals (see README scope boundaries)

- Predicting the real-world effect of novel compound combinations. Phase 6
  traces documented mechanisms; it does not invent pharmacology.
- Physics-based tissue simulation. Phase 8 is procedural and anatomical.
