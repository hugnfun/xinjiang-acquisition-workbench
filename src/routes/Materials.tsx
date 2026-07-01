import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { MaterialSummary, MaterialDetail } from '../types/models';

export default function Materials() {
  const [list, setList] = useState<MaterialSummary[]>([]);
  const [selected, setSelected] = useState<MaterialDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getMaterials(50, 0).then(r => setList(r.items));
  }, []);

  const open = async (id: number) => {
    setLoading(true);
    const d = await api.getMaterial(id);
    setSelected(d); setLoading(false);
  };

  const onTagAction = async (tvId: number, action: 'confirm' | 'reject') => {
    if (!selected) return;
    await api.confirmTag(selected.id, tvId, action);
    const d = await api.getMaterial(selected.id);
    setSelected(d);
    const r = await api.getMaterials(50, 0);
    setList(r.items);
  };

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ width: '40%', overflow: 'auto', borderRight: '1px solid #eee' }}>
        {list.map(m => (
          <div key={m.id} onClick={() => open(m.id)}
               style={{ padding: 12, cursor: 'pointer', borderBottom: '1px solid #f5f5f5' }}>
            <div style={{ fontWeight: 500 }}>{m.title}</div>
            <div style={{ color: '#888', fontSize: 13 }}>
              👤{m.author} 👍{m.likes} 💬{m.comments_count}
            </div>
            <div>
              {m.tags.map(t => (
                <span key={t.tag_value_id} style={{
                  fontSize: 12, margin: 2, padding: '2px 6px',
                  borderRadius: 4,
                  background: t.confirmed_by_human ? '#d4edda' : '#fff3cd',
                  opacity: t.confidence != null && t.confidence < 0.6 ? 0.6 : 1,
                }}>
                  {t.value}{t.confidence != null && t.confidence < 0.6 ? '?' : ''}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {loading && <p>加载中...</p>}
        {selected && (
          <>
            <h2>{selected.title}</h2>
            <p style={{ color: '#666' }}>👤{selected.author} · 👍{selected.likes} · 💛{selected.collects} · 💬{selected.comments_count}</p>
            <div style={{ display: 'flex', gap: 8, overflowX: 'auto', marginBottom: 16 }}>
              {selected.images.map(img => (
                <img key={img.idx} src={api.getImageUrl(selected.id, img.path)}
                     style={{ height: 200, borderRadius: 8 }} />
              ))}
            </div>
            <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{selected.content}</pre>
            <h3>标签</h3>
            {selected.tags.map(t => (
              <div key={t.tag_value_id} style={{ marginBottom: 6 }}>
                <span style={{ background: '#f0f0f0', padding: '2px 8px', borderRadius: 4 }}>
                  [{t.dimension}] {t.value}
                  {t.confidence != null && ` (${t.confidence})`}
                  {t.confirmed_by_human ? ' ✓' : ''}
                </span>
                {!t.confirmed_by_human && (
                  <>
                    <button onClick={() => onTagAction(t.tag_value_id, 'confirm')}>确认</button>
                    <button onClick={() => onTagAction(t.tag_value_id, 'reject')}>拒绝</button>
                  </>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
