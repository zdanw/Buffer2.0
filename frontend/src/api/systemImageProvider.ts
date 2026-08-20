import axiosInstance from './axiosInstance';

export interface SystemProviderSummary {
  has_provider: boolean;
  id?: string | null;
  name?: string | null;
  provider_type?: string | null;
  default_model?: string | null;
  manual_models?: { id: string; description?: string | null }[];
}

export const getSystemImageProviderSummary = async (): Promise<SystemProviderSummary> => {
  const response = await axiosInstance.get('/image-providers/system/summary');
  return response.data;
};

export interface SystemImageProvider {
  id: string;
  name: string;
  provider_type: string;
  base_url: string;
  api_key_masked: string;
  supports_list_models: boolean;
  default_model?: string | null;
  manual_models?: { id: string; description?: string | null }[];
  is_active: boolean;
  is_default: boolean;
  is_system: boolean;
}

export const listSystemImageProviders = async (): Promise<SystemImageProvider[]> => {
  const response = await axiosInstance.get('/admin/system-image-providers/');
  return Array.isArray(response.data) ? response.data : [];
};

export const createSystemImageProvider = async (body: Record<string, unknown>) => {
  const response = await axiosInstance.post('/admin/system-image-providers/', body);
  return response.data;
};

export const updateSystemImageProvider = async (
  id: string,
  body: Record<string, unknown>
) => {
  const response = await axiosInstance.put(`/admin/system-image-providers/${id}`, body);
  return response.data;
};

export const deleteSystemImageProvider = async (id: string): Promise<void> => {
  await axiosInstance.delete(`/admin/system-image-providers/${id}`);
};

export const setSystemImageProviderDefault = async (id: string) => {
  const response = await axiosInstance.post(
    `/admin/system-image-providers/${id}/set-default`
  );
  return response.data;
};
