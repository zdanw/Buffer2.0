export const NULL_DIMENSION_LABEL = 'NULL';

/** Normalize dimension values for UI; legacy "默认*" placeholders map to NULL. */
export function formatDimensionDisplayValue(value?: string | null): string {
  const text = (value ?? '').trim();
  if (!text || text.toUpperCase() === NULL_DIMENSION_LABEL) {
    return NULL_DIMENSION_LABEL;
  }
  if (text.startsWith('默认')) {
    return NULL_DIMENSION_LABEL;
  }
  return text;
}
