import axiosInstance from './axiosInstance';

export type ImageProviderType = 'openai_compatible' | 'doubao_ark' | 'aliyun_maas';

export interface ManualModelEntry {
  id: string;
  description?: string | null;
}

export interface ImageProvider {
  id: string;
  name: string;
  provider_type: ImageProviderType;
  base_url: string;
  api_key_masked: string;
  supports_list_models: boolean;
  default_model?: string | null;
  manual_models?: ManualModelEntry[];
  extra_headers?: Record<string, unknown> | null;
  extra_params?: Record<string, unknown> | null;
  is_active: boolean;
  is_default: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ImageProviderCreate {
  name: string;
  provider_type: ImageProviderType;
  base_url: string;
  api_key: string;
  supports_list_models?: boolean;
  default_model?: string | null;
  manual_models?: ManualModelEntry[];
  is_active?: boolean;
  is_default?: boolean;
}

export interface ImageProviderUpdate {
  name?: string;
  provider_type?: ImageProviderType;
  base_url?: string;
  api_key?: string;
  supports_list_models?: boolean;
  default_model?: string | null;
  manual_models?: ManualModelEntry[];
  is_active?: boolean;
  is_default?: boolean;
}

export interface ImageModelInfo {
  id: string;
  description?: string | null;
  owned_by?: string | null;
  source?: string | null;
}

export interface ImageModelsResponse {
  models: ImageModelInfo[];
  message?: string | null;
  allow_manual_input: boolean;
}

export interface ImageProviderTestResponse {
  ok: boolean;
  message: string;
}

export const listImageProviders = async (): Promise<ImageProvider[]> => {
  const response = await axiosInstance.get('/image-providers/');
  return response.data;
};

export const createImageProvider = async (data: ImageProviderCreate): Promise<ImageProvider> => {
  const response = await axiosInstance.post('/image-providers/', data);
  return response.data;
};

export const updateImageProvider = async (
  id: string,
  data: ImageProviderUpdate
): Promise<ImageProvider> => {
  const response = await axiosInstance.put(`/image-providers/${id}`, data);
  return response.data;
};

export const deleteImageProvider = async (id: string): Promise<void> => {
  await axiosInstance.delete(`/image-providers/${id}`);
};

export const listProviderModels = async (id: string): Promise<ImageModelsResponse> => {
  const response = await axiosInstance.get(`/image-providers/${id}/models`);
  return response.data;
};

export const testImageProvider = async (id: string): Promise<ImageProviderTestResponse> => {
  const response = await axiosInstance.post(`/image-providers/${id}/test`);
  return response.data;
};
