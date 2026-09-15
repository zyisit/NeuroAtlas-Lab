#!/usr/bin/env python3
"""Regenerate schemas/*.json for NeuroAtlas Lab schema v0.7.

The schemas are hand-designed; this script exists so that shared conventions
(camelCase, additionalProperties:false, common $defs, provenance block) are
applied uniformly and cannot drift between files. Edit the definitions here,
then run:  python scripts/gen_schemas.py
"""
import json
from pathlib import Path

VERSION = "0.7"
DRAFT = "https://json-schema.org/draft/2020-12/schema"
OUT = Path(__file__).resolve().parent.parent / "schemas"

ID = {"$ref": "common.json#/$defs/id"}
STR = {"$ref": "common.json#/$defs/nonEmptyString"}
URI = {"$ref": "common.json#/$defs/uri"}
PROV = {"$ref": "common.json#/$defs/provenance"}
SPECIES = {"$ref": "common.json#/$defs/species"}
CONTEXT = {"$ref": "common.json#/$defs/context"}
EXTIDS = {"$ref": "common.json#/$defs/externalIdentifiers"}
RECORD_STATUS = {"$ref": "common.json#/$defs/recordStatus"}
ASSERTION = {"$ref": "common.json#/$defs/assertionType"}
EVIDENCE_STATUS = {"$ref": "common.json#/$defs/evidenceStatus"}
CONFIDENCE = {"$ref": "common.json#/$defs/confidence"}
LICENSE = {"$ref": "common.json#/$defs/license"}


def idlist(desc):
    return {"type": "array", "items": ID, "uniqueItems": True, "description": desc}


def strlist(desc):
    return {"type": "array", "items": STR, "uniqueItems": True, "description": desc}


COMMON = {
    "$schema": DRAFT,
    "$id": "common.json",
    "title": "NeuroAtlas common definitions",
    "$defs": {
        "id": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9-]*:[a-z0-9][a-z0-9._-]*$",
            "description": "Stable local identifier of the form <record-type>:<slug>, e.g. brain-region:hippocampus. Never encode an external database ID here; use externalIdentifiers.",
        },
        "nonEmptyString": {"type": "string", "minLength": 1},
        "uri": {"type": "string", "format": "uri"},
        "date": {"type": "string", "format": "date"},
        "provenance": {
            "type": "object",
            "description": "Who/what created this record and when. Curatorial provenance, not scientific provenance (that lives in evidence/dataset records).",
            "properties": {
                "createdAt": {"type": "string", "format": "date-time"},
                "createdBy": {"$ref": "#/$defs/nonEmptyString"},
                "updatedAt": {"type": "string", "format": "date-time"},
                "updatedBy": {"$ref": "#/$defs/nonEmptyString"},
                "method": {"type": "string", "description": "e.g. manual curation, script name and version, import pipeline"},
                "notes": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "externalIdentifier": {
            "type": "object",
            "required": ["namespace", "identifier"],
            "properties": {
                "namespace": {"$ref": "#/$defs/nonEmptyString", "description": "e.g. UBERON, NeuroNames, Allen, JulichBrain, ChEBI, IUPHAR, GO, MONDO, DOID, PubMed, DOI"},
                "identifier": {"$ref": "#/$defs/nonEmptyString"},
                "url": {"$ref": "#/$defs/uri"},
                "sourceVersion": {"type": "string"},
            },
            "additionalProperties": False,
        },
        "externalIdentifiers": {"type": "array", "items": {"$ref": "#/$defs/externalIdentifier"}},
        "species": {
            "type": "string",
            "minLength": 1,
            "description": "Binomial name or NCBI Taxonomy label (e.g. 'Homo sapiens', 'Mus musculus'). Use 'multiple' only on records that explicitly aggregate across species.",
        },
        "context": {
            "type": "object",
            "description": "Experimental / interpretive context on which a statement depends.",
            "properties": {
                "preparation": {"enum": ["in_vivo", "ex_vivo", "in_vitro", "post_mortem", "in_silico", "clinical", "mixed", "unknown"]},
                "developmentalStage": {"type": "string"},
                "sex": {"enum": ["female", "male", "mixed", "unknown", "not_applicable"]},
                "strain": {"type": "string"},
                "condition": {"type": "string", "description": "e.g. healthy, disease model name, anaesthetised"},
                "notes": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "recordStatus": {
            "enum": ["draft", "proposed", "active", "deprecated", "superseded", "retracted"],
            "description": "Lifecycle of the record itself, not the truth of its content.",
        },
        "assertionType": {
            "enum": ["observed", "curated", "inferred", "model_derived", "hypothetical"],
            "description": "How the assertion came to exist. Required on every relationship/connection so model output is never confused with observation. Not a truth score.",
        },
        "evidenceStatus": {
            "enum": ["established", "well_supported", "supported", "emerging", "uncertain", "contested", "model_derived", "hypothetical"],
            "description": "Communication metadata about the weight of evidence behind a claim. See docs/scientific-governance/principles.md.",
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "Optional curator confidence. Omit rather than guess."},
        "license": {
            "type": "object",
            "required": ["spdx"],
            "properties": {
                "spdx": {"$ref": "#/$defs/nonEmptyString", "description": "SPDX identifier, e.g. CC-BY-4.0, CC-BY-NC-4.0, ODbL-1.0, or 'custom' with a url"},
                "url": {"$ref": "#/$defs/uri"},
                "attributionText": {"type": "string", "description": "Verbatim attribution the licensor requires"},
                "commercialUseAllowed": {"type": "boolean", "description": "Explicitly recorded so downstream tiers can filter data by permitted use"},
                "notes": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
}


def schema(name, title, required, props, description):
    return {
        "$schema": DRAFT,
        "$id": f"{name}.json",
        "title": title,
        "description": description,
        "type": "object",
        "required": required,
        "additionalProperties": False,
        "properties": props,
    }


SCHEMAS = {}

SCHEMAS["dataset"] = schema(
    "dataset", "Dataset", ["id", "name", "license"],
    {
        "id": ID,
        "name": STR,
        "description": {"type": "string"},
        "publisher": {"type": "string", "description": "Institution or project, e.g. Allen Institute, EBRAINS"},
        "homepage": URI,
        "license": {**LICENSE, "description": "Default license for the dataset; a DatasetVersion may override."},
        "externalIdentifiers": EXTIDS,
        "provenance": PROV,
    },
    "An enduring data source or collection (an atlas project, a database, a repository). Concrete releases are DatasetVersion records.",
)

SCHEMAS["dataset-version"] = schema(
    "dataset-version", "DatasetVersion", ["id", "datasetId", "version", "retrievedAt"],
    {
        "id": ID,
        "datasetId": ID,
        "version": STR,
        "releaseDate": {"$ref": "common.json#/$defs/date"},
        "retrievedAt": {"$ref": "common.json#/$defs/date", "description": "Date this version was retrieved by the project. Required: it anchors reproducibility."},
        "accessUrl": URI,
        "contentHash": {"type": "string", "description": "Hash of the retrieved payload where feasible"},
        "license": {**LICENSE, "description": "Override when a specific release carries different terms"},
        "transformations": strlist("Human-readable list of processing steps applied by this project after retrieval"),
        "notes": {"type": "string"},
        "provenance": PROV,
    },
    "One immutable, date-bounded release of a Dataset. Never overwrite a published DatasetVersion; create a new one.",
)

SCHEMAS["source"] = schema(
    "source", "Source", ["id", "sourceType", "title"],
    {
        "id": ID,
        "sourceType": {"enum": ["primary_research", "systematic_review", "meta_analysis", "textbook", "curated_database", "atlas", "experimental_dataset", "computational_model", "clinical_guideline", "educational_resource"]},
        "title": STR,
        "authors": strlist("Author names as published"),
        "year": {"type": "integer", "minimum": 1800, "maximum": 2100},
        "citation": {"type": "string", "description": "Formatted citation string"},
        "url": URI,
        "datasetVersionId": {**ID, "description": "When the source is a dataset release already recorded"},
        "externalIdentifiers": EXTIDS,
        "license": LICENSE,
        "provenance": PROV,
    },
    "A citable publication, database, or resource. EvidenceRecords point here.",
)

SCHEMAS["reference-space"] = schema(
    "reference-space", "ReferenceSpace", ["id", "name", "coordinateSystem", "species"],
    {
        "id": ID,
        "name": STR,
        "coordinateSystem": {**STR, "description": "e.g. MNI152 NLin2009cAsym, Talairach, CCFv3, native-scanner"},
        "species": SPECIES,
        "unit": {"enum": ["mm", "um", "voxel"]},
        "description": {"type": "string"},
        "datasetVersionId": ID,
        "externalIdentifiers": EXTIDS,
        "provenance": PROV,
    },
    "A named coordinate frame. Reference anatomy is not an individual brain; every space records the species and template it is defined on.",
)

SCHEMAS["spatial-transformation"] = schema(
    "spatial-transformation", "SpatialTransformation", ["id", "sourceReferenceSpaceId", "targetReferenceSpaceId", "method"],
    {
        "id": ID,
        "sourceReferenceSpaceId": ID,
        "targetReferenceSpaceId": ID,
        "method": {**STR, "description": "e.g. affine, SyN nonlinear, identity"},
        "datasetVersionId": ID,
        "parametersUrl": URI,
        "invertible": {"type": "boolean"},
        "notes": {"type": "string"},
        "provenance": PROV,
    },
    "A directed registration between two reference spaces.",
)

SCHEMAS["atlas"] = schema(
    "atlas", "Atlas", ["id", "name", "species", "referenceSpaceId", "datasetVersionId"],
    {
        "id": ID,
        "name": STR,
        "species": SPECIES,
        "referenceSpaceId": ID,
        "datasetVersionId": ID,
        "parcellationVersion": {"type": "string"},
        "description": {"type": "string"},
        "externalIdentifiers": EXTIDS,
        "provenance": PROV,
    },
    "A named parcellation of a reference space (e.g. Julich-Brain 3.0, Allen CCFv3). Regions map into atlases via AtlasMapping.",
)

SCHEMAS["brain-region"] = schema(
    "brain-region", "BrainRegion", ["id", "name", "species", "status"],
    {
        "id": ID,
        "name": STR,
        "aliases": strlist("Synonyms and abbreviations"),
        "description": {"type": "string"},
        "species": SPECIES,
        "hemisphere": {"enum": ["left", "right", "bilateral", "midline", "not_applicable"]},
        "anatomicalClass": {"type": "string", "description": "Coarse class, e.g. cortex, subcortex, brainstem, cerebellum, white_matter, ventricle"},
        "parentRegionIds": idlist("Containing regions in the project's canonical hierarchy. Atlas-specific hierarchy belongs in AtlasMapping."),
        "atlasMappingIds": idlist("AtlasMapping records tying this region to specific parcellations"),
        "spatialRepresentationIds": idlist("Geometry available for this region"),
        "externalIdentifiers": EXTIDS,
        "evidenceRecordIds": idlist("Evidence for the region's definition, if disputed or non-trivial"),
        "status": RECORD_STATUS,
        "provenance": PROV,
    },
    "A project-level anatomical region. Identity is NeuroAtlas-owned; atlas labels are mappings, not identity.",
)

SCHEMAS["atlas-mapping"] = schema(
    "atlas-mapping", "AtlasMapping", ["id", "brainRegionId", "atlasId", "mappingType"],
    {
        "id": ID,
        "brainRegionId": ID,
        "atlasId": ID,
        "atlasRegionId": {"type": "string", "description": "The region identifier as used inside the atlas"},
        "label": {"type": "string", "description": "The atlas's own label for the region"},
        "atlasParentRegionId": {"type": "string", "description": "Parent within the atlas's own hierarchy"},
        "mappingType": {"enum": ["exact", "overlap", "approximate", "curated"]},
        "datasetVersionId": ID,
        "displayColor": {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$", "description": "The atlas's own display colour for this region, for the viewer"},
        "notes": {"type": "string"},
        "provenance": PROV,
    },
    "Assignment of a BrainRegion to a region in a specific Atlas.",
)

SCHEMAS["spatial-representation"] = schema(
    "spatial-representation", "SpatialRepresentation", ["id", "referenceSpaceId", "datasetVersionId", "geometry"],
    {
        "id": ID,
        "subjectId": {**ID, "description": "The entity this geometry represents (usually a BrainRegion)"},
        "referenceSpaceId": ID,
        "datasetVersionId": ID,
        "transformationIds": idlist("Transformations required to interpret this geometry in referenceSpaceId"),
        "geometry": {
            "type": "object",
            "required": ["type"],
            "properties": {
                "type": {"enum": ["point", "bounding_box", "volume", "surface", "mask", "external"]},
                "coordinates": {"type": "array", "items": {"type": "number"}},
                "uri": {**URI, "description": "Location of the asset (mesh, NIfTI, etc.). Large assets are never committed to the repo."},
                "format": {"type": "string", "description": "e.g. glb, obj, nii.gz, ply"},
                "resolutionUm": {"type": "number"},
            },
            "additionalProperties": True,
        },
        "provenance": PROV,
    },
    "A geometric or coordinate payload for an entity in a reference space.",
)

SCHEMAS["brain-function"] = schema(
    "brain-function", "BrainFunction", ["id", "name", "status"],
    {
        "id": ID,
        "name": STR,
        "aliases": strlist("Synonyms"),
        "description": {"type": "string"},
        "category": {"enum": ["sensory", "motor", "cognitive", "affective", "memory", "language", "autonomic", "homeostatic", "arousal", "other"]},
        "externalIdentifiers": {**EXTIDS, "description": "e.g. Cognitive Atlas, NeuroLex"},
        "status": RECORD_STATUS,
        "provenance": PROV,
    },
    "A named function or process that entities can be associated with via relationships. Functional association is a claim, not an anatomical fact.",
)

SCHEMAS["connection"] = schema(
    "connection", "Connection", ["id", "sourceId", "targetId", "direction", "connectionType", "species", "assertionType"],
    {
        "id": ID,
        "sourceId": ID,
        "targetId": ID,
        "direction": {"enum": ["directed", "bidirectional", "undirected", "unknown"]},
        "connectionType": {"enum": ["anatomical_projection", "structural_connectivity", "functional_connectivity", "effective_connectivity", "synaptic_connection", "network_relationship"]},
        "species": SPECIES,
        "context": CONTEXT,
        "assertionType": ASSERTION,
        "method": {"type": "string", "description": "e.g. tract tracing, diffusion tractography, resting-state fMRI"},
        "strength": {"type": "number"},
        "strengthUnit": {"type": "string"},
        "neurotransmitterIds": idlist("Reserved for Phase 4; molecule records"),
        "evidenceRecordIds": idlist("Evidence supporting this connection"),
        "claimIds": idlist("Claims this connection instantiates"),
        "datasetVersionId": {**ID, "description": "The dataset release this edge was read from, for imported connectomes (added 0.10.0)"},
        "confidence": CONFIDENCE,
        "status": RECORD_STATUS,
        "provenance": PROV,
    },
    "A typed edge between two anatomical or cellular entities. Species and assertionType are required because connectivity findings do not transfer silently across species or methods.",
)

SCHEMAS["observation"] = schema(
    "observation", "Observation", ["id", "observationType", "datasetVersionId"],
    {
        "id": ID,
        "observationType": {"enum": ["measurement", "annotation", "derived", "reported"]},
        "datasetVersionId": ID,
        "sourceId": ID,
        "subjectId": {**ID, "description": "Entity the observation is about"},
        "species": SPECIES,
        "context": CONTEXT,
        "value": {},
        "unit": {"type": "string"},
        "method": {"type": "string"},
        "spatialRepresentationId": ID,
        "notes": {"type": "string"},
        "provenance": PROV,
    },
    "The atomic record of a measured, annotated, computed, or reported result.",
)

SCHEMAS["claim"] = schema(
    "claim", "Claim", ["id", "statement", "evidenceStatus", "status"],
    {
        "id": ID,
        "statement": STR,
        "subjectIds": idlist("Entities the claim is about"),
        "species": SPECIES,
        "context": CONTEXT,
        "evidenceStatus": EVIDENCE_STATUS,
        "observationIds": idlist("Observations directly supporting the claim"),
        "evidenceRecordIds": idlist("Evidence records for and against"),
        "supersededByClaimId": ID,
        "status": RECORD_STATUS,
        "provenance": PROV,
    },
    "A human-readable scientific statement with an explicit evidence status. Claims are what the UI shows; relationships are how the graph is walked.",
)

SCHEMAS["evidence-record"] = schema(
    "evidence-record", "EvidenceRecord", ["id", "claimId", "sourceId", "evidenceType", "polarity"],
    {
        "id": ID,
        "claimId": ID,
        "sourceId": ID,
        "evidenceType": {"enum": ["anatomical", "electrophysiological", "molecular", "imaging", "behavioral", "clinical", "computational", "curation", "mixed"]},
        "polarity": {"enum": ["supports", "contradicts", "mixed", "uninformative"], "description": "Contradicting evidence is recorded, not discarded."},
        "species": SPECIES,
        "context": CONTEXT,
        "methods": strlist("Methods used in the source"),
        "observationIds": idlist("Specific observations cited"),
        "datasetVersionId": ID,
        "locator": {"type": "string", "description": "Page, figure, table, or record ID within the source"},
        "notes": {"type": "string"},
        "provenance": PROV,
    },
    "Links a Claim to a Source, states whether the source supports or contradicts it, and preserves species/context.",
)

SCHEMAS["relationship"] = schema(
    "relationship", "Relationship", ["id", "subjectId", "predicate", "objectId", "assertionType", "status"],
    {
        "id": ID,
        "subjectId": ID,
        "predicate": {**STR, "description": "Must be a term in docs/ontology/predicate-vocabulary.md. Enforced by scripts/validate.py, not by JSON Schema."},
        "objectId": ID,
        "species": SPECIES,
        "context": CONTEXT,
        "assertionType": ASSERTION,
        "confidence": CONFIDENCE,
        "observationIds": idlist("Supporting observations"),
        "claimIds": idlist("Claims this edge instantiates"),
        "evidenceRecordIds": idlist("Direct evidence for this edge"),
        "status": RECORD_STATUS,
        "provenance": PROV,
    },
    "A generic typed edge between any two entities using the controlled predicate vocabulary.",
)

INDEX = {
    "package": "NeuroAtlas Lab schema package",
    "version": VERSION,
    "schemaDraft": "2020-12",
    "idConvention": "<record-type>:<slug>",
    "recordTypes": {name: f"{name}.json" for name in SCHEMAS},
    "shared": "common.json",
}


def main():
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    (OUT / "common.json").write_text(json.dumps(COMMON, indent=2) + "\n")
    for name, s in SCHEMAS.items():
        (OUT / f"{name}.json").write_text(json.dumps(s, indent=2) + "\n")
    (OUT / "index.json").write_text(json.dumps(INDEX, indent=2) + "\n")
    print(f"wrote {len(SCHEMAS) + 2} files to {OUT}")


if __name__ == "__main__":
    main()
