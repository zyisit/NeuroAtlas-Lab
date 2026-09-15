# Julich-Brain 3.1 ingestion notes

**Script:** `scripts/import/import_julich_brain.py`
**Output:** `data/anatomy/julich-brain-3.1/`
**License:** CC BY-NC-SA 4.0 (read from siibra at import time; `commercialUseAllowed: false`)
**Citation:** Amunts K, Mohlberg H, Bludau S, Zilles K (2020). Science 369:988–992. doi:10.1126/science.abb4588

## What is imported
- Every node of the Julich-Brain 3.1 region tree except the root (771 regions):
  grouping nodes (e.g. "occipital lobe"), bilateral areas (e.g. "Area hOc1 (V1, 17, CalcS)"),
  and their left/right leaves.
- `hemisphere` is inferred from the " left"/" right" name suffix; everything else is `bilateral`.
- `anatomicalClass` is inferred from ancestor names (cerebral cortex → cortex, etc.).
  One node (telencephalon itself) has no mapped class and keeps its own name.
- `parentRegionIds` reproduces the Julich hierarchy. `atlasParentRegionId` on the mapping
  holds the same link in Julich's own key space.
- `displayColor` on each mapping is Julich's published region colour.
- With `--spatial`: for each leaf region mapped in MNI152 ICBM 2009c asym, a centroid
  point (largest connected component) and a volume observation (mm³) from the
  maximum-probability labelled mask. Regions not mapped in that space are skipped and
  listed on stderr.

## What is deliberately not imported
- Probability maps and mask volumes themselves (large; will be external assets in Sprint 1b).
- Julich's linked data features (receptor densities, cell densities, connectivity). Those
  are Phases 2–4 and will come in through their own scripts with their own provenance.

## Identity caveat
Region ids are `brain-region:julich-<key>`. They are derived from one atlas and will be
merged into atlas-neutral project ids once a second atlas is ingested; the Julich mapping
records will survive that merge unchanged.
