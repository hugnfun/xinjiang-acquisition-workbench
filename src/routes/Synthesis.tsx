import { useEffect, useRef, useState } from 'react';
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
  const refreshTimer = useRef<number | null>(null);

  // race-guard：tab 快速切换时丢弃过期响应；卸载时清掉未触发的刷新定时器
  useEffect(() => {
    let active = true;
    api.listAssets(tab).then(list => { if (active) setAssets(list); });
    return () => { active = false; };
  }, [tab]);
  useEffect(() => () => {
    if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
  }, []);

  const refresh = () => api.listAssets(tab).then(setAssets);

  const extract = async () => {
    if (selectedMats.length === 0) { alert('请先在素材库选素材（输入 id 逗号分隔）'); return; }
    setBusy(true);
    try {
      const { job_id } = await api.extractAssets(selectedMats, [tab]);
      alert(`提炼任务已提交 (job ${job_id})，稍后刷新查看`);
      if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
      refreshTimer.current = window.setTimeout(refresh, 3000);
    } catch (e) {
      alert(`提炼失败: ${e instanceof Error ? e.message : e}`);
    } finally { setBusy(false); }
  };

  // dislike 后 refresh：服务端 GET /assets 默认 include_disliked=false 已过滤，
  // 点踩的卡片会从列表消失（非 bug）
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
