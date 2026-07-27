export interface TagView {
  tag_value_id: number;
  dimension: string | null;
  value: string | null;
  source: string;
  confidence: number | null;
  confirmed_by_human: boolean;
}
export interface MaterialSummary {
  id: number; title: string; author: string;
  likes: number; collects: number; comments_count: number;
  published_at: string | null; tags_raw: string;
  image_count: number; tags: TagView[];
}
export interface MaterialDetail extends MaterialSummary {
  content: string; url: string; local_folder: string | null;
  images: { idx: number; path: string; type: string }[];
}
export interface TagValueView {
  id: number; value: string; alias: string[];
  status: string; hit_count: number;
}
export interface TagDimensionView {
  id: number; name: string; description: string;
  values: TagValueView[];
}
export interface JobView {
  id: number; type: string; status: string;
  created_at: string | null; started_at: string | null;
  finished_at: string | null; error: string | null;
  progress: number; progress_total: number;
  cancel_requested: boolean;
}
export interface ClusterView {
  id: number; name: string; description: string; question_count: number;
  parent_id: number | null;
}
export interface QuestionView {
  id: number; normalized_text: string; raw_text: string;
  source_ref: number | null; source_type: string; cluster_id: number | null;
  source_comment_text?: string | null;
  source_material_id?: number | null;
  source_material_title?: string | null;
}
export interface AssetView {
  id: number; type: string; text: string;
  derived_from: number[]; tags: string[]; disliked: boolean;
  status: string; quality: number | null; reject_reason: string | null;
  cluster_id: number | null; target_audience: string | null;
}

export interface ExperimentAssetLink {
  id: number; asset_id: number | null; role: string;
  position: number; text_snapshot: string;
}
export interface ExperimentMetricSnapshot {
  id: number; measured_at: string;
  views: number; likes: number; collects: number; comments: number; shares: number;
  inquiries: number; qualified_leads: number; wechat_adds: number;
  quotes: number; orders: number; revenue_cents: number; notes: string | null;
}
export interface ContentExperiment {
  id: number; platform: string; status: 'draft' | 'published' | 'archived';
  final_title: string; final_body: string;
  published_url: string | null; published_at: string | null;
  cluster_id: number | null; target_audience: string | null; notes: string | null;
  created_at: string | null; updated_at: string | null;
  assets: ExperimentAssetLink[];
  metrics?: ExperimentMetricSnapshot[];
  latest_metrics?: ExperimentMetricSnapshot | null;
}
export interface ExperimentAnalytics {
  published_count: number; measured_count: number;
  views: number; likes: number; collects: number; comments: number; shares: number;
  inquiries: number; qualified_leads: number; wechat_adds: number;
  quotes: number; orders: number; revenue_cents: number; engagements: number;
  engagement_rate: number; inquiry_rate: number; wechat_rate: number; order_rate: number;
  ranking: Array<{
    experiment_id: number; title: string; cluster_id: number | null;
    measured_at: string; views: number; inquiries: number; wechat_adds: number;
    orders: number; revenue_cents: number; engagement_rate: number;
    inquiry_rate: number; order_rate: number;
  }>;
}
export interface CoverageItem {
  cluster_id: number; cluster_name: string;
  question_count: number; asset_count: number; covered: boolean;
  asset_types: string[];
  assets: { id: number; type: string; text: string; status: string }[];
}
export interface CoverageResult {
  total_clusters: number; covered_clusters: number; uncovered_clusters: number;
  top_uncovered: CoverageItem[];
  clusters: CoverageItem[];
}

export interface WorkVaultScanItem {
  filename: string;
  title: string;
  status: string;
  content_hash: string;
  image_count: number;
  image_missing: string[];
  comment_count_declared: number;
  comment_count_parsed: number;
  body_preview: string;
  tags_raw: string;
  published_at: string;
  duplicate_of: string;
}

export interface WorkVaultScanResult {
  vault_dir: string;
  total_files: number;
  summary: Record<string, number>;
  items: WorkVaultScanItem[];
}
