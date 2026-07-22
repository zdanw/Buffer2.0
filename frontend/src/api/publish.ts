import axiosInstance from './axiosInstance';

export const publishContent = async (
  text: string,
  image_url?: string,
  platforms?: string[]
): Promise<{ publish_id: string; status: string; published_platforms?: string[] }> => {
  const response = await axiosInstance.post('/publish/', {
    text,
    image_url: image_url || undefined,
    platforms: platforms && platforms.length > 0 ? platforms : undefined,
  });
  return response.data;
};
