import { useEffect, useState, useRef, useCallback } from 'react';
import { api } from '../api/client';
import type { MaterialSummary, MaterialDetail, TagDimensionView } from '../types/models';
import { getSelectedMaterialIds, toggleMaterialSelection, clearMaterialSelection, onSelectionChange } from '../App';

type TagCtx = { x: number; y: number; mt: MaterialSummary["tags"][0] } | null;
const PAGE_SIZE = 30;

export default function Materials({ pendingMaterialId, onConsumed }: {
  pendingMaterialId?: number | null;
  onConsumed?: () => void;
}) {
  const [list, setList] = useState<MaterialSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<MaterialDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [tagErr, setTagErr] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [order, setOrder] = useState("likes");
  const [filterTagId, setFilterTagId] = useState<number | undefined>(undefined);
  const [tags, setTags] = useState<TagDimensionView[]>([]);
  const [batchIds, setBatchIds] = useState<Set<number>>(new Set());
  const [selCount, setSelCount] = useState(0);
  const [batchTagId, setBatchTagId] = useState<number | undefined>(undefined);
  const [ctx, setCtx] = useState<TagCtx>(null);
  const [suggestVal, setSuggestVal] = useState("");
  const [suggestDim, setSuggestDim] = useState("");
  const searchTimer = useRef<number | null>(null);

  const loadList = useCallback(async () => {
    setErr(null);
    try {
      const r = await api.getMaterials(PAGE_SIZE, page * PAGE_SIZE, order, search || undefined, filterTagId);
      setList(r.items); setTotal(r.total);
    } catch (e: any) { setErr(e?.message || String(e)); }
  }, [order, search, filterTagId, page]);

  useEffect(() => {
    api.initPort(); api.getTags().then(setTags).catch(() => {});
    const unsub = onSelectionChange(() => setSelCount(getSelectedMaterialIds().length));
    // spec §5.4: 从合成库点击来源素材跳转过来，自动打开详情
    if (pendingMaterialId) {
      open(pendingMaterialId);
      onConsumed?.();
    }
    return unsub;
  }, [pendingMaterialId]);

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(loadList, 300);
    return () => {
      if (searchTimer.current) window.clearTimeout(searchTimer.current);
    };
  }, [loadList]);

  const open = async (id: number) => {
    setLoading(true);
    try { const d = await api.getMaterial(id); setSelected(d); }
    catch (e: any) { setErr(e?.message || String(e)); }
    finally { setLoading(false); }
  };

  const onTagAction = async (tvId: number, action: "confirm" | "reject" | "suggest_new", extra?: { new_dimension?: string; new_value?: string }) => {
    if (!selected) return;
    setTagErr(null);
    try {
      await api.confirmTag(selected.id, tvId, action, extra);
      setSelected(await api.getMaterial(selected.id));
      await loadList();
    } catch (e: any) { setTagErr(e?.message || String(e)); }
  };

  const onTagRightClick = (e: React.MouseEvent, mt: MaterialSummary["tags"][0]) => {
    e.preventDefault();
    setCtx({ x: e.clientX, y: e.clientY, mt });
  };

  useEffect(() => {
    if (!ctx) return;
    const close = () => setCtx(null);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [ctx]);

  const toggleBatch = (id: number) => {
    setBatchIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };

  const doBatchTag = async () => {
    if (batchIds.size === 0 || !batchTagId) return;
    try {
      await api.batchTag([...batchIds], batchTagId);
      setBatchIds(new Set());
      await loadList();
      if (selected) setSelected(await api.getMaterial(selected.id));
    } catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doBatchRelabel = async () => {
    if (batchIds.size === 0) return;
    try { const { job_id } = await api.triggerRelabel([...batchIds]); alert("重打标任务已提交 (job " + job_id + ")"); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const allTagValues = tags.flatMap(d => d.values.map(v => ({ ...v, dimName: d.name })));

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "8px 12px", borderBottom: "1px solid #eee", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <input placeholder="搜索标题/正文/作者…" value={search} onChange={e => { setSearch(e.target.value); setPage(0); }}
          style={{ width: 200, padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4 }} />
        <select value={filterTagId ?? ""} onChange={e => { setFilterTagId(e.target.value ? Number(e.target.value) : undefined); setPage(0); }}
          style={{ padding: "4px", border: "1px solid #ccc", borderRadius: 4, maxWidth: 220 }}>
          <option value="">全部标签</option>
          {tags.map(d => d.values.map(v => <option key={v.id} value={v.id}>[{d.name}] {v.value} ({v.hit_count})</option>))}
        </select>
        <select value={order} onChange={e => { setOrder(e.target.value); setPage(0); }} style={{ padding: "4px", border: "1px solid #ccc", borderRadius: 4 }}>
          <option value="likes">按点赞</option>
          <option value="collects">按收藏</option>
          <option value="latest">最新</option>
        </select>
        <span style={{ color: "#888", fontSize: 13 }}>{total} 条</span>
        {batchIds.size > 0 && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 13, color: "#2563eb" }}>已选 {batchIds.size} 条</span>
            <select value={batchTagId ?? ""} onChange={e => setBatchTagId(e.target.value ? Number(e.target.value) : undefined)}
              style={{ padding: "4px", border: "1px solid #ccc", borderRadius: 4 }}>
              <option value="">选标签…</option>
              {allTagValues.map(v => <option key={v.id} value={v.id}>[{v.dimName}] {v.value}</option>)}
            </select>
            <button onClick={doBatchTag} disabled={!batchTagId}
              style={{ padding: "4px 12px", border: "1px solid #2563eb", borderRadius: 4, background: "#2563eb", color: "#fff", cursor: "pointer" }}>批量打标</button>
            <button onClick={doBatchRelabel}
              style={{ padding: "4px 12px", border: "1px solid #ccc", borderRadius: 4, background: "#f5f5f5", cursor: "pointer" }}>AI 重打标</button>
            <button onClick={() => setBatchIds(new Set())}
              style={{ padding: "4px 12px", border: "1px solid #ccc", borderRadius: 4, cursor: "pointer" }}>取消</button>
          </div>
        )}
      </div>
      {err && <div style={{ padding: 12, color: "#b00020", background: "#fdecea" }}>加载失败：{err}<button onClick={loadList} style={{ marginLeft: 8 }}>重试</button></div>}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <div style={{ width: "40%", overflow: "auto", borderRight: "1px solid #eee" }}>
          {list.map(m => (
            <div key={m.id} onClick={() => open(m.id)}
              style={{ padding: 10, cursor: "pointer", borderBottom: "1px solid #f0f0f0", background: selected?.id === m.id ? "#f0f7ff" : "transparent", display: "flex", gap: 8, alignItems: "flex-start" }}>
              <input type="checkbox" checked={batchIds.has(m.id)} onClick={e => e.stopPropagation()} onChange={() => toggleBatch(m.id)} style={{ marginTop: 4, flexShrink: 0 }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{m.title}</div>
                <div style={{ color: "#888", fontSize: 13 }}>{m.author} · 👍{m.likes} · 💛{m.collects} · 💬{m.comments_count}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 2, marginTop: 2 }}>
                  {m.tags.map(t => (
                    <span key={t.tag_value_id} style={{ fontSize: 11, padding: "1px 5px", borderRadius: 3, background: t.confirmed_by_human ? "#d4edda" : "#fff3cd", opacity: t.confidence != null && t.confidence < 0.6 ? 0.6 : 1 }}>
                      {t.value}{t.confidence != null && t.confidence < 0.6 ? "?" : ""}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
          {total > PAGE_SIZE && (
            <div style={{ padding: 10, display: "flex", justifyContent: "center", alignItems: "center", gap: 8, borderTop: "1px solid #eee" }}>
              <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{ padding: "3px 10px", cursor: page === 0 ? "not-allowed" : "pointer" }}>上一页</button>
              <span style={{ fontSize: 12, color: "#666" }}>
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} / {total}
              </span>
              <button onClick={() => setPage(p => p + 1)} disabled={(page + 1) * PAGE_SIZE >= total} style={{ padding: "3px 10px", cursor: (page + 1) * PAGE_SIZE >= total ? "not-allowed" : "pointer" }}>下一页</button>
            </div>
          )}
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
          {loading && <p>加载中…</p>}
          {tagErr && <div style={{ color: "#b00020", background: "#fdecea", padding: 8, marginBottom: 8 }}>标签操作失败：{tagErr}</div>}
          {selected && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <h2 style={{ margin: 0, flex: 1 }}>{selected.title}</h2>
                <button onClick={() => toggleMaterialSelection(selected.id)} style={{ padding: "4px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 13, cursor: "pointer" }}>
                  {getSelectedMaterialIds().includes(selected.id) ? "✓ 已选待提炼" : "加入合成选区"}
                </button>
              </div>
              <p style={{ color: "#666" }}>{selected.author} · 👍{selected.likes} · 💛{selected.collects} · 💬{selected.comments_count}
                {selCount > 0 && <span style={{ marginLeft: 8, color: "#2563eb" }}>（合成选区 {selCount} 篇）</span>}
                {selCount > 0 && <button onClick={() => clearMaterialSelection()} style={{ marginLeft: 4, fontSize: 12, border: "none", background: "none", color: "#2563eb", cursor: "pointer", textDecoration: "underline" }}>清空</button>}
              </p>
              <div style={{ display: "flex", gap: 8, overflowX: "auto", marginBottom: 16 }}>
                {selected.images.map(img => <img key={img.idx} src={api.getImageUrl(selected.id, img.path)} style={{ height: 200, borderRadius: 8, flexShrink: 0 }} />)}
              </div>
              <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: 14, lineHeight: 1.6 }}>{selected.content}</pre>
              <h3 style={{ marginTop: 16 }}>标签（右键 = 改 / 拒绝 / 建议新标签）</h3>
              {selected.tags.map(t => (
                <div key={t.tag_value_id} style={{ marginBottom: 6, display: "flex", alignItems: "center", gap: 4 }}>
                  <span onContextMenu={e => onTagRightClick(e, t)} style={{ background: t.confirmed_by_human ? "#d4edda" : "#fff3cd", padding: "2px 8px", borderRadius: 4, fontSize: 13, cursor: "context-menu" }}>
                    [{t.dimension}] {t.value}{t.confidence != null && " (" + t.confidence + ")"}{t.confirmed_by_human ? " ✓" : ""}
                  </span>
                  {!t.confirmed_by_human && <>
                    <button onClick={() => onTagAction(t.tag_value_id, "confirm")} style={{ fontSize: 12, padding: "1px 6px", cursor: "pointer" }}>确认</button>
                    <button onClick={() => onTagAction(t.tag_value_id, "reject")} style={{ fontSize: 12, padding: "1px 6px", cursor: "pointer" }}>拒绝</button>
                  </>}
                </div>
              ))}
            </>
          )}
        </div>
      </div>
      {ctx && (
        <div style={{ position: "fixed", left: ctx.x, top: ctx.y, zIndex: 9999, background: "#fff", border: "1px solid #ccc", borderRadius: 6, boxShadow: "0 4px 12px rgba(0,0,0,0.15)", padding: 4, minWidth: 160 }} onClick={e => e.stopPropagation()}>
          <div style={{ padding: "4px 8px", fontSize: 13, color: "#888", borderBottom: "1px solid #eee" }}>[{ctx.mt.dimension}] {ctx.mt.value}</div>
          <button onClick={() => { onTagAction(ctx.mt.tag_value_id, "confirm"); setCtx(null); }} style={{ display: "block", width: "100%", padding: "6px 8px", border: "none", background: "none", textAlign: "left", cursor: "pointer", fontSize: 13 }}>✓ 确认标签</button>
          <button onClick={() => { onTagAction(ctx.mt.tag_value_id, "reject"); setCtx(null); }} style={{ display: "block", width: "100%", padding: "6px 8px", border: "none", background: "none", textAlign: "left", cursor: "pointer", fontSize: 13 }}>✗ 拒绝标签</button>
          <div style={{ padding: "6px 8px", borderTop: "1px solid #eee" }}>
            <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>转为"建议新标签"</div>
            <input placeholder="维度名" value={suggestDim} onChange={e => setSuggestDim(e.target.value)} style={{ width: "100%", padding: "2px 4px", border: "1px solid #ddd", borderRadius: 3, fontSize: 12, marginBottom: 4 }} />
            <input placeholder="新标签值" value={suggestVal} onChange={e => setSuggestVal(e.target.value)} style={{ width: "100%", padding: "2px 4px", border: "1px solid #ddd", borderRadius: 3, fontSize: 12, marginBottom: 4 }} />
            <button onClick={() => { if (!suggestVal.trim()) { alert("请输入新标签值"); return; } onTagAction(ctx.mt.tag_value_id, "suggest_new", { new_dimension: suggestDim.trim() || ctx.mt.dimension || "", new_value: suggestVal.trim() }); setSuggestVal(""); setSuggestDim(""); setCtx(null); }} style={{ width: "100%", padding: "4px", fontSize: 12, border: "1px solid #2563eb", borderRadius: 3, background: "#2563eb", color: "#fff", cursor: "pointer" }}>提交建议</button>
          </div>
        </div>
      )}
    </div>
  );
}
