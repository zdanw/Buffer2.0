import type { BrandSummary } from '@/api/brands';
import { useI18n } from '@/i18n/useI18n';

interface BrandBadgeProps {
  brand?: Pick<BrandSummary, 'name' | 'is_generic'> | null;
  variant?: 'generic' | 'system' | 'default';
  className?: string;
}

export default function BrandBadge({ brand, variant = 'default', className = '' }: BrandBadgeProps) {
  const { t } = useI18n();

  if (variant === 'system') {
    return (
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-ink-100 text-ink-600 ${className}`}>
        {t('brands.system')}
      </span>
    );
  }

  if (variant === 'generic' || brand?.is_generic) {
    return (
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 ${className}`}>
        {t('brands.generic')}
      </span>
    );
  }

  if (!brand) return null;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-forge-50 text-forge-700 ${className}`}>
      {brand.name}
    </span>
  );
}
