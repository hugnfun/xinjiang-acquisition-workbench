import type { MaterialSummary, MaterialDetail, TagDimensionView, JobView, ClusterView, QuestionView, AssetView } from '../types/models';

// Cached sidecar port. Resolved once via the `get_sidecar_port` Tauri command
// (pull-based — the frontend asks for the port before its first fetch), which
// avoids the eval-injection race where setup() ran before the webview's JS
// loaded, leaving window.__SIDECAR_PORT__ undefined → 8765 fallback → "Load failed".
let _port: string | null = null;

async function resolvePort(): Promise<string> {
  if (_port) return _port;
  // Try the Tauri invoke bridge directly (don't gate on a __TAURI_INTERNALS__
  // sniff — the flag name varies across Tauri v2 builds, and a wrong sniff
  // skips invoke entirely → 8765 fallback → "Load failed"). If we're not in
  // Tauri, the dynamic import or invoke throws and we fall through.
  try {
    const { invoke } = await import('@tauri-apps/api/core');
    const port = await invoke<number>('get_sidecar_port');
    _port = String(Number(port));
    return _port;
  } catch {
    // not in Tauri, or command missing → fall through to env/fallback
  }
  const env = (import.meta as any).env.VITE_SIDECAR_PORT;
  _port = env ? String(env) : '8765';
  return _port;
}

async function baseUrl(): Promise<string> {
  return `http://127.0.0.1:${await resolvePort()}`;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${await baseUrl()}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${await baseUrl()}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
async function put<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${await baseUrl()}${path}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  getMaterials: (limit = 50, offset = 0) =>
    get<{ total: number; items: MaterialSummary[] }>(`/materials?limit=${limit}&offset=${offset}`),
  getMaterial: (id: number) => get<MaterialDetail>(`/materials/${id}`),
  getTags: () => get<TagDimensionView[]>(`/tags`),
  getJobs: () => get<JobView[]>(`/jobs`),
  getJob: (id: number) => get<any>(`/jobs/${id}`),
  triggerLabel: () => post<{ job_id: number }>(`/jobs/label`, {}),
  confirmTag: (mid: number, tag_value_id: number, action: 'confirm' | 'reject') =>
    post(`/materials/${mid}/tags`, { tag_value_id, action }),
  // Image URLs are synchronous (<img src>), so they can't await resolvePort.
  // They are only rendered after getMaterial() succeeds — by which point
  // resolvePort has run and cached the port in _port. Use the cached value;
  // if somehow not yet resolved, fall back to the env/8765 (rare race).
  getImageUrl: (mid: number, path: string) => {
    const port = _port || (import.meta as any).env.VITE_SIDECAR_PORT || '8765';
    return `http://127.0.0.1:${port}/materials/${mid}/image?path=${encodeURIComponent(path)}`;
  },
  getClusters: () => get<ClusterView[]>('/questions/clusters'),
  getClusterQuestions: (cid: number) => get<QuestionView[]>(`/clusters/${cid}/questions`),
  listQuestions: (clusterId?: number) =>
    get<QuestionView[]>(`/questions${clusterId ? '?cluster_id=' + clusterId : ''}`),
  renameCluster: (cid: number, name: string, description?: string) =>
    put(`/clusters/${cid}`, { name, description }),
  extractAssets: (material_ids: number[], types: string[]) =>
    post<{ job_id: number }>('/synthesis/extract', { material_ids, types }),
  listAssets: (type?: string) =>
    get<AssetView[]>(`/assets${type ? '?type=' + type : ''}`),
  updateAsset: (aid: number, body: { text?: string; disliked?: boolean }) =>
    put(`/assets/${aid}`, body),
  deleteAsset: async (aid: number) => {
    const r = await fetch(`${await baseUrl()}/assets/${aid}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },
  // Eagerly resolve the port (call once on app mount) so getImageUrl works.
  initPort: () => resolvePort(),
};

