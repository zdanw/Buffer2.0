import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Search, X } from 'lucide-react';
import type { BrandSummary } from '@/api/brands';
import { GENERIC_BRAND_ID } from '@/api/brands';
import type { Product } from '@/api/products';
import BrandBadge from '@/components/BrandBadge';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import { useI18n } from '@/i18n/useI18n';

interface TaskProductPickerProps {
  products: Product[];
  brands: BrandSummary[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  error?: string;
}

function brandLabel(brand: BrandSummary | undefined, t: (key: string) => string): string {
  if (!brand) return t('brands.generic');
  if (brand.is_generic) return t('brands.generic');
  return brand.name;
}

export default function TaskProductPicker({
  products,
  brands,
  selectedIds,
  onChange,
  error,
}: TaskProductPickerProps) {
  const { t } = useI18n();
  const [searchQuery, setSearchQuery] = useState('');
  const [brandFilterId, setBrandFilterId] = useState<string>('');
  const [expandedCategories, setExpandedCategories] = useState<string[]>([]);

  const brandMap = useMemo(
    () => new Map(brands.map((brand) => [brand.brand_id, brand])),
    [brands]
  );

  const selectedProducts = useMemo(
    () =>
      selectedIds
        .map((id) => products.find((product) => product.product_id === id))
        .filter((product): product is Product => Boolean(product)),
    [products, selectedIds]
  );

  const filteredProducts = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return products.filter((product) => {
      if (brandFilterId && (product.brand_id || GENERIC_BRAND_ID) !== brandFilterId) {
        return false;
      }
      if (!query) return true;
      const brand = brandMap.get(product.brand_id || GENERIC_BRAND_ID);
      const brandName = brandLabel(brand, t).toLowerCase();
      return (
        product.product_name.toLowerCase().includes(query) ||
        product.category.toLowerCase().includes(query) ||
        brandName.includes(query)
      );
    });
  }, [products, searchQuery, brandFilterId, brandMap, t]);

  const categories = useMemo(() => {
    const unique = new Set(filteredProducts.map((product) => product.category));
    return [...unique].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
  }, [filteredProducts]);

  useEffect(() => {
    const categoriesWithSelection = [
      ...new Set(
        selectedProducts
          .map((product) => product.category)
          .filter((category) => categories.includes(category))
      ),
    ];
    if (categoriesWithSelection.length > 0) {
      setExpandedCategories((prev) => [...new Set([...prev, ...categoriesWithSelection])]);
    }
  }, [selectedProducts, categories]);

  const toggleProduct = (productId: string) => {
    onChange(
      selectedIds.includes(productId)
        ? selectedIds.filter((id) => id !== productId)
        : [...selectedIds, productId]
    );
  };

  const removeProduct = (productId: string) => {
    onChange(selectedIds.filter((id) => id !== productId));
  };

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) =>
      prev.includes(category) ? prev.filter((item) => item !== category) : [...prev, category]
    );
  };

  const getCategoryProducts = (category: string) =>
    filteredProducts.filter((product) => product.category === category);

  const getSelectedInCategory = (category: string) => {
    const ids = new Set(getCategoryProducts(category).map((product) => product.product_id));
    return selectedIds.filter((id) => ids.has(id)).length;
  };

  const setCategorySelection = (category: string, selectAll: boolean) => {
    const categoryIds = getCategoryProducts(category).map((product) => product.product_id);
    if (selectAll) {
      onChange([...new Set([...selectedIds, ...categoryIds])]);
      return;
    }
    const categoryIdSet = new Set(categoryIds);
    onChange(selectedIds.filter((id) => !categoryIdSet.has(id)));
  };

  if (products.length === 0) {
    return <p className="text-sm text-gray-400 py-2">{t('tasks.noProducts')}</p>;
  }

  return (
    <div className="space-y-3">
      {selectedProducts.length > 0 && (
        <div className="rounded-lg border border-forge-100 bg-forge-50/60 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-sm font-medium text-ink-900">
              {t('tasks.selectedProducts', { count: selectedProducts.length })}
            </span>
            <button
              type="button"
              onClick={() => onChange([])}
              className="text-xs font-medium text-forge-600 hover:text-forge-800"
            >
              {t('tasks.clearSelection')}
            </button>
          </div>
          <div className="flex max-h-24 flex-wrap gap-1.5 overflow-y-auto">
            {selectedProducts.map((product) => {
              const brand = brandMap.get(product.brand_id || GENERIC_BRAND_ID);
              return (
                <span
                  key={product.product_id}
                  className="inline-flex max-w-full items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs text-gray-700 shadow-sm ring-1 ring-forge-100"
                >
                  <span className="truncate">{product.product_name}</span>
                  {!brandFilterId && (
                    <span className="shrink-0 text-[10px] text-gray-400">
                      · {brandLabel(brand, t)}
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => removeProduct(product.product_id)}
                    className="shrink-0 rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                    aria-label={t('tasks.removeProduct', { name: product.product_name })}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div className="relative sm:col-span-2">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={t('placeholders.tasks.searchProducts')}
            className="w-full rounded-lg border border-gray-300 py-2 pl-9 pr-3 text-sm focus:border-transparent focus:ring-2 focus:ring-forge-500"
          />
        </div>
        <div className="sm:col-span-2">
          <label className="mb-1 block text-xs font-medium text-gray-500">{t('tasks.filterByBrand')}</label>
          <select
            value={brandFilterId}
            onChange={(event) => setBrandFilterId(event.target.value)}
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-forge-500 focus:ring-2 focus:ring-forge-200"
          >
            <option value="">{t('brands.allBrands')}</option>
            {brands.map((brand) => (
              <option key={brand.brand_id} value={brand.brand_id}>
                {brand.is_generic ? t('brands.generic') : brand.name}
                {brand.is_generic ? ` (${t('brands.system')})` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="max-h-72 space-y-2 overflow-y-auto rounded-lg border border-gray-200 p-2">
        {categories.length === 0 ? (
          <p className="px-2 py-6 text-center text-sm text-gray-400">{t('tasks.noMatchingProducts')}</p>
        ) : (
          categories.map((category) => {
            const categoryProducts = getCategoryProducts(category);
            const selectedInCategory = getSelectedInCategory(category);
            const isExpanded = expandedCategories.includes(category);
            const allSelected =
              categoryProducts.length > 0 && selectedInCategory === categoryProducts.length;

            return (
              <div key={category} className="overflow-hidden rounded-lg border border-gray-200">
                <div className="flex items-center justify-between gap-2 bg-gray-50 px-3 py-2">
                  <button
                    type="button"
                    onClick={() => toggleCategory(category)}
                    className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  >
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 shrink-0 text-gray-500" />
                    ) : (
                      <ChevronRight className="h-4 w-4 shrink-0 text-gray-500" />
                    )}
                    <span className="truncate font-medium text-gray-700">{category}</span>
                    <span className="shrink-0 text-xs text-gray-500">
                      {t('tasks.categoryProductCount', { count: categoryProducts.length })}
                    </span>
                    {selectedInCategory > 0 && (
                      <span className="shrink-0 rounded-full bg-forge-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                        {t('tasks.selectedInCategory', {
                          selected: selectedInCategory,
                          total: categoryProducts.length,
                        })}
                      </span>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => setCategorySelection(category, !allSelected)}
                    className="shrink-0 text-xs font-medium text-forge-600 hover:text-forge-800"
                  >
                    {allSelected ? t('tasks.deselectCategory') : t('tasks.selectCategory')}
                  </button>
                </div>
                {isExpanded && (
                  <div className="space-y-1 bg-white p-2">
                    {categoryProducts.map((product) => {
                      const isSelected = selectedIds.includes(product.product_id);
                      const brand = brandMap.get(product.brand_id || GENERIC_BRAND_ID);
                      return (
                        <label
                          key={product.product_id}
                          className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 transition-colors ${
                            isSelected
                              ? 'border-forge-200 bg-forge-50'
                              : 'border-transparent hover:bg-gray-50'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleProduct(product.product_id)}
                            className="h-4 w-4 rounded border-gray-300 text-forge-600 focus:ring-forge-500"
                          />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-800">
                              {product.product_name}
                            </p>
                            {!brandFilterId && (
                              <BrandBadge brand={brand} className="mt-1" />
                            )}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}

export function TaskProductPickerLabel() {
  const { t } = useI18n();
  return (
    <LabelWithTooltip
      label={t('tasks.selectProducts')}
      tooltip={t('tasks.tooltips.selectProducts')}
      required
    />
  );
}
