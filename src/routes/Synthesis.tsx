import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { AssetView } from "../types/models";
import { getSelectedMaterialIds, clearMaterialSelection, onSelectionChange } from "../App";

const STATUS_LABELS: Record<string, string> = {
  pending: "待审", minor_edit: "小改可用", ready: "直接可用",
  adopted: "已采用", published: "已发布",
};
const STATUS_COLORS: Record<string, string> = {
  pending: "#fff3cd", minor_edit: "#e0f2fe", ready: "#d4edda",
  adopted: "#d1e7dd", published: "#cfe2ff",
};
const STATUS_TEXT_COLORS: Record<string, string> = {
  pending: "#856404", minor_edit: "#0369a1", ready: "#155724",
  adopted: "#0f5132", published: "#084298",
};

const TYPES = [
  { key: "selling_point", label: "卖点" },
  { key: "hook", label: "钩子" },
  { key: "cta", label: "CTA" },
  { key: "title", label: "标题" },
];

export default function Synthesis({ onNavigateToMaterial }: {
  onNavigateToMaterial?: (id: number) => void;
}) {
  const [tab, setTab] = useState("selling_point");
  const [assets, setAssets] = useState<AssetView[]>([]);
  const [busy, setBusy] = useState(false);
  const [selCount, setSelCount] = useState(0);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const refreshTimer = useRef<number | null>(null);
  const tabRef = useRef(tab);

  useEffect(() => {
    tabRef.current = tab;
    let active = true;
    api.listAssets(tab, statusFilter).then(list => { if (active) setAssets(list); });
    return () => { active = false; };
  }, [tab]);

  useEffect(() => {
    const unsub = onSelectionChange(() => setSelCount(getSelectedMaterialIds().length));
    setSelCount(getSelectedMaterialIds().length);
    return unsub;
  }, []);

  useEffect(() => () => {
    if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
  }, []);

  const refresh = () => api.listAssets(tabRef.current, statusFilter).then(setAssets);

  const pollJob = (jobId: number, attempt = 0) => {
    api.getJob(jobId).then(job => {
      if (job.status === "done") {
        setNotice(`提炼完成，新增 ${job.result_summary?.written ?? 0} 条`);
        setBusy(false);
        refresh();
      } else if (job.status === "failed" || job.status === "cancelled") {
        setNotice(job.status === "failed" ? `提炼失败：${job.error || "请到任务中心查看日志"}` : "提炼任务已取消");
        setBusy(false);
      } else if (attempt < 300) {
        refreshTimer.current = window.setTimeout(() => pollJob(jobId, attempt + 1), 1000);
      } else {
        setNotice(`任务 #${jobId} 仍在运行，请到任务中心继续查看`);
        setBusy(false);
      }
    }).catch(e => {
      setNotice(`读取任务状态失败：${e?.message || String(e)}`);
      setBusy(false);
    });
  };

  const extract = async () => {
    const ids = getSelectedMaterialIds();
    if (ids.length === 0) { alert("请先到「素材库」勾选素材（详情页点\"加入合成选区\"）"); return; }
    setBusy(true);
    setNotice(null);
    try {
      const { job_id } = await api.extractAssets(ids, [tab]);
      setNotice(`提炼任务 #${job_id} 已排队`);
      if (refreshTimer.current) window.clearTimeout(refreshTimer.current);
      pollJob(job_id);
    } catch (e) {
      setNotice("提炼失败: " + e);
      setBusy(false);
    }
  };

  const dislike = async (aid: number) => {
    await api.updateAsset(aid, { disliked: true });
    refresh();
  };

  const del = async (aid: number) => {
    try { await api.deleteAsset(aid); refresh(); }
    catch (e) { alert("删除失败: " + e); }
  };

  const saveEdit = async (aid: number) => {
    if (!editText.trim()) return;
    try { await api.updateAsset(aid, { text: editText.trim() }); setEditingId(null); refresh(); }
    catch (e) { alert("编辑失败: " + e); }
  };

  return (
    <div style={{ padding: 16, height: "100%", overflow: "auto" }}>
      <div style={{ marginBottom: 12, display: "flex", gap: 4 }}>
        {TYPES.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            style={{ padding: "4px 16px", border: "none", borderRadius: 4, cursor: "pointer",
              background: tab === t.key ? "#2563eb" : "#e5e7eb", color: tab === t.key ? "#fff" : "#333",
              fontWeight: tab === t.key ? 600 : 400, fontSize: 14 }}>{t.label}</button>
        ))}
      </div>
      <div style={{ marginBottom: 12, display: "flex", gap: 8, alignItems: "center" }}>
        <select value={statusFilter ?? ""} onChange={e => { setStatusFilter(e.target.value || undefined); }} style={{ padding: "3px 8px", border: "1px solid #ccc", borderRadius: 4 }}>
          <option value="">全部状态</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <span style={{ fontSize: 13, color: "#888" }}>{assets.length} 条</span>
      </div>
      {/* 顶部「让 AI 从选中素材里提炼新一批」按钮 (spec §5.4) */}
      <div style={{ marginBottom: 16, padding: 12, background: "#f9f9f9", borderRadius: 6, display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 14 }}>
          合成选区：<strong style={{ color: selCount > 0 ? "#2563eb" : "#999" }}>{selCount}</strong> 篇素材
        </span>
        {selCount > 0 && <button onClick={() => clearMaterialSelection()} style={{ fontSize: 12, border: "none", background: "none", color: "#2563eb", cursor: "pointer", textDecoration: "underline" }}>清空</button>}
        <button onClick={extract} disabled={busy}
          style={{ marginLeft: "auto", padding: "6px 16px", border: "1px solid #2563eb", borderRadius: 4, background: "#2563eb", color: "#fff", cursor: "pointer", fontSize: 14, opacity: busy ? 0.6 : 1 }}>
          {busy ? "提炼中…" : "让 AI 从选中素材里提炼新一批"}
        </button>
      </div>
      {notice && <div style={{ marginBottom: 12, padding: 8, background: notice.includes("失败") ? "#fdecea" : "#e8f0fe", color: notice.includes("失败") ? "#b00020" : "#1a56db" }}>{notice}</div>}
      {assets.length === 0 && <p style={{ color: "#999" }}>暂无合成物。先到素材库选素材，再点提炼。</p>}
      {assets.map(a => (
        <div key={a.id} style={{ padding: 12, marginBottom: 8, borderBottom: "1px solid #eee" }}>
          {editingId === a.id ? (
            <div style={{ marginBottom: 8 }}>
              <textarea value={editText} onChange={e => setEditText(e.target.value)} rows={3}
                style={{ width: "100%", padding: 6, border: "1px solid #ccc", borderRadius: 4, boxSizing: "border-box", fontFamily: "inherit" }} autoFocus />
              <div style={{ display: "flex", gap: 4 }}>
                <button onClick={() => saveEdit(a.id)} style={{ padding: "3px 10px", border: "1px solid #2563eb", borderRadius: 3, background: "#2563eb", color: "#fff", cursor: "pointer" }}>保存</button>
                <button onClick={() => setEditingId(null)} style={{ padding: "3px 10px", border: "1px solid #ccc", borderRadius: 3, cursor: "pointer" }}>取消</button>
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: 6, lineHeight: 1.6 }}>{a.text}</div>
          )}
          {/* 质量状态 */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
            <span style={{ fontSize: 12, padding: "1px 8px", borderRadius: 3, background: STATUS_COLORS[a.status] || "#e5e7eb", color: STATUS_TEXT_COLORS[a.status] || "#555" }}>
              {STATUS_LABELS[a.status] || a.status}
            </span>
            <select value={a.status} onChange={e => { api.updateAsset(a.id, { status: e.target.value }).then(refresh); }}
              style={{ fontSize: 12, padding: "1px 4px", border: "1px solid #ddd", borderRadius: 3 }}>
              {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          {/* 适用标签 chips (spec §5.4) */}
          {a.tags.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 4 }}>
              {a.tags.map((t, i) => (
                <span key={i} style={{ fontSize: 12, padding: "1px 6px", borderRadius: 3, background: "#e8f0fe", color: "#1a56db" }}>{t}</span>
              ))}
            </div>
          )}
          {/* 来源素材链接（点击跳 /materials/<id>）(spec §5.4) */}
          <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>
            来源素材：
            {a.derived_from.map((mid, i) => (
              <span key={mid}>
                {i > 0 && " · "}
                <a href={"#/materials/" + mid} onClick={e => { e.preventDefault(); onNavigateToMaterial?.(mid); }}
                  style={{ color: "#2563eb", cursor: "pointer", textDecoration: "underline" }}>#{mid}</a>
              </span>
            ))}
          </div>
          {/* [编辑] [删除] [不喜欢] (spec §5.4) */}
          {editingId !== a.id && (
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={() => { setEditingId(a.id); setEditText(a.text); }} style={{ fontSize: 12, padding: "2px 8px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer" }}>编辑</button>
              <button onClick={() => del(a.id)} style={{ fontSize: 12, padding: "2px 8px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer", color: "#b00020" }}>删除</button>
              <button onClick={() => dislike(a.id)} style={{ fontSize: 12, padding: "2px 8px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer" }}>不喜欢</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
