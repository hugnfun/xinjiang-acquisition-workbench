import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { AssetView } from '../types/models';

const TYPES = [
  { key: 'selling_point', label: '卖点' },
  { key: 'hook', label: '钩子' },
  { key: 'cta', label: 'CTA' },
  { key: 'title', label: '标题' },
];

export default function Synthesis() {
  const [tab, setTab] = useState('selling_point');
  const [assets, setAssets] = useState<AssetView[]>([]);
  const [selectedMats, setSelectedMats] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.listAssets(tab).then(setAssets);
  useEffect(() => { refresh(); }, [tab]);

  const extract = async () => {
    if (selectedMats.length === 0) { alert('请先在素材库选素材（输入 id 逗号分隔）'); return; }
    setBusy(true);
    try {
      const { job_id } = await api.extractAssets(selectedMats, [tab]);
      alert(`提炼任务已提交 (job ${job_id})，稍后刷新查看`);
      setTimeout(refresh, 3000);
    } finally { setBusy(false); }
  };

  const dislike = async (aid: number) => {
    await api.updateAsset(aid, { disliked: true });
    refresh();
  };

  return (
    <div style={{ padding: 16 }}>
      <div style={{ marginBottom: 16 }}>
        {TYPES.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
                  style={{ fontWeight: tab===t.key?700:400, marginRight: 8 }}>{t.label}</button>
        ))}
      </div>
      <div style={{ marginBottom: 16, padding: 12, background: '#f9f9f9' }}>
        <input placeholder="素材 id 逗号分隔，如 1,2,3"
               onChange={e => setSelectedMats(e.target.value.split(',').map(x=>parseInt(x.trim())).filter(x=>x))} />
        <button onClick={extract} disabled={busy}>{busy ? '提炼中...' : '提炼合成物'}</button>
      </div>
      {assets.map(a => (
        <div key={a.id} style={{ padding: 12, marginBottom: 8, borderBottom: '1px solid #eee' }}>
          <div>{a.text}</div>
          <div style={{ color: '#888', fontSize: 12 }}>
            来源素材: {a.derived_from.join(',')} · 标签: {a.tags.join(',')}
          </div>
          <button onClick={() => dislike(a.id)} style={{ fontSize: 12 }}>👎 不喜欢</button>
        </div>
      ))}
    </div>
  );
}
