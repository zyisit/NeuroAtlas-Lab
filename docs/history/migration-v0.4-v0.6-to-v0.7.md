# Migration notes: v0.4 / v0.6 → v0.7

Both prior packages are retained unchanged under `archive/`. No v0.4 or v0.6
records exist in `data/`, so no data migration is needed; these notes exist so
the design decisions are traceable.

## Field renames (v0.4 → v0.7)
| v0.4 | v0.7 |
|---|---|
| `subject_id` / `object_id` | `subjectId` / `objectId` |
| `source` / `target` (Connection) | `sourceId` / `targetId` |
| `connection_type` | `connectionType` |
| `evidence_refs` | `evidenceRecordIds` |
| `external_identifiers` | `externalIdentifiers` |
| `atlas_memberships` | `atlasMappingIds` (now a real record, not a string) |
| `parent_regions` | `parentRegionIds` |
| `model_status` | `assertionType` (`biological` → `observed`) |
| `confidence` enum (high/moderate/…) | `confidence` number 0–1, optional |
| `source_id` (Evidence) | `sourceId` → `source` record |
| `status` (`draft/proposed/active/deprecated`) | `status` + `superseded`, `retracted` |
| ID `anatomy.region.hippocampus` | `brain-region:hippocampus` |

## Semantic changes
- Atlas labels are no longer intrinsic to a region (v0.4 `atlas_memberships`); they are `atlas-mapping` records (v0.6 idea, kept).
- Evidence now links to a `claim` and a `source` and states `polarity`. v0.4 evidence pointed at entities and claims loosely.
- `claim.evidenceStatus` replaces the governance-only prose vocabulary.
- `dataset-version.retrievedAt` is required; v0.6 had only `releaseDate`.

## Not carried forward
- `Brain`, `Entity`, `ProvenanceRecord` — see CHANGELOG.
- v0.6 placeholder predicate `hasIllustrativeResult` — not in vocabulary.
