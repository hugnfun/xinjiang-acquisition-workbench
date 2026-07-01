import type { MaterialSummary, MaterialDetail, TagDimensionView, JobView } from '../types/models';

function getPort(): string {
  // 1. Port injected by Tauri (main.rs spawns the sidecar on a free port and
  //    evals `window.__SIDECAR_PORT__ = <port>` into the webview).
  const injected = (window as any).__SIDECAR_PORT__;
  if (injected) return String(injected);
  // 2. Vite env override (for non-Tauri / `npm run dev` workflows).
  const env = (import.meta as any).env.VITE_SIDECAR_PORT;
  if (env) return String(env);
  // 3. Fallback.
  return '8765';
}
// LAZY: computed per-request, not at module load. Tauri's setup() hook evals
// `window.__SIDECAR_PORT__ = <port>` AFTER the webview's JS modules load, so a
// module-load `const BASE` would read an undefined port and fall back to 8765
// while the real sidecar runs on a random free port → ECONNREFUSED. By the
// time any real fetch fires (post-mount useEffect / event handler), the eval
// has run and the injected port is set.
function baseUrl(): string {
  return `http://127.0.0.1:${getPort()}`;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${baseUrl()}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}
async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${baseUrl()}${path}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
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
  getImageUrl: (mid: number, path: string) => `${baseUrl()}/materials/${mid}/image?path=${encodeURIComponent(path)}`,
};
