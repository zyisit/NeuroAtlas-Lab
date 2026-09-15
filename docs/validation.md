# Validation

`python scripts/validate.py [paths...]` — defaults to `examples/` and `data/`.

Files may hold one record or an array. Record type comes from the `id` prefix.

Checks:
1. JSON Schema shape (Draft 2020-12, with format checking for dates and URIs).
2. Every `*Id` / `*Ids` reference resolves inside the validated bundle, and to the expected record type.
3. `relationship.predicate` is in `docs/ontology/predicate-vocabulary.md`.
4. `causes` is rejected.
5. No duplicate `dataset-version` for the same dataset + version.
6. `model_derived` / `hypothetical` edges may not be linked to `established` / `well_supported` claims.

Not checked (application-level, later): controlled vocabularies for `species`,
immutability of published dataset versions across commits, asset URI reachability.

Because references must resolve *within the validated set*, split files that
reference each other must be validated together (the default does this by
walking whole directories).
