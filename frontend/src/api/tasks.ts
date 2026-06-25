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
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  next_run_at?: string;
}

export interface TaskExecution {
  execution_id: string;
  task_id: string;
  status: 'RUNNING' | 'SUCCESS' | 'FAILED';
  error_message?: string;
  generated_images?: string[];
  published_platforms?: string[];
  copywriting?: string;
  created_at: string;
}

export interface ManualTaskDraft {
  draft_id: string;
  task_id: string;
  product_id?: string;
  images: string[];
  copywritings: string[];
  status: 'pending' | 'published' | 'discarded';
  selected_image?: string;
  selected_copy?: string;
  published_platforms?: string[];
  created_at: string;
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
}

export interface DraftPublishRequest {
  selected_image_index: number;
  selected_copy_index: number;
  platforms: string[];
}

export const getTasks = async (): Promise<ScheduledTask[]> => {
  const response = await axiosInstance.get('/tasks/');
  return response.data;
};

export const getTask = async (taskId: string): Promise<ScheduledTask> => {
  const response = await axiosInstance.get(`/tasks/${taskId}`);
  return response.data;
};

export const getTaskExecutions = async (taskId: string): Promise<TaskExecution[]> => {
  const response = await axiosInstance.get(`/tasks/${taskId}/executions`);
  return response.data;
};

export const getAllExecutions = async (): Promise<TaskExecution[]> => {
  const response = await axiosInstance.get('/tasks/executions');
  return response.data;
};

export const createTask = async (data: TaskCreate): Promise<ScheduledTask> => {
  const response = await axiosInstance.post('/tasks', data);
  return response.data;
};

export const updateTask = async (taskId: string, data: TaskCreate): Promise<ScheduledTask> => {
  const response = await axiosInstance.put(`/tasks/${taskId}`, data);
  return response.data;
};

export const deleteTask = async (taskId: string): Promise<void> => {
  await axiosInstance.delete(`/tasks/${taskId}`);
};

export const getDrafts = async (status?: string): Promise<ManualTaskDraft[]> => {
  const params = status ? { status } : {};
  const response = await axiosInstance.get('/tasks/drafts', { params });
  return response.data;
};

export const publishDraft = async (draftId: string, request: DraftPublishRequest): Promise<{ success: boolean; draft_id: string; published_platforms: string[]; cdn_url: string }> => {
  const response = await axiosInstance.post(`/tasks/drafts/${draftId}/publish`, request);
  return response.data;
};

export const discardDraft = async (draftId: string): Promise<{ success: boolean; draft_id: string }> => {
  const response = await axiosInstance.post(`/tasks/drafts/${draftId}/discard`);
  return response.data;
};
