# Allen Human Reference Atlas – 3D, 2020 ingestion notes

**Script:** `scripts/import/import_allen_hra_3d.py` (no siibra; reads the release files directly)
**Output:** `data/anatomy/allen-hra-3d-2020/`
**License:** CC BY 4.0 (stated on the release page as of 2022-09-01; `commercialUseAllowed: true`)
**Citation:** Ding S-L, Royall JJ, Sunkin SM, Facer BAC, Lesnar P, Bernard A, Ng L, Lein ES (2020).
"Allen Human Reference Atlas – 3D, 2020", RRID:SCR_017764, version 1.0.0.
Ontology: Ding et al. (2016) J Comp Neurol 524:3127–3481. doi:10.1002/cne.24080
**Release directory:** https://download.alleninstitute.org/informatics-archive/allen_human_reference_atlas_3d_2020/version_1/

## Why this atlas is the second parcellation (decision, 2026-09-16)

The roadmap asked whether "the Allen Human Brain Atlas" should become the second
parcellation, and whether siibra exposes it. Findings:

- siibra has **no Allen human parcellation**. Its only Allen parcellations are Allen Mouse
  CCF v3. Its only Allen human data is the microarray gene-expression feature, which goes
  through the Allen web API (currently broken — siibra-python issue #636) and sits under the
  general Allen Terms of Use (non-commercial, derivative works included).
- The **Allen Human Reference Atlas – 3D, 2020** is a different resource: a 0.5 mm voxel
  parcellation of the whole adult brain into 141 structures, downloadable as NIfTI with its
  ontology in the same directory, and explicitly re-licensed **CC BY 4.0** on 2022-09-01.
  That makes it the first anatomy dataset in the project that could back a commercial tier
  (Julich-Brain is CC BY-NC-SA).
- It complements Julich rather than duplicating it: gyral-level cortex, cerebral nuclei,
  diencephalon, brainstem nuclei, cerebellum, named white-matter tracts and the ventricles,
  with a hierarchy and display colours. Julich is cytoarchitectonic and cortex-heavy.

Alternatives in siibra that were checked and set aside: DiFuMo (CC BY 4.0, but functional
modes, not anatomy), Desikan-Killiany (68 cortical labels only), Harvard-Oxford (FSL licence,
non-commercial), Von Economo–Koskinas (CC BY-NC-SA), and the Julich deep/superficial
fibre-bundle atlases (CC BY-NC-SA / CC BY-NC — usable later as named tracts, same paid-tier
problem as Julich).

**Atlas-neutral region ids were dropped from the plan.** The two atlases do not parcellate
the same way (Allen: hippocampus head / body / tail; Julich: CA1 / CA2 / CA3 / DG / subiculum),
so a shared id would be a fiction. Ids stay atlas-scoped (`julich-*`, `allen-*`) and the
atlases are joined by computed `overlaps` relationships instead (below).

## What is imported
- 205 ontology nodes: the 141 annotated structures and their 64 ancestors below "brain".
  The developmental scaffolding above it (neural plate, neural tube, brain) is skipped, so the
  roots are forebrain, midbrain and hindbrain.
- Each annotated structure is split into a **left** and a **right** leaf at x = 0 (RAS), giving
  268 hemisphere leaves; ventricles, commissures and the pineal body (`3V`, `Aq`, `4V`, `cec`,
  `ac`, `cc`, `Pin`) stay single **midline** leaves. 473 regions in total.
- Names, acronyms, colours and hierarchy come from `examples/voxel_count/voxel_count.csv`
  inside the CC BY 4.0 release directory. No call is made to the Allen API, so nothing in
  these records depends on the general Allen Terms of Use.
- One atlas-mapping per region; `mappingType` is `exact` for Allen's own structures and
  `approximate` for the hemisphere halves, whose notes state that the split is ours.
- Centroid (mean voxel position) and volume (voxel count × 0.125 mm³) for every leaf.
- Region ids are `brain-region:allen-<acronym>[-left|-right]`. Two acronym pairs collide
  case-insensitively (`MTG`/`MTg`, `LIG`/`LiG`); those get the Allen structure id appended.

## Caveats the records carry
- **Different template.** The atlas is drawn on ICBM 2009b Nonlinear *Symmetric*; Julich-Brain
  is on ICBM 2009c Nonlinear *Asymmetric*. The Allen records have their own reference-space
  record, and `spatial-transformation:mni152-2009b-sym-to-2009c-asym-approx-identity`
  states that the project treats the two as the same millimetre space without registration.
  Expect discrepancies of about a millimetre at boundaries wherever the atlases are compared.
- **The right hemisphere is a mirror.** `annotation_full.nii.gz` is Allen's left-hemisphere
  drawing flipped across x = 0; the importer verifies this voxel-for-voxel and refuses to run
  if the release ever changes. Right-side volumes therefore equal left-side volumes, and the
  observation notes say so.
- The annotation resolves the ontology only to the 141 structures present in the 3D volume;
  finer structures of the 2016 ontology (e.g. hippocampal subfields) exist only in the 2D atlas
  and are not imported.

## Meshes
`python scripts/build/build_meshes.py --atlas allen` writes `viewer/public/assets/allen-hra-3d-2020/{hull,regions}.glb`
(275 region meshes, one per leaf) and `meshes.json`. Smoothing is 1 mm (2 voxels), halved for
structures under 500 mm³ so thin tracts such as the mammillothalamic tract survive.

## Cross-atlas overlaps
`python scripts/build/build_overlaps.py` writes `data/anatomy/cross-atlas/julich31-allen2020-overlaps.json`:
one `relationship` (`predicate: overlaps`, `assertionType: inferred`) per Julich map leaf ×
Allen leaf pair where either region's share of the overlap is ≥ 10%, with
`context.overlapFractionOfSubject`, `overlapFractionOfObject` and `overlapVolumeMm3`.
Computed by nearest-neighbour lookup of Julich 1 mm voxel centres in the Allen 0.5 mm volume,
templates treated as identical (see above). 1,137 relationships cover all 414 Julich leaves and
210 of the 275 Allen leaves; the uncovered Allen leaves are brainstem, cerebellar, ventricular
and white-matter territory that Julich does not map.

The viewer shows these as "In <other atlas>" on every leaf region; clicking one switches atlas.

## What is deliberately not imported
- The Allen microarray gene-expression data (different resource, different licence, API down).
- The single-hemisphere `annotation.nii.gz`; the mirrored full volume is used so both
  hemispheres have geometry, and the mirroring is recorded.
