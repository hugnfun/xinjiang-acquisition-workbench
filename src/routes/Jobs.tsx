import { Fragment, useEffect, useState } from 'react';
import { api } from '../api/client';
import type { JobView } from '../types/models';

interface JobLogEntry { level: string; message: string; created_at: string | null; }
interface JobDetail {
  id: number; type: string; status: string;
  params: any; result_summary: any; error: string | null;
  logs: JobLogEntry[];
}

export default function Jobs() {
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [busy, setBusy] = useState<'label' | 'question-pool' | 'scrape' | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<Record<number, JobDetail>>({});
  const [detailErr, setDetailErr] = useState<string | null>(null);
  const [scrapeKeyword, setScrapeKeyword] = useState('');
  const [scrapeLimit, setScrapeLimit] = useState(20);

  const refresh = () =>
    api.getJobs().then(r => { setJobs(r); }).catch(e => setErr(e?.message || String(e)));
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2000);
    return () => clearInterval(t);
  }, []);

  const trigger = async (kind: 'label' | 'question-pool') => {
    setBusy(kind); setErr(null);
    try {
      if (kind === 'label') await api.triggerLabel();
      else await api.triggerQuestionPool();
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(null);
    }
    setTimeout(refresh, 500);
  };

  const triggerScrape = async () => {
    if (!scrapeKeyword.trim()) { setErr('请输入抓取关键词'); return; }
    setBusy('scrape'); setErr(null);
    try {
      await api.triggerScrape(scrapeKeyword.trim(), scrapeLimit);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(null);
    }
    setTimeout(refresh, 500);
  };

  // 防重：有 job 正在 running 时禁用触发按钮
  const running = jobs.some(j => j.status === 'running' || j.status === 'queued');

  const toggle = async (id: number) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id);
    setDetailErr(null);
    try {
      const d = await api.getJob(id);
      setDetail(prev => ({ ...prev, [id]: d }));
    } catch (e: any) {
      setDetailErr(e?.message || String(e));
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>任务中心</h2>
      <div style={{ marginBottom: 8 }}>
        <button onClick={() => trigger('label')} disabled={busy !== null || running} style={{ marginRight: 8 }}>
          {busy === 'label' ? '提交中...' : '▶ 触发批量打标（全部素材）'}
        </button>
        <button onClick={() => trigger('question-pool')} disabled={busy !== null || running}>
          {busy === 'question-pool' ? '提交中...' : '▶ 问题池冷启动（评论→聚类→命名）'}
        </button>
        {running && (
          <span style={{ marginLeft: 12, color: '#996600' }}>⏳ 有任务运行中，请等待完成</span>
        )}
      </div>
      <div style={{ marginBottom: 8, padding: 8, background: '#f6f8fa' }}>
        <span style={{ marginRight: 8 }}>🔍 关键词抓取：</span>
        <input value={scrapeKeyword} onChange={e => setScrapeKeyword(e.target.value)}
               placeholder="如 新疆旅游" style={{ marginRight: 8, width: 160 }} />
        <span style={{ marginRight: 4 }}>上限</span>
        <input type="number" value={scrapeLimit} min={1} max={100}
               onChange={e => setScrapeLimit(Math.max(1, Number(e.target.value) || 20))}
               style={{ marginRight: 8, width: 60 }} />
        <button onClick={triggerScrape} disabled={busy !== null || running || !scrapeKeyword.trim()}>
          {busy === 'scrape' ? '提交中...' : '▶ 抓取并入库'}
        </button>
      </div>
      {err && (
        <div style={{ marginTop: 8, padding: 8, color: '#b00020', background: '#fdecea' }}>
          {err}
        </div>
      )}
      <table style={{ marginTop: 16, width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr><th align="left">ID</th><th align="left">类型</th><th align="left">状态</th><th align="left">创建</th><th align="left">错误</th></tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <Fragment key={j.id}>
              <tr onClick={() => toggle(j.id)} style={{ borderBottom: '1px solid #eee', cursor: 'pointer' }}>
                <td>{j.id}</td>
                <td>{j.type}</td>
                <td>{j.status}</td>
                <td>{j.created_at}</td>
                <td style={{ color: 'red' }}>{j.error}</td>
              </tr>
              {expanded === j.id && (
                <tr>
                  <td colSpan={5} style={{ background: '#fafafa', padding: 8 }}>
                    {detailErr && <div style={{ color: '#b00020' }}>加载日志失败：{detailErr}</div>}
                    {!detailErr && !detail[j.id] && <div>加载中...</div>}
                    {detail[j.id] && (
                      <div style={{ fontSize: 13 }}>
                        {detail[j.id].error && (
                          <div style={{ color: '#b00020', marginBottom: 4 }}>错误：{detail[j.id].error}</div>
                        )}
                        <div>摘要：{JSON.stringify(detail[j.id].result_summary)}</div>
                        <div style={{ marginTop: 4 }}>日志：</div>
                        {detail[j.id].logs.length === 0 && <div style={{ color: '#999' }}>（无日志）</div>}
                        {detail[j.id].logs.map((l, i) => (
                          <div key={i} style={{ fontFamily: 'monospace', color: l.level === 'error' ? '#b00020' : '#555' }}>
                            [{l.level}] {l.created_at || ''} {l.message}
                          </div>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
