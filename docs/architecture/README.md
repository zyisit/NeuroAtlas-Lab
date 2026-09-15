# Architecture

Five separated concerns:

1. **Presentation** — React + TypeScript educational UI
2. **Visualization** — Three.js / WebGL, external mesh and volume assets
3. **Domain knowledge** — the records in `data/`, shaped by `schemas/`
4. **Computational models** — equations, parameters, interventions, simulations (Phase 7+)
5. **Evidence / provenance** — sources, claims, datasets, licenses, transformations

The frontend must never become the data model. The viewer reads validated
record bundles; it does not own facts.

## Planned viewer data flow (Sprint 2)

```
data/**/*.json ──validate──▶ build script ──▶ static bundle (JSON + mesh URIs)
                                                      │
                                              React app on GitHub Pages
```

No backend is required for Phase 1–2. A backend appears only when a paid tier
or expensive computation needs it, and that lives outside this repository.
