import { useMemo } from 'react';
import { createValidators } from '@/lib/formValidation';
import { useI18n } from './useI18n';

export function useValidators() {
  const { t } = useI18n();
  return useMemo(() => createValidators(t), [t]);
}

export { useDimensionTypeLabel } from './useDimensionTypeLabel';
