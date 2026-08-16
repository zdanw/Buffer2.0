import BrandPicker from '@/components/BrandPicker';
import { useBrandContext } from '@/context/BrandContext';
import { useI18n } from '@/i18n/useI18n';

export default function BrandSelectorBar() {
  const { t } = useI18n();
  const { brands, activeBrandId, activeBrand, setActiveBrandId, loading } = useBrandContext();

  const productCount = activeBrand?.product_count ?? 0;
  const kitComplete = Boolean(activeBrand?.voice?.trim());

  return (
    <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-canvas-border bg-white/95 backdrop-blur px-4 py-2.5 lg:px-6">
      <div className="min-w-0 flex-1 sm:flex-none sm:min-w-[200px]">
        <BrandPicker
          value={activeBrandId ?? ''}
          onChange={(id) => setActiveBrandId(id || null)}
          brands={brands}
          loading={loading}
          allowEmpty
          className="border-canvas-border font-medium"
        />
      </div>
      <div className="hidden sm:flex items-center gap-2 text-sm text-ink-500 shrink-0">
        {activeBrand ? (
          <>
            <span className="text-canvas-border">·</span>
            <span>{t('brands.selector.products', { count: productCount })}</span>
            <span className="text-canvas-border">·</span>
            <span className={kitComplete ? 'text-emerald-600' : 'text-amber-600'}>
              {kitComplete ? t('brands.selector.kitComplete') : t('brands.selector.kitIncomplete')}
              {kitComplete ? ' ✓' : ''}
            </span>
          </>
        ) : (
          <span className="text-ink-400">{t('brands.selector.viewingAll')}</span>
        )}
      </div>
    </div>
  );
}
