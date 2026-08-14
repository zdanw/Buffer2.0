export type Locale = 'en' | 'zh';

export type TranslationTree = {
  [key: string]: string | TranslationTree;
};

export type TranslateFn = (key: string, params?: Record<string, string | number>) => string;
