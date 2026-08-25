import type { Locale } from '@/i18n/types';

/** Stored dimension name only — no locale-based translation. */
export function getDimensionDisplayName(
  item: { name?: string | null },
  locale: Locale,
): string {
  const name = (item.name || '').trim();
  if (name) return name;
  return locale === 'zh' ? '默认' : 'Default';
}
