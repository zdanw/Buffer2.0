import axiosInstance from './axiosInstance';

export interface VisionChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface VisionChatConfig {
  enabled: boolean;
  chat_model: string;
  chat_api_url: string;
  image_model: string;
  image_api_url: string;
}

export interface VisionChatRequest {
  messages: VisionChatMessage[];
  system_prompt?: string;
  image_urls?: string[];
  temperature?: number;
  max_tokens?: number;
}

export interface VisionChatResponse {
  content: string;
  model: string;
  finish_reason?: string | null;
}

export interface VisionImageRequest {
  prompt: string;
  size?: string;
  image_urls?: string[];
}

export interface VisionImageResponse {
  model: string;
  image_urls: string[];
}

export async function getVisionChatConfig(): Promise<VisionChatConfig> {
  const { data } = await axiosInstance.get<VisionChatConfig>('/dev/vision-chat/config');
  return data;
}

export async function sendVisionChat(body: VisionChatRequest): Promise<VisionChatResponse> {
  const { data } = await axiosInstance.post<VisionChatResponse>('/dev/vision-chat', body, {
    timeout: 180000,
  });
  return data;
}

export async function generateVisionImage(body: VisionImageRequest): Promise<VisionImageResponse> {
  const { data } = await axiosInstance.post<VisionImageResponse>('/dev/vision-chat/image', body, {
    timeout: 180000,
  });
  return data;
}
