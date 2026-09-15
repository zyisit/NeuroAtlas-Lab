# Data model v0.7

## Conventions

- Field names are camelCase. Enum values are snake_case.
- Every record has an `id` of the form `<record-type>:<slug>`; the prefix selects the schema.
- `additionalProperties: false` everywhere. If you need a field, add it to `scripts/gen_schemas.py`.
- Cross-record references are plain ID strings. JSON Schema does not resolve them; `scripts/validate.py` does.
- Large payloads (meshes, volumes) are referenced by `geometry.uri`, never embedded or committed.

## Record types

### Provenance layer
| Type | Role |
|---|---|
| `dataset` | An enduring source (an atlas project, a database). Carries a default `license`. |
| `dataset-version` | One immutable release. `retrievedAt` is required. Never overwrite; add a new one. |
| `source` | A citable publication or resource. |

### Spatial layer
| Type | Role |
|---|---|
| `reference-space` | A coordinate frame, always bound to a species. |
| `spatial-transformation` | A directed registration between two spaces. |
| `atlas` | A parcellation defined on a reference space. |
| `atlas-mapping` | Ties a `brain-region` to a label inside one atlas. Atlas labels are mappings, not identity. |
| `spatial-representation` | Geometry for an entity in a space, with the transformations needed to interpret it. |

### Entity layer
| Type | Role |
|---|---|
| `brain-region` | Project-owned anatomical identity. `species` required. |
| `brain-function` | A named function; association with regions is a claim, not a fact. |
| `connection` | A typed edge between anatomical/cellular entities. `species` and `assertionType` required. |
| `relationship` | Generic typed edge using the controlled predicate vocabulary. `assertionType` required. |

### Evidence layer
| Type | Role |
|---|---|
| `observation` | Atomic measured/annotated/derived/reported result, bound to a dataset version. |
| `claim` | Human-readable statement with an `evidenceStatus`. This is what the UI displays. |
| `evidence-record` | Links a claim to a source with a `polarity` (supports / contradicts / mixed). Contradicting evidence is kept. |

## The two labels that matter most

**`assertionType`** (on relationships and connections): how the edge came to exist —
`observed`, `curated`, `inferred`, `model_derived`, `hypothetical`. Required. It is
not a truth score.

**`evidenceStatus`** (on claims): how well the statement is supported —
`established` … `hypothetical`. Required. It is communication metadata, not a
probability.

The validator refuses a `model_derived` or `hypothetical` edge that is linked to
an `established` or `well_supported` claim.

## Typical record chain

```
dataset → dataset-version → reference-space → atlas → atlas-mapping → brain-region
                                     ↘ spatial-transformation → spatial-representation
source → evidence-record → claim ← relationship / connection
dataset-version → observation ↗          ↖ dataset-version (imported connectomes)
```

`examples/hippocampus-bundle.json` walks every link above.

## Changes from v0.6 and v0.4

See `docs/history/CHANGELOG.md` and `docs/history/migration-v0.4-v0.6-to-v0.7.md`.
