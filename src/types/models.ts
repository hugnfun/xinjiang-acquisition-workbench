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
