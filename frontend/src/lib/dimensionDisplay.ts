export const NULL_DIMENSION_LABEL = 'NULL';

const DIMENSION_FIELD_NAMES = [
  'scene',
  'lighting',
  'style',
  'composition',
  'details',
  'quality',
  'viewpoint',
] as const;

const VISION_SCENE_FUSION_PLACEHOLDERS = new Set([
  '参考场景图+视觉模型',
  '视觉模型自主(场景融合)',
  'scene reference + vision model',
  'vision model (scene fusion)',
]);

/** Normalize dimension values for UI; legacy "默认*" placeholders map to NULL. */
export function formatDimensionDisplayValue(value?: string | null): string {
  const text = (value ?? '').trim();
  if (!text || text.toUpperCase() === NULL_DIMENSION_LABEL) {
    return NULL_DIMENSION_LABEL;
  }
  if (text.startsWith('默认')) {
    return NULL_DIMENSION_LABEL;
  }
  if (VISION_SCENE_FUSION_PLACEHOLDERS.has(text.toLowerCase())) {
    return NULL_DIMENSION_LABEL;
  }
  return text;
}

/** True when every dimension is empty / NULL (e.g. vision scene fusion). */
export function areDimensionsAllNull(dimensions?: Partial<Record<string, string>> | null): boolean {
  if (!dimensions) return true;
  return DIMENSION_FIELD_NAMES.every(
    (field) => formatDimensionDisplayValue(dimensions[field]) === NULL_DIMENSION_LABEL
  );
}
