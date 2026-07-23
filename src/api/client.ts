import type { MaterialSummary, MaterialDetail, TagDimensionView, JobView, ClusterView, QuestionView, AssetView } from '../types/models';

// Cached sidecar port. Resolved once via the `get_sidecar_port` Tauri command
// (pull-based — the frontend asks for the port before its first fetch), which
// avoids the eval-injection race where setup() ran before the webview's JS
// loaded, leaving window.__SIDECAR_PORT__ undefined → 8765 fallback → "Load failed".
let _port: string | null = null;

async function resolvePort(): Promise<string> {
  if (_port) return _port;
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
  // ── 素材库 ──
  getMaterials: (limit = 50, offset = 0, order = 'likes', search?: string, tagValueId?: number) => {
    const params = new URLSearchParams();
    params.set('limit', String(limit));
    params.set('offset', String(offset));
    params.set('order', order);
    if (search) params.set('search', search);
    if (tagValueId) params.set('tag_value_id', String(tagValueId));
    return get<{ total: number; items: MaterialSummary[] }>(`/materials?${params}`);
  },
  getMaterial: (id: number) => get<MaterialDetail>(`/materials/${id}`),
  confirmTag: (mid: number, tag_value_id: number, action: 'confirm' | 'reject' | 'suggest_new', extra?: { new_dimension?: string; new_value?: string }) =>
    post(`/materials/${mid}/tags`, { tag_value_id, action, ...extra }),
  batchTag: (material_ids: number[], tag_value_id: number) =>
    post<{ ok: boolean; added: number }>(`/materials/batch/tags`, { material_ids, tag_value_id }),

  // ── 标签体系 ──
  getTags: () => get<TagDimensionView[]>(`/tags`),
  mergeTags: (source_id: number, target_id: number) =>
    post(`/tags/merge`, { source_id, target_id }),
  updateTagValue: (vid: number, body: { value?: string; add_alias?: string; status?: string }) =>
    put(`/tag-values/${vid}`, body),
  createDimension: (name: string, description: string) =>
    post(`/tag-dimensions`, { name, description }),
  createTagValue: (did: number, value: string) =>
    post(`/tag-dimensions/${did}/values`, { value }),
  getSuggestions: () => get<any[]>(`/tags/suggestions`),
  actSuggestion: (sid: number, action: string, merge_into_value_id?: number, rename?: string) =>
    post(`/tags/suggestions/${sid}`, { action, merge_into_value_id, rename }),

  // ── 问题池 ──
  getClusters: () => get<ClusterView[]>('/questions/clusters'),
  getClusterQuestions: (cid: number) => get<QuestionView[]>(`/clusters/${cid}/questions`),
  listQuestions: (clusterId?: number) =>
    get<QuestionView[]>(`/questions${clusterId ? '?cluster_id=' + clusterId : ''}`),
  renameCluster: (cid: number, name: string, description?: string) =>
    put(`/clusters/${cid}`, { name, description }),
  createCluster: (name: string, description?: string, parent_id?: number | null) =>
    post(`/clusters`, { name, description: description || '', parent_id: parent_id ?? null }),
  mergeClusters: (source_id: number, target_id: number) =>
    post(`/clusters/merge`, { source_id, target_id }),
  splitCluster: (cid: number, question_ids: number[], new_cluster_name: string) =>
    post(`/clusters/${cid}/split`, { question_ids, new_cluster_name }),
  moveCluster: (cid: number, parent_id: number | null) =>
    put(`/clusters/${cid}/move`, { parent_id }),
  deleteCluster: async (cid: number) => {
    const r = await fetch(`${await baseUrl()}/clusters/${cid}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  },
  rewriteQuestion: (qid: number, normalized_text: string) =>
    put(`/questions/${qid}`, { normalized_text }),
  moveQuestion: (qid: number, target_cluster_id: number) =>
    put(`/questions/${qid}/move`, { target_cluster_id }),

  // ── 合成库 ──
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

  // ── 任务中心 ──
  getJobs: () => get<JobView[]>(`/jobs`),
  getJob: (id: number) => get<any>(`/jobs/${id}`),
  retryJob: (id: number) => post<{ job_id: number }>(`/jobs/${id}/retry`, {}),
  cancelJob: (id: number) =>
    post<{ job_id: number; status: string }>(`/jobs/${id}/cancel`, {}),
  triggerLabel: () => post<{ job_id: number }>(`/jobs/label`, {}),
  triggerRelabel: (material_ids: number[]) =>
    post<{ job_id: number }>(`/jobs/relabel`, { material_ids }),
  triggerQuestionPool: () => post<{ job_id: number }>(`/jobs/question-pool`, {}),
  triggerQuestionPoolIncremental: () =>
    post<{ job_id: number }>(`/jobs/question-pool`, { mode: 'incremental' }),
  triggerReport: () => post<{ job_id: number }>(`/jobs/report`, {}),
  triggerScrape: (body: { mode: string; keyword?: string; url?: string; limit: number }) =>
    post<{ job_id: number }>(`/jobs/scrape`, body),

  // Image URLs are synchronous (<img src>), so they can't await resolvePort.
  getImageUrl: (mid: number, path: string) => {
    const port = _port || (import.meta as any).env.VITE_SIDECAR_PORT || '8765';
    return `http://127.0.0.1:${port}/materials/${mid}/image?path=${encodeURIComponent(path)}`;
  },
  initPort: () => resolvePort(),
};
