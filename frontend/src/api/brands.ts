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
  buffer_account_id?: string | null;
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
  extra?: Record<string, unknown> | null;
  buffer_account_id?: string | null;
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
  buffer_account_id?: string | null;
}

export type BrandUpdate = Partial<BrandCreate> & {
  copy_system_prompt?: string;
  image_system_prompt?: string;
  vision_image_system_prompt?: string;
  vision_scene_system_prompt?: string;
  buffer_account_id?: string | null;
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

/** 仅返回当前用户品牌列表里有的 id，避免请求他人/系统品牌导致 404。 */
export function ownedBrandId(
  brands: { brand_id: string }[],
  preferred?: string | null,
): string {
  if (preferred && brands.some((b) => b.brand_id === preferred)) {
    return preferred;
  }
  return brands[0]?.brand_id ?? '';
}

/** Prefer a non-generic brand for new products; fall back to Generic only when none exist. */
export function defaultProductBrandId(
  brands: BrandSummary[],
  preferred?: string | null,
): string {
  const nonGeneric = brands.filter((b) => !b.is_generic);
  if (preferred) {
    const match = brands.find((b) => b.brand_id === preferred);
    if (match && !match.is_generic) return preferred;
  }
  if (nonGeneric.length > 0) return nonGeneric[0].brand_id;
  return ownedBrandId(brands, preferred);
}

export function findOwnedBrand<T extends { brand_id: string }>(
  brands: T[],
  brandId?: string | null,
): T | undefined {
  if (!brandId) return undefined;
  return brands.find((b) => b.brand_id === brandId);
}
