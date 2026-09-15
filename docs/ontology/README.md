# Ontology

The domain model is relational. Biological entities are distinct from:

- their spatial representations
- claims about them
- the evidence for those claims
- the datasets and sources the evidence came from
- computational models of them (future)

Core chain:

```
Entity —(relationship / connection)— Entity
   └── Claim ── EvidenceRecord ── Source / DatasetVersion ── Observation
```

Predicates are controlled: see `predicate-vocabulary.md`. External ontologies
(UBERON, NeuroNames, ChEBI, GO, MONDO, IUPHAR) are referenced via
`externalIdentifiers`; NeuroAtlas does not redefine them.
