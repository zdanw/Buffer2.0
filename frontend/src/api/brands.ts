import axiosInstance from './axiosInstance';

export interface BrandSummary {
  brand_id: string;
  slug: string;
  name: string;
  is_generic: boolean;
  is_system: boolean;
  voice?: string | null;
  logo_url?: string | null;
  vertical_pack?: string | null;
  product_count: number;
}

export interface BrandKit {
  brand_id: string;
  slug: string;
  name: string;
  is_generic: boolean;
  is_system: boolean;
  voice?: string | null;
  audience?: string | null;
  tone_keywords?: string | null;
  default_selling_points?: string[];
  default_hashtags?: string[];
  emoji_style?: string | null;
  words_to_avoid?: string | null;
  logo_url?: string | null;
  logo_font_rule?: string | null;
  vertical_pack?: string | null;
  default_product_type?: string | null;
  copy_system_prompt?: string | null;
  image_system_prompt?: string | null;
  vision_image_system_prompt?: string | null;
  vision_scene_system_prompt?: string | null;
  narrative_perspectives?: Record<string, unknown>[];
  writing_styles?: Record<string, unknown>[];
  copy_emoji_hints?: string | null;
  copy_example?: string | null;
  image_fallback_selling_points?: string | null;
  copy_fallback_selling_points?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface BrandCreate {
  name: string;
  slug?: string;
  voice?: string;
  audience?: string;
  tone_keywords?: string;
  default_selling_points?: string[];
  default_hashtags?: string[];
  emoji_style?: string;
  words_to_avoid?: string;
  logo_url?: string;
  logo_font_rule?: string;
  vertical_pack?: string;
  default_product_type?: string;
}

export type BrandUpdate = Partial<BrandCreate> & {
  copy_system_prompt?: string;
  image_system_prompt?: string;
  vision_image_system_prompt?: string;
  vision_scene_system_prompt?: string;
};

export const getBrands = async (): Promise<BrandSummary[]> => {
  const response = await axiosInstance.get('/brands/');
  return response.data?.data ?? [];
};

export const getBrand = async (brandId: string): Promise<BrandKit> => {
  const response = await axiosInstance.get(`/brands/${brandId}`);
  return response.data;
};

export const createBrand = async (data: BrandCreate): Promise<BrandKit> => {
  const response = await axiosInstance.post('/brands/', data);
  return response.data;
};

export const updateBrand = async (brandId: string, data: BrandUpdate): Promise<BrandKit> => {
  const response = await axiosInstance.put(`/brands/${brandId}`, data);
  return response.data;
};

export const deleteBrand = async (brandId: string): Promise<void> => {
  await axiosInstance.delete(`/brands/${brandId}`);
};

export const BEBCARE_BRAND_ID = '00000000-0000-0000-0000-000000000002';

export const uploadBrandLogo = async (brandId: string, file: File): Promise<{ logo_url: string }> => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await axiosInstance.post(`/brands/${brandId}/logo`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const initializeBrandPack = async (brandId: string): Promise<{ status: string; message: string }> => {
  const response = await axiosInstance.post(`/brands/${brandId}/initialize-pack`);
  return response.data;
};

export const GENERIC_BRAND_ID = '00000000-0000-0000-0000-000000000001';
