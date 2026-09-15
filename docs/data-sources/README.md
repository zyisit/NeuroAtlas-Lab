# Data sources

## Policy

Before ingesting any source, create a `dataset` and a `dataset-version` record
capturing: identity, version, retrieval date, license (as SPDX), attribution
text, whether commercial use is allowed, and the transformations this project
applied. The import script that produced the records is committed under
`scripts/import/`.

Raw assets (volumes, meshes, tables) are **never committed**. Records point to
them via `spatial-representation.geometry.uri`.

## Candidate sources by phase

| Phase | Source | Typical license | Notes |
|---|---|---|---|
| 1 | Julich-Brain 3.1 / EBRAINS (via siibra) | **CC BY-NC-SA 4.0** (verified 2026-09-14) | Ingested. Non-commercial + share-alike; excluded from any commercial tier |
| 1 | Allen Human Brain Atlas | Allen Terms of Use | Non-commercial restrictions apply to some resources |
| 1 | UBERON | CC BY 3.0 | Anatomical identifiers |
| 2 | Human Connectome Project | HCP Open Access terms | Registration required |
| 2 | OpenNeuro | CC0 | |
| 3 | NeuroMorpho.Org | CC BY | Morphologies |
| 3 | Allen Cell Types Database | Allen Terms of Use | |
| 4 | IUPHAR/BPS Guide to PHARMACOLOGY | CC BY-SA 4.0 | Share-alike: downstream implications |
| 4 | ChEBI | CC BY 4.0 | |
| 4 | Gene Ontology | CC BY 4.0 | |
| 5 | MONDO / Disease Ontology | CC BY 4.0 / CC0 | Disease identifiers |
| 6 | ChEMBL | CC BY-SA 3.0 | Binding data; share-alike |
| 6 | DrugBank | Academic vs commercial license | Commercial tier needs a paid license |

License columns are indicative and must be re-verified at ingestion time and
recorded on the dataset record. Sources with non-commercial or share-alike terms
are flagged with `license.commercialUseAllowed=false` or noted so that a future
commercial tier can exclude or re-license them.
