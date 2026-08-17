import type { BrandSummary } from '@/api/brands';
import { useI18n } from '@/i18n/useI18n';

interface BrandPickerProps {
  value?: string | null;
  onChange: (brandId: string) => void;
  brands: BrandSummary[];
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  allowEmpty?: boolean;
}

export default function BrandPicker({
  value,
  onChange,
  brands,
  loading = false,
  disabled = false,
  className = '',
  allowEmpty = false,
}: BrandPickerProps) {
  const { t } = useI18n();

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || loading}
      className={`w-full rounded-lg border border-canvas-border bg-white px-3 py-2 text-sm text-ink-900 focus:border-forge-500 focus:ring-2 focus:ring-forge-100 disabled:opacity-50 ${className}`}
    >
      {allowEmpty && <option value="">{t('brands.allBrands')}</option>}
      {brands.map((brand) => (
        <option key={brand.brand_id} value={brand.brand_id}>
          {brand.is_generic ? t('brands.generic') : brand.name}
          {brand.is_generic ? ` (${t('brands.system')})` : ''}
        </option>
      ))}
    </select>
  );
}
