import type { ImageProviderType } from '@/api/imageProviders';

export const IMAGE_PROVIDER_PRESETS: Record<
  ImageProviderType,
  { base_url: string; supports_list_models: boolean }
> = {
  openai_compatible: {
    base_url: 'https://api.openai.com/v1',
    supports_list_models: true,
  },
  doubao_ark: {
    base_url: 'https://ark.cn-beijing.volces.com/api/v3',
    supports_list_models: true,
  },
  aliyun_maas: {
    base_url:
      'https://ws-lxvmitlmy9ln8pda.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
    supports_list_models: true,
  },
  google_gemini: {
    base_url: 'https://generativelanguage.googleapis.com/v1beta',
    supports_list_models: true,
  },
  agnes: {
    base_url: 'https://api.agnes-ai.cn/v1',
    supports_list_models: true,
  },
};

export function presetForType(providerType: ImageProviderType) {
  return IMAGE_PROVIDER_PRESETS[providerType];
}
