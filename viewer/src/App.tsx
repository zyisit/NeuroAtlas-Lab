import { useEffect, useMemo, useRef, useState } from "react";
import { loadBundle, otherEnd, type Index, type BrainRegion, type Claim, type Connection, type Dataset, type DatasetVersion, type Atlas, type Source, type ReferenceSpace } from "./data";
import { createScene, type Edge, type SceneHandle } from "./scene";

const DEFAULT_LINES = 20; // how many of a region's strongest connections are drawn until the threshold is moved

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

const PREP: Record<string, string> = { in_vivo: "in vivo", ex_vivo: "ex vivo", in_vitro: "in vitro", post_mortem: "post-mortem", in_silico: "in silico", clinical: "clinical", mixed: "mixed methods", unknown: "" };

function ClaimView({ idx, c }: { idx: Index; c: Claim }) {
  const evidence = idx.evidenceByClaim.get(c.id) ?? [];
  return (
    <div className="claim">
      <p className="claim-statement">
        {c.statement}
        <span className={"tag status-" + c.evidenceStatus}>{c.evidenceStatus.replace("_", " ")}</span>
        {c.status !== "active" && <span className="tag">{c.status}</span>}
      </p>
      <p className="muted small">{c.species}{c.context?.preparation && c.context.preparation !== "unknown" && `, ${PREP[c.context.preparation] ?? c.context.preparation}`}</p>
      <ul className="evidence">
        {evidence.map((e) => {
          const s = idx.byId.get(e.sourceId) as Source | undefined;
          const prep = e.context?.preparation ? PREP[e.context.preparation] : "";
          return (
            <li key={e.id}>
              <span className={"tag polarity-" + e.polarity}>{e.polarity}</span>{" "}
              {s?.url ? <a href={s.url} target="_blank" rel="noreferrer">{s.citation ?? s.title}</a> : (s?.citation ?? s?.title ?? e.sourceId)}
              <small>{[e.species, prep, e.evidenceType].filter(Boolean).join(" · ")}{e.locator && ` — ${e.locator}`}</small>
              {e.notes && <small>{e.notes}</small>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ---------- connections ---------------------------------------------------

/** Connections of `id` at or above `minStrength`, strongest first. */
export function visibleConnections(idx: Index, id: string, minStrength: number): Connection[] {
  return (idx.connectionsByRegion.get(id) ?? []).filter((c) => (c.strength ?? 0) >= minStrength);
}

/** Strength of the Nth strongest connection: the default threshold for a freshly selected region. */
export function defaultThreshold(idx: Index, id: string): number {
  const all = idx.connectionsByRegion.get(id) ?? [];
  return all.length === 0 ? 0 : (all[Math.min(DEFAULT_LINES, all.length) - 1].strength ?? 0);
}

function Connections({ idx, id, onSelect, minStrength, setMinStrength }: {
  idx: Index; id: string; onSelect: (id: string) => void; minStrength: number; setMinStrength: (v: number) => void;
}) {
  const all = idx.connectionsByRegion.get(id) ?? [];
  const [showAll, setShowAll] = useState(false);
  if (all.length === 0) {
    // No edges for this region. Say why, rather than implying it is isolated.
    const leaves = [id, ...idx.descendants(id)].filter((d) => (idx.connectionsByRegion.get(d)?.length ?? 0) > 0);
    const hasData = (idx.bundle.records.connection?.length ?? 0) > 0;
    if (!hasData) return null;
    return (
      <div className="block">
        <h3>Connections</h3>
        {leaves.length > 0 ? (
          <p className="muted small">Connectivity is recorded for the mapped leaf regions, not for grouping nodes. See {leaves.map((l, i) => <span key={l}>{i > 0 && ", "}<button className="link" onClick={() => onSelect(l)}>{idx.regions.get(l)?.name}</button></span>)}.</p>
        ) : idx.centroidOf(id) ? (
          <p className="muted small">No connection to this region passed the import threshold. Small deep nuclei often receive few or no streamlines in diffusion tractography at this resolution; that is a limit of the method, not evidence that the region is isolated.</p>
        ) : (
          <p className="muted small">This region is not mapped in the labelled atlas, so no connectivity was computed for it.</p>
        )}
      </div>
    );
  }
  const shown = visibleConnections(idx, id, minStrength);
  const listed = showAll ? all : shown;
  const strongest = all[0].strength ?? 1, weakest = all[all.length - 1].strength ?? 1;
  // slider on a log scale between the region's weakest and strongest edge
  const toSlider = (v: number) => weakest >= strongest ? 1 : Math.log(v / weakest) / Math.log(strongest / weakest);
  const fromSlider = (t: number) => weakest * Math.pow(strongest / weakest, t);
  const dv = all[0].datasetVersionId ? (idx.byId.get(all[0].datasetVersionId) as DatasetVersion | undefined) : undefined;
  const ds = dv ? (idx.byId.get(dv.datasetId) as Dataset | undefined) : undefined;
  const pct = (c: Connection) => c.context?.subjectFraction !== undefined ? `${Math.round(c.context.subjectFraction * 100)}% of subjects` : "";
  return (
    <div className="block">
      <h3>Connections <span className="tag">{all[0].connectionType.replace(/_/g, " ")}</span></h3>
      <p className="muted small">
        {all[0].method}{ds && <>, from <a href={ds.homepage} target="_blank" rel="noreferrer">{ds.name}</a>{dv && ` (v${dv.version})`}</>}.
        {all[0].direction === "undirected" && " Tractography shows where a fibre bundle runs, not which way signals travel, so these edges have no direction."}
        {" "}Strength is the {all[0].strengthUnit}; it grows with region size and is comparable within this dataset only.
      </p>
      <label className="threshold">
        <span>Draw edges ≥ <strong>{Math.round(minStrength).toLocaleString()}</strong> streamlines · {shown.length} of {all.length}</span>
        <input type="range" min={0} max={1} step={0.005} value={Math.min(1, Math.max(0, toSlider(minStrength)))} onChange={(e) => setMinStrength(fromSlider(Number(e.target.value)))} aria-label="Minimum connection strength" />
      </label>
      <ol className="conn">
        {listed.map((c) => {
          const o = otherEnd(c, id);
          const dim = (c.strength ?? 0) < minStrength;
          return (
            <li key={c.id} className={dim ? "is-dim" : ""}>
              <span className="swatch" style={{ background: idx.colorOf(o) ?? "transparent" }} />
              <button className="link" onClick={() => onSelect(o)}>{idx.regions.get(o)?.name ?? o}</button>
              <span className="conn-strength">{(c.strength ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
              <small>{pct(c)}</small>
            </li>
          );
        })}
      </ol>
      {all.length > shown.length && <button className="link small" onClick={() => setShowAll(!showAll)}>{showAll ? `Show only the ${shown.length} drawn` : `List all ${all.length} connections`}</button>}
    </div>
  );
}

function Detail({ idx, id, onSelect, minStrength, setMinStrength }: { idx: Index; id: string | null; onSelect: (id: string) => void; minStrength: number; setMinStrength: (v: number) => void }) {
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
  const inherited = [...chain].reverse().map((a) => ({ region: a, claims: idx.claimsByRegion.get(a.id) ?? [] })).filter((x) => x.claims.length > 0);
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

      <Connections idx={idx} id={id} onSelect={onSelect} minStrength={minStrength} setMinStrength={setMinStrength} />

      <div className="block">
        <h3>Claims</h3>
        {claims.length === 0 && inherited.length === 0 && (
          <p className="muted">No curated claims about this region yet. When they are added, each will show its evidence status and the sources for and against it.</p>
        )}
        {claims.map((c) => <ClaimView key={c.id} idx={idx} c={c} />)}
        {inherited.map(({ region, claims: cs }) => (
          <div key={region.id} className="inherited">
            <p className="muted small">About <button className="link" onClick={() => onSelect(region.id)}>{region.name}</button>, which contains this region:</p>
            {cs.map((c) => <ClaimView key={c.id} idx={idx} c={c} />)}
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
  const [minStrength, setMinStrength] = useState(0);
  const canvasRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneHandle | null>(null);

  useEffect(() => { loadBundle().then(setIdx).catch((e) => setErr(String(e))); }, []);

  useEffect(() => {
    if (!idx || !canvasRef.current) return;
    const h = createScene(canvasRef.current, idx, {
      onPick: (id) => select(id),
      onHover: (id, x, y) => setHover(id ? { id, x, y } : null),
      onReady: setMeshCount,
    });
    sceneRef.current = h;
    return () => { h.dispose(); sceneRef.current = null; };
  }, [idx]);

  const select = (id: string | null) => { setSelected(id); if (id && idx) setMinStrength(defaultThreshold(idx, id)); };

  useEffect(() => {
    if (!idx || !sceneRef.current) return;
    if (!selected) { sceneRef.current.setSelection([]); sceneRef.current.setConnections([]); return; }
    const ids = [selected, ...idx.descendants(selected)];
    sceneRef.current.setSelection(ids);
    sceneRef.current.focus(selected);
  }, [selected, idx]);

  useEffect(() => {
    if (!idx || !sceneRef.current || !selected) return;
    const conns = visibleConnections(idx, selected, minStrength);
    const max = conns[0]?.strength ?? 1;
    const edges: Edge[] = conns.map((c) => ({ from: selected, to: otherEnd(c, selected), weight: (c.strength ?? 0) / max }));
    sceneRef.current.setConnections(edges);
  }, [selected, minStrength, idx]);

  const datasets = idx?.bundle.records.dataset ?? [];
  const atlases = idx?.bundle.records.atlas ?? [];
  const space = idx?.bundle.records["reference-space"]?.[0] as ReferenceSpace | undefined;

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <h1>NeuroAtlas Lab</h1>
          <p className="muted">{atlases[0]?.name ?? "Loading atlas"}{space && ` in ${space.name}`}{idx && ` · ${idx.regions.size} regions`}{meshCount !== null && ` · ${meshCount} surfaces`}{idx?.bundle.records.connection?.length ? ` · ${idx.bundle.records.connection.length.toLocaleString()} connections` : ""}</p>
        </div>
        <a className="link" href="https://github.com/zyisit/NeuroAtlas-Lab" target="_blank" rel="noreferrer">Source and data</a>
      </header>

      {err && <p className="error">Could not load the atlas: {err}</p>}

      <div className="workspace">
        <aside className="left">{idx ? <RegionTree idx={idx} selected={selected} onSelect={select} /> : <p className="muted">Loading regions…</p>}</aside>
        <main className="stage" ref={canvasRef} aria-label="3D brain model">
          {idx && meshCount === null && <p className="stage-note">Loading surfaces…</p>}
          {hover && idx && <div className="tip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{idx.regions.get(hover.id)?.name}</div>}
          {selected && <button className="clear" onClick={() => select(null)}>Clear selection</button>}
        </main>
        <aside className="right">{idx && <Detail idx={idx} id={selected} onSelect={select} minStrength={minStrength} setMinStrength={setMinStrength} />}</aside>
      </div>

      <footer className="attribution">
        {datasets.map((d: Dataset) => (
          <p key={d.id}>
            {d.homepage ? <a href={d.homepage} target="_blank" rel="noreferrer">{d.name}</a> : d.name}
            {d.publisher && `, ${d.publisher}`}. Licensed {d.license.url ? <a href={d.license.url} target="_blank" rel="noreferrer">{d.license.spdx}</a> : d.license.spdx}
            {d.license.commercialUseAllowed === false && " (non-commercial)"}.
          </p>
        ))}
        <p>Surfaces are smoothed, decimated illustrations of the atlas, not measurement-grade geometry. Connection tubes are drawn between region centres and do not follow real fibre paths. This is an educational tool, not a clinical one.</p>
      </footer>
    </div>
  );
}
