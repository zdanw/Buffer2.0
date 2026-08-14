import { useI18n } from '@/i18n/useI18n';
import type { DimensionTypeKey } from '@/api/dimensions';

const KNOWN_DIMENSION_TYPES = [
  'scenes',
  'lighting',
  'styles',
  'compositions',
  'details',
  'quality',
  'viewpoints',
] as const;

export function useDimensionTypeLabel() {
  const { t } = useI18n();
  return (key: string, fallback?: string) => {
    if ((KNOWN_DIMENSION_TYPES as readonly string[]).includes(key)) {
      return t(`dimensionTypes.${key as DimensionTypeKey}`);
    }
    return fallback || key;
  };
}
