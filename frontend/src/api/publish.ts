import axiosInstance from './axiosInstance';

export const publishContent = async (
  text: string,
  image_url?: string,
  platforms?: string[],
  opts?: { product_id?: string; brand_id?: string }
): Promise<{ publish_id: string; status: string; published_platforms?: string[] }> => {
  const response = await axiosInstance.post('/publish/', {
    text,
    image_url: image_url || undefined,
    platforms: platforms && platforms.length > 0 ? platforms : undefined,
    product_id: opts?.product_id || undefined,
    brand_id: opts?.brand_id || undefined,
  });
  return response.data;
};
