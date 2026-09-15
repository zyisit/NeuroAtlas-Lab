# Scientific Governance Principles

## Evidence status vocabulary

`claim.evidenceStatus` takes one of:

| Value | Meaning |
|---|---|
| `established` | Textbook-level consensus across methods and species where applicable |
| `well_supported` | Multiple independent lines of evidence, no serious contradiction |
| `supported` | Credible evidence, limited replication or scope |
| `emerging` | Recent, few sources |
| `uncertain` | Evidence is thin, indirect, or the linked sources are placeholders |
| `contested` | Credible evidence on both sides; contradicting evidence records exist |
| `model_derived` | Comes from a computational model, not from biology |
| `hypothetical` | Proposed, not yet tested |

These labels are communication metadata for readers. They are not probabilities
of truth and must not be summed, averaged, or ranked numerically in the UI.

## Assertion type

Every `relationship` and `connection` declares `assertionType`:
`observed`, `curated`, `inferred`, `model_derived`, `hypothetical`.
This is the mechanism by which model output can never be confused with an
observation. The validator enforces it.

## Causality

The predicate `causes` is excluded from the vocabulary and rejected by the
validator. Causal language may be admitted in a future version only with a
dedicated predicate, explicit evidence requirements, and review.

## Species and context

Human, animal, in-vitro, post-mortem, and computational findings must not be
silently conflated. `species` is required on regions, connections, and
reference spaces, and available on claims, observations, and evidence.
`context` records preparation, developmental stage, sex, strain, and condition.

## Contradicting evidence

`evidence-record.polarity` allows `contradicts`. Contradicting evidence is
recorded and displayed, never deleted to make a claim look cleaner.

## Modeling

A computational model is an explicit abstraction. Its equations, parameters,
assumptions, scale, and limitations must be inspectable. Model-derived
predictions are labeled as such everywhere they appear.

## Clinical content (Phase 5+)

Pathology, injury, and pharmacology records are educational. They describe
documented mechanisms and presentations with sources. They do not diagnose,
and they do not predict individual outcomes.

## Changing this document or the vocabulary

Changes to predicates, evidence-status semantics, assertion types, or clinical
scope require a pull request with rationale and are reviewed before merge.
