// Types mirror schemas/*.json (v0.7). Only the fields the viewer reads are typed.

export interface ExternalIdentifier { namespace: string; identifier: string; url?: string }
export interface Provenance { createdAt?: string; createdBy?: string; method?: string; notes?: string }

export interface BrainRegion {
  id: string; name: string; aliases?: string[]; description?: string; species: string;
  hemisphere?: string; anatomicalClass?: string; parentRegionIds?: string[];
  atlasMappingIds?: string[]; spatialRepresentationIds?: string[];
  externalIdentifiers?: ExternalIdentifier[]; status: string; provenance?: Provenance;
}
export interface AtlasMapping {
  id: string; brainRegionId: string; atlasId: string; atlasRegionId?: string; label?: string;
  atlasParentRegionId?: string; mappingType: string; datasetVersionId?: string; displayColor?: string; notes?: string;
}
export interface SpatialRepresentation {
  id: string; subjectId?: string; referenceSpaceId: string; datasetVersionId: string;
  geometry: { type: string; coordinates?: number[]; uri?: string; format?: string; note?: string };
  provenance?: Provenance;
}
export interface Observation {
  id: string; observationType: string; datasetVersionId: string; sourceId?: string; subjectId?: string;
  species?: string; context?: Record<string, string>; value?: unknown; unit?: string; method?: string;
  spatialRepresentationId?: string;
}
export interface Claim {
  id: string; statement: string; subjectIds?: string[]; species?: string; context?: Record<string, string>; evidenceStatus: string;
  evidenceRecordIds?: string[]; status: string;
}
export interface EvidenceRecord { id: string; claimId: string; sourceId: string; evidenceType: string; polarity: string; species?: string; context?: Record<string, string>; locator?: string; methods?: string[]; notes?: string }
export interface Source { id: string; sourceType: string; title: string; authors?: string[]; year?: number; citation?: string; url?: string }
export interface Connection {
  id: string; sourceId: string; targetId: string; direction: string; connectionType: string; species: string;
  context?: { preparation?: string; subjectFraction?: number; subjectSignFraction?: number; paradigm?: string; condition?: string; notes?: string };
  assertionType: string; method?: string;
  strength?: number; strengthUnit?: string; datasetVersionId?: string; status?: string;
}
export interface Relationship {
  id: string; subjectId: string; predicate: string; objectId: string; species?: string; assertionType: string; status: string;
  context?: { preparation?: string; overlapFractionOfSubject?: number; overlapFractionOfObject?: number; overlapVolumeMm3?: number; transformationId?: string; notes?: string };
}
export interface SpatialTransformation { id: string; sourceReferenceSpaceId: string; targetReferenceSpaceId: string; method: string; notes?: string }
export interface Dataset { id: string; name: string; publisher?: string; homepage?: string; license: { spdx: string; url?: string; attributionText?: string; commercialUseAllowed?: boolean } }
export interface DatasetVersion { id: string; datasetId: string; version: string; retrievedAt: string; accessUrl?: string }
export interface Atlas { id: string; name: string; species: string; referenceSpaceId: string; datasetVersionId: string; parcellationVersion?: string }
export interface ReferenceSpace { id: string; name: string; coordinateSystem: string; species: string; unit?: string }

export interface Bundle {
  schemaVersion: string;
  packed?: boolean;
  records: {
    "brain-region"?: BrainRegion[]; "atlas-mapping"?: AtlasMapping[]; "spatial-representation"?: SpatialRepresentation[];
    observation?: Observation[]; claim?: Claim[]; "evidence-record"?: EvidenceRecord[]; source?: Source[];
    dataset?: Dataset[]; "dataset-version"?: DatasetVersion[]; atlas?: Atlas[]; "reference-space"?: ReferenceSpace[];
    connection?: Connection[]; relationship?: Relationship[]; "spatial-transformation"?: SpatialTransformation[];
  };
}

/** Where an atlas's display meshes live, as URL paths relative to the viewer base (derived from spatial-representation uris). */
export interface AtlasAssets { hull?: string; regions?: string }

/** An `overlaps` relationship seen from one of its two regions. */
export interface Overlap { rel: Relationship; other: string; fractionOfThis?: number; fractionOfOther?: number }

export interface Index {
  bundle: Bundle;
  regions: Map<string, BrainRegion>;
  children: Map<string, string[]>;          // parent id -> child ids (sorted by name)
  roots: string[];
  mappingsByRegion: Map<string, AtlasMapping[]>;
  spatialByRegion: Map<string, SpatialRepresentation[]>;
  observationsByRegion: Map<string, Observation[]>;
  claimsByRegion: Map<string, Claim[]>;
  evidenceByClaim: Map<string, EvidenceRecord[]>;
  connectionsByRegion: Map<string, Connection[]>; // key `${connectionType}|${regionId}`, both endpoints; sorted by |strength|, strongest first — use connectionsOf()
  connectionTypes: string[];                       // connectionType values present, structural first
  connectionCountByType: Map<string, number>;
  lengthOf: Map<string, Observation>;              // structural connection id -> mean streamline length observation
  connectionsOf: (regionId: string, type: string) => Connection[];
  atlases: Atlas[];                                // in the order they joined the project (dataset-version retrievedAt)
  atlasOfRegion: Map<string, string>;             // region id -> atlas id (from its first atlas-mapping)
  rootsByAtlas: Map<string, string[]>;
  regionCountByAtlas: Map<string, number>;
  assetsByAtlas: Map<string, AtlasAssets>;
  atlasesWithConnections: Set<string>;
  overlapsByRegion: Map<string, Overlap[]>;       // both directions; sorted by the share of *this* region, largest first
  byId: Map<string, unknown>;
  colorOf: (regionId: string) => string | undefined;
  centroidOf: (regionId: string) => number[] | undefined;
  descendants: (regionId: string) => string[];
  ancestors: (regionId: string) => BrainRegion[];
}

function push<K, V>(m: Map<K, V[]>, k: K, v: V) { const a = m.get(k); if (a) a.push(v); else m.set(k, [v]); }

/** A run of records from one data file with the fields they all share written once (scripts/build/build_viewer_bundle.py). */
interface Pack { _shared: Record<string, unknown> & { context?: Record<string, unknown> }; _items: Record<string, unknown>[] }

/** Expand packed bundle entries back into complete records. Python twin: unpack() in build_viewer_bundle.py. */
export function unpackRecords<T>(entries: unknown[]): T[] {
  const out: T[] = [];
  for (const e of entries) {
    const p = e as Pack;
    if (!p || !Array.isArray(p._items)) { out.push(e as T); continue; }
    const sh = p._shared;
    for (const it of p._items) {
      const r: Record<string, unknown> = { ...sh, ...it };
      if (sh.context) r.context = { ...sh.context, ...((it.context as Record<string, unknown> | undefined) ?? {}) };
      out.push(r as T);
    }
  }
  return out;
}

const TYPE_ORDER = ["structural_connectivity", "functional_connectivity", "anatomical_projection", "effective_connectivity", "synaptic_connection", "network_relationship"];

export async function loadBundle(): Promise<Index> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/bundle.json`);
  if (!res.ok) throw new Error(`bundle.json: ${res.status}. Run scripts/build/build_viewer_bundle.py first.`);
  const bundle = (await res.json()) as Bundle;
  const R = bundle.records as Record<string, unknown[] | undefined>;
  for (const k of Object.keys(R)) R[k] = unpackRecords(R[k] ?? []);
  return buildIndex(bundle);
}

/** Build the lookup tables from an (unpacked) bundle. */
export function buildIndex(bundle: Bundle): Index {
  const R = bundle.records;

  const regions = new Map<string, BrainRegion>();
  for (const r of R["brain-region"] ?? []) regions.set(r.id, r);

  const children = new Map<string, string[]>();
  const roots: string[] = [];
  for (const r of regions.values()) {
    const p = r.parentRegionIds?.[0];
    if (p && regions.has(p)) push(children, p, r.id); else roots.push(r.id);
  }
  const byName = (a: string, b: string) => regions.get(a)!.name.localeCompare(regions.get(b)!.name);
  for (const arr of children.values()) arr.sort(byName);
  roots.sort(byName);

  const mappingsByRegion = new Map<string, AtlasMapping[]>();
  for (const m of R["atlas-mapping"] ?? []) push(mappingsByRegion, m.brainRegionId, m);
  const spatialByRegion = new Map<string, SpatialRepresentation[]>();
  for (const s of R["spatial-representation"] ?? []) if (s.subjectId) push(spatialByRegion, s.subjectId, s);
  const observationsByRegion = new Map<string, Observation[]>();
  const lengthOf = new Map<string, Observation>();
  for (const o of R.observation ?? []) {
    if (!o.subjectId) continue;
    if (o.subjectId.startsWith("connection:")) lengthOf.set(o.subjectId, o); // the only connection observations are streamline lengths
    else push(observationsByRegion, o.subjectId, o);
  }
  const claimsByRegion = new Map<string, Claim[]>();
  for (const c of R.claim ?? []) for (const s of c.subjectIds ?? []) push(claimsByRegion, s, c);
  const evidenceByClaim = new Map<string, EvidenceRecord[]>();
  for (const e of R["evidence-record"] ?? []) push(evidenceByClaim, e.claimId, e);

  const connectionsByRegion = new Map<string, Connection[]>();
  const connectionCountByType = new Map<string, number>();
  for (const c of R.connection ?? []) {
    push(connectionsByRegion, `${c.connectionType}|${c.sourceId}`, c); push(connectionsByRegion, `${c.connectionType}|${c.targetId}`, c);
    connectionCountByType.set(c.connectionType, (connectionCountByType.get(c.connectionType) ?? 0) + 1);
  }
  for (const arr of connectionsByRegion.values()) arr.sort((a, b) => Math.abs(b.strength ?? 0) - Math.abs(a.strength ?? 0));
  const rank = (t: string) => { const i = TYPE_ORDER.indexOf(t); return i < 0 ? TYPE_ORDER.length : i; };
  const connectionTypes = [...connectionCountByType.keys()].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
  const connectionsOf = (regionId: string, type: string) => connectionsByRegion.get(`${type}|${regionId}`) ?? [];

  const byId = new Map<string, unknown>();
  for (const list of Object.values(R)) for (const rec of list ?? []) byId.set((rec as { id: string }).id, rec);

  // atlases, in the order their dataset versions were retrieved (first imported first)
  const retrieved = (a: Atlas) => (byId.get(a.datasetVersionId) as DatasetVersion | undefined)?.retrievedAt ?? "";
  const atlases = [...(R.atlas ?? [])].sort((a, b) => retrieved(a).localeCompare(retrieved(b)) || a.name.localeCompare(b.name));
  const atlasOfRegion = new Map<string, string>();
  for (const m of R["atlas-mapping"] ?? []) if (!atlasOfRegion.has(m.brainRegionId)) atlasOfRegion.set(m.brainRegionId, m.atlasId);
  const rootsByAtlas = new Map<string, string[]>();
  const regionCountByAtlas = new Map<string, number>();
  for (const id of roots) push(rootsByAtlas, atlasOfRegion.get(id) ?? "", id);
  for (const id of regions.keys()) { const a = atlasOfRegion.get(id) ?? ""; regionCountByAtlas.set(a, (regionCountByAtlas.get(a) ?? 0) + 1); }
  // mesh assets: the hull is the surface whose subject is the atlas itself; region meshes are the surface of any region of that atlas
  const toUrl = (uri: string) => uri.replace(/^viewer\/public\//, "");
  const assetsByAtlas = new Map<string, AtlasAssets>();
  for (const s of R["spatial-representation"] ?? []) {
    if (s.geometry.type !== "surface" || !s.geometry.uri || !s.subjectId) continue;
    const atlasId = s.subjectId.startsWith("atlas:") ? s.subjectId : atlasOfRegion.get(s.subjectId);
    if (!atlasId) continue;
    const a = assetsByAtlas.get(atlasId) ?? {};
    if (s.subjectId.startsWith("atlas:")) a.hull = toUrl(s.geometry.uri); else a.regions ??= toUrl(s.geometry.uri);
    assetsByAtlas.set(atlasId, a);
  }
  const atlasesWithConnections = new Set<string>();
  for (const c of R.connection ?? []) { const a = atlasOfRegion.get(c.sourceId); if (a) atlasesWithConnections.add(a); }

  const overlapsByRegion = new Map<string, Overlap[]>();
  for (const rel of R.relationship ?? []) {
    if (rel.predicate !== "overlaps") continue;
    const c = rel.context ?? {};
    push(overlapsByRegion, rel.subjectId, { rel, other: rel.objectId, fractionOfThis: c.overlapFractionOfSubject, fractionOfOther: c.overlapFractionOfObject });
    push(overlapsByRegion, rel.objectId, { rel, other: rel.subjectId, fractionOfThis: c.overlapFractionOfObject, fractionOfOther: c.overlapFractionOfSubject });
  }
  for (const arr of overlapsByRegion.values()) arr.sort((a, b) => (b.fractionOfThis ?? 0) - (a.fractionOfThis ?? 0));

  const descendants = (id: string): string[] => {
    const out: string[] = []; const stack = [...(children.get(id) ?? [])];
    while (stack.length) { const c = stack.pop()!; out.push(c); stack.push(...(children.get(c) ?? [])); }
    return out;
  };
  const ownColor = (id: string) => mappingsByRegion.get(id)?.find((m) => m.displayColor)?.displayColor;
  const colorOf = (id: string): string | undefined => {
    // own colour, else nearest coloured ancestor, else first coloured descendant
    let cur: string | undefined = id;
    while (cur) { const c = ownColor(cur); if (c) return c; cur = regions.get(cur)?.parentRegionIds?.[0]; }
    for (const d of descendants(id)) { const c = ownColor(d); if (c) return c; }
    return undefined;
  };
  const centroidOf = (id: string) => spatialByRegion.get(id)?.find((s) => s.geometry.type === "point")?.geometry.coordinates;
  const ancestors = (id: string): BrainRegion[] => {
    const out: BrainRegion[] = []; let cur = regions.get(id)?.parentRegionIds?.[0];
    while (cur && regions.has(cur)) { out.unshift(regions.get(cur)!); cur = regions.get(cur)!.parentRegionIds?.[0]; }
    return out;
  };

  return { bundle, regions, children, roots, mappingsByRegion, spatialByRegion, observationsByRegion, claimsByRegion, evidenceByClaim, connectionsByRegion,
    connectionTypes, connectionCountByType, lengthOf, connectionsOf,
    atlases, atlasOfRegion, rootsByAtlas, regionCountByAtlas, assetsByAtlas, atlasesWithConnections, overlapsByRegion, byId, colorOf, centroidOf, descendants, ancestors };
}

/** The region at the far end of an undirected/bidirectional edge, seen from `regionId`. */
export function otherEnd(c: Connection, regionId: string): string { return c.sourceId === regionId ? c.targetId : c.sourceId; }
