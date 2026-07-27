import { useEffect, useMemo, useState } from "react";

import { api } from "../api/client";
import {
  clearAssetSelection, getSelectedAssetIds, onAssetSelectionChange,
} from "../App";
import type {
  AssetView, ClusterView, ContentExperiment, ExperimentAnalytics,
  ExperimentMetricSnapshot,
} from "../types/models";


const STATUS_LABELS: Record<string, string> = {
  draft: "草稿", published: "已发布", archived: "已归档",
};
const METRIC_FIELDS = [
  ["views", "浏览"], ["likes", "点赞"], ["collects", "收藏"],
  ["comments", "评论"], ["shares", "分享"], ["inquiries", "咨询"],
  ["qualified_leads", "有效线索"], ["wechat_adds", "加微信"],
  ["quotes", "报价"], ["orders", "成交"], ["revenue_cents", "成交金额（分）"],
] as const;

const emptyAnalytics: ExperimentAnalytics = {
  published_count: 0, measured_count: 0, views: 0, likes: 0, collects: 0,
  comments: 0, shares: 0, inquiries: 0, qualified_leads: 0, wechat_adds: 0,
  quotes: 0, orders: 0, revenue_cents: 0, engagements: 0,
  engagement_rate: 0, inquiry_rate: 0, wechat_rate: 0, order_rate: 0, ranking: [],
};

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

function localInputValue(iso: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export default function Experiments() {
  const [items, setItems] = useState<ContentExperiment[]>([]);
  const [selected, setSelected] = useState<ContentExperiment | null>(null);
  const [analytics, setAnalytics] = useState<ExperimentAnalytics>(emptyAnalytics);
  const [clusters, setClusters] = useState<ClusterView[]>([]);
  const [allAssets, setAllAssets] = useState<AssetView[]>([]);
  const [selectedAssetIds, setSelectedAssetIds] = useState(getSelectedAssetIds());
  const [statusFilter, setStatusFilter] = useState("");
  const [clusterFilter, setClusterFilter] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const cid = clusterFilter ? Number(clusterFilter) : undefined;
    const [list, stats] = await Promise.all([
      api.listExperiments(statusFilter || undefined, cid),
      api.getExperimentAnalytics(cid),
    ]);
    setItems(list.items);
    setAnalytics(stats);
  };

  useEffect(() => {
    refresh().catch(e => setNotice(`加载实验失败：${e}`));
  }, [statusFilter, clusterFilter]);

  useEffect(() => {
    Promise.all([api.getClusters(), api.listAssets()])
      .then(([cs, assets]) => { setClusters(cs); setAllAssets(assets); })
      .catch(e => setNotice(`加载基础数据失败：${e}`));
    return onAssetSelectionChange(() => setSelectedAssetIds(getSelectedAssetIds()));
  }, []);

  const selectedAssets = useMemo(() => {
    const byId = new Map(allAssets.map(a => [a.id, a]));
    return selectedAssetIds.map(id => byId.get(id)).filter(Boolean) as AssetView[];
  }, [allAssets, selectedAssetIds]);

  const openDetail = async (id: number) => {
    try { setSelected(await api.getExperiment(id)); }
    catch (e) { setNotice(`加载详情失败：${e}`); }
  };

  const created = async () => {
    await refresh();
    clearAssetSelection();
  };

  const cards = [
    ["发布实验", analytics.published_count],
    ["浏览", analytics.views],
    ["咨询", analytics.inquiries],
    ["加微信", analytics.wechat_adds],
    ["成交", analytics.orders],
    ["成交金额", `¥${(analytics.revenue_cents / 100).toLocaleString()}`],
    ["互动率", percent(analytics.engagement_rate)],
    ["咨询率", percent(analytics.inquiry_rate)],
    ["成交率", percent(analytics.order_rate)],
  ];

  return (
    <div style={{ height: "100%", overflow: "auto", padding: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(9, minmax(90px, 1fr))", gap: 8, marginBottom: 16 }}>
        {cards.map(([label, value]) => (
          <div key={String(label)} style={{ border: "1px solid #e5e7eb", borderRadius: 6, padding: 10, background: "#fff" }}>
            <div style={{ color: "#777", fontSize: 12 }}>{label}</div>
            <strong style={{ fontSize: 18 }}>{value}</strong>
          </div>
        ))}
      </div>

      {notice && <div style={{ padding: 8, marginBottom: 12, background: "#fff3cd" }}>{notice}</div>}

      {selectedAssets.length > 0 && (
        <CreateExperimentForm assets={selectedAssets} clusters={clusters}
          busy={busy} setBusy={setBusy} onCreated={async experiment => {
            setNotice(`实验 #${experiment.id} 已创建`);
            await created();
            await openDetail(experiment.id);
          }} />
      )}

      <div style={{ display: "flex", gap: 8, margin: "16px 0 10px" }}>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">全部状态</option>
          {Object.entries(STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <select value={clusterFilter} onChange={e => setClusterFilter(e.target.value)}>
          <option value="">全部问题簇</option>
          {clusters.map(c => <option key={c.id} value={c.id}>{c.name || `簇 #${c.id}`}</option>)}
        </select>
        <span style={{ color: "#888", fontSize: 13, alignSelf: "center" }}>{items.length} 条实验</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "minmax(280px, 38%) 1fr" : "1fr", gap: 16 }}>
        <div>
          {items.length === 0 && <p style={{ color: "#999" }}>暂无内容实验。请先到合成库选择内容片段。</p>}
          {items.map(item => (
            <button key={item.id} onClick={() => openDetail(item.id)}
              style={{ width: "100%", textAlign: "left", display: "block", padding: 12, marginBottom: 8,
                border: selected?.id === item.id ? "2px solid #7c3aed" : "1px solid #ddd",
                borderRadius: 6, background: "#fff", cursor: "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <strong>{item.final_title || `实验 #${item.id}`}</strong>
                <span style={{ color: item.status === "published" ? "#15803d" : "#666", fontSize: 12 }}>
                  {STATUS_LABELS[item.status]}
                </span>
              </div>
              <div style={{ color: "#777", fontSize: 12, marginTop: 6 }}>
                {item.assets.length} 个片段
                {item.latest_metrics ? ` · ${item.latest_metrics.views} 浏览 · ${item.latest_metrics.inquiries} 咨询` : " · 暂无指标"}
              </div>
            </button>
          ))}
        </div>
        {selected && <ExperimentDetail experiment={selected} clusters={clusters}
          onChanged={async updated => { setSelected(updated); await refresh(); }}
          onMetricChanged={async () => {
            const updated = await api.getExperiment(selected.id);
            setSelected(updated);
            await refresh();
          }} />}
      </div>
    </div>
  );
}

function CreateExperimentForm({ assets, clusters, busy, setBusy, onCreated }: {
  assets: AssetView[]; clusters: ClusterView[]; busy: boolean;
  setBusy: (busy: boolean) => void;
  onCreated: (experiment: ContentExperiment) => Promise<void>;
}) {
  const firstTitle = assets.find(a => a.type === "title")?.text || "";
  const defaultBody = assets.filter(a => a.type !== "title").map(a => a.text).join("\n\n");
  const [title, setTitle] = useState(firstTitle);
  const [body, setBody] = useState(defaultBody);
  const [clusterId, setClusterId] = useState("");
  const [audience, setAudience] = useState("");

  useEffect(() => {
    setTitle(assets.find(a => a.type === "title")?.text || "");
    setBody(assets.filter(a => a.type !== "title").map(a => a.text).join("\n\n"));
  }, [assets.map(a => a.id).join(",")]);

  const submit = async () => {
    setBusy(true);
    try {
      const experiment = await api.createExperiment({
        asset_ids: assets.map(a => a.id),
        final_title: title,
        final_body: body,
        cluster_id: clusterId ? Number(clusterId) : null,
        target_audience: audience,
      });
      await onCreated(experiment);
    } catch (e) {
      alert(`创建失败：${e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ border: "1px solid #c4b5fd", background: "#faf5ff", borderRadius: 8, padding: 14 }}>
      <strong>用 {assets.length} 个选中片段创建实验草稿</strong>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10 }}>
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="最终标题" style={{ padding: 6 }} />
        <select value={clusterId} onChange={e => setClusterId(e.target.value)} style={{ padding: 6 }}>
          <option value="">关联问题簇（可选）</option>
          {clusters.map(c => <option key={c.id} value={c.id}>{c.name || `簇 #${c.id}`}</option>)}
        </select>
        <textarea value={body} onChange={e => setBody(e.target.value)} rows={5}
          placeholder="最终正文" style={{ padding: 6, gridColumn: "1 / -1" }} />
        <input value={audience} onChange={e => setAudience(e.target.value)}
          placeholder="目标客群（可选）" style={{ padding: 6 }} />
        <button disabled={busy || (!title.trim() && !body.trim())} onClick={submit}
          style={{ border: "none", borderRadius: 4, background: "#7c3aed", color: "#fff", cursor: "pointer" }}>
          {busy ? "创建中…" : "创建实验草稿"}
        </button>
      </div>
    </div>
  );
}

function ExperimentDetail({ experiment, clusters, onChanged, onMetricChanged }: {
  experiment: ContentExperiment; clusters: ClusterView[];
  onChanged: (experiment: ContentExperiment) => Promise<void>;
  onMetricChanged: () => Promise<void>;
}) {
  const [title, setTitle] = useState(experiment.final_title);
  const [body, setBody] = useState(experiment.final_body);
  const [url, setUrl] = useState(experiment.published_url || "");
  const [publishedAt, setPublishedAt] = useState(localInputValue(experiment.published_at));
  const [clusterId, setClusterId] = useState(experiment.cluster_id ? String(experiment.cluster_id) : "");
  const [audience, setAudience] = useState(experiment.target_audience || "");
  const [notes, setNotes] = useState(experiment.notes || "");

  useEffect(() => {
    setTitle(experiment.final_title); setBody(experiment.final_body);
    setUrl(experiment.published_url || "");
    setPublishedAt(localInputValue(experiment.published_at));
    setClusterId(experiment.cluster_id ? String(experiment.cluster_id) : "");
    setAudience(experiment.target_audience || ""); setNotes(experiment.notes || "");
  }, [experiment.id, experiment.updated_at]);

  const save = async (nextStatus?: string) => {
    try {
      const updated = await api.updateExperiment(experiment.id, {
        final_title: title, final_body: body,
        published_url: url || undefined,
        published_at: publishedAt ? new Date(publishedAt).toISOString() : undefined,
        cluster_id: clusterId ? Number(clusterId) : null,
        target_audience: audience, notes,
        status: nextStatus,
      });
      await onChanged(updated);
    } catch (e) { alert(`保存失败：${e}`); }
  };

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 16, background: "#fff" }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>实验 #{experiment.id}</strong>
        <span>{STATUS_LABELS[experiment.status]}</span>
      </div>
      <input value={title} disabled={experiment.status !== "draft"} onChange={e => setTitle(e.target.value)}
        style={{ width: "100%", boxSizing: "border-box", padding: 7, marginTop: 10 }} />
      <textarea value={body} disabled={experiment.status !== "draft"} onChange={e => setBody(e.target.value)}
        rows={6} style={{ width: "100%", boxSizing: "border-box", padding: 7, marginTop: 8 }} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
        <select value={clusterId} disabled={experiment.status === "archived"} onChange={e => setClusterId(e.target.value)} style={{ padding: 6 }}>
          <option value="">未关联问题簇</option>
          {clusters.map(c => <option key={c.id} value={c.id}>{c.name || `簇 #${c.id}`}</option>)}
        </select>
        <input value={audience} disabled={experiment.status === "archived"} onChange={e => setAudience(e.target.value)} placeholder="目标客群" />
        <input value={url} disabled={experiment.status === "archived"} onChange={e => setUrl(e.target.value)} placeholder="发布链接" />
        <input type="datetime-local" value={publishedAt} disabled={experiment.status === "archived"} onChange={e => setPublishedAt(e.target.value)} />
        <input value={notes} disabled={experiment.status === "archived"} onChange={e => setNotes(e.target.value)} placeholder="备注" style={{ gridColumn: "1 / -1" }} />
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
        {experiment.status === "draft" && <>
          <button onClick={() => save()}>保存草稿</button>
          <button onClick={() => save("published")} style={{ background: "#15803d", color: "#fff", border: "none", borderRadius: 4, padding: "5px 12px" }}>标记已发布</button>
        </>}
        {experiment.status === "published" && <>
          <button onClick={() => save()}>保存信息</button>
          <button onClick={() => save("archived")}>归档</button>
        </>}
      </div>
      <div style={{ marginTop: 14 }}>
        <strong style={{ fontSize: 13 }}>使用片段</strong>
        {experiment.assets.map(a => <div key={a.id} style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
          [{a.role}] {a.text_snapshot}
        </div>)}
      </div>
      {experiment.status === "published" && (
        <MetricPanel experiment={experiment} onChanged={onMetricChanged} />
      )}
      {(experiment.metrics || []).length > 0 && (
        <MetricHistory experiment={experiment} onChanged={onMetricChanged} />
      )}
    </div>
  );
}

function MetricPanel({ experiment, onChanged }: {
  experiment: ContentExperiment; onChanged: () => Promise<void>;
}) {
  const latest = experiment.metrics?.[experiment.metrics.length - 1];
  const [values, setValues] = useState<Record<string, number>>(
    Object.fromEntries(METRIC_FIELDS.map(([key]) => [key, latest?.[key] || 0]))
  );
  const submit = async () => {
    try {
      await api.addExperimentMetric(experiment.id, {
        measured_at: new Date().toISOString(), ...values,
      });
      await onChanged();
    } catch (e) { alert(`录入失败：${e}`); }
  };
  return (
    <div style={{ marginTop: 16, padding: 12, background: "#f0fdf4", borderRadius: 6 }}>
      <strong style={{ fontSize: 13 }}>新增累计指标快照</strong>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginTop: 8 }}>
        {METRIC_FIELDS.map(([key, label]) => (
          <label key={key} style={{ fontSize: 11, color: "#666" }}>{label}
            <input type="number" min={0} value={values[key]}
              onChange={e => setValues(v => ({ ...v, [key]: Math.max(0, Number(e.target.value)) }))}
              style={{ display: "block", width: "100%", boxSizing: "border-box" }} />
          </label>
        ))}
      </div>
      <button onClick={submit} style={{ marginTop: 8 }}>保存新快照</button>
    </div>
  );
}

function MetricHistory({ experiment, onChanged }: {
  experiment: ContentExperiment; onChanged: () => Promise<void>;
}) {
  const editViews = async (metric: ExperimentMetricSnapshot) => {
    const value = prompt("修正浏览量", String(metric.views));
    if (value === null) return;
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < 0) return alert("请输入非负整数");
    try {
      await api.updateExperimentMetric(experiment.id, metric.id, { views: parsed });
      await onChanged();
    } catch (e) { alert(`修正失败：${e}`); }
  };
  return (
    <div style={{ marginTop: 16 }}>
      <strong style={{ fontSize: 13 }}>指标历史</strong>
      {[...(experiment.metrics || [])].reverse().map(metric => (
        <div key={metric.id} style={{ padding: "5px 0", borderBottom: "1px solid #eee", fontSize: 12 }}>
          {new Date(metric.measured_at).toLocaleString()} · {metric.views} 浏览 · {metric.inquiries} 咨询 · {metric.orders} 成交
          <button onClick={() => editViews(metric)} style={{ marginLeft: 8, fontSize: 11 }}>修正</button>
        </div>
      ))}
    </div>
  );
}
