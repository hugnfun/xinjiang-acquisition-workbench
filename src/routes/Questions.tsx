import { useEffect, useState, useCallback } from "react";
import { api } from "../api/client";
import type { ClusterView, QuestionView } from "../types/models";

interface ClusterNode extends ClusterView { children: ClusterNode[] }

function buildTree(clusters: ClusterView[]): ClusterNode[] {
  const map = new Map<number, ClusterNode>();
  clusters.forEach(c => map.set(c.id, { ...c, children: [] }));
  const roots: ClusterNode[] = [];
  map.forEach(node => {
    if (node.parent_id && map.has(node.parent_id)) {
      map.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

export default function Questions() {
  const [clusters, setClusters] = useState<ClusterView[]>([]);
  const [selCid, setSelCid] = useState<number | null>(null);
  const [questions, setQuestions] = useState<QuestionView[]>([]);
  const [renaming, setRenaming] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [checkedQids, setCheckedQids] = useState<Set<number>>(new Set());
  const [splitName, setSplitName] = useState("");
  // 合并：选中的簇作为源，mergeTgt 是目标；mergeSearch 过滤目标列表
  const [mergeTgt, setMergeTgt] = useState<number | null>(null);
  const [mergeSearch, setMergeSearch] = useState("");
  const [newClName, setNewClName] = useState("");
  const [newClParent, setNewClParent] = useState<number | null>(null);
  const [rewriteId, setRewriteId] = useState<number | null>(null);
  const [rewriteVal, setRewriteVal] = useState("");
  const [selQuestion, setSelQuestion] = useState<QuestionView | null>(null);

  const refreshClusters = useCallback(() => {
    api.getClusters().then(setClusters).catch(e => setErr(e?.message || String(e)));
  }, []);

  useEffect(() => { refreshClusters(); }, [refreshClusters]);

  useEffect(() => {
    if (!selCid) { setQuestions([]); return; }
    let active = true;
    api.getClusterQuestions(selCid).then(list => { if (active) setQuestions(list); });
    return () => { active = false; };
  }, [selCid]);

  const tree = buildTree(clusters);
  const selCluster = clusters.find(c => c.id === selCid);

  const toggleExpand = (id: number) => {
    setExpanded(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };

  const rename = async () => {
    if (!selCid || !renaming.trim()) return;
    try { await api.renameCluster(selCid, renaming.trim()); setRenaming(""); refreshClusters(); }
    catch (e) { alert("改名失败: " + e); }
  };

  const createCluster = async () => {
    if (!newClName.trim()) return;
    try { await api.createCluster(newClName.trim(), "", newClParent); setNewClName(""); setNewClParent(null); refreshClusters(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doMerge = async () => {
    if (!selCid || !mergeTgt || selCid === mergeTgt) { alert("请先在左侧选一个源簇，再选目标簇"); return; }
    // Tauri webview 不支持 confirm()，用 window.alert 代替确认提示
    try {
      if (checkedQids.size > 0) {
        // 只搬勾选的问题到目标簇（不是整簇合并）
        for (const qid of checkedQids) {
          await api.moveQuestion(qid, mergeTgt);
        }
        setCheckedQids(new Set());
      } else {
        // 没勾选问题 → 整簇合并
        await api.mergeClusters(selCid, mergeTgt);
        setSelCid(mergeTgt);  // 跳到目标簇
      }
      setMergeTgt(null); setMergeSearch("");
      refreshClusters();
      if (selCid) setQuestions(await api.getClusterQuestions(selCid));
    }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doDelete = async () => {
    if (!selCid) return;
    try {
      await api.deleteCluster(selCid);
      setSelCid(null);
      refreshClusters();
    } catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doSplit = async () => {
    if (!selCid || checkedQids.size === 0) { alert("先在问题列表勾选要拆分的问题"); return; }
    try { await api.splitCluster(selCid, [...checkedQids], splitName.trim() || "新簇"); setCheckedQids(new Set()); setSplitName(""); refreshClusters(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doRewrite = async (qid: number) => {
    if (!rewriteVal.trim()) return;
    try { await api.rewriteQuestion(qid, rewriteVal.trim()); setRewriteId(null); setRewriteVal("");
      if (selCid) setQuestions(await api.getClusterQuestions(selCid)); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const toggleQCheck = (qid: number) => {
    setCheckedQids(prev => { const n = new Set(prev); n.has(qid) ? n.delete(qid) : n.add(qid); return n; });
  };

  const renderNode = (node: ClusterNode, depth: number): React.ReactNode => (
    <div key={node.id}>
      <div onClick={() => setSelCid(node.id)}
        style={{ padding: "6px 8px", cursor: "pointer", paddingLeft: 8 + depth * 16,
          background: selCid === node.id ? "#e8f0fe" : "transparent", display: "flex", alignItems: "center", gap: 4 }}>
        {node.children.length > 0 && (
          <span onClick={e => { e.stopPropagation(); toggleExpand(node.id); }} style={{ cursor: "pointer", width: 16, textAlign: "center" }}>
            {expanded.has(node.id) ? "▾" : "▸"}
          </span>
        )}
        <span style={{ fontWeight: selCid === node.id ? 600 : 400 }}>{node.name || "(未命名)"}</span>
        <span style={{ color: "#aaa", fontSize: 12 }}>{node.question_count}</span>
      </div>
      {expanded.has(node.id) && node.children.map(c => renderNode(c, depth + 1))}
    </div>
  );

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 300, borderRight: "1px solid #eee", overflow: "auto" }}>
        {err && <div style={{ padding: 8, color: "#b00020", fontSize: 13 }}>{err}</div>}
        {tree.map(n => renderNode(n, 0))}
        <div style={{ padding: 8, marginTop: 8, background: "#f9f9f9", borderTop: "1px solid #eee" }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>新建 cluster</div>
          <input placeholder="名称" value={newClName} onChange={e => setNewClName(e.target.value)} style={{ width: "100%", padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, marginBottom: 4, boxSizing: "border-box" }} />
          <select value={newClParent ?? ""} onChange={e => setNewClParent(e.target.value ? Number(e.target.value) : null)} style={{ width: "100%", padding: "3px", border: "1px solid #ddd", borderRadius: 3, marginBottom: 4, boxSizing: "border-box" }}>
            <option value="">顶层（无父簇）</option>
            {clusters.map(c => <option key={c.id} value={c.id}>{c.name || "(未命名)"}</option>)}
          </select>
          <button onClick={createCluster} style={{ width: "100%", padding: "4px", border: "1px solid #2563eb", borderRadius: 3, background: "#2563eb", color: "#fff", cursor: "pointer", fontSize: 13 }}>+ 新建</button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {selCluster ? (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <h2 style={{ margin: 0 }}>{selCluster.name || "(未命名)"}</h2>
              <input value={renaming} onChange={e => setRenaming(e.target.value)} placeholder="重命名" style={{ padding: "3px 6px", border: "1px solid #ccc", borderRadius: 3, width: 120 }} />
             <button onClick={rename} style={{ padding: "3px 10px", border: "1px solid #ccc", borderRadius: 3, cursor: "pointer" }}>改名</button>
              {selCluster?.question_count === 0 && (
                <button onClick={doDelete} style={{ padding: "3px 10px", border: "1px solid #b00020", borderRadius: 3, cursor: "pointer", color: "#b00020", fontSize: 13 }}>删除空簇</button>
              )}
           </div>
            {/* 顶部工具栏：合并 / 拆分 / 改写归一化 / 新建 (spec §5.3) */}
            <div style={{ display: "flex", gap: 12, marginBottom: 16, padding: 8, background: "#f9f9f9", borderRadius: 6, flexWrap: "wrap", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>拆分：</span>
                <input placeholder="新簇名" value={splitName} onChange={e => setSplitName(e.target.value)} style={{ padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, width: 100 }} />
               <button onClick={doSplit} disabled={checkedQids.size === 0} style={{ padding: "3px 10px", border: "1px solid #ddd", borderRadius: 3, cursor: checkedQids.size ? "pointer" : "not-allowed", opacity: checkedQids.size ? 1 : 0.5 }}>
               拆出 {checkedQids.size > 0 ? `(${checkedQids.size}问)` : ""}
               </button>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "flex-start", flexWrap: "wrap" }}>
                <span style={{ fontSize: 13, fontWeight: 600 }}>合并：</span>
                <span style={{ fontSize: 13, color: "#555", padding: "3px 6px", background: "#e8f0fe", borderRadius: 3 }}>
                  {selCluster?.name || "(未命名)"} ({selCluster?.question_count}问)
                </span>
                <span style={{ fontSize: 13, color: "#888" }}>→</span>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <input placeholder="搜索目标簇名…" value={mergeSearch} onChange={e => setMergeSearch(e.target.value)}
                    style={{ padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, width: 180, boxSizing: "border-box" }} />
                  <select value={mergeTgt ?? ""} onChange={e => setMergeTgt(e.target.value ? Number(e.target.value) : null)}
                    style={{ padding: "3px", border: "1px solid #ddd", borderRadius: 3, width: 180, boxSizing: "border-box" }}>
                    <option value="">选目标簇…</option>
                    {clusters
                      .filter(c => c.id !== selCid)
                      .filter(c => !mergeSearch.trim() || (c.name || "").includes(mergeSearch.trim()))
                      .sort((a, b) => b.question_count - a.question_count)
                      .slice(0, 50)
                      .map(c => <option key={c.id} value={c.id}>{c.name || "(未命名)"} ({c.question_count}问)</option>)}
                  </select>
                </div>
               <button onClick={doMerge} disabled={!mergeTgt}
                 style={{ padding: "3px 12px", border: "1px solid #2563eb", borderRadius: 3, background: "#2563eb", color: "#fff",
                   cursor: mergeTgt ? "pointer" : "not-allowed", opacity: mergeTgt ? 1 : 0.5 }}>
                  {checkedQids.size > 0 ? `移动选中(${checkedQids.size}问)` : "整簇合并"}
               </button>
              </div>
            </div>
            {questions.map(q => (
              <div key={q.id} style={{ marginBottom: 8, borderBottom: "1px solid #f0f0f0", paddingBottom: 8 }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <input type="checkbox" checked={checkedQids.has(q.id)} onChange={() => toggleQCheck(q.id)} style={{ marginTop: 3 }} />
                  <div style={{ flex: 1 }}>
                    {rewriteId === q.id ? (
                      <div style={{ display: "flex", gap: 4 }}>
                        <input value={rewriteVal} onChange={e => setRewriteVal(e.target.value)} style={{ flex: 1, padding: "3px 6px", border: "1px solid #ccc", borderRadius: 3 }} autoFocus />
                        <button onClick={() => doRewrite(q.id)} style={{ fontSize: 12, padding: "2px 8px", cursor: "pointer" }}>保存</button>
                        <button onClick={() => setRewriteId(null)} style={{ fontSize: 12, padding: "2px 8px", cursor: "pointer" }}>取消</button>
                      </div>
                    ) : (
                      <div onClick={() => setSelQuestion(q)} style={{ cursor: "pointer" }}>
                        <div style={{ fontWeight: 500 }}>{q.normalized_text}</div>
                        <div style={{ color: "#aaa", fontSize: 12 }}>原文: {q.raw_text}</div>
                        <div style={{ color: "#888", fontSize: 12 }}>来源评论 #{q.source_ref ?? "—"}</div>
                      </div>
                    )}
                    {rewriteId !== q.id && (
                      <button onClick={() => { setRewriteId(q.id); setRewriteVal(q.normalized_text); }} style={{ fontSize: 12, padding: "1px 6px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer", marginTop: 2 }}>改写归一化</button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {questions.length === 0 && <p style={{ color: "#999" }}>该簇暂无问题</p>}
          </>
        ) : <p>选一个簇查看问题</p>}
      </div>
      {selQuestion && (
        <div style={{ width: 300, borderLeft: "1px solid #eee", padding: 16, overflow: "auto" }}>
          <h3 style={{ marginTop: 0 }}>问题详情</h3>
          <div style={{ marginBottom: 8 }}><strong>归一化：</strong>{selQuestion.normalized_text}</div>
          <div style={{ marginBottom: 8 }}><strong>原文：</strong>{selQuestion.raw_text}</div>
          <div style={{ marginBottom: 8 }}><strong>来源类型：</strong>{selQuestion.source_type}</div>
          <div style={{ marginBottom: 8 }}><strong>来源评论 ID：</strong>{selQuestion.source_ref ?? "—"}</div>
          <button onClick={() => setSelQuestion(null)} style={{ padding: "4px 12px", border: "1px solid #ccc", borderRadius: 4, cursor: "pointer" }}>关闭</button>
        </div>
      )}
    </div>
  );
}
