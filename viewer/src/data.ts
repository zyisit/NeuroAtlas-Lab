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
  atlasParentRegionId?: string; mappingType: string; datasetVersionId?: string; displayColor?: string;
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
export interface Dataset { id: string; name: string; publisher?: string; homepage?: string; license: { spdx: string; url?: string; attributionText?: string; commercialUseAllowed?: boolean } }
export interface DatasetVersion { id: string; datasetId: string; version: string; retrievedAt: string; accessUrl?: string }
export interface Atlas { id: string; name: string; species: string; referenceSpaceId: string; datasetVersionId: string; parcellationVersion?: string }
export interface ReferenceSpace { id: string; name: string; coordinateSystem: string; species: string; unit?: string }

export interface Bundle {
  schemaVersion: string;
  records: {
    "brain-region"?: BrainRegion[]; "atlas-mapping"?: AtlasMapping[]; "spatial-representation"?: SpatialRepresentation[];
    observation?: Observation[]; claim?: Claim[]; "evidence-record"?: EvidenceRecord[]; source?: Source[];
    dataset?: Dataset[]; "dataset-version"?: DatasetVersion[]; atlas?: Atlas[]; "reference-space"?: ReferenceSpace[];
  };
}

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
  byId: Map<string, unknown>;
  colorOf: (regionId: string) => string | undefined;
  centroidOf: (regionId: string) => number[] | undefined;
  descendants: (regionId: string) => string[];
  ancestors: (regionId: string) => BrainRegion[];
}

function push<K, V>(m: Map<K, V[]>, k: K, v: V) { const a = m.get(k); if (a) a.push(v); else m.set(k, [v]); }

export async function loadBundle(): Promise<Index> {
  const res = await fetch(`${import.meta.env.BASE_URL}data/bundle.json`);
  if (!res.ok) throw new Error(`bundle.json: ${res.status}. Run scripts/build/build_viewer_bundle.py first.`);
  const bundle = (await res.json()) as Bundle;
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
  for (const o of R.observation ?? []) if (o.subjectId) push(observationsByRegion, o.subjectId, o);
  const claimsByRegion = new Map<string, Claim[]>();
  for (const c of R.claim ?? []) for (const s of c.subjectIds ?? []) push(claimsByRegion, s, c);
  const evidenceByClaim = new Map<string, EvidenceRecord[]>();
  for (const e of R["evidence-record"] ?? []) push(evidenceByClaim, e.claimId, e);

  const byId = new Map<string, unknown>();
  for (const list of Object.values(R)) for (const rec of list ?? []) byId.set((rec as { id: string }).id, rec);

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

  return { bundle, regions, children, roots, mappingsByRegion, spatialByRegion, observationsByRegion, claimsByRegion, evidenceByClaim, byId, colorOf, centroidOf, descendants, ancestors };
}
