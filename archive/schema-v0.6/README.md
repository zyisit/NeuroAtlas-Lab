# NeuroAtlas Lab — schema package v0.6

This package is a repository-ready revision of the NeuroAtlas Lab conceptual schema. It contains JSON Schema (Draft 2020-12) definitions, documentation, and synthetic placeholder examples. It deliberately contains **no raw neuroscience datasets**.

## What changed from v0.4

v0.6 keeps the earlier concepts as a historical foundation, while making spatial and evidentiary provenance first-class:

- `AtlasMapping` makes a brain-region-to-atlas assignment explicit.
- `ReferenceSpace` and `SpatialTransformation` describe coordinate systems and their registered conversions.
- `DatasetVersion` separates a versioned data release from its parent `Dataset`.
- `Observation` represents a citable measured or derived observation.
- `BrainRegion` uses explicit atlas mappings rather than implicit labels.
- `SpatialRepresentation` references its space, dataset version, and transformations.
- `Claim` and `EvidenceRecord` may point to observations.
- `Relationship.assertionType` records whether an assertion is observed, curated, inferred, model-derived, or hypothetical.

## Layout

- `schemas/` — individual JSON Schema documents and `index.json` registry.
- `examples/` — non-scientific, synthetic records showing linkage patterns.
- `docs/` — model notes and validation guidance.

## Use

Validate an instance against the matching schema in `schemas/`. Schema `$ref` values are relative to the `schemas` directory; keep that directory structure intact when moving these files into the repository.

This is a schema package, not a database contract or an ontology release. Vocabulary identifiers, persistent URI policy, validation tooling, and migration scripts can be added in subsequent versions.
