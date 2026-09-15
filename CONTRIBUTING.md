# Contributing

NeuroAtlas Lab is in Phase 0–1. Contributions most useful right now:
schema review from neuroscientists, data-source license verification, and
import scripts.

## Adding or changing records
1. Every scientific record cites a `source` or `dataset-version`.
2. Record species and context wherever interpretation depends on them.
3. Set `assertionType` honestly. `curated` means a human read the source and
   entered it; `observed` means the record *is* the observation.
4. Leave new claims at `evidenceStatus: uncertain` or lower until reviewed.
5. Run `python scripts/validate.py` and `pytest` before opening a PR. CI runs both.

## Changing the schema
Edit `scripts/gen_schemas.py`, run it, commit the regenerated `schemas/`.
Add a CHANGELOG entry. Breaking changes bump the minor version.

## Changing governance or vocabulary
Open a PR that explains the scientific rationale. These are reviewed, not
merged on green CI alone.

## Not accepted
- Large binary assets in git
- Clinical or causal claims without sources meeting the governance principles
- Anything intended for a paid tier (see `docs/roadmap.md`, open-core boundary)
