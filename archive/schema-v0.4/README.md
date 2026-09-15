# NeuroAtlas Lab — JSON Schema Specification v0.4

First machine-readable MVP data contract for the Interactive Neuroscience Brain Atlas & Simulation Lab.

## Included
Entity, ExternalIdentifier, Brain, Atlas, BrainRegion, SpatialRepresentation,
Relationship, Connection, BrainFunction, Claim, EvidenceRecord, Source,
Dataset, and ProvenanceRecord.

## Scientific governance
- Model-derived results are never equivalent to established biological evidence.
- NeuroAtlas internal IDs remain stable while external database identifiers are preserved as mappings.
- Species and context should be attached wherever biological interpretation depends on them.
- Dataset licensing, attribution, versioning, and provenance are first-class data.
- Example records are placeholders and are not publication-ready scientific claims.

## Future schema phases
CellType → Neuron/Glia → Synapse → Pathway/Circuit → Neurotransmitter/Receptor →
IonChannel/Transporter/Enzyme → MolecularProcess → Model/Variable/Parameter/Equation →
Intervention/Simulation/SimulationResult → Disease/Injury/PathologicalState.
