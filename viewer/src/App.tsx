import { useEffect, useMemo, useRef, useState } from "react";
import { loadBundle, otherEnd, type Index, type BrainRegion, type Claim, type Connection, type Dataset, type DatasetVersion, type Atlas, type Source, type ReferenceSpace, type SpatialTransformation } from "./data";
import { createScene, type Edge, type SceneHandle } from "./scene";

const DEFAULT_LINES = 20; // how many of a region's strongest connections are drawn until the threshold is moved

/** Short label for the atlas switch; the full name stays in the masthead and detail panel. */
function shortAtlasName(a: Atlas): string {
  if (/julich/i.test(a.name)) return `Julich-Brain ${a.name.match(/\(v([\d.]+)\)/)?.[1] ?? a.parcellationVersion ?? ""}`.trim();
  if (/allen/i.test(a.name)) return "Allen HRA 3D 2020";
  return a.name;
}

// ---------- atlas switch --------------------------------------------------

function AtlasSwitch({ idx, atlasId, onChange }: { idx: Index; atlasId: string; onChange: (id: string) => void }) {
  if (idx.atlases.length < 2) return null;
  return (
    <div className="atlas-switch" role="group" aria-label="Atlas">
      {idx.atlases.map((a) => (
        <button key={a.id} className={a.id === atlasId ? "is-on" : ""} onClick={() => onChange(a.id)} title={a.name}>
          {shortAtlasName(a)}<small>{idx.regionCountByAtlas.get(a.id) ?? 0} regions</small>
        </button>
      ))}
    </div>
  );
}

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

function RegionTree({ idx, atlasId, selected, onSelect }: { idx: Index; atlasId: string; selected: string | null; onSelect: (id: string) => void }) {
  const [q, setQ] = useState("");
  const atlasRoots = idx.rootsByAtlas.get(atlasId) ?? [];
  const [open, setOpen] = useState<Set<string>>(() => new Set(atlasRoots));
  useEffect(() => { setOpen(new Set(idx.rootsByAtlas.get(atlasId) ?? [])); setQ(""); }, [atlasId, idx]);
  const filter = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return null;
    const keep = new Set<string>();
    for (const r of idx.regions.values()) {
      if (idx.atlasOfRegion.get(r.id) !== atlasId) continue;
      if (r.name.toLowerCase().includes(t) || r.aliases?.some((a) => a.toLowerCase().includes(t))) {
        keep.add(r.id);
        for (const a of idx.ancestors(r.id)) keep.add(a.id);
      }
    }
    return keep;
  }, [q, idx, atlasId]);
  const roots = atlasRoots.filter((r) => !filter || filter.has(r));
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

export const STRUCTURAL = "structural_connectivity";
export const FUNCTIONAL = "functional_connectivity";
const TYPE_LABEL: Record<string, string> = { [STRUCTURAL]: "Structural", [FUNCTIONAL]: "Functional" };
const TYPE_SUB: Record<string, string> = { [STRUCTURAL]: "tractography", [FUNCTIONAL]: "resting state" };
const typeLabel = (t: string) => TYPE_LABEL[t] ?? t.replace(/_/g, " ");
const signed = (c: Connection) => c.connectionType === FUNCTIONAL;
const mag = (c: Connection) => Math.abs(c.strength ?? 0);

/** Connections of `id` of one type with |strength| at or above `minStrength`, strongest first. */
export function visibleConnections(idx: Index, id: string, type: string, minStrength: number): Connection[] {
  return idx.connectionsOf(id, type).filter((c) => mag(c) >= minStrength);
}

/** |strength| of the Nth strongest connection: the default threshold for a freshly selected region. */
export function defaultThreshold(idx: Index, id: string, type: string): number {
  const all = idx.connectionsOf(id, type);
  return all.length === 0 ? 0 : mag(all[Math.min(DEFAULT_LINES, all.length) - 1]);
}

/** The smallest |strength| kept by the import, i.e. the import threshold as seen in the data. */
function importFloor(idx: Index, type: string): number {
  let m = Infinity;
  for (const c of idx.bundle.records.connection ?? []) if (c.connectionType === type) m = Math.min(m, mag(c));
  return m === Infinity ? 0 : m;
}

function TypeSwitch({ idx, id, type, setType }: { idx: Index; id: string; type: string; setType: (t: string) => void }) {
  if (idx.connectionTypes.length < 2) return null;
  return (
    <div className="type-switch" role="group" aria-label="Connection type">
      {idx.connectionTypes.map((t) => (
        <button key={t} className={t === type ? "is-on" : ""} onClick={() => setType(t)}>
          {typeLabel(t)}<small>{TYPE_SUB[t] ?? ""} · {idx.connectionsOf(id, t).length}</small>
        </button>
      ))}
    </div>
  );
}

function Connections({ idx, id, onSelect, type, setType, minStrength, setMinStrength }: {
  idx: Index; id: string; onSelect: (id: string) => void; type: string; setType: (t: string) => void;
  minStrength: number; setMinStrength: (v: number) => void;
}) {
  const all = idx.connectionsOf(id, type);
  const [showAll, setShowAll] = useState(false);
  const hasData = (idx.bundle.records.connection?.length ?? 0) > 0;
  if (!hasData) return null;
  const atlasId = idx.atlasOfRegion.get(id);
  if (atlasId && !idx.atlasesWithConnections.has(atlasId)) {
    const withData = idx.atlases.filter((a) => idx.atlasesWithConnections.has(a.id)).map((a) => a.name).join(", ");
    return (
      <div className="block">
        <h3>Connections</h3>
        <p className="muted small">Connectivity has been imported for {withData} only, not for this atlas. The overlaps above lead to the corresponding regions there.</p>
      </div>
    );
  }
  if (all.length === 0) {
    // No edges of this type for this region. Say why, rather than implying it is isolated.
    const leaves = [id, ...idx.descendants(id)].filter((d) => idx.connectionsOf(d, type).length > 0);
    const floor = importFloor(idx, type);
    return (
      <div className="block">
        <h3>Connections</h3>
        <TypeSwitch idx={idx} id={id} type={type} setType={setType} />
        {leaves.length > 0 ? (
          <p className="muted small">Connectivity is recorded for the mapped leaf regions, not for grouping nodes. See {leaves.slice(0, 12).map((l, i) => <span key={l}>{i > 0 && ", "}<button className="link" onClick={() => onSelect(l)}>{idx.regions.get(l)?.name}</button></span>)}{leaves.length > 12 && ` and ${leaves.length - 12} more`}.</p>
        ) : !idx.centroidOf(id) ? (
          <p className="muted small">This region is not mapped in the labelled atlas, so no connectivity was computed for it.</p>
        ) : type === FUNCTIONAL ? (
          <p className="muted small">No correlation between this region and any other reached |r| ≥ {floor.toFixed(2)} in the group mean. Small parcels, deep nuclei, and cortex next to the air-filled sinuses (orbitofrontal and medial temporal areas) give weak, noisy fMRI signal, and a few parcels have no fMRI values in this dataset at all; noise pulls a group-mean correlation towards zero. That is a limit of the method, not evidence that the region is inactive or unconnected.{idx.connectionsOf(id, STRUCTURAL).length > 0 && <> Its {idx.connectionsOf(id, STRUCTURAL).length} structural connections are under <button className="link" onClick={() => setType(STRUCTURAL)}>Structural</button>.</>}</p>
        ) : (
          <p className="muted small">No connection to this region passed the import threshold. Small deep nuclei often receive few or no streamlines in diffusion tractography at this resolution; that is a limit of the method, not evidence that the region is isolated.</p>
        )}
      </div>
    );
  }
  const shown = visibleConnections(idx, id, type, minStrength);
  const listed = showAll ? all : shown;
  const strongest = mag(all[0]) || 1, weakest = mag(all[all.length - 1]) || 1;
  const isSigned = signed(all[0]);
  // structural: log scale between the region's weakest and strongest edge; functional (r is bounded): linear
  const toSlider = (v: number) => weakest >= strongest ? 1 : isSigned ? (v - weakest) / (strongest - weakest) : Math.log(v / weakest) / Math.log(strongest / weakest);
  const fromSlider = (t: number) => isSigned ? weakest + t * (strongest - weakest) : weakest * Math.pow(strongest / weakest, t);
  const dv = all[0].datasetVersionId ? (idx.byId.get(all[0].datasetVersionId) as DatasetVersion | undefined) : undefined;
  const ds = dv ? (idx.byId.get(dv.datasetId) as Dataset | undefined) : undefined;
  const pct = (v?: number) => v === undefined ? "" : `${Math.round(v * 100)}%`;
  const fmt = (c: Connection) => isSigned ? `${(c.strength ?? 0) >= 0 ? "+" : "−"}${Math.abs(c.strength ?? 0).toFixed(2)}` : (c.strength ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
  const note = (c: Connection) => {
    if (isSigned) return c.context?.subjectSignFraction !== undefined ? `same sign in ${pct(c.context.subjectSignFraction)} of subjects` : "";
    const len = idx.lengthOf.get(c.id);
    return [c.context?.subjectFraction !== undefined && `${pct(c.context.subjectFraction)} of subjects`,
      typeof len?.value === "number" && `${Math.round(len.value)} ${len.unit ?? ""} mean streamline length`].filter(Boolean).join(" · ");
  };
  const negatives = all.filter((c) => (c.strength ?? 0) < 0).length;
  return (
    <div className="block">
      <h3>Connections <span className="tag">{all[0].connectionType.replace(/_/g, " ")}</span></h3>
      <TypeSwitch idx={idx} id={id} type={type} setType={setType} />
      <p className="muted small">
        {all[0].method}{all[0].context?.paradigm && `; ${all[0].context.paradigm}`}{ds && <>, from <a href={ds.homepage} target="_blank" rel="noreferrer">{ds.name}</a>{dv && ` (v${dv.version})`}</>}.
        {isSigned ? (
          <> Strength is the {all[0].strengthUnit}: how closely the slow rise and fall of activity at rest in the two regions tracks each other. A correlation is not a pathway; regions with no direct fibre link can be strongly correlated, and it has no direction.{negatives === 0 ? " Every correlation listed here is positive." : ` ${negatives} listed correlation${negatives > 1 ? "s are" : " is"} negative (blue).`}</>
        ) : (
          <>{all[0].direction === "undirected" && " Tractography shows where a fibre bundle runs, not which way signals travel, so these edges have no direction."}
          {" "}Strength is the {all[0].strengthUnit}; it grows with region size and is comparable within this dataset only. Streamline length is the length of the reconstructed path, not the straight-line distance.</>
        )}
      </p>
      <label className="threshold">
        <span>Draw edges {isSigned ? <>with |r| ≥ <strong>{minStrength.toFixed(2)}</strong></> : <>≥ <strong>{Math.round(minStrength).toLocaleString()}</strong> streamlines</>} · {shown.length} of {all.length}</span>
        <input type="range" min={0} max={1} step={0.005} value={Math.min(1, Math.max(0, toSlider(minStrength)))} onChange={(e) => setMinStrength(fromSlider(Number(e.target.value)))} aria-label={isSigned ? "Minimum absolute correlation" : "Minimum connection strength"} />
      </label>
      <ol className="conn">
        {listed.map((c) => {
          const o = otherEnd(c, id);
          const dim = mag(c) < minStrength;
          const swatch = isSigned ? ((c.strength ?? 0) < 0 ? "var(--negative)" : "var(--positive)") : (idx.colorOf(o) ?? "transparent");
          return (
            <li key={c.id} className={dim ? "is-dim" : ""}>
              <span className="swatch" style={{ background: swatch }} />
              <button className="link" onClick={() => onSelect(o)}>{idx.regions.get(o)?.name ?? o}</button>
              <span className="conn-strength">{fmt(c)}</span>
              <small>{note(c)}</small>
            </li>
          );
        })}
      </ol>
      {all.length > shown.length && <button className="link small" onClick={() => setShowAll(!showAll)}>{showAll ? `Show only the ${shown.length} drawn` : `List all ${all.length} connections`}</button>}
    </div>
  );
}

// ---------- cross-atlas overlaps -----------------------------------------

function Overlaps({ idx, id, onSelect }: { idx: Index; id: string; onSelect: (id: string) => void }) {
  const own = idx.overlapsByRegion.get(id) ?? [];
  const hasData = (idx.bundle.records.relationship ?? []).some((r) => r.predicate === "overlaps");
  if (!hasData || idx.atlases.length < 2) return null;
  const thisAtlas = idx.atlasOfRegion.get(id);
  const otherAtlases = idx.atlases.filter((a) => a.id !== thisAtlas);
  const otherName = otherAtlases.map((a) => a.name).join(", ");
  if (own.length === 0) {
    const leaves = [id, ...idx.descendants(id)].filter((d) => (idx.overlapsByRegion.get(d)?.length ?? 0) > 0);
    return (
      <div className="block">
        <h3>In {otherName}</h3>
        {leaves.length > 0 ? (
          <p className="muted small">Overlaps are computed for the mapped leaf regions, not for grouping nodes. See {leaves.slice(0, 12).map((l, i) => <span key={l}>{i > 0 && ", "}<button className="link" onClick={() => onSelect(l)}>{idx.regions.get(l)?.name}</button></span>)}{leaves.length > 12 && ` and ${leaves.length - 12} more`}.</p>
        ) : (
          <p className="muted small">No region of {otherName} covers 10% or more of this one, or vice versa. That usually means the other atlas does not map this territory.</p>
        )}
      </div>
    );
  }
  const tx = own[0].rel.context?.transformationId ? (idx.byId.get(own[0].rel.context.transformationId) as SpatialTransformation | undefined) : undefined;
  const pct = (v?: number) => v === undefined ? "" : `${Math.round(v * 100)}%`;
  return (
    <div className="block">
      <h3>In {otherName} <span className="tag">{own[0].rel.assertionType}</span></h3>
      <p className="muted small">
        Share of this region's volume that falls inside each region of the other atlas, from voxel overlap of the two labelled maps.
        {tx ? ` The atlases sit on different MNI templates; the mapping between them is "${tx.method}", so expect about a millimetre of error at boundaries.` : ""}
      </p>
      <ol className="conn overlap">
        {own.map((o) => (
          <li key={o.rel.id}>
            <span className="swatch" style={{ background: idx.colorOf(o.other) ?? "transparent" }} />
            <button className="link" onClick={() => onSelect(o.other)}>{idx.regions.get(o.other)?.name ?? o.other}</button>
            <span className="conn-strength">{pct(o.fractionOfThis)}</span>
            <small>{pct(o.fractionOfOther)} of that region · {o.rel.context?.overlapVolumeMm3?.toLocaleString()} mm³ shared</small>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Detail({ idx, id, onSelect, connType, setConnType, minStrength, setMinStrength }: {
  idx: Index; id: string | null; onSelect: (id: string) => void; connType: string; setConnType: (t: string) => void; minStrength: number; setMinStrength: (v: number) => void;
}) {
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
            {m.notes && <p className="muted small">{m.notes}</p>}
          </div>
        );
      })}

      {(obs.length > 0 || centroid) && (
        <div className="block">
          <h3>Measurements</h3>
          <dl>
            {centroid && <Row k="Centroid">{centroid.map((c) => c.toFixed(1)).join(", ")} mm ({(idx.byId.get((idx.byId.get(idx.atlasOfRegion.get(id) ?? "") as Atlas | undefined)?.referenceSpaceId ?? "") as ReferenceSpace | undefined)?.name ?? "MNI152"})</Row>}
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

      <Overlaps idx={idx} id={id} onSelect={onSelect} />

      <Connections idx={idx} id={id} onSelect={onSelect} type={connType} setType={setConnType} minStrength={minStrength} setMinStrength={setMinStrength} />

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

// ---------- stage background ----------------------------------------------

type StageBg = "pink" | "white";
const BG_KEY = "neuroatlas.stageBackground";
function readBg(): StageBg { try { return localStorage.getItem(BG_KEY) === "white" ? "white" : "pink"; } catch { return "pink"; } }

function BgSwitch({ bg, onChange }: { bg: StageBg; onChange: (b: StageBg) => void }) {
  return (
    <div className="bg-switch" role="group" aria-label="Background colour">
      <span>Background</span>
      <button className={bg === "pink" ? "is-on" : ""} onClick={() => onChange("pink")}><span className="dot" style={{ background: "var(--stage)" }} />Pink</button>
      <button className={bg === "white" ? "is-on" : ""} onClick={() => onChange("white")}><span className="dot" style={{ background: "var(--stage-white)" }} />White</button>
    </div>
  );
}

// ---------- app -----------------------------------------------------------

export default function App() {
  const [idx, setIdx] = useState<Index | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [atlasId, setAtlasId] = useState<string>("");
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const [meshCount, setMeshCount] = useState<number | null>(null);
  const [minStrength, setMinStrength] = useState(0);
  const [connType, setConnType] = useState<string>(STRUCTURAL);
  const [bg, setBg] = useState<StageBg>(readBg);
  const chooseBg = (b: StageBg) => { setBg(b); try { localStorage.setItem(BG_KEY, b); } catch { /* storage off: choice lasts this visit */ } };
  const canvasRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneHandle | null>(null);

  useEffect(() => { loadBundle().then((i) => { setIdx(i); setAtlasId(i.atlases[0]?.id ?? ""); }).catch((e) => setErr(String(e))); }, []);

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

  // Load the chosen atlas's surfaces whenever it changes (the scene keeps the camera).
  useEffect(() => {
    if (!idx || !sceneRef.current || !atlasId) return;
    setMeshCount(null);
    sceneRef.current.setAtlas(idx.assetsByAtlas.get(atlasId) ?? {});
  }, [atlasId, idx]);

  const select = (id: string | null) => {
    if (id && idx) {
      const a = idx.atlasOfRegion.get(id);
      if (a && a !== atlasId) setAtlasId(a); // picking a region of the other atlas (e.g. from the overlaps list) switches to it
      setMinStrength(defaultThreshold(idx, id, connType));
    }
    setSelected(id);
  };
  const switchAtlas = (a: string) => { setAtlasId(a); setSelected(null); };
  const switchConnType = (t: string) => { setConnType(t); if (idx && selected) setMinStrength(defaultThreshold(idx, selected, t)); };

  useEffect(() => {
    if (!idx || !sceneRef.current) return;
    if (!selected) { sceneRef.current.setSelection([]); sceneRef.current.setConnections([]); return; }
    const ids = [selected, ...idx.descendants(selected)];
    sceneRef.current.setSelection(ids);
    sceneRef.current.focus(selected);
  }, [selected, idx]);

  useEffect(() => {
    if (!idx || !sceneRef.current || !selected) return;
    const conns = visibleConnections(idx, selected, connType, minStrength);
    const max = Math.abs(conns[0]?.strength ?? 1) || 1;
    const isSigned = connType === FUNCTIONAL;
    const edges: Edge[] = conns.map((c) => ({ from: selected, to: otherEnd(c, selected), weight: Math.abs(c.strength ?? 0) / max, sign: isSigned ? Math.sign(c.strength ?? 0) : undefined }));
    sceneRef.current.setConnections(edges);
  }, [selected, minStrength, connType, idx]);

  const datasets = idx?.bundle.records.dataset ?? [];
  const atlas = idx?.atlases.find((a) => a.id === atlasId);
  const space = atlas ? (idx?.byId.get(atlas.referenceSpaceId) as ReferenceSpace | undefined) : undefined;
  const connSummary = atlas && idx?.atlasesWithConnections.has(atlas.id)
    ? idx.connectionTypes.map((t) => `${(idx.connectionCountByType.get(t) ?? 0).toLocaleString()} ${typeLabel(t).toLowerCase()}`).join(" + ") + " connections"
    : "";

  return (
    <div className="app">
      <header className="masthead">
        <div>
          <h1>NeuroAtlas Lab</h1>
          <p className="muted">{atlas?.name ?? "Loading atlas"}{space && ` in ${space.name}`}{idx && atlas && ` · ${idx.regionCountByAtlas.get(atlas.id) ?? 0} regions`}{meshCount !== null && ` · ${meshCount} surfaces`}{connSummary && ` · ${connSummary}`}</p>
        </div>
        <a className="link" href="https://github.com/zyisit/NeuroAtlas-Lab" target="_blank" rel="noreferrer">Source and data</a>
      </header>

      {err && <p className="error">Could not load the atlas: {err}</p>}

      <div className="workspace">
        <aside className="left">{idx ? <><AtlasSwitch idx={idx} atlasId={atlasId} onChange={switchAtlas} /><RegionTree idx={idx} atlasId={atlasId} selected={selected} onSelect={select} /></> : <p className="muted">Loading regions…</p>}</aside>
        <main className="stage" data-bg={bg} ref={canvasRef} aria-label="3D brain model">
          {idx && meshCount === null && <p className="stage-note">Loading surfaces…</p>}
          {hover && idx && <div className="tip" style={{ left: hover.x + 12, top: hover.y + 12 }}>{idx.regions.get(hover.id)?.name}</div>}
          {selected && <button className="clear" onClick={() => select(null)}>Clear selection</button>}
          <BgSwitch bg={bg} onChange={chooseBg} />
        </main>
        <aside className="right">{idx && <Detail idx={idx} id={selected} onSelect={select} connType={connType} setConnType={switchConnType} minStrength={minStrength} setMinStrength={setMinStrength} />}</aside>
      </div>

      <footer className="attribution">
        {datasets.map((d: Dataset) => (
          <p key={d.id}>
            {d.homepage ? <a href={d.homepage} target="_blank" rel="noreferrer">{d.name}</a> : d.name}
            {d.publisher && `, ${d.publisher}`}. Licensed {d.license.url ? <a href={d.license.url} target="_blank" rel="noreferrer">{d.license.spdx}</a> : d.license.spdx}
            {d.license.commercialUseAllowed === false && " (non-commercial)"}.
          </p>
        ))}
        <p>Surfaces are smoothed, decimated illustrations of the atlas, not measurement-grade geometry. Connection tubes are drawn between region centres and do not follow real fibre paths; functional connections are correlations of activity at rest and are drawn the same way without implying any pathway. Where two atlases are compared, their MNI templates are treated as the same space without registration. This is an educational tool, not a clinical one.</p>
      </footer>
    </div>
  );
}
