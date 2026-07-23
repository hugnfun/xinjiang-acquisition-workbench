import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { TagDimensionView } from "../types/models";

export default function Tags() {
  const [dims, setDims] = useState<TagDimensionView[]>([]);
  const [selDimId, setSelDimId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [newDimName, setNewDimName] = useState("");
  const [newDimDesc, setNewDimDesc] = useState("");
  const [newVal, setNewVal] = useState("");
  const [renameId, setRenameId] = useState<number | null>(null);
  const [renameVal, setRenameVal] = useState("");
  const [aliasId, setAliasId] = useState<number | null>(null);
  const [aliasVal, setAliasVal] = useState("");
  const [mergeSrc, setMergeSrc] = useState<number | null>(null);
  const [mergeTgt, setMergeTgt] = useState<number | null>(null);

  const refresh = () => api.getTags().then(setDims).catch(e => setErr(e?.message || String(e)));
  useEffect(() => { refresh(); }, []);

  const selDim = dims.find(d => d.id === selDimId);
  const allValues = dims.flatMap(d => d.values.map(v => ({ ...v, dimName: d.name })));

  const createDim = async () => {
    if (!newDimName.trim()) return;
    try { await api.createDimension(newDimName.trim(), newDimDesc.trim()); setNewDimName(""); setNewDimDesc(""); await refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const createVal = async (did: number) => {
    if (!newVal.trim()) return;
    try { await api.createTagValue(did, newVal.trim()); setNewVal(""); await refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doRename = async (vid: number) => {
    if (!renameVal.trim()) return;
    try { await api.updateTagValue(vid, { value: renameVal.trim() }); setRenameId(null); await refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doAddAlias = async (vid: number) => {
    if (!aliasVal.trim()) return;
    try { await api.updateTagValue(vid, { add_alias: aliasVal.trim() }); setAliasId(null); setAliasVal(""); await refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doDeprecate = async (vid: number) => {
    try { await api.updateTagValue(vid, { status: "deprecated" }); await refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  const doMerge = async () => {
    if (!mergeSrc || !mergeTgt || mergeSrc === mergeTgt) { alert("请选不同的源和目标"); return; }
    try { await api.mergeTags(mergeSrc, mergeTgt); setMergeSrc(null); setMergeTgt(null); await refresh(); }
    catch (e: any) { setErr(e?.message || String(e)); }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div style={{ width: 280, borderRight: "1px solid #eee", overflow: "auto", padding: 8 }}>
        <h3 style={{ margin: "4px 0 8px" }}>标签维度</h3>
        {dims.map(d => (
          <div key={d.id} onClick={() => setSelDimId(d.id)}
            style={{ padding: "8px 10px", cursor: "pointer", borderRadius: 4, marginBottom: 2,
              background: selDimId === d.id ? "#e8f0fe" : "transparent", fontWeight: selDimId === d.id ? 600 : 400 }}>
            {d.name}
            <span style={{ color: "#999", fontSize: 12, marginLeft: 6 }}>{d.values.filter(v => v.status === "active").length}</span>
          </div>
        ))}
        <div style={{ marginTop: 12, padding: 8, background: "#f9f9f9", borderRadius: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>新建维度</div>
          <input placeholder="维度名" value={newDimName} onChange={e => setNewDimName(e.target.value)} style={{ width: "100%", padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, marginBottom: 4, boxSizing: "border-box" }} />
          <input placeholder="描述（可选）" value={newDimDesc} onChange={e => setNewDimDesc(e.target.value)} style={{ width: "100%", padding: "3px 6px", border: "1px solid #ddd", borderRadius: 3, marginBottom: 4, boxSizing: "border-box" }} />
          <button onClick={createDim} style={{ width: "100%", padding: "4px", border: "1px solid #2563eb", borderRadius: 3, background: "#2563eb", color: "#fff", cursor: "pointer", fontSize: 13 }}>+ 新建</button>
        </div>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {err && <div style={{ color: "#b00020", background: "#fdecea", padding: 8, marginBottom: 8 }}>{err}</div>}
        {selDim ? (
          <>
            <h2 style={{ marginTop: 0 }}>{selDim.name}</h2>
            <p style={{ color: "#666", fontSize: 13 }}>{selDim.description}</p>
            <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: 16 }}>
              <thead>
                <tr style={{ borderBottom: "2px solid #eee", textAlign: "left" }}>
                  <th style={{ padding: "4px 8px" }}>标签值</th>
                  <th style={{ padding: "4px 8px" }}>命中素材</th>
                  <th style={{ padding: "4px 8px" }}>别名</th>
                  <th style={{ padding: "4px 8px" }}>状态</th>
                  <th style={{ padding: "4px 8px" }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {selDim.values.map(v => (
                  <tr key={v.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                    <td style={{ padding: "6px 8px", fontWeight: 500 }}>{v.value}</td>
                    <td style={{ padding: "6px 8px", color: "#888" }}>{v.hit_count}</td>
                    <td style={{ padding: "6px 8px", color: "#aaa", fontSize: 12 }}>{v.alias.join(", ") || "—"}</td>
                    <td style={{ padding: "6px 8px" }}>
                      <span style={{ fontSize: 12, padding: "1px 6px", borderRadius: 3, background: v.status === "deprecated" ? "#fdecea" : "#d4edda", color: v.status === "deprecated" ? "#b00020" : "#155724" }}>{v.status}</span>
                    </td>
                    <td style={{ padding: "6px 8px", display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {renameId === v.id ? (
                        <>
                          <input value={renameVal} onChange={e => setRenameVal(e.target.value)} style={{ padding: "2px 4px", border: "1px solid #ddd", borderRadius: 3, fontSize: 12, width: 80 }} autoFocus />
                          <button onClick={() => doRename(v.id)} style={{ fontSize: 12, padding: "1px 6px", cursor: "pointer" }}>保存</button>
                          <button onClick={() => setRenameId(null)} style={{ fontSize: 12, padding: "1px 6px", cursor: "pointer" }}>取消</button>
                        </>
                      ) : aliasId === v.id ? (
                        <>
                          <input value={aliasVal} onChange={e => setAliasVal(e.target.value)} placeholder="新别名" style={{ padding: "2px 4px", border: "1px solid #ddd", borderRadius: 3, fontSize: 12, width: 80 }} autoFocus />
                          <button onClick={() => doAddAlias(v.id)} style={{ fontSize: 12, padding: "1px 6px", cursor: "pointer" }}>加</button>
                          <button onClick={() => setAliasId(null)} style={{ fontSize: 12, padding: "1px 6px", cursor: "pointer" }}>取消</button>
                        </>
                      ) : (
                        <>
                          <button onClick={() => { setRenameId(v.id); setRenameVal(v.value); }} style={{ fontSize: 12, padding: "1px 6px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer" }}>改名</button>
                          <button onClick={() => setAliasId(v.id)} style={{ fontSize: 12, padding: "1px 6px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer" }}>加别名</button>
                          {v.status === "active" && <button onClick={() => doDeprecate(v.id)} style={{ fontSize: 12, padding: "1px 6px", border: "1px solid #ddd", borderRadius: 3, cursor: "pointer", color: "#b00020" }}>弃用</button>}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16 }}>
              <input placeholder="新标签值" value={newVal} onChange={e => setNewVal(e.target.value)} style={{ padding: "4px 8px", border: "1px solid #ccc", borderRadius: 4, width: 200 }} />
              <button onClick={() => createVal(selDim.id)} style={{ padding: "4px 12px", border: "1px solid #2563eb", borderRadius: 4, background: "#2563eb", color: "#fff", cursor: "pointer" }}>+ 新建标签值</button>
            </div>
            <div style={{ padding: 12, background: "#f9f9f9", borderRadius: 6 }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>合并同义标签</div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 13 }}>源：</span>
                <select value={mergeSrc ?? ""} onChange={e => setMergeSrc(e.target.value ? Number(e.target.value) : null)} style={{ padding: "3px", border: "1px solid #ccc", borderRadius: 3, maxWidth: 160 }}>
                  <option value="">选源标签…</option>
                  {allValues.filter(v => v.status === "active").map(v => <option key={v.id} value={v.id}>[{v.dimName}] {v.value}</option>)}
                </select>
                <span style={{ fontSize: 13 }}>→ 目标：</span>
                <select value={mergeTgt ?? ""} onChange={e => setMergeTgt(e.target.value ? Number(e.target.value) : null)} style={{ padding: "3px", border: "1px solid #ccc", borderRadius: 3, maxWidth: 160 }}>
                  <option value="">选目标标签…</option>
                  {allValues.filter(v => v.status === "active").map(v => <option key={v.id} value={v.id}>[{v.dimName}] {v.value}</option>)}
                </select>
                <button onClick={doMerge} style={{ padding: "4px 12px", border: "1px solid #ccc", borderRadius: 4, cursor: "pointer" }}>合并</button>
              </div>
            </div>
          </>
        ) : <p>左侧选一个维度查看标签值</p>}
      </div>
    </div>
  );
}
