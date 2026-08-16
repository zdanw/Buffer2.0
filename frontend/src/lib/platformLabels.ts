export const PLATFORMS = ['instagram', 'tiktok', 'facebook'] as const;

export type Platform = typeof PLATFORMS[number];

export const PLATFORM_LABELS: Record<Platform, string> = {
  instagram: 'Instagram',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

export function platformLabel(platform: string): string {
  if (platform in PLATFORM_LABELS) {
    return PLATFORM_LABELS[platform as Platform];
  }
  return platform;
}
