import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Plus, Upload, Trash2, Eye, Edit2, X, RefreshCw, Palette, FileText, Sparkles, Megaphone, AlertCircle } from 'lucide-react';
import type { Product, ProductCreate, PaginatedResponse } from '@/api/products';
import { getProducts, getProduct, getCategories, createProduct, updateProduct, deleteProduct, uploadProductImages, deleteProductImage } from '@/api/products';
import { findOwnedBrand, defaultProductBrandId } from '@/api/brands';
import type { DimensionType } from '@/api/dimensions';
import { getDimensionTypes } from '@/api/dimensions';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import {
  LIMITS,
  alertValidationErrors,
  createValidators,
} from '@/lib/formValidation';
import {
  validateImageFiles,
  getUploadErrorMessage,
  formatFileSize,
  MAX_IMAGE_FILE_LABEL,
} from '@/lib/imageUpload';
import { isProductIncomplete } from '@/lib/productCompleteness';
import Pagination from '@/components/Pagination';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import BrandPicker from '@/components/BrandPicker';
import BrandBadge from '@/components/BrandBadge';
import BrandInheritanceHint from '@/components/BrandInheritanceHint';
import CategoryCombobox, { findCanonicalCategory } from '@/components/CategoryCombobox';
import SetupFlowCallout from '@/components/SetupFlowCallout';
import {
  clearProductFormDraft,
  loadProductFormDraft,
  saveProductFormDraft,
  type ProductFormDraft,
} from '@/lib/formDraft';
import { useBrandContext } from '@/context/BrandContext';
import { useI18n } from '@/i18n/useI18n';

const RETURN_TO_PRODUCT_KEY = 'pulseforge:return-to-product';

export default function AssetManagement() {
  const { t } = useI18n();
  const v = createValidators(t);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { activeBrandId, brands, loading: brandsLoading, refreshBrands } = useBrandContext();
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
  const [formData, setFormData] = useState<ProductCreate & { use_brand_voice?: boolean }>({
    product_name: '',
    category: '',
    description: '',
    selling_points: [],
    brand_voice: '',
    brand_id: '',
    use_brand_voice: false,
  });
  const [inheritedVoice, setInheritedVoice] = useState<string>('');
  const [detailInheritedVoice, setDetailInheritedVoice] = useState<string>('');

  useEffect(() => {
    void Promise.all([loadProducts(1), loadDimensionTypes()]);
  }, [activeBrandId]);

  const applyProductDraft = useCallback((draft: ProductFormDraft, brandId?: string | null) => {
    setIsEdit(draft.isEdit);
    setFormData({
      product_name: '',
      category: '',
      description: '',
      selling_points: [],
      brand_voice: '',
      use_brand_voice: false,
      ...draft.formData,
      brand_id: brandId || (draft.formData.brand_id as string) || '',
    });
    if (draft.isEdit && draft.selectedProductId) {
      const product = products.find((p) => p.product_id === draft.selectedProductId);
      if (product) setSelectedProduct(product);
    } else {
      setSelectedProduct(null);
    }
    setShowModal(true);
  }, [products]);

  useEffect(() => {
    const resume = searchParams.get('resumeForm');
    const brandId = searchParams.get('brandId');
    if (resume !== '1') return;

    const draft = loadProductFormDraft();
    if (draft) {
      applyProductDraft(draft, brandId);
    } else if (brandId) {
      setFormData((prev) => ({ ...prev, brand_id: brandId }));
      setShowModal(true);
    }
    navigate('/products', { replace: true });
  }, [searchParams, navigate, applyProductDraft]);

  useEffect(() => {
    if (!showModal) return;
    saveProductFormDraft({
      formData: { ...formData },
      isEdit,
      selectedProductId: selectedProduct?.product_id ?? null,
    });
  }, [showModal, formData, isEdit, selectedProduct?.product_id]);

  const ownedBrands = brands.filter((b) => !b.is_generic);
  const effectiveBrandId = formData.brand_id || defaultProductBrandId(brands, activeBrandId);
  const selectedBrand = brands.find((b) => b.brand_id === effectiveBrandId);
  const needsBrandSetup = !isEdit && ownedBrands.length === 0;
  const usingGenericWithBrandsAvailable =
    !isEdit && ownedBrands.length > 0 && selectedBrand?.is_generic;

  const goToBrandSetup = () => {
    saveProductFormDraft({
      formData: { ...formData },
      isEdit,
      selectedProductId: selectedProduct?.product_id ?? null,
    });
    try {
      sessionStorage.setItem(RETURN_TO_PRODUCT_KEY, '1');
    } catch {
      /* ignore */
    }
    const url = `${window.location.origin}/brand?openAdd=1`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  useEffect(() => {
    if (!showModal) return;
    const onFocus = () => void refreshBrands();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [showModal, refreshBrands]);

  useEffect(() => {
    if (formData.use_brand_voice) {
      setInheritedVoice('');
      return;
    }
    const brand = findOwnedBrand(brands, formData.brand_id);
    setInheritedVoice(brand?.voice || '');
  }, [formData.brand_id, formData.use_brand_voice, brands]);

  useEffect(() => {
    if (!selectedProduct) {
      setDetailInheritedVoice('');
      return;
    }
    if (selectedProduct.use_brand_voice) {
      setDetailInheritedVoice('');
      return;
    }
    const brand = findOwnedBrand(brands, selectedProduct.brand_id);
    setDetailInheritedVoice(brand?.voice || '');
  }, [selectedProduct?.product_id, selectedProduct?.use_brand_voice, selectedProduct?.brand_id, brands]);

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
      const response: PaginatedResponse<Product> = await getProducts(page, size, activeBrandId || undefined);
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
        v.required(t('assets.productName'), formData.product_name),
        v.maxLen(t('assets.productName'), formData.product_name, LIMITS.productName),
        v.required(t('assets.category'), formData.category),
        v.maxLen(t('assets.category'), formData.category, LIMITS.category),
        v.maxLen(t('assets.description'), formData.description, LIMITS.description),
        v.maxLen(t('assets.sellingPoints'), sellingJoined, LIMITS.sellingPointsJoined),
        ...(formData.use_brand_voice
          ? [v.maxLen(t('assets.brandVoice'), formData.brand_voice, LIMITS.brandVoice)]
          : []),
      ])
    ) {
      return;
    }
    setSaving(true);
    try {
      const categories = await cachedFetch('categories', () => getCategories());
      const resolvedCategory =
        findCanonicalCategory(formData.category, categories) ?? formData.category.trim();
      const payload = { ...formData, category: resolvedCategory };

      if (isEdit && selectedProduct) {
        const updated = await updateProduct(selectedProduct.product_id, payload);
        setSelectedProduct(updated);
        setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
        invalidateCache('products');
        invalidateCache('categories');
      } else {
        const created = await createProduct(payload);
        invalidateCache('products');
        invalidateCache('categories');
        if (currentPage === 1) {
          setProducts(prev => [created, ...prev].slice(0, pageSize));
          setTotal(t => t + 1);
        } else {
          setTotal(t => t + 1);
        }
      }
      clearProductFormDraft();
      setShowModal(false);
      setFormData({
        product_name: '',
        category: '',
        description: '',
        selling_points: [],
        brand_voice: '',
        brand_id: defaultProductBrandId(brands, activeBrandId),
        use_brand_voice: false,
      });
    } catch (error) {
      console.error('Failed to save product:', error);
      alert(t('assets.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (productId: string) => {
    if (confirm(t('assets.confirmDeleteProduct'))) {
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

    const validation = validateImageFiles(files);
    if (!validation.ok) {
      if (validation.error === 'fileTooLarge' && validation.oversized) {
        alert(
          t('assets.uploadFileTooLarge', {
            max: MAX_IMAGE_FILE_LABEL,
            names: validation.oversized.map((f) => `${f.name} (${formatFileSize(f.size)})`).join(', '),
          })
        );
      } else if (validation.error === 'batchTooLarge' && validation.totalBytes) {
        alert(
          t('assets.uploadBatchTooLarge', {
            max: MAX_IMAGE_FILE_LABEL,
            total: formatFileSize(validation.totalBytes),
          })
        );
      } else {
        alert(t('assets.uploadFailed'));
      }
      return;
    }

    setUploadingType(imageType);
    try {
      const response = await uploadProductImages(selectedProduct.product_id, validation.files, imageType);
      if (response.failed && response.failed.length > 0) {
        alert(t('assets.uploadPartialFail', {
          uploaded: response.uploaded.length,
          failed: response.failed.length,
          list: response.failed.join(', '),
        }));
      }
    } catch (error) {
      console.error('Failed to upload images:', error);
      const message = getUploadErrorMessage(error, t('assets.uploadFailed'));
      if ((error as { response?: { status?: number } })?.response?.status === 413) {
        alert(t('assets.uploadTooLarge', { max: MAX_IMAGE_FILE_LABEL }));
      } else {
        alert(message);
      }
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
    if (confirm(t('assets.confirmDeleteImage'))) {
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
        brand_id: defaultProductBrandId(brands, product.brand_id || activeBrandId),
        use_brand_voice: product.use_brand_voice ?? false,
      });
    } else {
      setIsEdit(false);
      setSelectedProduct(null);
      setFormData({
        product_name: '',
        category: '',
        description: '',
        selling_points: [],
        brand_voice: '',
        brand_id: defaultProductBrandId(brands, activeBrandId),
        use_brand_voice: false,
      });
    }
    setShowModal(true);
  };

  return (
    <>
      <div className="p-4 sm:p-6 lg:p-8">
        <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4 mb-6">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-ink-900">{t('assets.title')}</h2>
            <p className="text-ink-500 mt-1 text-sm">{t('assets.subtitle')}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
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
              className="flex items-center gap-2 bg-white border border-canvas-border text-ink-700 px-4 py-2 rounded-lg hover:shadow-card transition-shadow disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <RefreshCw className={`w-4 h-4 ${loading || listBusy ? 'animate-spin' : ''}`} />
              {t('common.refresh')}
            </button>
            <button
              onClick={() => openModal()}
              className="flex items-center gap-2 bg-forge-600 text-white px-4 py-2 rounded-lg hover:bg-forge-700 transition-colors"
            >
              <Plus className="w-5 h-5" />
              {t('assets.addProduct')}
            </button>
          </div>
        </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-white rounded-xl shadow-card border border-canvas-border p-4 min-h-[320px] lg:min-h-[480px]">
            <h3 className="font-semibold text-gray-800 mb-4">{t('assets.productList')}</h3>
            <div className={`space-y-2 ${listBusy ? 'opacity-70 pointer-events-none' : ''}`}>
              {loading && products.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-forge-600 border-t-transparent rounded-full animate-spin mb-3"></div>
                  <span className="text-gray-500 text-sm">{t('assets.startingUp')}</span>
                </div>
              ) : products.length === 0 ? (
                <div className="text-center py-8 text-gray-400 text-sm">{t('assets.noProducts')}</div>
              ) : (
                products.map((product) => (
                  <div
                    key={product.product_id}
                    onClick={() => setSelectedProduct(product)}
                    className={`p-3 rounded-lg cursor-pointer transition-all ${
                      selectedProduct?.product_id === product.product_id
                        ? 'bg-forge-50 border border-forge-200'
                        : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h4 className="font-medium text-gray-800 leading-snug">{product.product_name}</h4>
                      {isProductIncomplete(product) && (
                        <span className="inline-flex items-center gap-1 shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide bg-amber-100 text-amber-800 border border-amber-200">
                          <AlertCircle className="w-3 h-3" />
                          {t('assets.incomplete')}
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500">{product.category}</p>
                    {product.brand && (
                      <div className="mt-1">
                        <BrandBadge brand={{ name: product.brand.name, is_generic: product.brand.slug === 'generic' }} />
                      </div>
                    )}
                    {(product.selling_points || []).filter(Boolean).length > 0 && (
                      <p className="text-xs text-amber-700/80 mt-1.5 truncate">
                        {(product.selling_points || []).filter(Boolean).slice(0, 2).join(' · ')}
                        {(product.selling_points || []).filter(Boolean).length > 2 ? ' …' : ''}
                      </p>
                    )}
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

        <div className="lg:col-span-2 min-h-[320px] lg:min-h-[480px]">
          {selectedProduct ? (
            <div className="bg-white rounded-xl shadow-card border border-canvas-border p-6 h-full">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-xl font-semibold text-gray-900">{selectedProduct.product_name}</h3>
                    {isProductIncomplete(selectedProduct) && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
                        <AlertCircle className="w-3.5 h-3.5" />
                        {t('assets.incomplete')}
                      </span>
                    )}
                  </div>
                  <p className="text-gray-500 mt-1">{selectedProduct.category}</p>
                  {selectedProduct.brand && (
                    <div className="mt-2">
                      <BrandBadge brand={{ name: selectedProduct.brand.name, is_generic: selectedProduct.brand.slug === 'generic' }} />
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => openModal(selectedProduct)}
                    className="p-2 text-gray-500 hover:text-forge-600 hover:bg-forge-50 rounded-lg"
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

              {isProductIncomplete(selectedProduct) && (
                <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 flex gap-3">
                  <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-semibold text-amber-900">{t('assets.incompleteBannerTitle')}</p>
                    <p className="text-sm text-amber-800 mt-1">{t('assets.incompleteBannerBody')}</p>
                  </div>
                </div>
              )}

              <div className="mb-6 space-y-4">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500 mb-2">
                    <FileText className="w-3.5 h-3.5" />
                    {t('assets.productDescription')}
                  </div>
                  <p className="text-gray-600 leading-relaxed">
                    {selectedProduct.description || <span className="text-gray-400">{t('assets.noDescription')}</span>}
                  </p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500 mb-2">
                      <Megaphone className="w-3.5 h-3.5" />
                      {t('assets.brandVoice')}
                    </div>
                    {selectedProduct.use_brand_voice && selectedProduct.brand_voice ? (
                      <div>
                        <span className="inline-block px-3 py-1 bg-forge-50 text-forge-700 border border-forge-100 rounded-full text-sm">
                          {selectedProduct.brand_voice}
                        </span>
                        <p className="text-[10px] text-gray-400 mt-1.5">{t('assets.productVoiceOverride')}</p>
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-gray-500">
                          {t('assets.inheritedBrandVoice', {
                            brand: selectedProduct.brand?.name || t('brands.generic'),
                          })}
                        </p>
                        {detailInheritedVoice ? (
                          <p className="text-sm text-gray-700 leading-relaxed line-clamp-4">
                            {detailInheritedVoice}
                          </p>
                        ) : (
                          <p className="text-sm text-gray-400">{t('brands.noVoiceInherited')}</p>
                        )}
                        {selectedProduct.brand_id && selectedProduct.brand?.slug !== 'generic' && (
                          <Link
                            to="/brand"
                            className="text-xs font-medium text-forge-600 hover:text-forge-700 hover:underline"
                          >
                            {t('assets.viewBrandVoice')} →
                          </Link>
                        )}
                      </div>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5 text-xs font-medium text-gray-500 mb-2">
                      <Sparkles className="w-3.5 h-3.5" />
                      {t('assets.coreSellingPoints')}
                    </div>
                    {(selectedProduct.selling_points || []).filter(Boolean).length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {(selectedProduct.selling_points || []).filter(Boolean).map((point, i) => (
                          <span
                            key={`${point}-${i}`}
                            className="inline-flex items-center px-3 py-1.5 bg-amber-50 text-amber-900 border border-amber-200 rounded-lg text-sm leading-snug"
                          >
                            {point}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400">{t('assets.noSellingPoints')}</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-semibold text-gray-800">{t('assets.productImages')}</h4>
                    <label className={`flex items-center gap-1.5 text-sm font-medium text-forge-600 ${uploadingType ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:text-forge-700'}`}>
                      {uploadingType === 'product' ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                      <span>{uploadingType === 'product' ? t('assets.uploading') : t('assets.upload')}</span>
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
                  <p className="text-[10px] text-gray-400 mb-2">
                    {t('assets.uploadSizeHint', { max: MAX_IMAGE_FILE_LABEL })}
                  </p>
                  <div className={`grid grid-cols-3 gap-3 ${uploadingType === 'product' ? 'opacity-70' : ''}`}>
                    {(Array.isArray(selectedProduct.product_images) ? selectedProduct.product_images : []).length === 0 ? (
                      <div className="col-span-3 rounded-lg border-2 border-dashed border-amber-200 bg-amber-50/40 p-5 text-center">
                        <Upload className="w-8 h-8 text-amber-400 mx-auto mb-2" />
                        <p className="text-sm font-medium text-amber-900">{t('assets.uploadProductImagesHint')}</p>
                        <p className="text-xs text-amber-700/80 mt-1">{t('assets.incompleteBannerBody')}</p>
                      </div>
                    ) : (
                      (Array.isArray(selectedProduct.product_images) ? selectedProduct.product_images : []).map((image) => (
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
                    ))
                    )}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="font-semibold text-gray-800">{t('assets.sceneImages')}</h4>
                    <label className={`flex items-center gap-1.5 text-sm font-medium text-forge-600 ${uploadingType ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:text-forge-700'}`}>
                      {uploadingType === 'scene' ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        <Upload className="w-4 h-4" />
                      )}
                      <span>{uploadingType === 'scene' ? t('assets.uploading') : t('assets.upload')}</span>
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
                  <p className="text-[10px] text-gray-400 mb-2">
                    {t('assets.uploadSizeHint', { max: MAX_IMAGE_FILE_LABEL })}
                  </p>
                  <div className={`grid grid-cols-3 gap-3 ${uploadingType === 'scene' ? 'opacity-70' : ''}`}>
                    {(Array.isArray(selectedProduct.scene_images) ? selectedProduct.scene_images : []).length === 0 ? (
                      <div className="col-span-3 rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 p-5 text-center">
                        <Upload className="w-7 h-7 text-gray-300 mx-auto mb-2" />
                        <p className="text-sm text-gray-600">{t('assets.uploadSceneImagesHint')}</p>
                      </div>
                    ) : (
                      (Array.isArray(selectedProduct.scene_images) ? selectedProduct.scene_images : []).map((image) => (
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
                    ))
                    )}
                  </div>
                </div>
              </div>

              {Array.isArray(selectedProduct.dimensions) && selectedProduct.dimensions.length > 0 && (
                <div className="mt-6">
                  <h4 className="flex items-center gap-2 font-semibold text-gray-800 mb-3">
                    <Palette className="w-5 h-5" />
                    {t('assets.linkedDimensions')}
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
                            {dims.length === 0 && <div className="text-xs text-gray-400">{t('assets.noDimensions')}</div>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl shadow-card border border-canvas-border p-12 text-center h-full flex flex-col items-center justify-center min-h-[320px]">
              <Image className="w-16 h-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">{t('assets.selectProductHint')}</p>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                {isEdit ? t('assets.editProduct') : t('assets.addProduct')}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit}>
              <div className="space-y-4">
                <div>
                  <LabelWithTooltip label={t('assets.brand')} tooltip={t('assets.tooltips.brand')} />
                  <BrandPicker
                    value={formData.brand_id || defaultProductBrandId(brands, activeBrandId)}
                    onChange={(brandId) => setFormData({ ...formData, brand_id: brandId })}
                    brands={brands}
                    loading={brandsLoading}
                  />
                  {!formData.use_brand_voice && <BrandInheritanceHint voice={inheritedVoice} className="mt-1" />}
                  {needsBrandSetup && (
                    <div className="mt-3">
                      <SetupFlowCallout
                        variant="warning"
                        title={t('assets.brandSetup.title')}
                        description={t('assets.brandSetup.description')}
                        actionLabel={t('assets.brandSetup.action')}
                        onAction={goToBrandSetup}
                        openActionInNewTab
                      />
                    </div>
                  )}
                  {usingGenericWithBrandsAvailable && (
                    <p className="mt-2 text-xs text-amber-700 leading-relaxed">
                      {t('assets.brandPickHint')}
                    </p>
                  )}
                </div>
                <div>
                  <LabelWithTooltip
                    label={t('assets.productName')}
                    tooltip={t('assets.tooltips.productName')}
                  />
                  <input
                    type="text"
                    value={formData.product_name}
                    onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    required
                    maxLength={LIMITS.productName}
                    placeholder={t('placeholders.assets.productName')}
                  />
                </div>
                <div>
                  <LabelWithTooltip
                    label={t('assets.category')}
                    tooltip={t('assets.tooltips.category')}
                  />
                  <CategoryCombobox
                    value={formData.category}
                    onChange={(category) => setFormData({ ...formData, category })}
                    maxLength={LIMITS.category}
                    required
                  />
                </div>
                <div>
                  <LabelWithTooltip
                    label={t('assets.description')}
                    tooltip={t('assets.tooltips.description')}
                  />
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    rows={3}
                    maxLength={LIMITS.description}
                    placeholder={t('placeholders.assets.description')}
                  />
                  <p className="mt-1 text-xs text-gray-400 text-right">
                    {t('common.charCount', { current: (formData.description || '').length, max: LIMITS.description })}
                  </p>
                </div>
                <div>
                  <LabelWithTooltip
                    label={t('assets.sellingPoints')}
                    tooltip={t('assets.tooltips.sellingPoints')}
                  />
                  <input
                    type="text"
                    value={(formData.selling_points || []).join(',')}
                    onChange={(e) => setFormData({ ...formData, selling_points: e.target.value.split(',').map(s => s.trim()) })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    placeholder={t('placeholders.assets.sellingPoints')}
                    maxLength={LIMITS.sellingPointsJoined}
                  />
                  <p className="mt-1 text-xs text-gray-400 text-right">
                    {t('common.charCount', { current: (formData.selling_points || []).filter(Boolean).join(',').length, max: LIMITS.sellingPointsJoined })}
                  </p>
                </div>
                <div>
                  <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.use_brand_voice ?? false}
                      onChange={(e) => setFormData({ ...formData, use_brand_voice: e.target.checked })}
                      className="rounded border-gray-300 text-forge-600 focus:ring-forge-500"
                    />
                    {t('assets.overrideBrandVoice')}
                  </label>
                </div>
                {formData.use_brand_voice && (
                <div>
                  <LabelWithTooltip
                    label={t('assets.brandVoice')}
                    tooltip={t('assets.tooltips.brandVoice', { max: LIMITS.brandVoice })}
                  />
                  <textarea
                    value={formData.brand_voice}
                    onChange={(e) => setFormData({ ...formData, brand_voice: e.target.value })}
                    rows={3}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    maxLength={LIMITS.brandVoice}
                    placeholder={t('placeholders.assets.brandVoice')}
                  />
                  <p className={`mt-1 text-xs text-right ${(formData.brand_voice || '').length >= LIMITS.brandVoice ? 'text-red-500' : 'text-gray-400'}`}>
                    {t('common.charCount', { current: (formData.brand_voice || '').length, max: LIMITS.brandVoice })}
                  </p>
                </div>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  disabled={saving}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? t('common.saving') : isEdit ? t('assets.saveChanges') : t('assets.addProduct')}
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
            <img src={previewImage} alt={t('assets.previewAlt')} className="max-w-full max-h-[90vh] object-contain rounded-lg" />
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
