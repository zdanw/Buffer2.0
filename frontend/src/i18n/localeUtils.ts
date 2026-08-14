import type { Locale } from './types';

export function localeToIntl(locale: Locale): string {
  return locale === 'zh' ? 'zh-CN' : 'en-US';
}

export function useDateLocale(locale: Locale) {
  return localeToIntl(locale);
}
