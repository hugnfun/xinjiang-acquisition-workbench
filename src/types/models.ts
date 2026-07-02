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
export interface TagDimensionView {
  id: number; name: string; description: string;
  values: { id: number; value: string; alias: string[]; status: string }[];
}
export interface JobView {
  id: number; type: string; status: string;
  created_at: string | null; started_at: string | null;
  finished_at: string | null; error: string | null;
}
export interface ClusterView {
  id: number; name: string; description: string; question_count: number;
}
export interface QuestionView {
  id: number; normalized_text: string; raw_text: string;
  source_ref: number | null; source_type: string; cluster_id: number | null;
}
export interface AssetView {
  id: number; type: string; text: string;
  derived_from: number[]; tags: string[]; disliked: boolean;
}
