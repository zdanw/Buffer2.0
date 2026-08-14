import { createContext, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { en } from './locales/en';
import { zh } from './locales/zh';
import { resolveTranslation } from './resolve';
import type { Locale, TranslationTree } from './types';

const STORAGE_KEY = 'pulseforge_locale';

const LOCALES: Record<Locale, TranslationTree> = { en, zh };

function readStoredLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'en' || stored === 'zh') return stored;
  } catch {
    // ignore
  }
  const browser = navigator.language.toLowerCase();
  return browser.startsWith('zh') ? 'zh' : 'en';
}

export type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
};

export const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => readStoredLocale());

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore
    }
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) =>
      resolveTranslation(LOCALES[locale], key, params),
    [locale],
  );

  useEffect(() => {
    document.documentElement.lang = locale === 'zh' ? 'zh-CN' : 'en';
    document.title = resolveTranslation(LOCALES[locale], 'brand.name');
  }, [locale]);

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
