import axiosInstance from './axiosInstance';

export interface DimensionType {
  name: string;
  display_name: string;
}

/** unrestricted = 全部兼容；allowlist 空列表 = 都不兼容；allowlist 有项 = 白名单 */
export type CompatMode = 'unrestricted' | 'allowlist' | 'blocklist';

export interface DimensionCompatEntry {
  mode: CompatMode;
  items: string[];
}

/** 新格式为 DimensionCompatEntry；旧 API 可能仍返回 string[] */
export type DimensionCompatValue = DimensionCompatEntry | string[];

export interface DimensionCompatibilities {
  scenes?: DimensionCompatValue;
  lighting?: DimensionCompatValue;
  styles?: DimensionCompatValue;
  compositions?: DimensionCompatValue;
  details?: DimensionCompatValue;
  quality?: DimensionCompatValue;
  viewpoints?: DimensionCompatValue;
}

export const ALL_DIMENSION_TYPES = [
  { key: 'scenes', label: '场景', color: 'bg-green-100 text-green-800' },
  { key: 'lighting', label: '光线', color: 'bg-blue-100 text-blue-800' },
  { key: 'styles', label: '风格', color: 'bg-purple-100 text-purple-800' },
  { key: 'compositions', label: '构图', color: 'bg-orange-100 text-orange-800' },
  { key: 'details', label: '细节', color: 'bg-cyan-100 text-cyan-800' },
  { key: 'quality', label: '画质', color: 'bg-pink-100 text-pink-800' },
  { key: 'viewpoints', label: '视角', color: 'bg-teal-100 text-teal-800' },
] as const;

export type DimensionTypeKey = typeof ALL_DIMENSION_TYPES[number]['key'];

export function emptyCompatEntry(mode: CompatMode = 'unrestricted'): DimensionCompatEntry {
  return { mode, items: [] };
}

export function getCompatEntry(
  compat: DimensionCompatibilities | undefined,
  key: string
): DimensionCompatEntry {
  const entry = compat?.[key as keyof DimensionCompatibilities];
  if (entry && typeof entry === 'object' && 'mode' in entry) {
    return { mode: entry.mode, items: entry.items || [] };
  }
  // 兼容旧 API：string[] —— 空 = 全部兼容，非空 = 白名单
  if (Array.isArray(entry)) {
    return entry.length === 0
      ? emptyCompatEntry('unrestricted')
      : { mode: 'allowlist', items: entry };
  }
  return emptyCompatEntry('unrestricted');
}

export interface PromptDimension {
  dimension_id: string;
  product_type: string;
  dimension_type: string;
  item_id: string;
  name: string;
  /** false = 已禁用，生成链路不会使用 */
  enabled?: boolean;
  compatibilities?: DimensionCompatibilities;
  created_at: string;
  updated_at: string;
}

export interface PromptDimensionCreate {
  product_type: string;
  dimension_type: string;
  name: string;
  item_id?: string;
  compatibilities?: DimensionCompatibilities;
}

export interface PromptDimensionUpdate {
  name?: string;
  enabled?: boolean;
  compatibilities?: DimensionCompatibilities;
}

export interface ProductDimension {
  id: string;
  product_id: string;
  dimension_id?: string;
  dimension_type: string;
  item_id?: string;
  name?: string;
  time?: string;
  lighting?: string[];
  is_custom: boolean;
  created_at: string;
}

export interface ProductType {
  value: string;
  label: string;
}

export const getDimensionTypes = async (): Promise<DimensionType[]> => {
  const response = await axiosInstance.get('/prompt-dimensions/dimension-types');
  return response.data;
};

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

export const getPromptDimensions = async (
  productType?: string,
  dimensionType?: string,
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedResponse<PromptDimension>> => {
  const params = new URLSearchParams();
  if (productType) params.append('product_type', productType);
  if (dimensionType) params.append('dimension_type', dimensionType);
  params.append('page', page.toString());
  params.append('page_size', pageSize.toString());
  
  const response = await axiosInstance.get(`/prompt-dimensions/?${params.toString()}`);
  
  if (response.data && response.data.data && Array.isArray(response.data.data)) {
    return response.data;
  }
  
  return { data: [], pagination: { current: 1, page_size: pageSize, total: 0, pages: 0 } };
};

export const createPromptDimension = async (data: PromptDimensionCreate): Promise<PromptDimension> => {
  const response = await axiosInstance.post('/prompt-dimensions/', data);
  return response.data;
};

export const updatePromptDimension = async (
  dimensionId: string,
  data: PromptDimensionUpdate
): Promise<PromptDimension> => {
  const response = await axiosInstance.put(`/prompt-dimensions/${dimensionId}`, data);
  return response.data;
};

export const deletePromptDimension = async (dimensionId: string): Promise<void> => {
  await axiosInstance.delete(`/prompt-dimensions/${dimensionId}`);
};

export const importVisualStylePack = async (packId: string): Promise<{ status: string; message: string }> => {
  const response = await axiosInstance.post(`/prompt-dimensions/import-pack/${packId}`);
  return response.data;
};

export const resetVisualStyles = async (packId: string = 'general'): Promise<{ status: string; message: string }> => {
  const response = await axiosInstance.post('/prompt-dimensions/reset', { pack_id: packId });
  return response.data;
};

/** @deprecated Use importVisualStylePack or resetVisualStyles */
export const initializeDimensions = async (): Promise<{ status: string; message: string }> => {
  const response = await axiosInstance.post('/prompt-dimensions/initialize/');
  return response.data;
};

export const getDimensionsByType = async (
  productType: string,
  dimensionType: string
): Promise<any[]> => {
  const response = await axiosInstance.get(`/prompt-dimensions/${productType}/by-type/${dimensionType}`);
  return response.data;
};

export const getProductTypes = async (): Promise<ProductType[]> => {
  const response = await axiosInstance.get('/prompt-dimensions/product-types');
  return response.data.product_types || [];
};
