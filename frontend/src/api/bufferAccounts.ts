import axiosInstance from './axiosInstance';

export interface BufferBrandSummary {
  brand_id: string;
  name: string;
  slug: string;
  is_generic?: boolean;
  is_system?: boolean;
}

export interface BufferAccount {
  id: string;
  name: string;
  api_token_masked: string;
  buffer_email?: string | null;
  buffer_remote_id?: string | null;
  brand_ids: string[];
  brands: BufferBrandSummary[];
  is_active: boolean;
  is_default: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface BufferAccountCreate {
  name: string;
  api_token: string;
  brand_ids?: string[];
  is_active?: boolean;
  is_default?: boolean;
}

export interface BufferAccountUpdate {
  name?: string;
  api_token?: string;
  brand_ids?: string[];
  is_active?: boolean;
  is_default?: boolean;
}

export interface BufferAccountTestResponse {
  ok: boolean;
  message: string;
  email?: string | null;
  remote_id?: string | null;
}

export const listBufferAccounts = async (): Promise<BufferAccount[]> => {
  const response = await axiosInstance.get('/buffer-accounts/');
  return response.data;
};

export const createBufferAccount = async (
  data: BufferAccountCreate
): Promise<BufferAccount> => {
  const response = await axiosInstance.post('/buffer-accounts/', data);
  return response.data;
};

export const updateBufferAccount = async (
  id: string,
  data: BufferAccountUpdate
): Promise<BufferAccount> => {
  const response = await axiosInstance.put(`/buffer-accounts/${id}`, data);
  return response.data;
};

export const deleteBufferAccount = async (id: string): Promise<void> => {
  await axiosInstance.delete(`/buffer-accounts/${id}`);
};

export const testBufferAccount = async (
  id: string
): Promise<BufferAccountTestResponse> => {
  const response = await axiosInstance.post(`/buffer-accounts/${id}/test`);
  return response.data;
};
