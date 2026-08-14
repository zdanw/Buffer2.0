import { ChevronDown } from 'lucide-react';
import BrandPicker from '@/components/BrandPicker';
import { useBrandContext } from '@/context/BrandContext';
import { useI18n } from '@/i18n/useI18n';

export default function BrandSelectorBar() {
  const { t } = useI18n();
  const { activeBrandId, activeBrand, setActiveBrandId } = useBrandContext();

  const productCount = activeBrand?.product_count ?? 0;
  const kitComplete = Boolean(activeBrand?.voice?.trim());

  return (
    <div className="sticky top-0 z-20 hidden lg:flex items-center gap-3 border-b border-gray-200 bg-white/95 backdrop-blur px-6 py-2.5">
      <div className="flex items-center gap-2 min-w-[200px]">
        <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" aria-hidden />
        <BrandPicker
          value={activeBrandId ?? ''}
          onChange={(id) => setActiveBrandId(id || null)}
          allowEmpty
          className="border-0 shadow-none focus:ring-0 font-medium text-gray-900"
        />
      </div>
      <span className="text-gray-300">·</span>
      <span className="text-sm text-gray-500">
        {activeBrand
          ? t('brands.selector.products', { count: productCount })
          : t('brands.allBrands')}
      </span>
      {activeBrand && (
        <>
          <span className="text-gray-300">·</span>
          <span
            className={`text-sm ${kitComplete ? 'text-emerald-600' : 'text-amber-600'}`}
          >
            {kitComplete ? t('brands.selector.kitComplete') : t('brands.selector.kitIncomplete')}
            {kitComplete ? ' ✓' : ''}
          </span>
        </>
      )}
    </div>
  );
}
