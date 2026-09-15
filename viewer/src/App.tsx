import { useEffect, useMemo, useRef, useState } from "react";
import { loadBundle, type Index, type BrainRegion, type Dataset, type DatasetVersion, type Atlas, type Source, type ReferenceSpace } from "./data";
import { createScene, type SceneHandle } from "./scene";

// ---------- region tree ---------------------------------------------------

function RegionNode({ id, idx, selected, onSelect, open, setOpen, filter }: {
  id: string; idx: Index; selected: string | null; onSelect: (id: string) => void;
  open: Set<string>; setOpen: (s: Set<string>) => void; filter: Set<string> | null;
}) {
  const r = idx.regions.get(id)!;
  const kids = (idx.children.get(id) ?? []).filter((k) => !filter || filter.has(k));
  const isOpen = open.has(id) || (filter !== null);
  const color = idx.colorOf(id);
  return (
    <li>
      <div className={"node" + (selected === id ? " is-selected" : "")}>
        {kids.length > 0 ? (
          <button className="twisty" aria-label={isOpen ? "Collapse" : "Expand"} onClick={() => { const s = new Set(open); isOpen ? s.delete(id) : s.add(id); setOpen(s); }}>{isOpen ? "–" : "+"}</button>
        ) : <span className="twisty-gap" />}
        <span className="swatch" style={{ background: color ?? "transparent", borderColor: color ? "transparent" : "var(--rule)" }} />
        <button className="node-name" onClick={() => onSelect(id)}>{r.name}</button>
      </div>
      {isOpen && kids.length > 0 && (
        <ul>{kids.map((k) => <RegionNode key={k} id={k} idx={idx} selected={selected} onSelect={onSelect} open={open} setOpen={setOpen} filter={filter} />)}</ul>
      )}
    </li>
  );
}

function RegionTree({ idx, selected, onSelect }: { idx: Index; selected: string | null; onSelect: (id: string) => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Set<string>>(() => new Set(idx.roots));
  const filter = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return null;
    const keep = new Set<string>();
    for (const r of idx.regions.values()) {
      if (r.name.toLowerCase().includes(t) || r.aliases?.some((a) => a.toLowerCase().includes(t))) {
        keep.add(r.id);
        for (const a of idx.ancestors(r.id)) keep.add(a.id);
      }
    }
    return keep;
  }, [q, idx]);
  const roots = idx.roots.filter((r) => !filter || filter.has(r));
  return (
    <nav className="tree" aria-label="Brain regions">
      <input className="search" type="search" placeholder="Find a region, e.g. hippocampus or V1" value={q} onChange={(e) => setQ(e.target.value)} />
      {filter && roots.length === 0 && <p className="muted">No region matches “{q}”.</p>}
      <ul className="tree-root">
        {roots.map((id) => <RegionNode key={id} id={id} idx={idx} selected={selected} onSelect={onSelect} open={open} setOpen={setOpen} filter={filter} />)}
      </ul>
    </nav>
  );
}

// ---------- detail panel --------------------------------------------------

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="row"><dt>{k}</dt><dd>{children}</dd></div>;
}

function Detail({ idx, id, onSelect }: { idx: Index; id: string | null; onSelect: (id: string) => void }) {
  if (!id) return (
    <section className="detail">
      <h2>Pick a region</h2>
      <p>Click any structure in the model, or choose one from the list. Everything shown here comes from a validated record with a source attached — nothing is typed in by hand.</p>
    </section>
  );
  const r = idx.regions.get(id)!;
  const mappings = idx.mappingsByRegion.get(id) ?? [];
  const spatial = idx.spatialByRegion.get(id) ?? [];
  const obs = idx.observationsByRegion.get(id) ?? [];
  const claims = idx.claimsByRegion.get(id) ?? [];
  const chain = idx.ancestors(id);
  const kids = idx.children.get(id) ?? [];
  const centroid = idx.centroidOf(id);
  const dv = (dvid?: string) => dvid ? (idx.byId.get(dvid) as DatasetVersion | undefined) : undefined;

  return (
    <section className="detail">
      {chain.length > 0 && (
        <p className="crumbs">{chain.map((a, i) => <span key={a.id}>{i > 0 && " / "}<button className="link" onClick={() => onSelect(a.id)}>{a.name}</button></span>)}</p>
      )}
      <h2 style={{ borderColor: idx.colorOf(id) ?? "var(--rule)" }}>{r.name}</h2>
      {r.aliases && r.aliases.length > 0 && <p className="muted">Also called {r.aliases.join(", ")}.</p>}
      {r.description && <p>{r.description}</p>}

      <dl>
        <Row k="Species">{r.species}</Row>
        {r.hemisphere && <Row k="Hemisphere">{r.hemisphere}</Row>}
        {r.anatomicalClass && <Row k="Class">{r.anatomicalClass.replace("_", " ")}</Row>}
        {kids.length > 0 && <Row k="Contains">{kids.length} sub-regions</Row>}
      </dl>

      {mappings.map((m) => {
        const atlas = idx.byId.get(m.atlasId) as Atlas | undefined;
        const v = dv(m.datasetVersionId);
        return (
          <div className="block" key={m.id}>
            <h3>In {atlas?.name ?? m.atlasId}</h3>
            <dl>
              <Row k="Label">{m.label}</Row>
              {m.atlasRegionId && <Row k="Atlas id"><code>{m.atlasRegionId}</code></Row>}
              <Row k="Mapping">{m.mappingType}</Row>
              {v && <Row k="Release">{v.version}, retrieved {v.retrievedAt}</Row>}
            </dl>
          </div>
        );
      })}

      {(obs.length > 0 || centroid) && (
        <div className="block">
          <h3>Measurements</h3>
          <dl>
            {centroid && <Row k="Centroid">{centroid.map((c) => c.toFixed(1)).join(", ")} mm (MNI152)</Row>}
            {obs.map((o) => (
              <Row key={o.id} k={o.unit === "mm3" ? "Volume" : o.observationType}>
                {typeof o.value === "number" ? o.value.toLocaleString() : String(o.value)} {o.unit}
                <span className="tag">{o.observationType}</span>
                {o.method && <small>{o.method}</small>}
                {o.context?.notes && <small>{o.context.notes}</small>}
              </Row>
            ))}
          </dl>
        </div>
      )}

      <div className="block">
        <h3>Claims</h3>
        {claims.length === 0 ? (
          <p className="muted">No curated claims about this region yet. When they are added, each will show its evidence status and the sources for and against it.</p>
        ) : claims.map((c) => (
          <div key={c.id} className="claim">
            <p>{c.statement} <span className={"tag status-" + c.evidenceStatus}>{c.evidenceStatus.replace("_", " ")}</span></p>
            <ul>
              {(idx.evidenceByClaim.get(c.id) ?? []).map((e) => {
                const s = idx.byId.get(e.sourceId) as Source | undefined;
                return <li key={e.id}><span className={"tag polarity-" + e.polarity}>{e.polarity}</span> {s?.citation ?? s?.title ?? e.sourceId}{e.locator && `, ${e.locator}`}</li>;
              })}
            </ul>
          </div>
        ))}
      </div>

      {(r.externalIdentifiers?.length ?? 0) > 0 && (
        <div className="block">
          <h3>Identifiers</h3>
          <dl>{r.externalIdentifiers!.map((e) => <Row key={e.namespace + e.identifier} k={e.namespace}>{e.url ? <a href={e.url} target="_blank" rel="noreferrer">{e.identifier}</a> : <code>{e.identifier}</code>}</Row>)}</dl>
        </div>
      )}

      {spatial.length > 0 && (
        <p className="muted small">Geometry: {spatial.map((s) => s.geometry.type).join(", ")}. {spatial.find((s) => s.geometry.note)?.geometry.note}</p>
      )}
      <p className="muted small">Record {r.id} · status {r.status}{r.provenance?.createdBy && ` · created by ${r.provenance.createdBy}`}</p>
    </section>
  );
}

// ---------- app -----------------------------------------------------------

export default function App() {
  const [idx, setIdx] = useState<Index | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const [meshCount, setMeshCount] = useState<number | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneHandle | null>(null);

  useEffect(() => { loadBundle().then(setIdx).catch((e) => setErr(String(e))); }, []);

  useEffect(() => {
    if (!idx || !canvasRef.current) return;
    const h = createScene(canvasRef.current, idx, {
      onPick: (id) => setSelected(id),
      onHover: (id, x, y) => setHover(id ? { id, x, y } : null),
      onReady: setMeshCount,
    });
    sceneRef.current = h;
    return () => { h.dispose(); sceneRef.current = null; };
  }, [idx]);

  useEffect(() => {
    if (!idx || !sceneRef.current) return;
    if (!selected) { sceneRef.current.setSelection([]); return; }
    const ids = [selected, ...idx.descendants(selected)];
    sceneRef.current.setSelection(ids);
    sceneRef.current.focus(selected);
  }, [selected, idx]);

  const datasets = idx?.bundle.records.dataset ?? [];
  const atlases = idx?.bundle.records.atlas ?? [];
  const space = idx?.bundle.records["reference-space"]?.[0] as ReferenceSpace | undefined;

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <h1>NeuroAtlas Lab</h1>
          <p className="muted">{atlases[0]?.name ?? "Loading atlas"}{space && ` in ${space.name}`}{idx && ` · ${idx.regions.size} regions`}{meshCount !== null && ` · ${meshCount} surfaces`}</p>
        </div>
        <a className="link" href="https://github.com/zyisit/NeuroAtlas-Lab" target="_blank" rel="noreferrer">Source and data</a>
      </header>

      {err && <p className="error">Could not load the atlas: {err}</p>}

      <div className="workspace">
        <aside className="left">{idx ? <RegionTree idx={idx} selected={selected} onSelect={setSelected} /> : <p className="muted">Loading regions…</p>}</aside>
        <main className="stage" ref={canvasRef} aria-label="3D brain model">
          {idx && meshCount === null && <p className="stage-note">Loading surfaces…</p>}
          {hover && idx && <div className="tip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{idx.regions.get(hover.id)?.name}</div>}
          {selected && <button className="clear" onClick={() => setSelected(null)}>Clear selection</button>}
        </main>
        <aside className="right">{idx && <Detail idx={idx} id={selected} onSelect={setSelected} />}</aside>
      </div>

      <footer className="attribution">
        {datasets.map((d: Dataset) => (
          <p key={d.id}>
            {d.homepage ? <a href={d.homepage} target="_blank" rel="noreferrer">{d.name}</a> : d.name}
            {d.publisher && `, ${d.publisher}`}. Licensed {d.license.url ? <a href={d.license.url} target="_blank" rel="noreferrer">{d.license.spdx}</a> : d.license.spdx}
            {d.license.commercialUseAllowed === false && " (non-commercial)"}.
          </p>
        ))}
        <p>Surfaces are smoothed, decimated illustrations of the atlas, not measurement-grade geometry. This is an educational tool, not a clinical one.</p>
      </footer>
    </div>
  );
}
