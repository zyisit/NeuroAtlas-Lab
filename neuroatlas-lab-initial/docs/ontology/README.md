# Ontology

The core domain model is intentionally relational.

Biological entities are not the same thing as:
- spatial representations
- claims
- evidence
- datasets
- computational models
- simulation results

The central architecture is:

Entity
  → Relationship
  → Claim
  → Evidence
  → Source/Dataset

and later:

Biological entities
  → Model
  → Intervention
  → Simulation
  → SimulationResult
