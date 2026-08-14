import type { TranslationTree } from './types';

export function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{\{(\w+)\}\}/g, (_, key: string) =>
    params[key] !== undefined ? String(params[key]) : `{{${key}}}`,
  );
}

export function resolveTranslation(
  tree: TranslationTree,
  key: string,
  params?: Record<string, string | number>,
): string {
  const value = key.split('.').reduce<unknown>((node, part) => {
    if (node && typeof node === 'object' && part in node) {
      return (node as TranslationTree)[part];
    }
    return undefined;
  }, tree);

  return typeof value === 'string' ? interpolate(value, params) : key;
}
