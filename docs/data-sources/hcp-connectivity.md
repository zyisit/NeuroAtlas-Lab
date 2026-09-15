# HCP structural connectivity for Julich-Brain 3.1 — ingestion notes

**Script:** `scripts/import/import_connectivity.py`
**Output:** `data/connectivity/hcp-julich-3.1/` (`provenance.json`, `connections.json`)
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
The same dataset also ships streamline *lengths* and resting-state functional connectivity; neither is
imported yet.

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
- Streamline lengths and functional connectivity (planned: same script, new `connectionType`).
- Anything that would let an edge be read as directed.
