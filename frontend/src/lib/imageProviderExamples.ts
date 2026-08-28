import type { ImageProviderType } from '@/api/imageProviders';
import { IMAGE_PROVIDER_PRESETS } from './imageProviderPresets';

export type ImageProviderExamples = {
  name: string;
  apiKey: string;
  defaultModel: string;
  baseUrl: string;
};

export const IMAGE_PROVIDER_EXAMPLES: Record<ImageProviderType, ImageProviderExamples> = {
  openai_compatible: {
    name: 'Production OpenAI',
    apiKey: 'sk-proj-abc123…',
    defaultModel: 'gpt-image-1',
    baseUrl: IMAGE_PROVIDER_PRESETS.openai_compatible.base_url,
  },
  doubao_ark: {
    name: 'Production Doubao',
    apiKey: 'your-volcengine-access-key',
    defaultModel: 'ep-20260616164806-7pj5g',
    baseUrl: IMAGE_PROVIDER_PRESETS.doubao_ark.base_url,
  },
  aliyun_maas: {
    name: 'Production Qwen Image',
    apiKey: 'sk-abc123…',
    defaultModel: 'qwen-image-3.0',
    baseUrl: IMAGE_PROVIDER_PRESETS.aliyun_maas.base_url,
  },
  google_gemini: {
    name: 'Nano Banana Pro',
    apiKey: 'AIzaSy…',
    defaultModel: 'gemini-3.1-flash-image',
    baseUrl: IMAGE_PROVIDER_PRESETS.google_gemini.base_url,
  },
  agnes: {
    name: 'Production Agnes',
    apiKey: 'agnes-api-key…',
    defaultModel: 'agnes-image-2.1-flash',
    baseUrl: IMAGE_PROVIDER_PRESETS.agnes.base_url,
  },
};

export function examplesForProviderType(type: ImageProviderType): ImageProviderExamples {
  return IMAGE_PROVIDER_EXAMPLES[type];
}
