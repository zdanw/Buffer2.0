import { useState, useEffect, useRef } from 'react';
import { Plus, Edit2, Trash2, X, RefreshCw, Database, Filter } from 'lucide-react';
import type { PromptDimension, PromptDimensionCreate, PromptDimensionUpdate, DimensionType, ProductType, PaginatedResponse, DimensionCompatibilities } from '@/api/dimensions';
import { getDimensionTypes, getPromptDimensions, createPromptDimension, updatePromptDimension, deletePromptDimension, initializeDimensions, getProductTypes, getDimensionsByType, ALL_DIMENSION_TYPES } from '@/api/dimensions';
import Pagination from '@/components/Pagination';

type CompatOptions = Record<string, { id: string; name: string }[]>;

export default function DimensionManagement() {
  const [dimensions, setDimensions] = useState<PromptDimension[]>([]);
  const [dimensionTypes, setDimensionTypes] = useState<DimensionType[]>([]);
  const [productTypes, setProductTypes] = useState<ProductType[]>([]);
  const [selectedProductType, setSelectedProductType] = useState<string>('');
  const [selectedDimensionType, setSelectedDimensionType] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [loading, setLoading] = useState(false);
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
  /** 按产品类型缓存兼容选项，避免每次点编辑都打 7 个接口 */
  const compatCacheRef = useRef<Record<string, CompatOptions>>({});

  const loadAllDimensions = async (productType: string, force = false) => {
    if (!force && compatCacheRef.current[productType]) {
      setAllDimensions(compatCacheRef.current[productType]);
      return;
    }
    setModalOptionsLoading(true);
    try {
      const entries = await Promise.all(
        ALL_DIMENSION_TYPES.map(async (dimType) => {
          try {
            const data = await getDimensionsByType(productType, dimType.key);
            return [dimType.key, data] as const;
          } catch {
            return [dimType.key, []] as const;
          }
        })
      );
      const result = Object.fromEntries(entries) as CompatOptions;
      compatCacheRef.current[productType] = result;
      setAllDimensions(result);
    } finally {
      setModalOptionsLoading(false);
    }
  };

  const invalidateCompatCache = (productType?: string) => {
    if (productType) {
      delete compatCacheRef.current[productType];
    } else {
      compatCacheRef.current = {};
    }
  };

  const getCompatibleDimensionTypes = (currentType: string) => {
    return ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== currentType);
  };

  const [expandedDimensions, setExpandedDimensions] = useState<Record<string, boolean>>({});

  const toggleDimension = (dimType: string) => {
    setExpandedDimensions(prev => ({
      ...prev,
      [dimType]: !prev[dimType]
    }));
  };

  const toggleSelectAll = (dimType: string) => {
    const current = ((formData.compatibilities || {})[dimType as keyof DimensionCompatibilities] || []);
    const allItems = allDimensions[dimType]?.map(item => item.id) || [];
    const isAllSelected = allItems.length > 0 && allItems.every(id => current.includes(id));
    
    setFormData({
      ...formData,
      compatibilities: {
        ...(formData.compatibilities || {}),
        [dimType]: isAllSelected ? [] : allItems
      }
    });
  };

  useEffect(() => {
    loadDimensionTypes();
    loadProductTypes();
    loadDimensions(1);
  }, []);

  const loadDimensionTypes = async () => {
    try {
      const data = await getDimensionTypes();
      setDimensionTypes(data);
    } catch (error) {
      console.error('Failed to load dimension types:', error);
    }
  };

  const loadProductTypes = async () => {
    try {
      const data = await getProductTypes();
      setProductTypes(data);
    } catch (error) {
      console.error('Failed to load product types:', error);
    }
  };

  const loadDimensions = async (page: number = currentPage, newPageSize?: number, opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
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
      if (newPageSize) {
        setPageSize(newPageSize);
      }
    } catch (error) {
      console.error('Failed to load dimensions:', error);
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    loadDimensions(1, newPageSize);
  };

  const matchesCurrentFilters = (dim: PromptDimension) => {
    if (selectedProductType && dim.product_type !== selectedProductType) return false;
    if (selectedDimensionType && dim.dimension_type !== selectedDimensionType) return false;
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
    setSaving(true);
    try {
      const submitData = { ...formData };

      if (isEdit && selectedDimension) {
        const updatePayload: PromptDimensionUpdate = {
          name: submitData.name,
          compatibilities: submitData.compatibilities,
        };
        const updated = await updatePromptDimension(selectedDimension.dimension_id, updatePayload);
        setDimensions((prev) =>
          prev.map((d) => (d.dimension_id === updated.dimension_id ? { ...d, ...updated } : d))
        );
        // 兼容关系双向变更可能影响同页其他行计数，后台静默刷新当前页
        void loadDimensions(currentPage, undefined, { silent: true });
      } else {
        const created = await createPromptDimension(submitData);
        invalidateCompatCache(created.product_type);
        if (matchesCurrentFilters(created) && currentPage === 1) {
          setDimensions((prev) => [created, ...prev].slice(0, pageSize));
          setTotal((t) => t + 1);
        } else if (matchesCurrentFilters(created)) {
          setTotal((t) => t + 1);
          void loadDimensions(currentPage, undefined, { silent: true });
        } else {
          setTotal((t) => t + 1);
        }
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
        if (removed) invalidateCompatCache(removed.product_type);
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

  const handleInitialize = async () => {
    if (confirm('确定初始化默认维度数据吗？这将覆盖现有数据。')) {
      try {
        await initializeDimensions();
        invalidateCompatCache();
        await Promise.all([loadProductTypes(), loadDimensions(1)]);
        alert('初始化成功');
      } catch (error) {
        console.error('Failed to initialize dimensions:', error);
      }
    }
  };

  const openModal = (dimension?: PromptDimension) => {
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
      void loadAllDimensions(dimension.product_type);
    } else {
      setIsEdit(false);
      setSelectedDimension(null);
      const pt = selectedProductType || 'night_lights';
      const dt = selectedDimensionType || 'scenes';
      setFormData({
        product_type: pt,
        dimension_type: dt,
        item_id: '',
        name: '',
        compatibilities: createEmptyCompatibilities(dt),
      });
      void loadAllDimensions(pt);
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
              onClick={() => loadDimensions(1)}
              disabled={loading}
              className="mt-6 flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              筛选
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">产品类型</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">维度类型</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">名称</th>
                {ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== selectedDimensionType).map((dimType) => (
                  <th key={dimType.key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    兼容{dimType.label}
                  </th>
                ))}
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">操作</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {loading ? (
                <tr>
                  <td colSpan={selectedDimensionType ? 11 : 12} className="px-6 py-12 text-center">
                    <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
                    <span className="text-gray-500 text-sm">加载中...</span>
                  </td>
                </tr>
              ) : dimensions.length === 0 ? (
                <tr>
                  <td colSpan={selectedDimensionType ? 11 : 12} className="px-6 py-12 text-center text-gray-400 text-sm">
                    暂无数据
                  </td>
                </tr>
              ) : (
                dimensions.map((dimension) => (
                  <tr key={dimension.dimension_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
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
                    {ALL_DIMENSION_TYPES.filter(dimType => dimType.key !== selectedDimensionType).map((dimType) => {
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
            onChange={loadDimensions}
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
                      void loadAllDimensions(pt);
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
                    placeholder="如 温馨婴儿房角落配有木质婴儿床"
                  />
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
                  
                  return (
                    <div key={dimType.key} className="border border-gray-200 rounded-lg overflow-hidden">
                      <button
                        type="button"
                        onClick={() => toggleDimension(dimType.key)}
                        className="w-full px-4 py-2 bg-gray-50 hover:bg-gray-100 flex items-center justify-between text-left transition-colors"
                      >
                        <span className="font-medium text-gray-700">兼容{dimType.label}</span>
                        <span className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={isAllSelected}
                            onChange={() => toggleSelectAll(dimType.key)}
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
                            {!allDimensions[dimType.key] || allDimensions[dimType.key].length === 0 && (
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