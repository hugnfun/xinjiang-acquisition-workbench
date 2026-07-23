import { Fragment, useEffect, useState } from "react";
import { api } from "../api/client";
import type { JobView } from "../types/models";

interface JobLogEntry { level: string; message: string; created_at: string | null; }
interface JobDetail {
  id: number; type: string; status: string;
  params: any; result_summary: any; error: string | null;
  progress: number; progress_total: number;
  logs: JobLogEntry[];
}

type JobTab = "scrape" | "ai";

export default function Jobs() {
  const [tab, setTab] = useState<JobTab>("scrape");
  const [jobs, setJobs] = useState<JobView[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<Record<number, JobDetail>>({});
  const [detailErr, setDetailErr] = useState<string | null>(null);

  // scrape form state
  const [scrapeMode, setScrapeMode] = useState<"keyword" | "note" | "user">("keyword");
  const [scrapeKeyword, setScrapeKeyword] = useState("");
  const [scrapeUrl, setScrapeUrl] = useState("");
  const [scrapeLimit, setScrapeLimit] = useState(20);

  const refresh = () => api.getJobs().then(setJobs).catch(e => setErr(e?.message || String(e)));
  useEffect(() => { refresh(); const t = setInterval(refresh, 2000); return () => clearInterval(t); }, []);

  const trigger = async (kind: string) => {
    setBusy(kind); setErr(null);
    try {
      if (kind === "label") await api.triggerLabel();
      else if (kind === "question-pool") await api.triggerQuestionPool();
      else if (kind === "incremental") await api.triggerQuestionPoolIncremental();
      else if (kind === "report") await api.triggerReport();
    } catch (e: any) { setErr(e?.message || String(e)); }
    finally { setBusy(null); }
    setTimeout(refresh, 500);
  };

  const triggerScrape = async () => {
    if (scrapeMode === "keyword" && !scrapeKeyword.trim()) { setErr("请输入关键词"); return; }
    if ((scrapeMode === "note" || scrapeMode === "user") && !scrapeUrl.trim()) { setErr("请输入 URL"); return; }
    setBusy("scrape"); setErr(null);
    try {
      await api.triggerScrape({
        mode: scrapeMode,
        keyword: scrapeMode === "keyword" ? scrapeKeyword.trim() : undefined,
        url: scrapeMode !== "keyword" ? scrapeUrl.trim() : undefined,
        limit: scrapeLimit,
      });
    } catch (e: any) { setErr(e?.message || String(e)); }
    finally { setBusy(null); }
    setTimeout(refresh, 500);
  };

  const retry = async (id: number) => {
    try { await api.retryJob(id); refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const cancel = async (id: number) => {
    try { await api.cancelJob(id); refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const running = jobs.some(j => j.status === "running" || j.status === "queued");

  const toggle = async (id: number) => {
    if (expanded === id) { setExpanded(null); return; }
    setExpanded(id); setDetailErr(null);
    try { const d = await api.getJob(id); setDetail(prev => ({ ...prev, [id]: d })); }
    catch (e: any) { setDetailErr(e?.message || String(e)); }
  };

  const pct = (p: number, t: number) => t > 0 ? Math.round(p / t * 100) : 0;

  return (
    <div style={{ padding: 16, height: "100%", overflow: "auto" }}>
      <h2 style={{ marginTop: 0 }}>任务中心</h2>
      {/* Tabs: 抓取 / AI (spec §5.5) */}
      <div style={{ marginBottom: 16, display: "flex", gap: 4 }}>
        <button onClick={() => setTab("scrape")} style={{ padding: "6px 20px", border: "none", borderRadius: 4, cursor: "pointer", background: tab === "scrape" ? "#2563eb" : "#e5e7eb", color: tab === "scrape" ? "#fff" : "#333", fontWeight: tab === "scrape" ? 600 : 400 }}>抓取</button>
        <button onClick={() => setTab("ai")} style={{ padding: "6px 20px", border: "none", borderRadius: 4, cursor: "pointer", background: tab === "ai" ? "#2563eb" : "#e5e7eb", color: tab === "ai" ? "#fff" : "#333", fontWeight: tab === "ai" ? 600 : 400 }}>AI 批处理</button>
      </div>

      {tab === "scrape" && (
        <div style={{ marginBottom: 16, padding: 12, background: "#f6f8fa", borderRadius: 6 }}>
          {/* 抓取 tab：新关键词搜索 / 抓某条评论(笔记) / 抓某用户主页 (spec §5.5) */}
          <div style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
            <select value={scrapeMode} onChange={e => setScrapeMode(e.target.value as any)} style={{ padding: "4px", border: "1px solid #ccc", borderRadius: 4 }}>
              <option value="keyword">关键词搜索</option>
              <option value="note">抓单条笔记</option>
              <option value="user">抓用户主页</option>
            </select>
            {scrapeMode === "keyword" ? (
              <>
                <input value={scrapeKeyword} onChange={e => setScrapeKeyword(e.target.value)} placeholder="如 新疆旅游" style={{ padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4, width: 200 }} />
                <span style={{ fontSize: 13, color: "#666" }}>上限</span>
                <input type="number" value={scrapeLimit} min={1} max={100} onChange={e => setScrapeLimit(Math.max(1, Number(e.target.value) || 20))} style={{ padding: "4px", border: "1px solid #ccc", borderRadius: 4, width: 60 }} />
              </>
            ) : (
              <input value={scrapeUrl} onChange={e => setScrapeUrl(e.target.value)} placeholder={scrapeMode === "note" ? "笔记 URL" : "用户主页 URL"} style={{ padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4, width: 320 }} />
            )}
            <button onClick={triggerScrape} disabled={busy !== null || running} style={{ padding: "4px 16px", border: "1px solid #2563eb", borderRadius: 4, background: "#2563eb", color: "#fff", cursor: "pointer", opacity: busy !== null || running ? 0.6 : 1 }}>
              {busy === "scrape" ? "提交中…" : "抓取并入库"}
            </button>
          </div>
        </div>
      )}

      {tab === "ai" && (
        <div style={{ marginBottom: 16, padding: 12, background: "#f6f8fa", borderRadius: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {/* AI tab：批量打标 / 提炼问题 / 合成卖点 (spec §5.5) */}
          <button onClick={() => trigger("label")} disabled={busy !== null || running} style={{ padding: "6px 16px", border: "1px solid #2563eb", borderRadius: 4, background: "#2563eb", color: "#fff", cursor: "pointer", opacity: busy !== null || running ? 0.6 : 1 }}>
            {busy === "label" ? "提交中…" : "批量打标（仅未打标素材）"}
          </button>
          <button onClick={() => trigger("question-pool")} disabled={busy !== null || running} style={{ padding: "6px 16px", border: "1px solid #2563eb", borderRadius: 4, background: "#2563eb", color: "#fff", cursor: "pointer", opacity: busy !== null || running ? 0.6 : 1 }}>
            {busy === "question-pool" ? "提交中…" : "提炼问题（冷启动）"}
          </button>
          <button onClick={() => trigger("incremental")} disabled={busy !== null || running} style={{ padding: "6px 16px", border: "1px solid #ccc", borderRadius: 4, background: "#f5f5f5", cursor: "pointer", opacity: busy !== null || running ? 0.6 : 1 }}>
            {busy === "incremental" ? "提交中…" : "问题池增量更新"}
          </button>
          <button onClick={() => trigger("report")} disabled={busy !== null || running} style={{ padding: "6px 16px", border: "1px solid #ccc", borderRadius: 4, background: "#f5f5f5", cursor: "pointer", opacity: busy !== null || running ? 0.6 : 1 }}>
            {busy === "report" ? "提交中…" : "生成周报"}
          </button>
        </div>
      )}

      {running && <div style={{ marginBottom: 8, color: "#996600" }}>有任务运行中，请等待完成</div>}
      {err && <div style={{ marginBottom: 8, padding: 8, color: "#b00020", background: "#fdecea" }}>{err}</div>}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #eee", textAlign: "left" }}>
            <th style={{ padding: "4px 8px" }}>ID</th>
            <th style={{ padding: "4px 8px" }}>类型</th>
            <th style={{ padding: "4px 8px" }}>状态</th>
            <th style={{ padding: "4px 8px" }}>进度</th>
            <th style={{ padding: "4px 8px" }}>创建</th>
            <th style={{ padding: "4px 8px" }}>操作</th>
            <th style={{ padding: "4px 8px" }}>错误</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <Fragment key={j.id}>
              <tr onClick={() => toggle(j.id)} style={{ borderBottom: "1px solid #eee", cursor: "pointer" }}>
                <td style={{ padding: "4px 8px" }}>{j.id}</td>
                <td style={{ padding: "4px 8px" }}>{j.type}</td>
                <td style={{ padding: "4px 8px" }}>
                  <span style={{ fontSize: 12, padding: "1px 6px", borderRadius: 3, background: j.status === "done" ? "#d4edda" : j.status === "failed" ? "#fdecea" : "#fff3cd", color: j.status === "done" ? "#155724" : j.status === "failed" ? "#b00020" : "#856404" }}>{j.status}</span>
                </td>
                {/* 进度条 (spec §5.5) */}
                <td style={{ padding: "4px 8px", minWidth: 120 }}>
                  {j.progress_total > 0 ? (
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ flex: 1, height: 8, background: "#e5e7eb", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{ width: pct(j.progress, j.progress_total) + "%", height: "100%", background: "#2563eb", borderRadius: 4, transition: "width 0.3s" }} />
                      </div>
                      <span style={{ fontSize: 12, color: "#666", whiteSpace: "nowrap" }}>{j.progress}/{j.progress_total}</span>
                    </div>
                  ) : j.status === "running" ? "…" : "—"}
                </td>
                <td style={{ padding: "4px 8px", fontSize: 12, color: "#888" }}>{j.created_at?.slice(0, 19)}</td>
                <td style={{ padding: "4px 8px" }}>
                  {/* 失败重试 (spec §5.5) */}
                  {(j.status === "failed" || j.status === "cancelled") && (
                    <button onClick={e => { e.stopPropagation(); retry(j.id); }} style={{ fontSize: 12, padding: "2px 8px", border: "1px solid #ccc", borderRadius: 3, cursor: "pointer" }}>重试</button>
                  )}
                  {(j.status === "queued" || j.status === "running") && (
                    <button onClick={e => { e.stopPropagation(); cancel(j.id); }} style={{ fontSize: 12, padding: "2px 8px", border: "1px solid #ccc", borderRadius: 3, cursor: "pointer" }}>
                      {j.status === "running" ? "请求取消" : "取消"}
                    </button>
                  )}
                </td>
                <td style={{ padding: "4px 8px", color: "#b00020", fontSize: 12, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{j.error}</td>
              </tr>
              {expanded === j.id && (
                <tr>
                  <td colSpan={7} style={{ background: "#fafafa", padding: 8 }}>
                    {detailErr && <div style={{ color: "#b00020" }}>加载日志失败：{detailErr}</div>}
                    {!detailErr && !detail[j.id] && <div>加载中…</div>}
                    {detail[j.id] && (
                      <div style={{ fontSize: 13 }}>
                        {detail[j.id].error && <div style={{ color: "#b00020", marginBottom: 4 }}>错误：{detail[j.id].error}</div>}
                        <div>摘要：{JSON.stringify(detail[j.id].result_summary)}</div>
                        <div style={{ marginTop: 4 }}>参数：{JSON.stringify(detail[j.id].params)}</div>
                        <div style={{ marginTop: 4 }}>日志：</div>
                        {detail[j.id].logs.length === 0 && <div style={{ color: "#999" }}>（无日志）</div>}
                        {detail[j.id].logs.map((l, i) => (
                          <div key={i} style={{ fontFamily: "monospace", color: l.level === "error" ? "#b00020" : "#555" }}>
                            [{l.level}] {l.created_at?.slice(0, 19) || ""} {l.message}
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
