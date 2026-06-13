import axiosInstance from './axiosInstance';

export interface ScheduledTask {
  task_id: string;
  name: string;
  cron: string;
  target_categories: string[];
  target_products: string[];
  platforms: string[];
  reference_image_count: number;
  run_count_per_execution: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  name: string;
  cron: string;
  target_categories: string[];
  target_products: string[];
  platforms: string[];
  reference_image_count?: number;
  run_count_per_execution?: number;
  enabled?: boolean;
}

export const getTasks = async (): Promise<ScheduledTask[]> => {
  const response = await axiosInstance.get('/tasks');
  return response.data;
};

export const getTask = async (taskId: string): Promise<ScheduledTask> => {
  const response = await axiosInstance.get(`/tasks/${taskId}`);
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