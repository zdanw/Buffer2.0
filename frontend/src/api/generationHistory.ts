import axiosInstance from './axiosInstance';
import type { ExecutionDimensions } from './tasks';

export interface GenerationHistoryUser {
  user_id: string;
  username: string;
  email: string;
}

export interface GenerationHistoryProduct {
  product_id: string;
  name: string;
}

export interface GenerationHistoryQaSummary {
  hard_fail_count: number;
  warning_count: number;
}

export interface GenerationHistoryListItem {
  run_id: string;
  created_at: string;
  status: string;
  source: string;
  user: GenerationHistoryUser;
  product?: GenerationHistoryProduct | null;
  thumbnail_url?: string | null;
  credits_charged: number;
  latency_ms?: number | null;
  provider_summary?: string | null;
  qa_summary: GenerationHistoryQaSummary;
  diagnosis_line: string;
}

export interface GenerationHistoryListResponse {
  items: GenerationHistoryListItem[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface GenerationHistoryArtifact {
  artifact_id: string;
  cdn_url: string;
  selected: boolean;
  persistence_warning?: string | null;
  candidate_index: number;
}

export interface GenerationHistoryFinding {
  finding_id: string;
  stage: string;
  check_code: string;
  check_label: string;
  severity: string;
  passed: boolean;
  details?: Record<string, unknown> | null;
  qa_kind: string;
  confidence?: string | null;
  created_at: string;
}

export interface GenerationHistoryCreditInfo {
  charged: number;
  reservation_status?: string | null;
  grant_source?: string | null;
  grant_note?: string | null;
}

export interface GenerationHistoryGenerateTask {
  task_id: string;
  status: string;
  progress: number;
  stage?: string | null;
  result?: Record<string, unknown> | null;
  expired: boolean;
}

export interface GenerationHistoryCompareSibling {
  run_id: string;
  status: string;
  image_prompt_pipeline?: string | null;
  thumbnail_url?: string | null;
  selected: boolean;
  created_at: string;
}

export interface GenerationHistoryOutputSnapshot {
  image_prompt?: string;
  copywriting?: string;
  dimensions?: ExecutionDimensions;
  warning?: string;
  error?: string;
  reference_product_images?: string[];
  reference_scene_images?: string[];
}

export interface GenerationHistoryDetail {
  run_id: string;
  owner_user_id: string;
  source: string;
  product_id?: string | null;
  scheduled_task_id?: string | null;
  generate_task_id?: string | null;
  rollout_mode_at_start: string;
  experiment_variant?: string | null;
  requested_pipeline_version: string;
  executed_pipeline_version: string;
  fallback_reason?: string | null;
  fallback_path?: string | null;
  image_prompt_pipeline?: string | null;
  compare_group_id?: string | null;
  provider_type?: string | null;
  provider_id?: string | null;
  model?: string | null;
  image_size?: string | null;
  image_provider_mode?: string | null;
  status: string;
  error_category?: string | null;
  latency_ms?: number | null;
  retry_count?: number | null;
  credits_charged: number;
  provider_usage?: Record<string, unknown> | null;
  created_at: string;
  completed_at?: string | null;
  quality_protection_mode?: string | null;
  quality_policy_version?: string | null;
  product_fidelity_prevention_mode?: string | null;
  visual_fidelity_qa_mode?: string | null;
  visual_fidelity_policy_version?: string | null;
  requested_selector_strategy?: string | null;
  executed_selector_strategy?: string | null;
  selection_seed?: string | null;
  user: GenerationHistoryUser;
  product?: GenerationHistoryProduct | null;
  output_snapshot?: GenerationHistoryOutputSnapshot | null;
  generate_task?: GenerationHistoryGenerateTask | null;
  artifacts: GenerationHistoryArtifact[];
  quality_findings: GenerationHistoryFinding[];
  credit: GenerationHistoryCreditInfo;
  generation_plan?: Record<string, unknown> | null;
  reference_manifest?: Record<string, unknown> | null;
  qa_summary: GenerationHistoryQaSummary;
  diagnosis_line: string;
  compare_siblings: GenerationHistoryCompareSibling[];
}

export interface GenerationHistoryListParams {
  page?: number;
  page_size?: number;
  user_id?: string;
  username?: string;
  email?: string;
  product_id?: string;
  status?: string;
  source?: string;
  date_from?: string;
  date_to?: string;
  has_qa_failures?: boolean;
  credits_charged_min?: number;
}

export const listGenerationRuns = async (
  params: GenerationHistoryListParams = {},
): Promise<GenerationHistoryListResponse> => {
  const response = await axiosInstance.get('/admin/generation-runs', { params });
  const data = response.data;
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    total: data?.total ?? 0,
    page: data?.page ?? 1,
    page_size: data?.page_size ?? 20,
    pages: data?.pages ?? 1,
  };
};

export const getGenerationRun = async (runId: string): Promise<GenerationHistoryDetail> => {
  const response = await axiosInstance.get(`/admin/generation-runs/${runId}`);
  return response.data;
};
