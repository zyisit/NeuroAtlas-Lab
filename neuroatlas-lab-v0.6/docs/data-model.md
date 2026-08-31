# v0.6 data model

## Identity and provenance

Every record has a stable local `id`. `Dataset` describes the enduring source or collection; `DatasetVersion` identifies one immutable or date-bounded release of it. A record that came from a dataset should cite the relevant `datasetVersionId`, not merely its dataset.

## Spatial model

`ReferenceSpace` names a coordinate frame. `SpatialTransformation` captures a directed mapping between two reference spaces and may cite the dataset version or method producing it. `SpatialRepresentation` records a geometry or coordinate payload in a reference space and lists the transformation IDs needed to interpret or reproduce it.

`BrainRegion` does not treat an atlas label as intrinsic identity. Each atlas-specific label is represented by an `AtlasMapping` that connects a brain region to an atlas and optionally to a region identifier within that atlas.

## Assertions and evidence

`Observation` is the atomic record of a measured, annotated, computed, or otherwise reported result. `EvidenceRecord` gives a claim’s supporting context and may reference one or more observations. `Claim` may link directly to observations as well.

`Relationship` describes an edge between two entities. Its `assertionType` is required so users can distinguish direct observations from expert curation, inference, model output, and hypotheses. It is not a truth score; optional confidence belongs in `confidence`.

## Versioning policy

- Package version: v0.6.
- Schema documents declare Draft 2020-12.
- Do not overwrite a published DatasetVersion record; create a new one.
- Retain v0.4 files in a historical location if they exist in the target repository; v0.6 is a forward revision, not a destructive replacement.
