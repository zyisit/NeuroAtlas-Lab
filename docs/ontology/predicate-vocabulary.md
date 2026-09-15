# NeuroAtlas Predicate Vocabulary v0.4

Controlled terms for `Relationship.predicate`. `scripts/validate.py` rejects any
relationship whose predicate is not listed here. Add a term by editing this file
in a reviewed change; see `docs/scientific-governance/principles.md`.

Each line lists predicates in one group. Inverse predicates are noted where the
project stores only one direction.

## Anatomy
part_of, contains, adjacent_to, overlaps, located_in, continuous_with

## Connectivity
projects_to, receives_from, connected_to, innervates

## Cellular
contains_cell_type, expresses, derived_from, has_morphology

## Chemistry
releases, binds, activates, inhibits, transports, synthesizes, degrades, metabolized_by, agonist_of, antagonist_of, allosteric_modulator_of

## Function
associated_with, contributes_to, required_for, modulates, participates_in, activated_during, impaired_by

## Pathology and intervention
affected_in, lesion_produces, presents_with, risk_factor_for, treated_with, side_effect_of, contraindicated_with

## Modeling
represented_by, modeled_by, parameterizes, simulates, produces

## Evidence
supported_by, contradicted_by

## Excluded
`causes` is intentionally excluded and the validator rejects it. Causal claims
require explicit scientific-governance review and, when admitted, a dedicated
predicate with stated evidence requirements. Use `contributes_to`,
`associated_with`, or `lesion_produces` with an honest `assertionType` instead.
