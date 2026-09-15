#!/usr/bin/env python3
"""Emit data/function/curated-claims-v1.json.

Hand-curated claims for four well-studied regions. Every claim links to at
least one source with a verified DOI. Claims are written with record status
`proposed`; the curator flips them to `active` after review (docs/curation.md).
Edit this script, not the JSON.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "function" / "curated-claims-v1.json"
# Curator review: add a claim's slug here once you have read its sources and
# confirmed the statement says what they say. Everything not listed stays
# `proposed`. Slugs are the part after "claim:" (see the claim(...) calls below).
REVIEWED_ACTIVE = {
    # "hf-bilateral-mtl-damage-anterograde-amnesia",
    # "ca1-bilateral-lesion-sufficient-for-amnesia",
    # "hf-place-cells-rat",
    # "hf-posterior-volume-taxi-drivers",
    # "hoc1-is-brodmann-17",
    # "v1-orientation-selectivity",
    # "v1-retinotopic-map-human",
    # "m1-stimulation-somatotopic-order",
    # "m1-continuous-homunculus",
    # "amygdala-required-for-cued-fear-conditioning-rat",
    # "amygdala-damage-impairs-fear-recognition-human",
    # "amygdala-is-the-fear-centre",
}

PROV = {"createdAt": "2026-09-14T00:00:00Z", "createdBy": "NeuroAtlas curation v1 (AI-assisted draft; pending human review)", "method": "manual curation from primary literature; DOIs verified 2026-09-14"}

HF = "brain-region:julich-hippocampal-formation"
CA1 = "brain-region:julich-ca1-hippocampus"
V1 = "brain-region:julich-area-hoc1-v1-17-calcs"
M1A = "brain-region:julich-area-4a-precg"
M1P = "brain-region:julich-area-4p-precg"
AMY = "brain-region:julich-amygdala"

HUMAN, RAT, CAT, MAC = "Homo sapiens", "Rattus norvegicus", "Felis catus", "Macaca mulatta"

records = []


def fn(slug, name, category, aliases=None, ext=None):
    r = {"id": f"brain-function:{slug}", "name": name, "category": category, "status": "active", "provenance": PROV}
    if aliases: r["aliases"] = aliases
    if ext: r["externalIdentifiers"] = ext
    records.append(r); return r["id"]


def src(slug, stype, title, authors, year, citation, doi, url=None):
    r = {"id": f"source:{slug}", "sourceType": stype, "title": title, "authors": authors, "year": year, "citation": citation,
         "url": url or f"https://doi.org/{doi}", "externalIdentifiers": [{"namespace": "DOI", "identifier": doi}], "provenance": PROV}
    records.append(r); return r["id"]


def claim(slug, statement, subjects, species, status, context=None):
    r = {"id": f"claim:{slug}", "statement": statement, "subjectIds": subjects, "species": species, "evidenceStatus": status,
         "evidenceRecordIds": [], "status": "active" if slug in REVIEWED_ACTIVE else "proposed", "provenance": PROV}
    if context: r["context"] = context
    records.append(r); return r


def ev(c, source_id, etype, polarity, species, prep, locator=None, methods=None, notes=None):
    n = len(c["evidenceRecordIds"]) + 1
    r = {"id": f"evidence-record:{c['id'].split(':',1)[1]}-{n}", "claimId": c["id"], "sourceId": source_id, "evidenceType": etype,
         "polarity": polarity, "species": species, "context": {"preparation": prep}, "provenance": PROV}
    if locator: r["locator"] = locator
    if methods: r["methods"] = methods
    if notes: r["notes"] = notes
    records.append(r); c["evidenceRecordIds"].append(r["id"])


def rel(slug, subj, pred, obj, species, claims, assertion="curated"):
    # A relationship goes active once every claim it rests on is active.
    active = all(c.split(":", 1)[1] in REVIEWED_ACTIVE for c in claims)
    records.append({"id": f"relationship:{slug}", "subjectId": subj, "predicate": pred, "objectId": obj, "species": species,
                    "assertionType": assertion, "claimIds": claims, "status": "active" if active else "proposed", "provenance": PROV})


# ---------------------------------------------------------------- functions
F_EPI = fn("episodic-memory", "Episodic memory", "memory", ["declarative memory (episodic)"])
F_NAV = fn("spatial-navigation", "Spatial navigation", "cognitive", ["spatial memory", "wayfinding"])
F_VIS = fn("vision", "Vision", "sensory", ["visual perception"])
F_MOV = fn("voluntary-movement", "Voluntary movement", "motor", ["skeletomotor control"])
F_FEAR = fn("fear-processing", "Fear processing", "affective", ["threat processing", "fear conditioning"])
F_FACE = fn("facial-emotion-recognition", "Recognition of emotion from facial expressions", "affective")

# ---------------------------------------------------------------- sources
S_SM57 = src("scoville-milner-1957", "primary_research", "Loss of recent memory after bilateral hippocampal lesions",
             ["Scoville WB", "Milner B"], 1957, "Scoville WB, Milner B (1957). J Neurol Neurosurg Psychiatry 20(1):11-21.", "10.1136/jnnp.20.1.11")
S_SQ91 = src("squire-zola-morgan-1991", "systematic_review", "The medial temporal lobe memory system",
             ["Squire LR", "Zola-Morgan S"], 1991, "Squire LR, Zola-Morgan S (1991). Science 253(5026):1380-1386.", "10.1126/science.1896849")
S_ZM86 = src("zola-morgan-1986", "primary_research", "Human amnesia and the medial temporal region: enduring memory impairment following a bilateral lesion limited to field CA1 of the hippocampus",
             ["Zola-Morgan S", "Squire LR", "Amaral DG"], 1986, "Zola-Morgan S, Squire LR, Amaral DG (1986). J Neurosci 6(10):2950-2967.", "10.1523/JNEUROSCI.06-10-02950.1986")
S_RC96 = src("rempel-clower-1996", "primary_research", "Three cases of enduring memory impairment after bilateral damage limited to the hippocampal formation",
             ["Rempel-Clower NL", "Zola SM", "Squire LR", "Amaral DG"], 1996, "Rempel-Clower NL, Zola SM, Squire LR, Amaral DG (1996). J Neurosci 16(16):5233-5255.", "10.1523/JNEUROSCI.16-16-05233.1996")
S_OD71 = src("okeefe-dostrovsky-1971", "primary_research", "The hippocampus as a spatial map. Preliminary evidence from unit activity in the freely-moving rat",
             ["O'Keefe J", "Dostrovsky J"], 1971, "O'Keefe J, Dostrovsky J (1971). Brain Res 34(1):171-175.", "10.1016/0006-8993(71)90358-1")
S_MKM08 = src("moser-2008", "systematic_review", "Place cells, grid cells, and the brain's spatial representation system",
              ["Moser EI", "Kropff E", "Moser MB"], 2008, "Moser EI, Kropff E, Moser MB (2008). Annu Rev Neurosci 31:69-89.", "10.1146/annurev.neuro.31.061307.090723")
S_MAG00 = src("maguire-2000", "primary_research", "Navigation-related structural change in the hippocampi of taxi drivers",
              ["Maguire EA", "Gadian DG", "Johnsrude IS", "Good CD", "Ashburner J", "Frackowiak RSJ", "Frith CD"], 2000,
              "Maguire EA et al. (2000). Proc Natl Acad Sci USA 97(8):4398-4403.", "10.1073/pnas.070039597")
S_WM11 = src("woollett-maguire-2011", "primary_research", "Acquiring \"the Knowledge\" of London's layout drives structural brain changes",
             ["Woollett K", "Maguire EA"], 2011, "Woollett K, Maguire EA (2011). Curr Biol 21(24):2109-2114.", "10.1016/j.cub.2011.11.018")
S_AM00 = src("amunts-2000", "primary_research", "Brodmann's areas 17 and 18 brought into stereotaxic space - where and how variable?",
             ["Amunts K", "Malikovic A", "Mohlberg H", "Schormann T", "Zilles K"], 2000, "Amunts K et al. (2000). NeuroImage 11(1):66-84.", "10.1006/nimg.1999.0516")
S_HW62 = src("hubel-wiesel-1962", "primary_research", "Receptive fields, binocular interaction and functional architecture in the cat's visual cortex",
             ["Hubel DH", "Wiesel TN"], 1962, "Hubel DH, Wiesel TN (1962). J Physiol 160(1):106-154.", "10.1113/jphysiol.1962.sp006837")
S_HW68 = src("hubel-wiesel-1968", "primary_research", "Receptive fields and functional architecture of monkey striate cortex",
             ["Hubel DH", "Wiesel TN"], 1968, "Hubel DH, Wiesel TN (1968). J Physiol 195(1):215-243.", "10.1113/jphysiol.1968.sp008455")
S_EN94 = src("engel-1994", "primary_research", "fMRI of human visual cortex",
             ["Engel SA", "Rumelhart DE", "Wandell BA", "Lee AT", "Glover GH", "Chichilnisky EJ", "Shadlen MN"], 1994, "Engel SA et al. (1994). Nature 369(6481):525.", "10.1038/369525a0")
S_SE95 = src("sereno-1995", "primary_research", "Borders of multiple visual areas in humans revealed by functional magnetic resonance imaging",
             ["Sereno MI", "Dale AM", "Reppas JB", "Kwong KK", "Belliveau JW", "Brady TJ", "Rosen BR", "Tootell RBH"], 1995, "Sereno MI et al. (1995). Science 268(5212):889-893.", "10.1126/science.7754376")
S_PB37 = src("penfield-boldrey-1937", "primary_research", "Somatic motor and sensory representation in the cerebral cortex of man as studied by electrical stimulation",
             ["Penfield W", "Boldrey E"], 1937, "Penfield W, Boldrey E (1937). Brain 60(4):389-443.", "10.1093/brain/60.4.389")
S_SH93 = src("schieber-hibbard-1993", "primary_research", "How somatotopic is the motor cortex hand area?",
             ["Schieber MH", "Hibbard LS"], 1993, "Schieber MH, Hibbard LS (1993). Science 261(5120):489-492.", "10.1126/science.8342021")
S_GO23 = src("gordon-2023", "primary_research", "A somato-cognitive action network alternates with effector regions in motor cortex",
             ["Gordon EM", "Chauvin RJ", "Van AN", "Dosenbach NUF", "et al."], 2023, "Gordon EM et al. (2023). Nature 617(7960):351-359.", "10.1038/s41586-023-05964-2")
S_LD00 = src("ledoux-2000", "systematic_review", "Emotion circuits in the brain",
             ["LeDoux JE"], 2000, "LeDoux JE (2000). Annu Rev Neurosci 23:155-184.", "10.1146/annurev.neuro.23.1.155")
S_PL92 = src("phillips-ledoux-1992", "primary_research", "Differential contribution of amygdala and hippocampus to cued and contextual fear conditioning",
             ["Phillips RG", "LeDoux JE"], 1992, "Phillips RG, LeDoux JE (1992). Behav Neurosci 106(2):274-285.", "10.1037/0735-7044.106.2.274")
S_AD94 = src("adolphs-1994", "primary_research", "Impaired recognition of emotion in facial expressions following bilateral damage to the human amygdala",
             ["Adolphs R", "Tranel D", "Damasio H", "Damasio A"], 1994, "Adolphs R, Tranel D, Damasio H, Damasio A (1994). Nature 372(6507):669-672.", "10.1038/372669a0")
S_AD05 = src("adolphs-2005", "primary_research", "A mechanism for impaired fear recognition after amygdala damage",
             ["Adolphs R", "Gosselin F", "Buchanan TW", "Tranel D", "Schyns P", "Damasio AR"], 2005, "Adolphs R et al. (2005). Nature 433(7021):68-72.", "10.1038/nature03086")
S_FE13 = src("feinstein-2013", "primary_research", "Fear and panic in humans with bilateral amygdala damage",
             ["Feinstein JS", "Buzza C", "Hurlemann R", "Follmer RL", "Dahdaleh NS", "Coryell WH", "Welsh MJ", "Tranel D", "Wemmie JA"], 2013,
             "Feinstein JS et al. (2013). Nat Neurosci 16(3):270-272.", "10.1038/nn.3323")
S_PA10 = src("pessoa-adolphs-2010", "systematic_review", "Emotion processing and the amygdala: from a 'low road' to 'many roads' of evaluating biological significance",
             ["Pessoa L", "Adolphs R"], 2010, "Pessoa L, Adolphs R (2010). Nat Rev Neurosci 11(11):773-783.", "10.1038/nrn2920")
S_LP16 = src("ledoux-pine-2016", "systematic_review", "Using neuroscience to help understand fear and anxiety: a two-system framework",
             ["LeDoux JE", "Pine DS"], 2016, "LeDoux JE, Pine DS (2016). Am J Psychiatry 173(11):1083-1093.", "10.1176/appi.ajp.2016.16030353")

# ---------------------------------------------------------------- hippocampus
c = claim("hf-bilateral-mtl-damage-anterograde-amnesia",
          "Bilateral damage to the medial temporal lobe that includes the hippocampal formation produces severe, enduring anterograde amnesia in humans, with relative sparing of general intelligence, perception, and procedural learning.",
          [HF], HUMAN, "established", {"preparation": "clinical"})
ev(c, S_SM57, "clinical", "supports", HUMAN, "clinical", locator="patient H.M. and eight further cases", methods=["bilateral medial temporal resection", "neuropsychological testing"])
ev(c, S_ZM86, "clinical", "supports", HUMAN, "post_mortem", locator="patient R.B.", methods=["neuropsychological testing", "histology"])
ev(c, S_SQ91, "mixed", "supports", HUMAN, "mixed", notes="Review integrating human lesion cases and monkey lesion studies into the medial temporal lobe memory system model.")
C_HF_AMN = c["id"]

c = claim("ca1-bilateral-lesion-sufficient-for-amnesia",
          "Bilateral damage confined to the CA1 field of the hippocampus is sufficient to produce enduring anterograde amnesia in humans.",
          [CA1], HUMAN, "well_supported", {"preparation": "post_mortem", "condition": "ischaemic injury"})
ev(c, S_ZM86, "clinical", "supports", HUMAN, "post_mortem", locator="patient R.B.; histology showed the lesion limited to CA1 bilaterally", methods=["neuropsychological testing", "post-mortem histology"])
ev(c, S_RC96, "clinical", "supports", HUMAN, "post_mortem", locator="patients G.D., L.M., W.H.", notes="Damage in these cases extended beyond CA1 within the hippocampal formation; they support hippocampal sufficiency, and R.B. remains the single CA1-limited case.")
C_CA1 = c["id"]

c = claim("hf-place-cells-rat",
          "Hippocampal pyramidal neurons in freely moving rats fire selectively when the animal occupies a particular location in its environment (place cells).",
          [HF, CA1], RAT, "established", {"preparation": "in_vivo", "condition": "awake, freely moving"})
ev(c, S_OD71, "electrophysiological", "supports", RAT, "in_vivo", methods=["single-unit recording in dorsal hippocampus"])
ev(c, S_MKM08, "electrophysiological", "supports", RAT, "in_vivo", notes="Review of four decades of replication and extension, including grid cells in entorhinal cortex.")
C_PLACE = c["id"]

c = claim("hf-posterior-volume-taxi-drivers",
          "Posterior hippocampal grey-matter volume is greater in licensed London taxi drivers than in matched controls and increases with time spent navigating.",
          [HF], HUMAN, "supported", {"preparation": "in_vivo", "condition": "healthy adults"})
ev(c, S_MAG00, "imaging", "supports", HUMAN, "in_vivo", methods=["structural MRI", "voxel-based morphometry", "manual volumetry"], notes="Cross-sectional; n=16 drivers. Anterior hippocampus showed the opposite pattern.")
ev(c, S_WM11, "imaging", "supports", HUMAN, "in_vivo", methods=["longitudinal structural MRI"], notes="Longitudinal design: trainees who qualified showed posterior hippocampal increase; those who failed did not.")
C_TAXI = c["id"]

rel("hf-required-for-episodic-memory", HF, "required_for", F_EPI, HUMAN, [C_HF_AMN, C_CA1])
rel("ca1-required-for-episodic-memory", CA1, "required_for", F_EPI, HUMAN, [C_CA1])
rel("hf-contributes-to-spatial-navigation", HF, "contributes_to", F_NAV, "multiple", [C_PLACE, C_TAXI])

# ---------------------------------------------------------------- V1
c = claim("hoc1-is-brodmann-17",
          "Area hOc1 corresponds to Brodmann area 17, the primary visual cortex, identified cytoarchitectonically by the stria of Gennari in layer IV; its extent varies substantially between individuals in stereotaxic space.",
          [V1], HUMAN, "established", {"preparation": "post_mortem"})
ev(c, S_AM00, "anatomical", "supports", HUMAN, "post_mortem", methods=["observer-independent cytoarchitectonic mapping", "ten post-mortem brains"])
ev(c, "source:amunts-2020-julich-brain", "anatomical", "supports", HUMAN, "post_mortem", notes="The Julich-Brain probability map for hOc1 is built from the same cytoarchitectonic definition.")
C_V1_ANAT = c["id"]

c = claim("v1-orientation-selectivity",
          "Neurons in primary visual cortex respond selectively to the orientation of edges within their receptive field, and cells with similar preferences are grouped in columns.",
          [V1], "multiple", "established", {"preparation": "in_vivo", "condition": "anaesthetised"})
ev(c, S_HW62, "electrophysiological", "supports", CAT, "in_vivo", methods=["single-unit recording"])
ev(c, S_HW68, "electrophysiological", "supports", MAC, "in_vivo", methods=["single-unit recording"], notes="Confirms and extends the cat findings in macaque striate cortex.")
C_V1_ORI = c["id"]

c = claim("v1-retinotopic-map-human",
          "Human primary visual cortex contains a retinotopic map of the contralateral visual hemifield that can be measured non-invasively with fMRI.",
          [V1], HUMAN, "established", {"preparation": "in_vivo", "condition": "healthy adults"})
ev(c, S_EN94, "imaging", "supports", HUMAN, "in_vivo", methods=["phase-encoded fMRI"])
ev(c, S_SE95, "imaging", "supports", HUMAN, "in_vivo", methods=["phase-encoded fMRI", "cortical surface reconstruction"])
C_V1_RET = c["id"]

rel("hoc1-required-for-vision", V1, "required_for", F_VIS, HUMAN, [C_V1_ANAT, C_V1_RET])

# ---------------------------------------------------------------- M1
c = claim("m1-stimulation-somatotopic-order",
          "Electrical stimulation of the human precentral gyrus evokes movements of body parts in a broadly somatotopic order, with the lower limb represented medially and the face laterally.",
          [M1A, M1P], HUMAN, "established", {"preparation": "clinical", "condition": "awake neurosurgery"})
ev(c, S_PB37, "clinical", "supports", HUMAN, "clinical", methods=["intraoperative electrical stimulation"], notes="Origin of the motor homunculus figure.")
ev(c, S_GO23, "imaging", "supports", HUMAN, "in_vivo", methods=["precision fMRI"], notes="Confirms distinct foot, hand and mouth effector zones in the expected medial-to-lateral order.")
C_M1_SOMA = c["id"]

c = claim("m1-continuous-homunculus",
          "The motor cortex forms a single continuous, orderly somatotopic map (the classic homunculus) along the precentral gyrus.",
          [M1A, M1P], "multiple", "contested", {"preparation": "mixed"})
ev(c, S_PB37, "clinical", "supports", HUMAN, "clinical", notes="The original stimulation maps were drawn as a continuous strip.")
ev(c, S_SH93, "electrophysiological", "contradicts", MAC, "in_vivo", methods=["intracortical microstimulation", "single-unit recording"], notes="Representations of individual fingers overlap extensively; the hand area is not cleanly somatotopic at fine scale.")
ev(c, S_GO23, "imaging", "contradicts", HUMAN, "in_vivo", methods=["precision fMRI"], notes="Effector regions are interrupted by inter-effector regions with distinct connectivity (somato-cognitive action network).")
C_M1_CONT = c["id"]

rel("m1-4a-contributes-to-voluntary-movement", M1A, "contributes_to", F_MOV, HUMAN, [C_M1_SOMA])
rel("m1-4p-contributes-to-voluntary-movement", M1P, "contributes_to", F_MOV, HUMAN, [C_M1_SOMA])

# ---------------------------------------------------------------- amygdala
c = claim("amygdala-required-for-cued-fear-conditioning-rat",
          "The amygdala is required for the acquisition and expression of conditioned fear responses to discrete external cues in rats.",
          [AMY], RAT, "established", {"preparation": "in_vivo"})
ev(c, S_PL92, "behavioral", "supports", RAT, "in_vivo", methods=["electrolytic lesions", "Pavlovian fear conditioning"], notes="Amygdala lesions abolished cued and contextual conditioning; hippocampal lesions affected contextual only.")
ev(c, S_LD00, "mixed", "supports", RAT, "mixed", notes="Review of the lesion, tracing and physiology literature on the amygdala fear circuit.")
C_AMY_COND = c["id"]

c = claim("amygdala-damage-impairs-fear-recognition-human",
          "Bilateral amygdala damage in humans impairs recognition of fear in facial expressions.",
          [AMY], HUMAN, "well_supported", {"preparation": "clinical"})
ev(c, S_AD94, "clinical", "supports", HUMAN, "clinical", locator="patient S.M. (Urbach-Wiethe disease)", methods=["facial expression rating tasks"])
ev(c, S_AD05, "behavioral", "supports", HUMAN, "clinical", locator="patient S.M.", methods=["eye tracking", "bubbles method"], notes="The deficit reflects failure to fixate the eye region; instructing fixation restored fear recognition.")
C_AMY_FACE = c["id"]

c = claim("amygdala-is-the-fear-centre",
          "The amygdala is the brain's fear centre, necessary for the subjective experience of fear.",
          [AMY], HUMAN, "contested", {"preparation": "mixed"})
ev(c, S_LD00, "mixed", "supports", RAT, "mixed", notes="Supports a central role in threat detection and conditioned fear responses in rodents, which is often extended to human fear experience.")
ev(c, S_FE13, "clinical", "contradicts", HUMAN, "clinical", locator="patients S.M., A.M., B.G.", methods=["35% CO2 inhalation challenge"], notes="Fear and panic were evoked, and panic was more frequent than in controls, despite bilateral amygdala lesions.")
ev(c, S_PA10, "mixed", "contradicts", HUMAN, "mixed", notes="Argues for a broader role in evaluating biological relevance rather than fear specifically.")
ev(c, S_LP16, "mixed", "contradicts", HUMAN, "mixed", notes="Distinguishes defensive-survival circuits from the conscious feeling of fear; the amygdala is central to the former, not established for the latter.")
C_AMY_CENTRE = c["id"]

rel("amygdala-contributes-to-fear-processing", AMY, "contributes_to", F_FEAR, "multiple", [C_AMY_COND, C_AMY_FACE, C_AMY_CENTRE])
rel("amygdala-contributes-to-facial-emotion-recognition", AMY, "contributes_to", F_FACE, HUMAN, [C_AMY_FACE])

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
from collections import Counter
print(f"wrote {len(records)} records:", dict(Counter(r["id"].split(":")[0] for r in records)))
