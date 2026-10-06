# HCP connectivity for Julich-Brain 3.1 — ingestion notes

**Script:** `scripts/import/import_connectivity.py`
**Output:** `data/connectivity/hcp-julich-3.1/` (`provenance.json`, `connections.json`, `streamline-lengths.json`,
`functional-connections.json`)
**License:** CC BY 4.0 (read from siibra at import time; `commercialUseAllowed: true`)
**Dataset:** Domhof JWM, Jung K, Eickhoff SB, Popovych OV (2022). *Parcellation-based structural and
resting-state functional brain connectomes of a healthy cohort (v1.2)*. EBRAINS. doi:10.25493/3PMM-FPW
**Paper:** Domhof JWM, Jung K, Eickhoff SB, Popovych OV (2021). *Parcellation-induced variation of
empirical and simulated brain connectomes at group and subject levels*. Network Neuroscience 5(3):798–830.
doi:10.1162/netn_a_00202

## What the dataset is
Per-subject connectomes for 200 Human Connectome Project subjects, computed for 20 parcellations.
For Julich-Brain the parcels are the 414 regions that carry a label in the maximum-probability map —
exactly the set that has centroids and meshes in `data/anatomy/julich-brain-3.1/`. Structural
connectivity is the streamline count between each pair of parcels from whole-brain probabilistic
tractography (MRtrix3, multi-shell multi-tissue constrained spherical deconvolution) on HCP dwMRI.
The same dataset also ships streamline *lengths* and resting-state functional connectivity; both are
imported since 0.12.0 (sections below).

siibra exposes this as one `StreamlineCounts` compound feature with 200 elements (one per subject),
each a 414×414 symmetric matrix indexed by Julich region. The matrix diagonal is non-zero
(intra-parcel streamlines) and is discarded.

## What is imported
- One `dataset`, one `dataset-version` (v1.2, retrieval date, the group-mean and threshold
  transformations spelled out), and two `source` records: the EBRAINS dataset and the methods paper.
- One `connection` record per retained region pair, written once (the matrix is symmetric):
  - `direction: undirected` — tractography shows where a bundle runs, not which way signals travel.
    The viewer must never render these as "projects to / receives from".
  - `connectionType: structural_connectivity`, `assertionType: observed`, `status: active`
  - `strength` = group-mean streamline count; `strengthUnit` says so and names the subject count
  - `context.subjectFraction` = fraction of the 200 subjects in which the pair has ≥ 1 streamline
  - `context.preparation: in_vivo` (the atlas regions themselves are post-mortem; the connectivity is not)
  - `datasetVersionId` (field added to the connection schema in 0.10.0)
  - `method` in short form; the full pipeline description is on the dataset-version record

## Thresholds
Default: keep a pair if mean count ≥ 20 **and** it is present in ≥ 90% of subjects. On the 200-subject
group this retains 10,990 of 85,491 possible pairs. Both thresholds are flags on the script. Sweep on
the full cohort (pairs retained):

| subject fraction ≥ | mean ≥ 5 | ≥ 10 | ≥ 20 | ≥ 50 | ≥ 100 |
|---|---|---|---|---|---|
| 0.50 | 19,613 | 15,109 | 11,325 | 7,347 | 5,095 |
| 0.75 | 19,136 | 14,973 | 11,265 | 7,332 | 5,091 |
| **0.90** | 16,063 | 14,059 | **10,990** | 7,251 | 5,074 |
| 0.95 | 13,323 | 12,723 | 10,529 | 7,098 | 5,007 |
| 1.00 | 6,935 | 6,934 | 6,832 | 5,805 | 4,485 |

The 0.9 / 20 cell was chosen because it drops the noise floor (pairs that exist in only some
subjects with a handful of streamlines) without cutting into edges that are reliably reconstructed.
`subjectFraction` is stored on every edge so a stricter cut can be applied without re-importing.

## Regions with no connections
50 of the 414 parcels have fewer than 10 mean streamlines to *any* other parcel and get no edges at
any sensible threshold: small thalamic nuclei (VAmc, Pv, PUa, VM, Sg, Po, Li, Pf, sPf, CM, MV, VPM,
VPMpc, CGM), amygdalar groups (SF, MF, VTM), HATA, piriform sub-areas, the red nucleus parts, the
cerebellar nuclei (dentate, interposed, fastigial) and the basal-forebrain tuberculum. This is the
known small-parcel / deep-structure limitation of dwMRI tractography, not evidence that those regions
are isolated. The viewer states this on the region rather than showing an empty list.

## Known limitations of the strength value
- Streamline counts scale with parcel volume and seeding density; they are comparable within this
  dataset only and are not a fibre count.
- Interhemispheric and long-range edges are systematically under-reconstructed by tractography.
- The group mean is over healthy young adults (HCP); it is not a reference for any individual.

## What is deliberately not imported
- Individual-subject matrices (200 × 85k values). Only the group summary is kept; the script can be
  re-run at any threshold.
- The four single-run functional paradigms (REST1/REST2 × LR/RL). They are read only by
  `--fc-reliability`, to check the concatenated result against itself.
- Anything that would let an edge be read as directed.

## Streamline lengths (0.12.0)
**Decision:** one `observation` per structural connection, not a second structural edge set. A
`connection` carries one `strength`; a second undirected edge for the same pair in the same dataset
version would break validator rule 7 anyway, and two edges for one bundle would double-count it in
the viewer. The observation's `subjectId` is the connection (the schema defines it as "entity the
observation is about"; the validator accepts any record type there).

- `observationType: measurement`, `unit: mm`, `method` and `datasetVersionId` as for the edges,
  `sourceId` = the EBRAINS dataset source, `context.subjectCount` = subjects that contributed.
- Value = mean over the subjects in which the pair has ≥ 1 streamline. The source matrices hold 0
  where a subject has no streamline for a pair; that is a missing measurement, not 0 mm, so those
  subjects are left out. (Weighting by streamline count instead changes almost nothing: r = 0.995
  between the two versions over the retained edges.)
- The dataset ships the matrices without a unit field. Millimetres is the MRtrix3 convention and
  matches the range: 4.0 to 229.5 mm, median 90.7 mm over the 10,990 edges.
- It is the length of the reconstructed path, which curves, not the straight-line distance between
  region centres. The viewer says so.

## Resting-state functional connectivity (0.12.0)
siibra exposes five `FunctionalConnectivity` features for Julich-Brain 3.1 (200 subjects each):
`Resting state (EmpCorrFC REST1-LR)`, `REST1-RL`, `REST2-LR`, `REST2-RL` and
`Resting state (EmpCorrFC concatenated)`. Each element is a 414×414 matrix of Pearson correlations.

**Decisions**
- **One paradigm:** the concatenated one (the paradigm label says the four runs are concatenated:
  the most data per subject). Rule 7 allows one undirected edge per pair, type and dataset version,
  so importing more paradigms would need a dataset version each for what is one release. The
  single-run paradigms serve as a reliability check instead (below).
- **Same dataset version as the structural edges.** It is the same EBRAINS release; rule 7 keys on
  `connectionType`, so structural and functional edges for a pair do not collide.
- **Group mean in Fisher-z space:** arctanh per subject, mean over subjects that have a value,
  tanh back. Averaging raw r values is biased towards zero for strong correlations.
- **Signed strength.** `strength` is the group-mean r, sign kept; the threshold is on |r|.
  `context.subjectSignFraction` = share of subjects whose own r has the group-mean sign (the
  functional analogue of `subjectFraction`). `context.paradigm` names the paradigm.
- `connectionType: functional_connectivity`, `direction: undirected` (a correlation has no
  direction), `assertionType: observed`, `context.condition: healthy, eyes-open rest`.

**Threshold:** keep a pair if |r| ≥ 0.3 and the pair has a value in ≥ 90% of subjects → 6,768 of
85,491 pairs. Both are flags (`--fc-min-abs-r`, `--fc-min-valid-fraction`). Sweep (valid ≥ 90%):

| \|r\| ≥ | pairs kept | regions with no edge |
|---|---|---|
| 0.20 | 14,139 | 151 |
| 0.25 | 9,734 | 164 |
| **0.30** | **6,768** | **183** |
| 0.35 | 4,549 | 205 |
| 0.40 | 2,774 | 220 |
| 0.50 | 981 | 251 |

0.3 is a conventional "moderate correlation" cut; lowering it adds mostly cortical pairs among
regions that already have edges and barely reduces the number of regions without any.

**There are no negative edges.** The strongest negative group-mean r anywhere in the matrix is
−0.175, so no negative pair reaches |r| ≥ 0.3. The near-absence of anticorrelations depends on
preprocessing (global-signal handling in particular), so the sign is meaningful within this dataset
only. The viewer colours functional tubes by sign regardless, so a future import or threshold that
keeps negative pairs is shown correctly.

**Regions with no functional edge (183 of 414).** Two groups: small and deep parcels (60 thalamic
nuclei, 14 amygdalar, 10 basal-forebrain, 8 midbrain, 8 cerebellar) and cortex in the classic
low-signal zones next to the sinuses and ear canals: orbitofrontal (Fo1–Fo4, Fo7), subgenual cingulate
(25, s24, s32), most anterior and dysgranular insular areas, entorhinal cortex and the hippocampal
subfields (CA1–CA3, DG, subiculum), and ventral temporal areas (FG5, CoS1, TI). Noise pulls a group-mean r
towards zero, so these regions rarely reach 0.3. Three parcels have no fMRI value in any subject
(VPM left and right, Area PirTB left). This is a limitation of the method at this parcel size, not
evidence of inactivity; the viewer says so on the region and points to its structural edges.

**Reliability.** Group-mean r computed separately for the two HCP sessions (REST1 = mean of
REST1-LR and RL in Fisher-z, same for REST2) correlates at **0.998** across all pairs. Of the 6,768
retained edges, 6,592 (97%) also reach |r| ≥ 0.3 in *both* sessions on their own; the median
difference |r(REST1) − r(REST2)| over the retained edges is 0.015. Reproduce with
`python scripts/import/import_connectivity.py --fc-reliability` (reads the four single-run
paradigms too, ~5 minutes more).

**How structural and functional relate here.** 3,772 pairs (56% of functional edges, 34% of
structural edges) appear in both sets. Functional edges are more often interhemispheric (3,064 vs
2,616), as expected: homotopic regions correlate strongly at rest, while tractography
under-reconstructs callosal and long-range fibres. Neither set is a ground truth for the other.

## Viewer bundle size
The viewer bundle packs each data file's repeated fields (`scripts/build/build_viewer_bundle.py`,
lossless, checked by `tests/test_connectivity.py`), so adding 17,758 records made the bundle
smaller than it was in 0.11.0.
