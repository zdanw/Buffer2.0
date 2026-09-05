import BrandPicker from '@/components/BrandPicker';
import { useBrandContext } from '@/context/BrandContext';
import { useDelayedVisible } from '@/hooks/useDelayedVisible';
import { useI18n } from '@/i18n/useI18n';
import { Loader2 } from 'lucide-react';

/** Brand context strip below the global app chrome header. */
export default function BrandSelectorBar() {
  const { t } = useI18n();
  const {
    brands,
    activeBrandId,
    activeBrand,
    setActiveBrandId,
    loading,
    brandFilterLoading,
  } = useBrandContext();

  const productCount = activeBrand?.product_count ?? 0;
  const kitComplete = Boolean(activeBrand?.voice?.trim());
  const isBusy = loading || brandFilterLoading;
  const showBusyStatus = useDelayedVisible(isBusy);

  const loadingMessage = brandFilterLoading
    ? activeBrand
      ? t('brands.selector.loadingProductsFor', { brand: activeBrand.name })
      : t('brands.selector.loadingAllProducts')
    : t('brands.selector.loading');

  return (
    <div className="relative border-t border-canvas-border bg-white">
      {brandFilterLoading && showBusyStatus && (
        <div className="absolute inset-x-0 top-0 h-0.5 overflow-hidden bg-forge-100" aria-hidden="true">
          <div className="h-full w-1/3 bg-forge-600 animate-brand-filter-progress" />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-2.5 lg:px-6">
        <div className="min-w-0 w-full sm:w-auto sm:min-w-[200px] flex items-center gap-2">
          <BrandPicker
            value={activeBrandId ?? ''}
            onChange={(id) => setActiveBrandId(id || null)}
            brands={brands}
            loading={loading}
            disabled={brandFilterLoading}
            allowEmpty
            className="border-canvas-border font-medium"
          />
        </div>

        {showBusyStatus ? (
          <div
            className="inline-flex items-center gap-2 rounded-full border border-forge-200 bg-forge-50 px-3 py-1 text-sm font-medium text-forge-800"
            role="status"
            aria-live="polite"
          >
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-forge-600" />
            <span>{loadingMessage}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 text-sm text-ink-500 shrink-0">
            {activeBrand ? (
              <>
                <span className="text-canvas-border hidden sm:inline">·</span>
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
        )}
      </div>
    </div>
  );
}
