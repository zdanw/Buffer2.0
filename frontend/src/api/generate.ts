import axiosInstance from './axiosInstance';

export interface GenerateRequest {
  product_id: string;
  platform: string;
  reference_count?: number;
  style_hint?: string;
  use_scene_reference?: boolean;
  use_vision_image_prompt?: boolean;
  image_provider_id?: string | null;
  image_model?: string | null;
  image_size?: string | null;
  image_provider_mode?: 'platform' | 'byok' | null;
}

export interface GenerateResponse {
  task_id: string;
  status: string;
}

export interface DimensionInfo {
  scene: string;
  viewpoint: string;
  composition: string;
  style: string;
  quality: string;
  details: string;
  lighting: string;
}

export interface GenerateResult {
  success?: boolean;
  text?: string;
  image?: string;
  error?: string;
  dimensions?: DimensionInfo;
  image_prompt?: string;
  reference_product_images?: string[];
  reference_scene_images?: string[];
  warning?: string;
  logo_mode?: string;
}

export interface GenerateStatus {
  task_id: string;
  status: string;
  result?: GenerateResult;
}

export const generateContent = async (data: GenerateRequest): Promise<GenerateResponse> => {
  const response = await axiosInstance.post('/generate/', data);
  return response.data;
};

export const generateCopywriting = async (data: GenerateRequest): Promise<GenerateResponse> => {
  const response = await axiosInstance.post('/generate/copywriting/', data);
  return response.data;
};

export const generateImage = async (data: GenerateRequest): Promise<GenerateResponse> => {
  const response = await axiosInstance.post('/generate/image/', data);
  return response.data;
};

export const getGenerateStatus = async (taskId: string): Promise<GenerateStatus> => {
  const response = await axiosInstance.get(`/generate/status/${taskId}`);
  return response.data;
};