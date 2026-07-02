import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ClusterView, QuestionView } from '../types/models';

export default function Questions() {
  const [clusters, setClusters] = useState<ClusterView[]>([]);
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);
  const [questions, setQuestions] = useState<QuestionView[]>([]);
  const [renaming, setRenaming] = useState<string>('');

  useEffect(() => { api.getClusters().then(setClusters); }, []);
  useEffect(() => {
    if (selectedCluster) api.getClusterQuestions(selectedCluster).then(setQuestions);
    else setQuestions([]);
  }, [selectedCluster]);

  const rename = async () => {
    if (!selectedCluster || !renaming.trim()) return;
    await api.renameCluster(selectedCluster, renaming.trim());
    api.getClusters().then(setClusters);
  };

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 50px)' }}>
      <div style={{ width: '30%', borderRight: '1px solid #eee', overflow: 'auto' }}>
        {clusters.map(c => (
          <div key={c.id} onClick={() => setSelectedCluster(c.id)}
               style={{ padding: 12, cursor: 'pointer', background: selectedCluster === c.id ? '#f0f8ff' : 'transparent' }}>
            <div style={{ fontWeight: 500 }}>{c.name || '(未命名)'}</div>
            <div style={{ color: '#888', fontSize: 13 }}>{c.question_count} 个问题</div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {selectedCluster ? (
          <>
            <h2>{clusters.find(c => c.id === selectedCluster)?.name || '(未命名)'}</h2>
            <div style={{ marginBottom: 16 }}>
              <input value={renaming} onChange={e => setRenaming(e.target.value)} placeholder="重命名簇" />
              <button onClick={rename}>改名</button>
            </div>
            {questions.map(q => (
              <div key={q.id} style={{ marginBottom: 12, borderBottom: '1px solid #f5f5f5', paddingBottom: 8 }}>
                <div>{q.normalized_text}</div>
                <div style={{ color: '#aaa', fontSize: 12 }}>原文: {q.raw_text}</div>
                <div style={{ color: '#0066cc', fontSize: 12, cursor: 'pointer' }}
                     onClick={() => window.open(`#material-${q.source_ref}`, '_blank')}>
                  回溯评论 #{q.source_ref}
                </div>
              </div>
            ))}
          </>
        ) : <p>选一个簇查看问题</p>}
      </div>
    </div>
  );
}
