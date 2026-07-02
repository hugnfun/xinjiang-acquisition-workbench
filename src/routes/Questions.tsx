import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ClusterView, QuestionView } from '../types/models';

export default function Questions() {
  const [clusters, setClusters] = useState<ClusterView[]>([]);
  const [selectedCluster, setSelectedCluster] = useState<number | null>(null);
  const [questions, setQuestions] = useState<QuestionView[]>([]);
  const [renaming, setRenaming] = useState<string>('');

  // race-guard：卸载或簇切换时丢弃过期响应，避免在已卸载组件上 setState
  useEffect(() => {
    let active = true;
    api.getClusters().then(list => { if (active) setClusters(list); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!selectedCluster) { setQuestions([]); return; }
    let active = true;
    api.getClusterQuestions(selectedCluster).then(list => { if (active) setQuestions(list); });
    return () => { active = false; };
  }, [selectedCluster]);

  const rename = async () => {
    if (!selectedCluster || !renaming.trim()) return;
    try {
      await api.renameCluster(selectedCluster, renaming.trim());
      setRenaming('');  // 改名成功后清空输入
      api.getClusters().then(setClusters);
    } catch (e) {
      alert(`改名失败: ${e instanceof Error ? e.message : e}`);
    }
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
                {/* 回溯到 /materials 该评论的路由尚未实现(spec 暂缓)；先纯文本显示来源，避免 #material-X 开垃圾页 */}
                <div style={{ color: '#888', fontSize: 12 }}>来源评论 #{q.source_ref ?? '—'}</div>
              </div>
            ))}
          </>
        ) : <p>选一个簇查看问题</p>}
      </div>
    </div>
  );
}
