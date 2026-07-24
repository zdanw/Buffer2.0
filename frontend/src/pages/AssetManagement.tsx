import { useState, useEffect } from 'react';
import { Plus, Upload, Trash2, Eye, Edit2, X, RefreshCw, Palette, Package, FolderOpen, FileText, Sparkles, Megaphone } from 'lucide-react';
import type { Product, ProductCreate, PaginatedResponse } from '@/api/products';
import { getProducts, getProduct, createProduct, updateProduct, deleteProduct, uploadProductImages, deleteProductImage } from '@/api/products';
import type { DimensionType } from '@/api/dimensions';
import { getDimensionTypes } from '@/api/dimensions';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import {
  LIMITS,
  alertValidationErrors,
  maxLen,
  required,
} from '@/lib/formValidation';
import Pagination from '@/components/Pagination';

export default function AssetManagement() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [loading, setLoading] = useState(false);
  const [listBusy, setListBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [uploadingType, setUploadingType] = useState<'product' | 'scene' | null>(null);
  const [deletingImageId, setDeletingImageId] = useState<string | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [dimensionTypes, setDimensionTypes] = useState<DimensionType[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [formData, setFormData] = useState<ProductCreate>({
    product_name: '',
    category: '',
    description: '',
    selling_points: [],
    brand_voice: '',
  });

  useEffect(() => {
    void Promise.all([loadProducts(1), loadDimensionTypes()]);
  }, []);

  const loadDimensionTypes = async () => {
    try {
      const data = await cachedFetch('dimensionTypes', () => getDimensionTypes());
      setDimensionTypes(data);
    } catch (error) {
      console.error('Failed to load dimension types:', error);
    }
  };

  const loadProducts = async (
    page: number = currentPage,
    newPageSize?: number,
    opts?: { silent?: boolean; keepRows?: boolean }
  ) => {
    const keepRows = Boolean(opts?.keepRows || opts?.silent);
    if (!opts?.silent && !keepRows) setLoading(true);
    if (keepRows && !opts?.silent) setListBusy(true);
    const size = newPageSize ?? pageSize;
    try {
      const response: PaginatedResponse<Product> = await getProducts(page, size);
      setProducts(response.data);
      setTotal(response.pagination.total);
      setCurrentPage(response.pagination.current);
      if (newPageSize) {
        setPageSize(newPageSize);
      }
    } catch (error) {
      console.error('Failed to load products:', error);
    } finally {
      if (!opts?.silent && !keepRows) setLoading(false);
      if (keepRows && !opts?.silent) setListBusy(false);
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    void loadProducts(1, newPageSize, { keepRows: true });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const sellingJoined = (formData.selling_points || []).filter(Boolean).join(',');
    if (
      alertValidationErrors([
        required('产品名称', formData.product_name),
        maxLen('产品名称', formData.product_name, LIMITS.productName),
        required('分类', formData.category),
        maxLen('分类', formData.category, LIMITS.category),
        maxLen('描述', formData.description, LIMITS.description),
        maxLen('卖点', sellingJoined, LIMITS.sellingPointsJoined),
        maxLen('品牌调性', formData.brand_voice, LIMITS.brandVoice),
      ])
    ) {
      return;
    }
    setSaving(true);
    try {
      if (isEdit && selectedProduct) {
        const updated = await updateProduct(selectedProduct.product_id, formData);
        setSelectedProduct(updated);
        setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
        invalidateCache('products');
        invalidateCache('categories');
      } else {
        const created = await createProduct(formData);
        invalidateCache('products');
        invalidateCache('categories');
        if (currentPage === 1) {
          setProducts(prev => [created, ...prev].slice(0, pageSize));
          setTotal(t => t + 1);
        } else {
          setTotal(t => t + 1);
        }
      }
      setShowModal(false);
      setFormData({ product_name: '', category: '', description: '', selling_points: [], brand_voice: '' });
    } catch (error) {
      console.error('Failed to save product:', error);
      alert('保存失败，请检查输入后重试');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (productId: string) => {
    if (confirm('确定删除该产品及其所有图片吗？')) {
      setDeleting(true);
      try {
        await deleteProduct(productId);
        invalidateCache('products');
        invalidateCache('categories');
        if (selectedProduct?.product_id === productId) {
          setSelectedProduct(null);
        }
        setProducts(prev => prev.filter(p => p.product_id !== productId));
        setTotal(t => Math.max(0, t - 1));
      } catch (error) {
        console.error('Failed to delete product:', error);
      } finally {
        setDeleting(false);
      }
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>, imageType: 'product' | 'scene') => {
    if (!e.target.files || !selectedProduct || uploadingType) return;
    const files = Array.from(e.target.files);
    e.target.value = '';
    setUploadingType(imageType);
    try {
      const response = await uploadProductImages(selectedProduct.product_id, files, imageType);
      if (response.failed && response.failed.length > 0) {
        alert(`${response.uploaded.length} 张图片上传成功，${response.failed.length} 张失败: ${response.failed.join(', ')}`);
      }
    } catch (error) {
      console.error('Failed to upload images:', error);
      alert('图片上传失败，请重试');
    } finally {
      try {
        const updated = await getProduct(selectedProduct.product_id);
        setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
        setSelectedProduct(updated);
      } catch (error) {
        console.error('Failed to refresh product after upload:', error);
      }
      setUploadingType(null);
    }
  };

  const handleImageDelete = async (imageId: string) => {
    if (!selectedProduct || deletingImageId) return;
    if (confirm('确定删除该图片吗？')) {
      setDeletingImageId(imageId);
      try {
        await deleteProductImage(selectedProduct.product_id, imageId);
      } catch (error) {
        console.error('Failed to delete image:', error);
      } finally {
        try {
          const updated = await getProduct(selectedProduct.product_id);
          setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
          setSelectedProduct(updated);
        } catch (error) {
          console.error('Failed to refresh product after delete:', error);
        }
        setDeletingImageId(null);
      }
    }
  };

  const openModal = (product?: Product) => {
    if (product) {
      setIsEdit(true);
      setSelectedProduct(product);
      setFormData({
        product_name: product.product_name,
        category: product.category,
        description: product.description,
        selling_points: product.selling_points || [],
        brand_voice: product.brand_voice,
      });
    } else {
      setIsEdit(false);
      setSelectedProduct(null);
      setFormData({ product_name: '', category: '', description: '', selling_points: [], brand_voice: '' });
    }
    setShowModal(true);
  };

  return (
    <>
      <div className="p-6">
        <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">素材管理</h2>
          <p className="text-gray-500 mt-1">管理产品和图片素材</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => {
              invalidateCache('products');
              invalidateCache('dimensionTypes');
              void Promise.all([
                loadProducts(currentPage, undefined, { keepRows: true }),
                loadDimensionTypes(),
              ]);
            }}
            disabled={loading || listBusy}
            className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${loading || listBusy ? 'animate-spin' : ''}`} />
            刷新
          </button>
          <button
            onClick={() => openModal()}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            添加产品
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-800 mb-4">产品列表</h3>
            <div className={`space-y-2 ${listBusy ? 'opacity-70 pointer-events-none' : ''}`}>
              {loading && products.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin mb-3"></div>
                  <span className="text-gray-500 text-sm">服务正在启动中，请稍候...</span>
                </div>
              ) : products.length === 0 ? (
                <div className="text-center py-8 text-gray-400 text-sm">暂无产品</div>
              ) : (
                products.map((product) => (
                  <div
                    key={product.product_id}
                    onClick={() => setSelectedProduct(product)}
                    className={`p-3 rounded-lg cursor-pointer transition-all ${
                      selectedProduct?.product_id === product.product_id
                        ? 'bg-indigo-50 border border-indigo-200'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <h4 className="font-medium text-gray-800">{product.product_name}</h4>
                    <p className="text-sm text-gray-500">{product.category}</p>
                  </div>
                ))
              )}
            </div>
            {total > 0 && (
              <div className="mt-4">
                <Pagination
                  current={currentPage}
                  total={total}
                  pageSize={pageSize}
                  disabled={listBusy || loading}
                  onChange={(page) => void loadProducts(page, undefined, { keepRows: true })}
                  onPageSizeChange={handlePageSizeChange}
                />
              </div>
            )}
          </div>
        </div>

        <div className="col-span-2">
          {selectedProduct ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <h3 className="text-xl font-semibold text-gray-900">{selectedProduct.product_name}</h3>
                  <p className="text-gray-500 mt-1">{selectedProduct.category}</p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openModal(selectedProduct)}
                    className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg"
                  >
                    <Edit2 className="w-5 h-5" />
                  </button>
                  <button
                    onClick={() => handleDelete(selectedProduct.product_id)}
                    disabled={deleting}
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {deleting ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <Trash2 className="w-5 h-5" />
                    )}
                  </button>
                </div>
              </div>

              <div className="mb-6">
                <p className="text-gray-600">{selectedProduct.description}</p>
                {selectedProduct.brand_voice && (
                  <span className="inline-block mt-2 px-3 py-1 bg-indigo-100 text-indigo-700 rounded-full text-sm">
                    {selectedProduct.brand_voice}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="mb-3">
                    <label className={`flex items-center gap-2 text-sm font-medium text-gray-700 ${uploadingType ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}>
                      {uploadingType === 'product' ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                      <span>{uploadingType === 'product' ? '上传中…' : '上传产品图像'}</span>
                      <input
                        type="file"
                        multiple
                        accept="image/*"
                        disabled={!!uploadingType}
                        onChange={(e) => handleImageUpload(e, 'product')}
                        className="hidden"
                      />
                    </label>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-3">产品图像</h4>
                    <div className={`grid grid-cols-3 gap-3 ${uploadingType === 'product' ? 'opacity-70' : ''}`}>
                      {(Array.isArray(selectedProduct.product_images) ? selectedProduct.product_images : []).map((image) => (
                        <div key={image.image_id} className="relative group">
                          <img
                            src={image.cdn_url}
                            alt=""
                            className="w-full aspect-square object-cover rounded-lg"
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                            <button onClick={() => setPreviewImage(image.cdn_url)} className="p-2 bg-white rounded-full text-gray-800 hover:bg-gray-100">
                              <Eye className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleImageDelete(image.image_id)}
                              disabled={deletingImageId === image.image_id || !!uploadingType}
                              className="p-2 bg-white rounded-full text-red-600 hover:bg-red-100 disabled:opacity-50"
                            >
                              {deletingImageId === image.image_id ? (
                                <RefreshCw className="w-4 h-4 animate-spin" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="mb-3">
                    <label className={`flex items-center gap-2 text-sm font-medium text-gray-700 ${uploadingType ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}>
                      {uploadingType === 'scene' ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                      <span>{uploadingType === 'scene' ? '上传中…' : '上传场景图像'}</span>
                      <input
                        type="file"
                        multiple
                        accept="image/*"
                        disabled={!!uploadingType}
                        onChange={(e) => handleImageUpload(e, 'scene')}
                        className="hidden"
                      />
                    </label>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-3">场景图像</h4>
                    <div className={`grid grid-cols-3 gap-3 ${uploadingType === 'scene' ? 'opacity-70' : ''}`}>
                      {(Array.isArray(selectedProduct.scene_images) ? selectedProduct.scene_images : []).map((image) => (
                        <div key={image.image_id} className="relative group">
                          <img
                            src={image.cdn_url}
                            alt=""
                            className="w-full aspect-square object-cover rounded-lg"
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                            <button onClick={() => setPreviewImage(image.cdn_url)} className="p-2 bg-white rounded-full text-gray-800 hover:bg-gray-100">
                              <Eye className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleImageDelete(image.image_id)}
                              disabled={deletingImageId === image.image_id || !!uploadingType}
                              className="p-2 bg-white rounded-full text-red-600 hover:bg-red-100 disabled:opacity-50"
                            >
                              {deletingImageId === image.image_id ? (
                                <RefreshCw className="w-4 h-4 animate-spin" />
                              ) : (
                                <Trash2 className="w-4 h-4" />
                              )}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {Array.isArray(selectedProduct.dimensions) && selectedProduct.dimensions.length > 0 && (
                <div className="mt-6">
                  <h4 className="flex items-center gap-2 font-semibold text-gray-800 mb-3">
                    <Palette className="w-5 h-5" />
                    关联维度
                  </h4>
                  <div className="grid grid-cols-7 gap-4">
                    {dimensionTypes.map((dimType) => {
                      const dims = selectedProduct.dimensions.filter(d => d.dimension_type === dimType.name);
                      return (
                        <div key={dimType.name} className="bg-gray-50 rounded-lg p-3">
                          <div className="text-xs font-medium text-gray-500 mb-2">{dimType.display_name}</div>
                          <div className="space-y-1">
                            {dims.map((dim) => (
                              <div key={dim.id} className="text-sm text-gray-700 truncate" title={dim.name}>
                                {dim.is_custom && <span className="text-red-500">*</span>}
                                {dim.name}
                              </div>
                            ))}
                            {dims.length === 0 && <div className="text-xs text-gray-400">-</div>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
              <Image className="w-16 h-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">请选择一个产品查看详情</p>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                {isEdit ? '编辑产品' : '添加产品'}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <div className="flex items-center gap-2">
                      <span>产品名称</span>
                      <TooltipWrapper icon={<Package className="w-4 h-4" />} text="产品的名称，用于识别和展示" />
                      
                    </div>
                  </label>
                  <input
                    type="text"
                    value={formData.product_name}
                    onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                    maxLength={LIMITS.productName}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <div className="flex items-center gap-2">
                      <span>分类</span>
                      <TooltipWrapper icon={<FolderOpen className="w-4 h-4" />} text="产品所属分类，如Audio Monitor、Night Lights" />
                      
                    </div>
                  </label>
                  <input
                    type="text"
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                    maxLength={LIMITS.category}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <div className="flex items-center gap-2">
                      <span>描述</span>
                      <TooltipWrapper icon={<FileText className="w-4 h-4" />} text="产品的详细描述，用于生成文案和图像提示词" />
                      
                    </div>
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    rows={3}
                    maxLength={LIMITS.description}
                  />
                  <p className="mt-1 text-xs text-gray-400 text-right">
                    {(formData.description || '').length}/{LIMITS.description}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <div className="flex items-center gap-2">
                      <span>卖点</span>
                      <TooltipWrapper icon={<Sparkles className="w-4 h-4" />} text="产品的核心卖点，用逗号分隔多个卖点，用于生成文案" />
                      
                    </div>
                  </label>
                  <input
                    type="text"
                    value={(formData.selling_points || []).join(',')}
                    onChange={(e) => setFormData({ ...formData, selling_points: e.target.value.split(',').map(t => t.trim()) })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="用逗号分隔"
                    maxLength={LIMITS.sellingPointsJoined}
                  />
                  <p className="mt-1 text-xs text-gray-400 text-right">
                    {(formData.selling_points || []).filter(Boolean).join(',').length}/{LIMITS.sellingPointsJoined}
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    <div className="flex items-center gap-2">
                      <span>品牌调性</span>
                      <TooltipWrapper icon={<Megaphone className="w-4 h-4" />} text={`品牌的语言风格和调性，影响生成文案的语气（最多 ${LIMITS.brandVoice} 字）`} />
                      
                    </div>
                  </label>
                  <input
                    type="text"
                    value={formData.brand_voice}
                    onChange={(e) => setFormData({ ...formData, brand_voice: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    maxLength={LIMITS.brandVoice}
                  />
                  <p className={`mt-1 text-xs text-right ${(formData.brand_voice || '').length >= LIMITS.brandVoice ? 'text-red-500' : 'text-gray-400'}`}>
                    {(formData.brand_voice || '').length}/{LIMITS.brandVoice}
                  </p>
                </div>
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
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? '保存中…' : isEdit ? '保存修改' : '添加产品'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      </div>

      {previewImage && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setPreviewImage(null)}>
          <div className="relative max-w-4xl max-h-[90vh]">
            <button onClick={() => setPreviewImage(null)} className="absolute -top-10 right-0 text-white hover:text-gray-300">
              <X className="w-8 h-8" />
            </button>
            <img src={previewImage} alt="预览" className="max-w-full max-h-[90vh] object-contain rounded-lg" />
          </div>
        </div>
      )}
    </>
  );
}

function Image(props: { className?: string }) {
  return (
    <svg className={props.className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

function TooltipWrapper(props: { icon: React.ReactNode; text: string }) {
  const [showTooltip, setShowTooltip] = useState(false);
  
  return (
    <div className="relative group">
      <span 
        className="cursor-help text-gray-500 hover:text-indigo-600 transition-colors"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {props.icon}
      </span>
      {showTooltip && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg z-50 whitespace-nowrap">
          {props.text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900"></div>
        </div>
      )}
    </div>
  );
}