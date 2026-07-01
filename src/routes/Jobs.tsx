import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { JobView } from '../types/models';

export default function Jobs() {
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [busy, setBusy] = useState(false);

  const refresh = () => api.getJobs().then(setJobs);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const trigger = async () => {
    setBusy(true);
    try { await api.triggerLabel(); } finally { setBusy(false); }
    setTimeout(refresh, 500);
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>任务中心</h2>
      <button onClick={trigger} disabled={busy}>
        {busy ? '提交中...' : '▶ 触发批量打标（全部素材）'}
      </button>
      <table style={{ marginTop: 16, width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr><th align="left">ID</th><th align="left">类型</th><th align="left">状态</th><th align="left">创建</th><th align="left">错误</th></tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.id} style={{ borderBottom: '1px solid #eee' }}>
              <td>{j.id}</td>
              <td>{j.type}</td>
              <td>{j.status}</td>
              <td>{j.created_at}</td>
              <td style={{ color: 'red' }}>{j.error}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
