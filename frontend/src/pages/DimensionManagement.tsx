import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X, RefreshCw, Database, Filter } from 'lucide-react';
import type { PromptDimension, PromptDimensionCreate, PromptDimensionUpdate, DimensionType, ProductType, PaginatedResponse, DimensionCompatibilities } from '@/api/dimensions';
import { getDimensionTypes, getPromptDimensions, createPromptDimension, updatePromptDimension, deletePromptDimension, initializeDimensions, getProductTypes, ALL_DIMENSION_TYPES } from '@/api/dimensions';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import {
  LIMITS,
  alertValidationErrors,
  itemIdFormat,
  maxLen,
  required,
} from '@/lib/formValidation';
import Pagination from '@/components/Pagination';

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
      const res = await getPromptDimensions(productType, undefined, page, 100);
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

/**
 * 编辑兼容关系后，按双向边本地修正当前页其他行的计数，避免整表重新筛选请求。
 */
function syncReverseCompatInList(
  rows: PromptDimension[],
  edited: PromptDimension,
  prevCompat: DimensionCompatibilities | undefined,
  nextCompat: DimensionCompatibilities | undefined
): PromptDimension[] {
  return rows.map((row) => {
    if (row.dimension_id === edited.dimension_id) {
      return { ...row, ...edited };
    }

    const targetType = row.dimension_type as keyof DimensionCompatibilities;
    const sourceType = edited.dimension_type as keyof DimensionCompatibilities;
    const oldTargets = new Set(prevCompat?.[targetType] || []);
    const newTargets = new Set(nextCompat?.[targetType] || []);
    const wasLinked = oldTargets.has(row.item_id);
    const isLinked = newTargets.has(row.item_id);
    if (wasLinked === isLinked) return row;

    const compat: DimensionCompatibilities = { ...(row.compatibilities || {}) };
    const reverseList = [...(compat[sourceType] || [])];
    if (isLinked && !reverseList.includes(edited.item_id)) {
      reverseList.push(edited.item_id);
    } else if (!isLinked) {
      const idx = reverseList.indexOf(edited.item_id);
      if (idx >= 0) reverseList.splice(idx, 1);
    }
    compat[sourceType] = reverseList;
    return { ...row, compatibilities: compat };
  });
}

export default function DimensionManagement() {
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
  const [saving, setSaving] = useState(false);
  const [modalOptionsLoading, setModalOptionsLoading] = useState(false);
  const [selectedDimension, setSelectedDimension] = useState<PromptDimension | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const createEmptyCompatibilities = (excludeType?: string): DimensionCompatibilities => {
    const result: DimensionCompatibilities = {};
    for (const dimType of ALL_DIMENSION_TYPES) {
      if (dimType.key !== excludeType) {
        result[dimType.key] = [];
      }
    }
    return result;
  };

  const [formData, setFormData] = useState<PromptDimensionCreate>({
    product_type: 'night_lights',
    dimension_type: 'scenes',
    item_id: '',
    name: '',
    compatibilities: createEmptyCompatibilities('scenes'),
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
    const current = ((formData.compatibilities || {})[dimType as keyof DimensionCompatibilities] || []);
    const allItems = opts[dimType]?.map(item => item.id) || [];
    const isAllSelected = allItems.length > 0 && allItems.every(id => current.includes(id));
    
    setFormData(prev => ({
      ...prev,
      compatibilities: {
        ...(prev.compatibilities || {}),
        [dimType]: isAllSelected ? [] : allItems
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
    opts?: { silent?: boolean; keepRows?: boolean }
  ) => {
    const userFilter = Boolean(opts?.keepRows);
    const silent = Boolean(opts?.silent);
    if (!silent && !userFilter) setLoading(true);
    if (userFilter) setFiltering(true);
    const size = newPageSize ?? pageSize;
    try {
      const response: PaginatedResponse<PromptDimension> = await getPromptDimensions(
        selectedProductType || undefined, 
        selectedDimensionType || undefined,
        page,
        size
      );
      setDimensions(response.data);
      setTotal(response.pagination.total);
      setCurrentPage(response.pagination.current);
      setAppliedProductType(selectedProductType);
      setAppliedDimensionType(selectedDimensionType);
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
      if (!silent && !userFilter) setLoading(false);
      if (userFilter) setFiltering(false);
    }
  };

  const handleFilter = () => {
    // 保留当前表格内容，只在筛选按钮上转圈，避免“全部重置”的闪烁
    void loadDimensions(1, undefined, { keepRows: true });
  };

  const handlePageSizeChange = (newPageSize: number) => {
    loadDimensions(1, newPageSize, { keepRows: true });
  };

  const matchesCurrentFilters = (dim: PromptDimension) => {
    if (appliedProductType && dim.product_type !== appliedProductType) return false;
    if (appliedDimensionType && dim.dimension_type !== appliedDimensionType) return false;
    return true;
  };

  const resetForm = () => {
    setFormData({
      product_type: 'night_lights',
      dimension_type: 'scenes',
      item_id: '',
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
        required('产品类型', formData.product_type),
        maxLen('产品类型', formData.product_type, LIMITS.productType),
        required('维度类型', formData.dimension_type),
        isEdit ? null : itemIdFormat(formData.item_id),
        required('名称', formData.name),
        maxLen('名称', formData.name, LIMITS.dimensionName),
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
        const prevCompat = selectedDimension.compatibilities;
        const updated = await updatePromptDimension(selectedDimension.dimension_id, updatePayload);
        // 本地更新列表 + 就地改缓存名称；不清空兼容选项缓存
        upsertCompatCacheItem(updated);
        setDimensions((prev) =>
          syncReverseCompatInList(prev, updated, prevCompat, updated.compatibilities)
        );
      } else {
        const created = await createPromptDimension(submitData);
        upsertCompatCacheItem(created);
        if (matchesCurrentFilters(created) && currentPage === 1) {
          setDimensions((prev) => [created, ...prev].slice(0, pageSize));
        }
        setTotal((t) => t + 1);
        void loadProductTypes();
      }
      setShowModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to save dimension:', error);
      alert('保存失败，请检查输入');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (dimensionId: string) => {
    if (confirm('确定删除该维度吗？')) {
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
      }
    }
  };

  const handleToggleEnabled = async (dimension: PromptDimension) => {
    const nextEnabled = dimension.enabled === false;
    try {
      const updated = await updatePromptDimension(dimension.dimension_id, { enabled: nextEnabled });
      upsertCompatCacheItem(updated);
      setDimensions((prev) =>
        prev.map((d) => (d.dimension_id === updated.dimension_id ? { ...d, ...updated } : d))
      );
    } catch (error) {
      console.error('Failed to toggle dimension enabled:', error);
      alert(nextEnabled ? '启用失败，请重试' : '禁用失败，请重试');
    }
  };

  const handleInitialize = async () => {
    if (confirm('确定初始化默认维度数据吗？这将覆盖现有数据。')) {
      try {
        await initializeDimensions();
        invalidateCompatCache();
        invalidateCache('productTypes');
        invalidateCache('dimensionTypes');
        await Promise.all([loadProductTypes(), loadDimensions(1)]);
        alert('初始化成功');
      } catch (error) {
        console.error('Failed to initialize dimensions:', error);
      }
    }
  };

  const openModal = (dimension?: PromptDimension) => {
    setExpandedDimensions({});
    setModalOptionsLoading(false);

    const pt = dimension?.product_type || selectedProductType || 'night_lights';
    const cached = getCachedOptions(pt);
    setAllDimensions(cached || {});

    if (dimension) {
      setIsEdit(true);
      setSelectedDimension(dimension);
      setFormData({
        product_type: dimension.product_type,
        dimension_type: dimension.dimension_type,
        item_id: dimension.item_id,
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
        item_id: '',
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
    const found = dimensionTypes.find(t => t.name === typeName);
    return found?.display_name || typeName;
  };

  const getProductTypeLabel = (value: string) => {
    const found = productTypes.find(t => t.value === value);
    return found?.label || value;
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">提示词维度管理</h2>
          <p className="text-gray-500 mt-1">管理AI图像生成的提示词维度配置</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleInitialize}
            className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors"
          >
            <Database className="w-4 h-4" />
            初始化数据
          </button>
          <button
            onClick={() => openModal()}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            添加维度
          </button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 mb-6">
        <div className="flex items-center gap-4">
          <Filter className="w-5 h-5 text-gray-400" />
          <div className="flex items-center gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">产品类型</label>
              <select
                value={selectedProductType}
                onChange={(e) => setSelectedProductType(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">全部</option>
                {productTypes.map((type) => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">维度类型</label>
              <select
                value={selectedDimensionType}
                onChange={(e) => setSelectedDimensionType(e.target.value)}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
              >
                <option value="">全部</option>
                {dimensionTypes.map((type) => (
                  <option key={type.name} value={type.name}>{type.display_name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleFilter}
              disabled={filtering || loading}
              className="mt-6 flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${filtering ? 'animate-spin' : ''}`} />
              {filtering ? '筛选中…' : '筛选'}
            </button>
          </div>
        </div>
      </div>

      <div className={`bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden ${filtering ? 'opacity-70 pointer-events-none' : ''}`}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">产品类型</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">维度类型</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">名称</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">状态</th>
                {ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== appliedDimensionType).map((dimType) => (
                  <th key={dimType.key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    兼容{dimType.label}
                  </th>
                ))}
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading && dimensions.length === 0 ? (
                <tr>
                  <td colSpan={appliedDimensionType ? 12 : 13} className="px-6 py-12 text-center">
                    <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                    <span className="text-gray-500 text-sm">加载中...</span>
                  </td>
                </tr>
              ) : dimensions.length === 0 ? (
                <tr>
                  <td colSpan={appliedDimensionType ? 12 : 13} className="px-6 py-12 text-center text-gray-400 text-sm">
                    暂无数据
                  </td>
                </tr>
              ) : (
                dimensions.map((dimension) => (
                  <tr
                    key={dimension.dimension_id}
                    className={`hover:bg-gray-50 ${dimension.enabled === false ? 'bg-gray-50 opacity-60' : ''}`}
                  >                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 text-indigo-800">
                        {getProductTypeLabel(dimension.product_type)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                        {getDimensionTypeDisplayName(dimension.dimension_type)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600 font-mono">
                      {dimension.item_id}
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-sm text-gray-900">{dimension.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => void handleToggleEnabled(dimension)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          dimension.enabled === false ? 'bg-gray-300' : 'bg-indigo-600'
                        }`}
                        title={dimension.enabled === false ? '已禁用（点击启用）' : '已启用（点击禁用）'}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            dimension.enabled === false ? 'translate-x-1' : 'translate-x-6'
                          }`}
                        />
                      </button>
                      <span className={`ml-2 text-xs ${dimension.enabled === false ? 'text-red-500' : 'text-gray-500'}`}>
                        {dimension.enabled === false ? '已禁用' : '启用中'}
                      </span>
                    </td>
                    {ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== appliedDimensionType).map((dimType) => {
                      const compatList = dimension.compatibilities?.[dimType.key as keyof DimensionCompatibilities];
                      const isSelf = dimension.dimension_type === dimType.key;
                      const count = compatList?.length || 0;
                      return (
                        <td key={dimType.key} className="px-6 py-4 text-sm">
                          {isSelf ? (
                            <span className="text-gray-300 text-xs">-</span>
                          ) : count > 0 ? (
                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${dimType.color}`}>
                              {count}项
                            </span>
                          ) : '-'}
                        </td>
                      );
                    })}
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openModal(dimension)}
                          className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(dimension.dimension_id)}
                          className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                        >
                          <Trash2 className="w-4 h-4" />
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
            onChange={(page) => loadDimensions(page, undefined, { keepRows: true })}
            onPageSizeChange={handlePageSizeChange}
          />
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                {isEdit ? '编辑维度' : '添加维度'}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">产品类型</label>
                  <select
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
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                    disabled={isEdit}
                  >
                    {productTypes.map((type) => (
                      <option key={type.value} value={type.value}>{type.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">维度类型</label>
                  <select
                    value={formData.dimension_type}
                    onChange={(e) => setFormData({ ...formData, dimension_type: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                    disabled={isEdit}
                  >
                    {dimensionTypes.map((type) => (
                      <option key={type.name} value={type.name}>{type.display_name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">维度项ID</label>
                  <input
                    type="text"
                    value={formData.item_id}
                    onChange={(e) => setFormData({ ...formData, item_id: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                    disabled={isEdit}
                    maxLength={LIMITS.dimensionItemId}
                    placeholder="如 nursery"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                    maxLength={LIMITS.dimensionName}
                    placeholder="如 温馨婴儿房角落配有木质婴儿床"
                  />
                  <p className="mt-1 text-xs text-gray-400 text-right">
                    {(formData.name || '').length}/{LIMITS.dimensionName}
                  </p>
                </div>
                {isEdit && (
                  <>
                    {modalOptionsLoading && (
                      <div className="text-sm text-gray-500 flex items-center gap-2">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        加载兼容选项…
                      </div>
                    )}
                    {getCompatibleDimensionTypes(formData.dimension_type).map((dimType) => {
                  const current = ((formData.compatibilities || {})[dimType.key as keyof DimensionCompatibilities] || []);
                  const allItems = allDimensions[dimType.key]?.map(item => item.id) || [];
                  const isAllSelected = allItems.length > 0 && allItems.every(id => current.includes(id));
                  const isExpanded = expandedDimensions[dimType.key] || false;
                  const selectedCount = current.length;
                  
                  return (
                    <div key={dimType.key} className="border border-gray-200 rounded-lg overflow-hidden">
                      <button
                        type="button"
                        onClick={() => toggleDimension(dimType.key)}
                        className="w-full px-4 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-left transition-colors"
                      >
                        <span className="font-medium text-gray-700">
                          兼容{dimType.label}
                          {selectedCount > 0 && (
                            <span className="ml-2 text-xs font-normal text-indigo-600">已选 {selectedCount}</span>
                          )}
                        </span>
                        <span className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isAllSelected}
                            onChange={() => void toggleSelectAll(dimType.key)}
                            onClick={(e) => e.stopPropagation()}
                            className="w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                          />
                          <span className="text-xs text-gray-500">全选</span>
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
                                      ? 'bg-indigo-600 text-white shadow-md border-2 border-indigo-800'
                                      : 'bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200 hover:border-gray-300'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={(e) => {
                                      const newList = e.target.checked
                                        ? [...current, item.id]
                                        : current.filter(id => id !== item.id);
                                      setFormData({
                                        ...formData,
                                        compatibilities: { ...(formData.compatibilities || {}), [dimType.key]: newList },
                                      });
                                    }}
                                    className="w-4 h-4 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                                  />
                                  <span className="text-xs">{item.name}</span>
                                </label>
                              );
                            })}
                            {modalOptionsLoading && (!allDimensions[dimType.key] || allDimensions[dimType.key].length === 0) && (
                              <span className="text-sm text-gray-400">加载中…</span>
                            )}
                            {!modalOptionsLoading && (!allDimensions[dimType.key] || allDimensions[dimType.key].length === 0) && (
                              <span className="text-sm text-gray-400">暂无数据</span>
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

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  disabled={saving}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                >
                  {saving ? '保存中…' : isEdit ? '保存修改' : '添加维度'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}