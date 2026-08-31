# Validation notes

1. Validate each JSON document against its named schema.
2. Resolve all cross-record IDs inside the intended project bundle or service.
3. Ensure `DatasetVersion.datasetId` resolves to a `Dataset`.
4. Ensure `AtlasMapping.brainRegionId` and `atlasId` resolve to their respective records.
5. Ensure a transformation’s `sourceReferenceSpaceId` and `targetReferenceSpaceId` resolve to `ReferenceSpace` records.
6. Require that observations and spatial representations cite a `DatasetVersion` when provenance is available.

JSON Schema checks document shape. Referential integrity, immutable-version policy, and controlled vocabulary checks require application-level validation.
