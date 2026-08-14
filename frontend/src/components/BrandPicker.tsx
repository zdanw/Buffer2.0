import { useEffect, useState } from 'react';
import type { BrandSummary } from '@/api/brands';
import { getBrands } from '@/api/brands';
import { useI18n } from '@/i18n/useI18n';

interface BrandPickerProps {
  value?: string | null;
  onChange: (brandId: string) => void;
  disabled?: boolean;
  className?: string;
  allowEmpty?: boolean;
}

export default function BrandPicker({
  value,
  onChange,
  disabled = false,
  className = '',
  allowEmpty = false,
}: BrandPickerProps) {
  const { t } = useI18n();
  const [brands, setBrands] = useState<BrandSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        setBrands(await getBrands());
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled || loading}
      className={`w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 disabled:opacity-50 ${className}`}
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
