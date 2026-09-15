# NeuroAtlas viewer

React + TypeScript + three.js, built with Vite. No backend: it reads one JSON
bundle and two GLB files, all generated from the validated records in `data/`.

## Run it locally

```bash
# from the repository root
python scripts/build/build_viewer_bundle.py   # data/ -> viewer/public/data/bundle.json
cd viewer
npm install
npm run dev                                   # opens on http://localhost:5173
```

## Regenerate the meshes

```bash
python -m pip install -r requirements-import.txt
python scripts/build/build_meshes.py          # ~3 min; writes viewer/public/assets/julich-3.1/*.glb
```

## How it works

- `src/data.ts` loads the bundle and builds lookup indexes (hierarchy, mappings, spatial, claims, connections).
- `src/scene.ts` is the three.js scene: whole-brain hull at low opacity, one mesh per mapped leaf
  region coloured with the atlas's own colours, raycast picking, selection dims everything else,
  and one bowed tube per drawn connection from the selected region (width and opacity follow strength).
- `src/App.tsx` is the UI: searchable region tree, detail panel that renders only what the records
  contain (atlas mapping, measurements with their method and dataset version, claims with evidence
  polarity, connections with a strength threshold, external identifiers), and the dataset attribution footer.

The viewer never owns facts. If something should appear in the panel, it goes into a record
in `data/`, gets validated, and the bundle is rebuilt.

## Deployment

`.github/workflows/viewer.yml` builds the bundle and the site on every push and deploys to
GitHub Pages from `main`. Pages must be enabled (Settings → Pages → Source: GitHub Actions)
and the repository must be public for Pages on a free account.
