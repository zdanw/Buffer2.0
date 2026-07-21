import axiosInstance from './axiosInstance';

export const publishContent = async (text: string, image_url?: string, platforms?: string[]): Promise<{ publish_id: string; status: string }> => {
  const params = new URLSearchParams();
  params.append('text', text);
  if (image_url) params.append('image_url', image_url);
  if (platforms) params.append('platforms', JSON.stringify(platforms));
  
  const response = await axiosInstance.post('/publish/', params);
  return response.data;
};
