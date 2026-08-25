import axiosInstance from './axiosInstance';

export interface ScheduledTask {
  task_id: string;
  name: string;
  cron: string;
  mode: 'auto' | 'manual';
  target_categories: string[];
  target_products: string[];
  platforms: string[];
  reference_image_count: number;
  run_count_per_execution: number;
  generate_image_count: number;
  generate_copy_count: number;
  enabled: boolean;
  use_scene_reference: boolean;
  use_vision_image_prompt?: boolean;
  image_provider_id?: string | null;
  image_provider_mode?: 'platform' | 'byok' | null;
  image_model?: string | null;
  image_size?: string | null;
  notify_on_publish?: boolean;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  next_run_at?: string;
}

export interface ExecutionDimensions {
  scene?: string;
  viewpoint?: string;
  composition?: string;
  style?: string;
  quality?: string;
  details?: string;
  lighting?: string;
}

export interface PlatformPost {
  platform: string;
  channel?: string;
  post_id?: string;
  post_link?: string;
}

export interface TaskExecution {
  execution_id: string;
  task_id: string;
  status: 'RUNNING' | 'SUCCESS' | 'FAILED';
  error_message?: string;
  generated_images?: string[];
  published_platforms?: string[];
  platform_posts?: PlatformPost[];
  copywriting?: string;
  dimensions?: ExecutionDimensions | null;
  image_prompt?: string | null;
  reference_product_images?: string[];
  reference_scene_images?: string[];
  created_at: string;
}

export interface CalendarExecutionSummary {
  execution_id: string;
  task_id: string | null;
  task_name: string;
  product_id?: string | null;
  status: string;
  created_at: string;
  thumbnail_url?: string | null;
  published_platforms: string[];
  platform_posts: PlatformPost[];
}

export interface CalendarDraftSummary {
  draft_id: string;
  task_id: string | null;
  task_name: string;
  product_id?: string | null;
  status: 'pending' | 'published' | 'discarded' | string;
  created_at: string;
  thumbnail_url?: string | null;
  copy_preview?: string | null;
  published_platforms: string[];
  platform_posts: PlatformPost[];
}

export interface CalendarMonthResponse {
  year: number;
  month: number;
  executions: CalendarExecutionSummary[];
  drafts: CalendarDraftSummary[];
}

export interface ManualTaskDraft {
  draft_id: string;
  task_id?: string | null;
  product_id?: string;
  images: string[];
  copywritings: string[];
  /** 与 images 一一对应的维度信息 */
  dimensions?: Array<ExecutionDimensions | null>;
  /** 与 images 一一对应的图像提示词 */
  image_prompts?: Array<string | null>;
  reference_product_images?: string[];
  reference_scene_images?: string[];
  status: 'pending' | 'published' | 'discarded';
  selected_image?: string;
  selected_copy?: string;
  published_platforms?: string[];
  platform_posts?: PlatformPost[];
  /** 是否仍有图片未成功上传到 GitHub CDN（临时链接） */
  cdn_upload_failed?: boolean;
  created_at: string;
}

export interface DraftCreateRequest {
  product_id?: string;
  images?: string[];
  copywritings?: string[];
  dimensions?: Array<ExecutionDimensions | null>;
  image_prompts?: Array<string | null>;
  reference_product_images?: string[];
  reference_scene_images?: string[];
}

export interface TaskCreate {
  name: string;
  cron: string;
  mode?: 'auto' | 'manual';
  target_categories: string[];
  target_products: string[];
  platforms: string[];
  reference_image_count?: number;
  run_count_per_execution?: number;
  generate_image_count?: number;
  generate_copy_count?: number;
  enabled?: boolean;
  use_scene_reference?: boolean;
  use_vision_image_prompt?: boolean;
  image_provider_id?: string | null;
  image_provider_mode?: 'platform' | 'byok' | null;
  image_model?: string | null;
  image_size?: string | null;
  notify_on_publish?: boolean;
}

export interface DraftPublishRequest {
  selected_image_index: number;
  selected_copy_index: number;
  platforms: string[];
}

export interface Pagination {
  current: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export const getTasks = async (page: number = 1, pageSize: number = 10): Promise<PaginatedResponse<ScheduledTask>> => {
  const response = await axiosInstance.get('/tasks/', { params: { page, page_size: pageSize } });
  
  if (response.data && response.data.data && Array.isArray(response.data.data)) {
    return response.data;
  }
  
  return { data: [], pagination: { current: 1, page_size: pageSize, total: 0, pages: 0 } };
};

export const getTask = async (taskId: string): Promise<ScheduledTask> => {
  const response = await axiosInstance.get(`/tasks/${taskId}`);
  return response.data;
};

export const getCalendarMonth = async (year: number, month: number): Promise<CalendarMonthResponse> => {
  const response = await axiosInstance.get('/tasks/calendar', { params: { year, month } });
  const data = response.data;
  return {
    year: data.year,
    month: data.month,
    executions: Array.isArray(data.executions) ? data.executions : [],
    drafts: Array.isArray(data.drafts) ? data.drafts : [],
  };
};

export const getExecutionDetail = async (executionId: string): Promise<TaskExecution> => {
  const response = await axiosInstance.get(`/tasks/executions/${executionId}`);
  return response.data;
};

/** @deprecated Use getCalendarMonth for calendar views */
export const getAllExecutions = async (): Promise<TaskExecution[]> => {
  const response = await axiosInstance.get('/tasks/executions');
  return Array.isArray(response.data) ? response.data : [];
};

export const createTask = async (data: TaskCreate): Promise<ScheduledTask> => {
  const response = await axiosInstance.post('/tasks/', data);
  return response.data;
};

export const updateTask = async (taskId: string, data: TaskCreate): Promise<ScheduledTask> => {
  const response = await axiosInstance.put(`/tasks/${taskId}`, data);
  return response.data;
};

export const deleteTask = async (taskId: string): Promise<void> => {
  await axiosInstance.delete(`/tasks/${taskId}`);
};

export const getDrafts = async (
  status?: string,
  page: number = 1,
  pageSize: number = 10
): Promise<PaginatedResponse<ManualTaskDraft>> => {
  const params: Record<string, any> = { page, page_size: pageSize };
  if (status) params.status = status;
  const response = await axiosInstance.get('/tasks/drafts/', { params });
  
  if (response.data && response.data.data && Array.isArray(response.data.data)) {
    return response.data;
  }
  
  return { data: [], pagination: { current: 1, page_size: pageSize, total: 0, pages: 0 } };
};

export const createDraft = async (
  request: DraftCreateRequest
): Promise<{ success: boolean; draft_id: string; status: string; created_at: string }> => {
  const response = await axiosInstance.post('/tasks/drafts/', request);
  return response.data;
};

export const publishDraft = async (draftId: string, request: DraftPublishRequest): Promise<{ success: boolean; draft_id: string; published_platforms: string[]; cdn_url: string }> => {
  const response = await axiosInstance.post(`/tasks/drafts/${draftId}/publish/`, request);
  return response.data;
};

export const discardDraft = async (draftId: string): Promise<{ success: boolean; draft_id: string }> => {
  const response = await axiosInstance.post(`/tasks/drafts/${draftId}/discard/`);
  return response.data;
};

export const reuploadDraftCdn = async (
  draftId: string
): Promise<{
  success: boolean;
  draft_id: string;
  images: string[];
  cdn_upload_failed: boolean;
  failed: Array<{ index: number; error: string }>;
}> => {
  const response = await axiosInstance.post(`/tasks/drafts/${draftId}/reupload-cdn/`);
  return response.data;
};
