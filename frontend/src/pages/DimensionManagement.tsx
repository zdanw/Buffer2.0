import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Edit2, Trash2, X, RefreshCw, Database, Filter, ChevronDown } from 'lucide-react';
import type { PromptDimension, PromptDimensionUpdate, DimensionType, ProductType, PaginatedResponse, DimensionCompatibilities, DimensionCompatEntry } from '@/api/dimensions';
import { getDimensionTypes, getPromptDimensions, createPromptDimension, updatePromptDimension, deletePromptDimension, importVisualStylePack, resetVisualStyles, getProductTypes, ALL_DIMENSION_TYPES, getCompatEntry, emptyCompatEntry } from '@/api/dimensions';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import {
  LIMITS,
  alertValidationErrors,
  createValidators,
} from '@/lib/formValidation';
import Pagination from '@/components/Pagination';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import { useI18n } from '@/i18n/useI18n';
import { useDimensionTypeLabel } from '@/i18n/useDimensionTypeLabel';
import { getDimensionDisplayName } from '@/i18n/dimensionDisplayName';
import type { TranslateFn } from '@/lib/formValidation';
import { toast, confirmDialog, promptDialog } from '@/lib/feedback';

type CompatOptions = Record<string, { id: string; name: string }[]>;

type CompatCacheEntry = {
  options: CompatOptions;
  /** true = 已拉过该产品类型全部分页，可安全全选 */
  complete: boolean;
};

/** 模块级缓存：切 tab / 筛选后仍保留，避免编辑时反复拉兼容选项 */
const compatOptionsCache = new Map<string, CompatCacheEntry>();
const compatOptionsInflight = new Map<string, Promise<CompatOptions>>();

function emptyCompatOptions(): CompatOptions {
  return Object.fromEntries(ALL_DIMENSION_TYPES.map((t) => [t.key, []])) as CompatOptions;
}

function getCachedOptions(productType: string): CompatOptions | undefined {
  return compatOptionsCache.get(productType)?.options;
}

function isCompatCacheComplete(productType: string): boolean {
  return compatOptionsCache.get(productType)?.complete === true;
}

/** 用当前列表页数据预热缓存（不完全，仅加速展示；全选仍会补全） */
function seedCompatCacheFromList(dims: PromptDimension[]) {
  for (const dim of dims) {
    if (dim.enabled === false) continue;
    const entry = compatOptionsCache.get(dim.product_type) || {
      options: emptyCompatOptions(),
      complete: false,
    };
    if (entry.complete) continue;
    const bucket = entry.options[dim.dimension_type] || (entry.options[dim.dimension_type] = []);
    if (!bucket.some((x) => x.id === dim.item_id)) {
      bucket.push({ id: dim.item_id, name: dim.name });
    }
    compatOptionsCache.set(dim.product_type, entry);
  }
}

/** 后台预热：把当前页出现的产品类型拉全，编辑展开时直接命中 */
function prefetchCompatForProductTypes(productTypes: string[]) {
  for (const pt of productTypes) {
    if (!pt || isCompatCacheComplete(pt) || compatOptionsInflight.has(pt)) continue;
    void fetchCompatOptions(pt);
  }
}

/** 一次分页列表拉取该产品类型全部维度 */
async function fetchCompatOptions(productType: string): Promise<CompatOptions> {
  const cached = compatOptionsCache.get(productType);
  if (cached?.complete) return cached.options;

  const inflight = compatOptionsInflight.get(productType);
  if (inflight) return inflight;

  const promise = (async () => {
    const result = emptyCompatOptions();
    let page = 1;
    let pages = 1;
    do {
      const res = await getPromptDimensions(productType, undefined, page, 100, false);
      for (const dim of res.data) {
        if (dim.enabled === false) continue;
        const bucket = result[dim.dimension_type] || (result[dim.dimension_type] = []);
        bucket.push({ id: dim.item_id, name: dim.name });
      }
      pages = res.pagination.pages || 1;
      page += 1;
    } while (page <= pages);

    compatOptionsCache.set(productType, { options: result, complete: true });
    compatOptionsInflight.delete(productType);
    return result;
  })().catch((err) => {
    compatOptionsInflight.delete(productType);
    throw err;
  });

  compatOptionsInflight.set(productType, promise);
  return promise;
}

function invalidateCompatCache(productType?: string) {
  if (productType) {
    compatOptionsCache.delete(productType);
    compatOptionsInflight.delete(productType);
  } else {
    compatOptionsCache.clear();
    compatOptionsInflight.clear();
  }
}

/** 创建/改名后写入缓存，保留 complete，避免下次编辑整表重拉 */
function upsertCompatCacheItem(dim: PromptDimension) {
  if (dim.enabled === false) {
    removeCompatCacheItem(dim.product_type, dim.dimension_type, dim.item_id);
    return;
  }
  const entry = compatOptionsCache.get(dim.product_type) || {
    options: emptyCompatOptions(),
    complete: false,
  };
  const bucket = entry.options[dim.dimension_type] || (entry.options[dim.dimension_type] = []);
  const idx = bucket.findIndex((x) => x.id === dim.item_id);
  if (idx >= 0) {
    bucket[idx] = { id: dim.item_id, name: dim.name };
  } else {
    bucket.push({ id: dim.item_id, name: dim.name });
  }
  compatOptionsCache.set(dim.product_type, entry);
}

/** 删除后从缓存移除该项，保留其余选项与 complete */
function removeCompatCacheItem(productType: string, dimensionType: string, itemId: string) {
  const entry = compatOptionsCache.get(productType);
  if (!entry) return;
  const bucket = entry.options[dimensionType];
  if (!bucket) return;
  entry.options[dimensionType] = bucket.filter((x) => x.id !== itemId);
}

/** 兼容策略为单向，仅替换当前编辑行 */
function syncEditedCompatInList(
  rows: PromptDimension[],
  edited: PromptDimension,
): PromptDimension[] {
  return rows.map((row) =>
    row.dimension_id === edited.dimension_id ? { ...row, ...edited } : row
  );
}

/** UI 勾选集合：全部兼容视为全选；都不兼容为空；白名单为 items */
function selectedIdsForUi(entry: DimensionCompatEntry, allItemIds: string[]): string[] {
  if (entry.mode === 'unrestricted') return allItemIds;
  return entry.items || [];
}

function compatLabel(entry: DimensionCompatEntry, t: TranslateFn): string {
  if (entry.mode === 'unrestricted') return t('compat.unrestricted');
  if (entry.mode === 'allowlist' && (!entry.items || entry.items.length === 0)) return t('compat.none');
  if (entry.mode === 'blocklist') return t('compat.blocklist', { count: entry.items?.length || 0 });
  return t('compat.count', { count: entry.items?.length || 0 });
}

/** 列表单元格：全部兼容用 ✔ 节省列宽 */
function compatTableLabel(entry: DimensionCompatEntry, t: TranslateFn): string {
  if (entry.mode === 'unrestricted') return t('compat.checkmark');
  return compatLabel(entry, t);
}

export default function DimensionManagement({ isAdmin = false }: { isAdmin?: boolean }) {
  const { t, locale } = useI18n();
  const navigate = useNavigate();
  const dimensionTypeLabel = useDimensionTypeLabel();
  const v = useMemo(() => createValidators(t), [t]);
  const [dimensions, setDimensions] = useState<PromptDimension[]>([]);
  const [dimensionTypes, setDimensionTypes] = useState<DimensionType[]>([]);
  const [productTypes, setProductTypes] = useState<ProductType[]>([]);
  const [selectedProductType, setSelectedProductType] = useState<string>('');
  const [selectedDimensionType, setSelectedDimensionType] = useState<string>('');
  /** 已点「筛选」后生效的条件；表头/列只跟这个走，避免改下拉就改列 */
  const [appliedProductType, setAppliedProductType] = useState<string>('');
  const [appliedDimensionType, setAppliedDimensionType] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [loading, setLoading] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [listBusy, setListBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(false);
  const [importAction, setImportAction] = useState('');
  const [modalOptionsLoading, setModalOptionsLoading] = useState(false);
  const [selectedDimension, setSelectedDimension] = useState<PromptDimension | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const createEmptyCompatibilities = (excludeType?: string): DimensionCompatibilities => {
    const result: DimensionCompatibilities = {};
    for (const dimType of ALL_DIMENSION_TYPES) {
      if (dimType.key !== excludeType) {
        result[dimType.key] = emptyCompatEntry('unrestricted');
      }
    }
    return result;
  };

  const [formData, setFormData] = useState({
    product_type: 'General',
    dimension_type: 'scenes',
    name: '',
    compatibilities: createEmptyCompatibilities('scenes') as DimensionCompatibilities,
  });

  const [allDimensions, setAllDimensions] = useState<CompatOptions>({});

  /** 有完整缓存则同步命中；否则拉全量并写入缓存（筛选不会清缓存） */
  const ensureCompatOptions = async (productType: string) => {
    if (isCompatCacheComplete(productType)) {
      const cached = getCachedOptions(productType)!;
      setAllDimensions(cached);
      return cached;
    }
    const partial = getCachedOptions(productType);
    if (partial) setAllDimensions(partial);

    setModalOptionsLoading(true);
    try {
      const result = await fetchCompatOptions(productType);
      setAllDimensions(result);
      return result;
    } catch (error) {
      console.error('Failed to load compat options:', error);
      const empty = emptyCompatOptions();
      setAllDimensions(empty);
      return empty;
    } finally {
      setModalOptionsLoading(false);
    }
  };

  const getCompatibleDimensionTypes = (currentType: string) => {
    return ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== currentType);
  };

  const [expandedDimensions, setExpandedDimensions] = useState<Record<string, boolean>>({});

  const toggleDimension = (dimType: string) => {
    const willExpand = !expandedDimensions[dimType];
    setExpandedDimensions(prev => ({
      ...prev,
      [dimType]: !prev[dimType]
    }));
    if (willExpand) {
      void ensureCompatOptions(formData.product_type);
    }
  };

  const toggleSelectAll = async (dimType: string) => {
    const opts = await ensureCompatOptions(formData.product_type);
    const entry = getCompatEntry(formData.compatibilities, dimType);
    const allItems = opts[dimType]?.map(item => item.id) || [];
    const selected = selectedIdsForUi(entry, allItems);
    const isAllSelected =
      entry.mode === 'unrestricted' ||
      (allItems.length > 0 && allItems.every(id => selected.includes(id)));

    setFormData(prev => ({
      ...prev,
      compatibilities: {
        ...(prev.compatibilities || {}),
        // 全选 → 全部兼容；取消全选 → 都不兼容
        [dimType]: isAllSelected
          ? emptyCompatEntry('allowlist')
          : emptyCompatEntry('unrestricted'),
      }
    }));
  };

  useEffect(() => {
    void Promise.all([loadDimensionTypes(), loadProductTypes(), loadDimensions(1)]);
  }, []);

  const loadDimensionTypes = async () => {
    try {
      const data = await cachedFetch('dimensionTypes', () => getDimensionTypes());
      setDimensionTypes(data);
    } catch (error) {
      console.error('Failed to load dimension types:', error);
    }
  };

  const loadProductTypes = async () => {
    try {
      const data = await cachedFetch('productTypes', () => getProductTypes());
      setProductTypes(data);
    } catch (error) {
      console.error('Failed to load product types:', error);
    }
  };

  const loadDimensions = async (
    page: number = currentPage,
    newPageSize?: number,
    opts?: { silent?: boolean; keepRows?: boolean; fromFilter?: boolean }
  ) => {
    const fromFilter = Boolean(opts?.fromFilter);
    const silent = Boolean(opts?.silent);
    const keepRows = Boolean(opts?.keepRows) || fromFilter;
    if (!silent && !keepRows) setLoading(true);
    // 仅点「筛选」时显示筛选中；翻页/改每页条数用 listBusy
    if (fromFilter) setFiltering(true);
    else if (keepRows && !silent) setListBusy(true);
    const size = newPageSize ?? pageSize;
    // 翻页/改页大小沿用已生效条件；点筛选才用下拉当前值
    const productType = fromFilter ? selectedProductType : appliedProductType;
    const dimensionType = fromFilter ? selectedDimensionType : appliedDimensionType;
    try {
      const response: PaginatedResponse<PromptDimension> = await getPromptDimensions(
        productType || undefined,
        dimensionType || undefined,
        page,
        size
      );
      setDimensions(response.data);
      setTotal(response.pagination.total);
      setCurrentPage(response.pagination.current);
      if (fromFilter) {
        setAppliedProductType(selectedProductType);
        setAppliedDimensionType(selectedDimensionType);
      }
      if (newPageSize) {
        setPageSize(newPageSize);
      }
      // 预热：列表数据写入缓存 + 后台补全当前页产品类型，编辑时不再整表重拉
      seedCompatCacheFromList(response.data);
      const pts = [...new Set(response.data.map((d) => d.product_type))];
      prefetchCompatForProductTypes(pts);
    } catch (error) {
      console.error('Failed to load dimensions:', error);
    } finally {
      if (!silent && !keepRows) setLoading(false);
      if (fromFilter) setFiltering(false);
      else if (keepRows && !silent) setListBusy(false);
    }
  };

  const handleFilter = () => {
    // 保留当前表格内容，只在筛选按钮上转圈，避免“全部重置”的闪烁
    void loadDimensions(1, undefined, { fromFilter: true, keepRows: true });
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      invalidateCache('productTypes');
      invalidateCache('dimensionTypes');
      await Promise.all([
        loadDimensionTypes(),
        loadProductTypes(),
        loadDimensions(currentPage, undefined, { keepRows: true }),
      ]);
    } finally {
      setRefreshing(false);
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    void loadDimensions(1, newPageSize, { keepRows: true });
  };

  const matchesCurrentFilters = (dim: PromptDimension) => {
    if (appliedProductType && dim.product_type !== appliedProductType) return false;
    if (appliedDimensionType && dim.dimension_type !== appliedDimensionType) return false;
    return true;
  };

  const resetForm = () => {
    setFormData({
      product_type: productTypes[0]?.value ?? '',
      dimension_type: 'scenes',
      name: '',
      compatibilities: createEmptyCompatibilities('scenes'),
    });
    setSelectedDimension(null);
    setIsEdit(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      alertValidationErrors([
        v.required(t('dimensionsPage.productType'), formData.product_type),
        v.maxLen(t('dimensionsPage.productType'), formData.product_type, LIMITS.productType),
        v.required(t('dimensionsPage.dimensionType'), formData.dimension_type),
        v.required(t('dimensionsPage.name'), formData.name),
        v.maxLen(t('dimensionsPage.name'), formData.name, LIMITS.dimensionName),
      ])
    ) {
      return;
    }
    setSaving(true);
    try {
      const submitData = { ...formData };

      if (isEdit && selectedDimension) {
        const updatePayload: PromptDimensionUpdate = {
          name: submitData.name,
          compatibilities: submitData.compatibilities,
        };
        const updated = await updatePromptDimension(selectedDimension.dimension_id, updatePayload);
        // 本地更新列表 + 就地改缓存名称；不清空兼容选项缓存
        upsertCompatCacheItem(updated);
        setDimensions((prev) => syncEditedCompatInList(prev, updated));
      } else {
        const created = await createPromptDimension({
          product_type: submitData.product_type,
          dimension_type: submitData.dimension_type,
          name: submitData.name,
          compatibilities: submitData.compatibilities,
        });
        upsertCompatCacheItem(created);
        if (matchesCurrentFilters(created) && currentPage === 1) {
          setDimensions((prev) => [created, ...prev].slice(0, pageSize));
        }
        setTotal((t) => t + 1);
        void loadProductTypes();
      }
      setShowModal(false);
      resetForm();
    } catch (error: unknown) {
      console.error('Failed to save dimension:', error);
      const err = error as { response?: { data?: { detail?: unknown } } };
      const detail = err.response?.data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join('; ')
        : typeof detail === 'string'
          ? detail
          : t('dimensionsPage.saveFailed');
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (dimensionId: string) => {
    const ok = await confirmDialog({
      message: t('dimensionsPage.confirmDelete'),
      danger: true,
    });
    if (!ok) return;
    setDeletingId(dimensionId);
    try {
      const removed = dimensions.find((d) => d.dimension_id === dimensionId);
      await deletePromptDimension(dimensionId);
      if (removed) {
        removeCompatCacheItem(removed.product_type, removed.dimension_type, removed.item_id);
      }
      setDimensions((prev) => prev.filter((d) => d.dimension_id !== dimensionId));
      setTotal((t) => Math.max(0, t - 1));
      // 当前页删空则回到上一页
      if (dimensions.length <= 1 && currentPage > 1) {
        void loadDimensions(currentPage - 1, undefined, { silent: true });
      }
    } catch (error) {
      console.error('Failed to delete dimension:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const handleToggleEnabled = async (dimension: PromptDimension) => {
    if (togglingId) return;
    const nextEnabled = dimension.enabled === false;
    setTogglingId(dimension.dimension_id);
    try {
      const updated = await updatePromptDimension(dimension.dimension_id, { enabled: nextEnabled });
      upsertCompatCacheItem(updated);
      setDimensions((prev) =>
        prev.map((d) => (d.dimension_id === updated.dimension_id ? { ...d, ...updated } : d))
      );
    } catch (error) {
      console.error('Failed to toggle dimension enabled:', error);
      toast.error(nextEnabled ? t('dimensionsPage.toggleEnableFailed') : t('dimensionsPage.toggleDisableFailed'));
    } finally {
      setTogglingId(null);
    }
  };

  const reloadAfterPresetChange = async () => {
    invalidateCompatCache();
    invalidateCache('productTypes');
    invalidateCache('dimensionTypes');
    await Promise.all([loadProductTypes(), loadDimensions(1)]);
  };

  const handleImportPreset = async () => {
    if (!importAction || importAction === 'reset') return;
    setInitializing(true);
    try {
      const result = await importVisualStylePack(importAction);
      await reloadAfterPresetChange();
      toast.success(result.message || t('dimensionsPage.importSuccess'));
      setImportAction('');
    } catch (error) {
      console.error('Failed to import visual style pack:', error);
      toast.error(t('dimensionsPage.importFailed'));
    } finally {
      setInitializing(false);
    }
  };

  const handleResetPresets = async () => {
    const typed = await promptDialog({
      message: t('dimensionsPage.confirmReset'),
      expectedValue: 'RESET',
    });
    if (typed == null || typed !== 'RESET') return;
    setInitializing(true);
    try {
      const result = await resetVisualStyles('general');
      await reloadAfterPresetChange();
      toast.success(result.message || t('dimensionsPage.resetSuccess'));
      setImportAction('');
    } catch (error) {
      console.error('Failed to reset visual styles:', error);
      toast.error(t('dimensionsPage.resetFailed'));
    } finally {
      setInitializing(false);
    }
  };

  const handleAdminPresetAction = () => {
    if (importAction === 'reset') {
      void handleResetPresets();
    } else if (importAction) {
      void handleImportPreset();
    }
  };

  const openModal = (dimension?: PromptDimension) => {
    setExpandedDimensions({});
    setModalOptionsLoading(false);

    const pt = dimension?.product_type || selectedProductType || productTypes[0]?.value || '';
    const cached = getCachedOptions(pt);
    setAllDimensions(cached || {});

    if (dimension) {
      setIsEdit(true);
      setSelectedDimension(dimension);
      setFormData({
        product_type: dimension.product_type,
        dimension_type: dimension.dimension_type,
        name: dimension.name,
        compatibilities: dimension.compatibilities || createEmptyCompatibilities(dimension.dimension_type),
      });
      // 缓存已完整则不再请求；未完整才后台补全
      if (!isCompatCacheComplete(dimension.product_type)) {
        void ensureCompatOptions(dimension.product_type);
      }
    } else {
      setIsEdit(false);
      setSelectedDimension(null);
      const dt = selectedDimensionType || 'scenes';
      setFormData({
        product_type: pt,
        dimension_type: dt,
        name: '',
        compatibilities: createEmptyCompatibilities(dt),
      });
      if (!isCompatCacheComplete(pt)) {
        void ensureCompatOptions(pt);
      }
    }
    setShowModal(true);
  };

  const getDimensionTypeDisplayName = (typeName: string) => {
    const localized = dimensionTypeLabel(typeName);
    if (localized !== typeName) return localized;
    const found = dimensionTypes.find((dt) => dt.name === typeName);
    return found?.display_name || typeName;
  };

  const getDimensionTypeDescription = (typeName: string) => {
    const key = `dimensionTypeDescriptions.${typeName}`;
    const desc = t(key);
    return desc !== key ? desc : '';
  };

  const getProductTypeLabel = (value: string) => {
    const found = productTypes.find(t => t.value === value);
    return found?.label || value;
  };

  const compatColCount = ALL_DIMENSION_TYPES.filter((dimType) => dimType.key !== appliedDimensionType).length;
  const tableColSpan = 5 + compatColCount;

  return (
    <div className="min-w-0 p-4 sm:p-6">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 sm:text-2xl">{t('dimensionsPage.title')}</h2>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">{t('dimensionsPage.subtitle')}</p>
          <p className="text-gray-400 mt-1 text-xs sm:text-sm">{t('dimensionsPage.emptyStateHint')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={refreshing || loading || filtering || listBusy}
            className="flex items-center gap-2 bg-gray-100 text-gray-700 px-3 py-2 sm:px-4 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing || listBusy ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
          {isAdmin && (
            <div className="flex items-center gap-1">
              <div className="relative">
                <select
                  value={importAction}
                  onChange={(e) => setImportAction(e.target.value)}
                  disabled={initializing}
                  className="appearance-none pl-3 pr-8 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-forge-500 disabled:opacity-50"
                >
                  <option value="">{t('dimensionsPage.importPresets')}</option>
                  <option value="general">{t('dimensionsPage.importGeneral')}</option>
                  <option value="baby_family">{t('dimensionsPage.importBaby')}</option>
                  <option value="reset">{t('dimensionsPage.resetFactory')}</option>
                </select>
                <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
              <button
                type="button"
                onClick={handleAdminPresetAction}
                disabled={initializing || !importAction}
                className="flex items-center gap-2 bg-amber-600 text-white px-3 py-2 sm:px-4 rounded-lg hover:bg-amber-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm"
              >
                {initializing ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Database className="w-4 h-4" />
                )}
                {initializing ? t('dimensionsPage.applying') : t('dimensionsPage.applyPreset')}
              </button>
            </div>
          )}
          <button
            onClick={() => openModal()}
            className="flex items-center gap-2 bg-forge-600 text-white px-3 py-2 sm:px-4 rounded-lg hover:bg-forge-700 transition-colors text-sm"
          >
            <Plus className="w-5 h-5" />
            {t('dimensionsPage.addDimension')}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="flex items-center gap-2 text-gray-400 sm:mb-1">
            <Filter className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium text-gray-700 sm:hidden">{t('fields.filter')}</span>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:flex lg:flex-wrap lg:items-end">
            <div className="min-w-0">
              <LabelWithTooltip
                label={t('dimensionsPage.productType')}
                tooltip={t('dimensionsPage.tooltips.productType')}
                required={false}
              />
              <select
                value={selectedProductType}
                onChange={(e) => setSelectedProductType(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
              >
                <option value="">{t('fields.all')}</option>
                {productTypes.map((type) => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>
            <div className="min-w-0">
              <LabelWithTooltip
                label={t('dimensionsPage.dimensionType')}
                tooltip={t('dimensionsPage.tooltips.dimensionType')}
                required={false}
              />
              <select
                value={selectedDimensionType}
                onChange={(e) => setSelectedDimensionType(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
              >
                <option value="">{t('fields.all')}</option>
                {dimensionTypes.map((type) => (
                  <option key={type.name} value={type.name}>{getDimensionTypeDisplayName(type.name)}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleFilter}
              disabled={filtering || loading}
              className="flex w-full items-center justify-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 sm:w-auto"
            >
              <RefreshCw className={`w-4 h-4 ${filtering ? 'animate-spin' : ''}`} />
              {filtering ? t('fields.filtering') : t('fields.filter')}
            </button>
          </div>
        </div>
      </div>

      <div className={`bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden min-w-0 ${filtering || listBusy ? 'opacity-70 pointer-events-none' : ''}`}>
        <div className="overflow-x-auto">
          <table className="w-max min-w-full text-left">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">{t('dimensionsPage.productType')}</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">{t('dimensionsPage.dimensionType')}</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[10rem]">{t('dimensionsPage.name')}</th>
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">{t('fields.status')}</th>
                {ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== appliedDimensionType).map((dimType) => (
                  <th key={dimType.key} className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                    {t('compat.compatibleWith', { label: t(`dimensionTypes.${dimType.key}`) })}
                  </th>
                ))}
                <th className="px-3 sm:px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">{t('fields.actions')}</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading && dimensions.length === 0 ? (
                <tr>
                  <td colSpan={tableColSpan} className="px-6 py-12 text-center">
                    <div className="w-6 h-6 border-2 border-forge-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                    <span className="text-gray-500 text-sm">{t('common.loading')}</span>
                  </td>
                </tr>
              ) : dimensions.length === 0 ? (
                <tr>
                  <td colSpan={tableColSpan} className="px-6 py-12 text-center text-gray-400 text-sm">
                    <p>{t('fields.noData')}</p>
                    <p className="mt-2 text-xs text-gray-400">{t('dimensionsPage.emptyStateHint')}</p>
                  </td>
                </tr>
              ) : (
                dimensions.map((dimension) => (
                  <tr
                    key={dimension.dimension_id}
                    className={`hover:bg-gray-50 ${dimension.enabled === false ? 'bg-gray-50 opacity-60' : ''}`}
                  >                    <td className="px-3 sm:px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-forge-100 text-forge-800">
                        {getProductTypeLabel(dimension.product_type)}
                      </span>
                    </td>
                    <td className="px-3 sm:px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        {getDimensionTypeDisplayName(dimension.dimension_type)}
                      </span>
                    </td>
                    <td className="px-3 sm:px-6 py-4 min-w-[10rem] max-w-xs">
                      <div
                        className="text-sm text-gray-900 break-words cursor-default"
                        title={t('dimensionsPage.idTooltip', { id: dimension.item_id })}
                      >
                        {getDimensionDisplayName(dimension, locale)}
                      </div>
                    </td>
                    <td className="px-3 sm:px-6 py-4 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => void handleToggleEnabled(dimension)}
                        disabled={togglingId === dimension.dimension_id}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors disabled:opacity-50 ${
                          dimension.enabled === false ? 'bg-gray-300' : 'bg-forge-600'
                        }`}
                        aria-label={dimension.enabled === false ? t('dimensionsPage.disabledTitle') : t('dimensionsPage.enabledTitle')}
                        title={dimension.enabled === false ? t('dimensionsPage.disabledTitle') : t('dimensionsPage.enabledTitle')}
                      >
                        {togglingId === dimension.dimension_id ? (
                          <span className="absolute inset-0 flex items-center justify-center">
                            <RefreshCw className="w-3 h-3 text-white animate-spin" />
                          </span>
                        ) : (
                          <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                              dimension.enabled === false ? 'translate-x-1' : 'translate-x-6'
                            }`}
                          />
                        )}
                      </button>
                    </td>
                    {ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== appliedDimensionType).map((dimType) => {
                      const entry = getCompatEntry(dimension.compatibilities, dimType.key);
                      const isSelf = dimension.dimension_type === dimType.key;
                      const label = compatTableLabel(entry, t);
                      return (
                        <td key={dimType.key} className="px-3 sm:px-6 py-4 text-sm whitespace-nowrap">
                          {isSelf ? (
                            <span className="text-gray-300 text-xs">{t('compat.self')}</span>
                          ) : (
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                              entry.mode === 'unrestricted'
                                ? 'bg-gray-100 text-gray-600'
                                : entry.mode === 'allowlist' && entry.items.length === 0
                                  ? 'bg-red-50 text-red-600'
                                  : dimType.color
                            }`}>
                              {label}
                            </span>
                          )}
                        </td>
                      );
                    })}
                    <td className="px-3 sm:px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openModal(dimension)}
                          className="p-2 text-gray-500 hover:text-forge-600 hover:bg-forge-50 rounded-lg"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(dimension.dimension_id)}
                          disabled={deletingId === dimension.dimension_id}
                          className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50"
                        >
                          {deletingId === dimension.dimension_id ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {total > 0 && (
          <Pagination
            current={currentPage}
            total={total}
            pageSize={pageSize}
            disabled={listBusy || filtering || loading}
            onChange={(page) => loadDimensions(page, undefined, { keepRows: true })}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-4 sm:p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                {isEdit ? t('dimensionsPage.editDimension') : t('dimensionsPage.addDimension')}
              </h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-gray-400 hover:text-gray-600"
                aria-label={t('common.close')}
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              {!isEdit && productTypes.length === 0 ? (
                <div className="rounded-lg border border-dashed border-amber-200 bg-amber-50 px-4 py-5 text-center">
                  <p className="text-sm font-medium text-gray-900">{t('dimensionsPage.noProductTypesTitle')}</p>
                  <p className="mt-2 text-xs text-gray-600 leading-relaxed">{t('dimensionsPage.noProductTypesBody')}</p>
                  <button
                    type="button"
                    onClick={() => {
                      setShowModal(false);
                      navigate('/products');
                    }}
                    className="mt-4 inline-flex items-center justify-center rounded-lg bg-forge-600 px-4 py-2 text-sm font-medium text-white hover:bg-forge-700 transition-colors"
                  >
                    {t('dimensionsPage.goToProducts')}
                  </button>
                </div>
              ) : (
              <div className="space-y-4">
                <div>
                  <LabelWithTooltip
                    htmlFor="dimension-product-type"
                    label={t('dimensionsPage.productType')}
                    tooltip={t('dimensionsPage.tooltips.productType')}
                    required
                  />
                  <select
                    id="dimension-product-type"
                    value={formData.product_type}
                    onChange={(e) => {
                      const pt = e.target.value;
                      setFormData({ ...formData, product_type: pt });
                      setAllDimensions(getCachedOptions(pt) || {});
                      // 新建时若已展开过选项，换产品类型再按需加载
                      if (Object.values(expandedDimensions).some(Boolean)) {
                        void ensureCompatOptions(pt);
                      }
                    }}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    required
                    disabled={isEdit}
                  >
                    {productTypes.map((type) => (
                      <option key={type.value} value={type.value}>{type.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <LabelWithTooltip
                    htmlFor="dimension-type"
                    label={t('dimensionsPage.dimensionType')}
                    tooltip={t('dimensionsPage.tooltips.dimensionType')}
                    required
                  />
                  <select
                    id="dimension-type"
                    value={formData.dimension_type}
                    onChange={(e) => setFormData({ ...formData, dimension_type: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    required
                    disabled={isEdit}
                  >
                    {dimensionTypes.map((type) => (
                      <option key={type.name} value={type.name}>{getDimensionTypeDisplayName(type.name)}</option>
                    ))}
                  </select>
                  {formData.dimension_type && getDimensionTypeDescription(formData.dimension_type) && (
                    <p className="mt-1 text-xs text-gray-500">
                      {getDimensionTypeDescription(formData.dimension_type)}
                    </p>
                  )}
                </div>
                <div>
                  <LabelWithTooltip
                    htmlFor="dimension-name"
                    label={t('dimensionsPage.name')}
                    tooltip={t('dimensionsPage.tooltips.name')}
                    required
                  />
                  <input
                    id="dimension-name"
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    required
                    maxLength={LIMITS.dimensionName}
                    placeholder={t('placeholders.dimensions.name')}
                  />
                  <p className="mt-1 text-xs text-gray-400 text-right">
                    {t('common.charCount', { current: (formData.name || '').length, max: LIMITS.dimensionName })}
                  </p>
                </div>
                {isEdit && (
                  <>
                    {modalOptionsLoading && (
                      <div className="text-sm text-gray-500 flex items-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        {t('dimensionsPage.loadCompat')}
                      </div>
                    )}
                    {getCompatibleDimensionTypes(formData.dimension_type).map((dimType) => {
                  const entry = getCompatEntry(formData.compatibilities, dimType.key);
                  const allItems = allDimensions[dimType.key]?.map(item => item.id) || [];
                  const current = selectedIdsForUi(entry, allItems);
                  const isAllSelected =
                    entry.mode === 'unrestricted' ||
                    (allItems.length > 0 && allItems.every(id => current.includes(id)));
                  const isExpanded = expandedDimensions[dimType.key] || false;
                  const statusText = compatLabel(entry, t);
                  
                  return (
                    <div key={dimType.key} className="border border-gray-200 rounded-lg overflow-hidden">
                      <button
                        type="button"
                        onClick={() => toggleDimension(dimType.key)}
                        className="w-full px-4 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-left transition-colors"
                      >
                        <span className="font-medium text-gray-700">
                          {t('compat.compatibleWith', { label: t(`dimensionTypes.${dimType.key}`) })}
                          <span className="ml-2 text-xs font-normal text-forge-600">{statusText}</span>
                        </span>
                        <span className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isAllSelected}
                            onChange={() => void toggleSelectAll(dimType.key)}
                            onClick={(e) => e.stopPropagation()}
                            className="w-4 h-4 text-forge-600 rounded border-gray-300 focus:ring-forge-500"
                          />
                          <span className="text-xs text-gray-500">{t('dimensionsPage.selectAll')}</span>
                          <svg
                            className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </span>
                      </button>
                      
                      {isExpanded && (
                        <div className="p-4 bg-white">
                          <div className="flex flex-wrap gap-2">
                            {allDimensions[dimType.key]?.map((item) => {
                              const isChecked = current.includes(item.id);
                              return (
                                <label
                                  key={item.id}
                                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg cursor-pointer transition-all duration-200 ${
                                    isChecked
                                      ? 'bg-forge-600 text-white shadow-md border-2 border-forge-800'
                                      : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200 hover:border-gray-300'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={(e) => {
                                      let nextIds: string[];
                                      if (e.target.checked) {
                                        nextIds = [...current, item.id];
                                      } else {
                                        // 从「全部兼容」取消某一项 → 变为除该项外的白名单
                                        nextIds = current.filter(id => id !== item.id);
                                      }
                                      const nextEntry: DimensionCompatEntry =
                                        allItems.length > 0 && allItems.every(id => nextIds.includes(id))
                                          ? emptyCompatEntry('unrestricted')
                                          : { mode: 'allowlist', items: nextIds };
                                      setFormData({
                                        ...formData,
                                        compatibilities: {
                                          ...(formData.compatibilities || {}),
                                          [dimType.key]: nextEntry,
                                        },
                                      });
                                    }}
                                    className="w-4 h-4 text-forge-600 rounded border-gray-300 focus:ring-forge-500"
                                  />
                                  <span className="text-xs">{getDimensionDisplayName(item, locale)}</span>
                                </label>
                              );
                            })}
                            {modalOptionsLoading && (!allDimensions[dimType.key] || allDimensions[dimType.key].length === 0) && (
                              <span className="text-sm text-gray-400">{t('dimensionsPage.loadingCompat')}</span>
                            )}
                            {!modalOptionsLoading && (!allDimensions[dimType.key] || allDimensions[dimType.key].length === 0) && (
                              <span className="text-sm text-gray-400">{t('fields.noData')}</span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                    })}
                  </>
                )}
              </div>
              )}

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  disabled={saving}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {t('common.cancel')}
                </button>
                {!( !isEdit && productTypes.length === 0) && (
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50"
                >
                  {saving ? t('common.saving') : isEdit ? t('common.save') : t('dimensionsPage.addDimension')}
                </button>
                )}
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}