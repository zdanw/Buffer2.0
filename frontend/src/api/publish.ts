import axiosInstance from './axiosInstance';

export interface PublishRecord {
  publish_id: string;
  task_id?: string;
  product_id?: string;
  platform?: string;
  content: {
    text: string;
    image_url?: string;
  };
  status: string;
  buffer_id?: string;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

export const publishContent = async (text: string, image_url?: string, platforms?: string[]): Promise<{ publish_id: string; status: string }> => {
  const params = new URLSearchParams();
  params.append('text', text);
  if (image_url) params.append('image_url', image_url);
  if (platforms) params.append('platforms', JSON.stringify(platforms));
  
  const response = await axiosInstance.post('/publish/', params);
  return response.data;
};

export const getPublishStatus = async (publishId: string): Promise<PublishRecord> => {
  const response = await axiosInstance.get(`/publish/status/${publishId}`);
  return response.data;
};