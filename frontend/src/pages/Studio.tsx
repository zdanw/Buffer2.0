import { useState, useEffect } from 'react';
import { Play, RefreshCw, Image as ImageIcon, FileText, Image, Send, CheckCircle, X, BookmarkPlus } from 'lucide-react';
import type { Product } from '@/api/products';
import { getProducts } from '@/api/products';
import {
  generateContent,
  generateCopywriting,
  generateImage,
  getGenerateStatus,
  type GenerateRequest,
  type GenerateStatus,
  type DimensionInfo,
} from '@/api/generate';
import { publishContent } from '@/api/publish';
import { createDraft } from '@/api/tasks';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import ReferenceImagesDisplay from '@/components/ReferenceImagesDisplay';
import ImageModelPicker from '@/components/ImageModelPicker';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import HelpTooltip from '@/components/HelpTooltip';
import { useBrandContext } from '@/context/BrandContext';
import { useI18n } from '@/i18n/useI18n';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];
const DIMENSION_FIELD_KEYS: Record<string, string> = {
  scene: 'scenes',
  lighting: 'lighting',
  style: 'styles',
  composition: 'compositions',
  details: 'details',
  quality: 'quality',
  viewpoint: 'viewpoints',
};
const DIMENSION_FIELDS = ['scene', 'lighting', 'style', 'composition', 'details', 'quality', 'viewpoint'] as const;
const LEGACY_STORAGE_KEY = 'bebcare_content_preview_state';
const STORAGE_KEY = 'pulseforge_studio_state';

interface PreviewState {
  selectedProduct: string;
  selectedPlatforms: string[];
  useSceneReference: boolean;
  useVisionImagePrompt: boolean;
  imageProviderId?: string | null;
  imageModel?: string | null;
  generatedContent: {
    text: string;
    image: string;
    dimensions?: DimensionInfo;
    image_prompt?: string;
    reference_product_images?: string[];
    reference_scene_images?: string[];
    warning?: string;
  } | null;
  taskId: string | null;
  isGenerating: boolean;
  generatingType: string | null;
}

const loadStateFromStorage = (): PreviewState => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
    if (saved) {
      const parsed = JSON.parse(saved);
      if (!localStorage.getItem(STORAGE_KEY) && localStorage.getItem(LEGACY_STORAGE_KEY)) {
        localStorage.setItem(STORAGE_KEY, saved);
        localStorage.removeItem(LEGACY_STORAGE_KEY);
      }
      return parsed;
    }
  } catch (e) {
    console.error('Failed to load state from localStorage:', e);
  }
  return {
    selectedProduct: '',
    selectedPlatforms: ['instagram'],
    useSceneReference: false,
    useVisionImagePrompt: false,
    imageProviderId: null,
    imageModel: null,
    generatedContent: null,
    taskId: null,
    isGenerating: false,
    generatingType: null,
  };
};

const saveStateToStorage = (state: PreviewState) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    console.error('Failed to save state to localStorage:', e);
  }
};

export default function Studio() {
  const { t } = useI18n();
  const { activeBrandId, activeBrand } = useBrandContext();
  const savedState = loadStateFromStorage();
  
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>(savedState.selectedProduct);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(savedState.selectedPlatforms);
  const [useSceneReference, setUseSceneReference] = useState(savedState.useSceneReference);
  const [useVisionImagePrompt, setUseVisionImagePrompt] = useState(
    savedState.useVisionImagePrompt ?? false
  );
  const [imageProviderId, setImageProviderId] = useState<string | null>(savedState.imageProviderId ?? null);
  const [imageModel, setImageModel] = useState<string | null>(savedState.imageModel ?? null);
  const [isGenerating, setIsGenerating] = useState(savedState.isGenerating);
  const [generatingType, setGeneratingType] = useState<string | null>(savedState.generatingType);
  const [taskId, setTaskId] = useState<string | null>(savedState.taskId);
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus | null>(null);
  const [generatedContent, setGeneratedContent] = useState<{
    text: string;
    image: string;
    dimensions?: DimensionInfo;
    image_prompt?: string;
    reference_product_images?: string[];
    reference_scene_images?: string[];
    warning?: string;
  } | null>(savedState.generatedContent);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string | null>(null);
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [saveDraftStatus, setSaveDraftStatus] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [productsLoading, setProductsLoading] = useState(true);
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  useEffect(() => {
    void loadProducts();
  }, [activeBrandId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await loadProducts(true);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    saveStateToStorage({
      selectedProduct,
      selectedPlatforms,
      useSceneReference,
      useVisionImagePrompt,
      imageProviderId,
      imageModel,
      generatedContent,
      taskId,
      isGenerating,
      generatingType,
    });
  }, [selectedProduct, selectedPlatforms, useSceneReference, useVisionImagePrompt, imageProviderId, imageModel, generatedContent, taskId, isGenerating, generatingType]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | undefined;
    if (taskId && isGenerating) {
      const checkStatus = async () => {
        try {
          const status = await getGenerateStatus(taskId);
          setGenerateStatus(status);
          
          if (status.status === 'SUCCESS') {
            setIsGenerating(false);
            if (interval) clearInterval(interval);
            if (status.result) {
              setGeneratedContent((prev) => ({
                text: status.result?.text || prev?.text || '',
                image: status.result?.image || prev?.image || '',
                // 仅文案接口不返回维度/提示词，需保留上一次图片生成的结果
                dimensions: status.result?.dimensions ?? prev?.dimensions,
                image_prompt: status.result?.image_prompt ?? prev?.image_prompt,
                reference_product_images:
                  status.result?.reference_product_images ?? prev?.reference_product_images,
                reference_scene_images:
                  status.result?.reference_scene_images ?? prev?.reference_scene_images,
                warning: status.result?.warning ?? prev?.warning,
              }));
            }
          } else if (status.status === 'FAILURE') {
            setIsGenerating(false);
            if (interval) clearInterval(interval);
          }
        } catch (error) {
          console.error('Failed to check status:', error);
          setIsGenerating(false);
          if (interval) clearInterval(interval);
        }
      };
      
      checkStatus();
      interval = setInterval(checkStatus, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [taskId, isGenerating]);

  const loadProducts = async (force = false) => {
    if (!force) setProductsLoading(true);
    const cacheKey = `products:list:100:${activeBrandId || 'all'}`;
    try {
      if (force) invalidateCache(cacheKey);
      const data = force
        ? (await getProducts(1, 100, activeBrandId || undefined)).data
        : await cachedFetch(cacheKey, async () => {
            const response = await getProducts(1, 100, activeBrandId || undefined);
            return response.data;
          });
      setProducts(data);
      // 仅在没有已选产品时设默认，避免覆盖 localStorage
      setSelectedProduct((prev) => {
        if (prev && data.some((p) => p.product_id === prev)) return prev;
        return data[0]?.product_id ?? '';
      });
    } catch (error) {
      console.error('Failed to load products:', error);
    } finally {
      setProductsLoading(false);
    }
  };

  const handleGenerate = async (type: 'all' | 'copywriting' | 'image') => {
    if (!selectedProduct) {
      alert(t('preview.selectProductFirst'));
      return;
    }
    if (selectedPlatforms.length === 0) {
      alert(t('preview.selectPlatform'));
      return;
    }
    if (isGenerating) return;
    
    setIsGenerating(true);
    setGeneratingType(type);
    setPublishStatus(null);
    setSaveDraftStatus(null);
    setTaskId(null);
    
    if (type === 'copywriting') {
      setGeneratedContent(prev => ({
        text: '',
        image: prev?.image || '',
        dimensions: prev?.dimensions,
        image_prompt: prev?.image_prompt,
        reference_product_images: prev?.reference_product_images,
        reference_scene_images: prev?.reference_scene_images,
        warning: prev?.warning,
      }));
    } else if (type === 'image') {
      setGeneratedContent(prev => ({
        text: prev?.text || '',
        image: '',
        dimensions: undefined,
        image_prompt: undefined,
        reference_product_images: undefined,
        reference_scene_images: undefined,
        warning: undefined,
      }));
    } else {
      setGeneratedContent(null);
    }
    
    setGenerateStatus(null);

    try {
      const request: GenerateRequest = {
        product_id: selectedProduct,
        platform: selectedPlatforms[0],
        style_hint: 'storytelling',
        use_scene_reference: useSceneReference,
        use_vision_image_prompt: useVisionImagePrompt,
        image_provider_id: imageProviderId || undefined,
        image_model: imageModel || undefined,
      };

      let response;
      if (type === 'copywriting') {
        response = await generateCopywriting(request);
      } else if (type === 'image') {
        response = await generateImage(request);
      } else {
        response = await generateContent(request);
      }
      setTaskId(response.task_id);
    } catch (error) {
      console.error('Failed to generate content:', error);
      setIsGenerating(false);
      setGeneratingType(null);
      setTaskId(null);
      alert(t('preview.generateFailed'));
    }
  };

  const handlePublish = async () => {
    if (!generatedContent || !generatedContent.text) {
      alert(t('preview.generateCopyFirst'));
      return;
    }
    if (selectedPlatforms.length === 0) {
      alert(t('preview.selectPlatform'));
      return;
    }
    
    setIsPublishing(true);
    setPublishStatus(null);
    
    try {
      await publishContent(
        generatedContent.text,
        generatedContent.image,
        selectedPlatforms
      );
      setPublishStatus('success');
    } catch (error) {
      console.error('Failed to publish content:', error);
      setPublishStatus('failed');
      alert(t('preview.publishFailed'));
    } finally {
      setIsPublishing(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!generatedContent?.text && !generatedContent?.image) {
      alert(t('preview.generateBeforeSave'));
      return;
    }

    setIsSavingDraft(true);
    setSaveDraftStatus(null);
    try {
      const images = generatedContent.image ? [generatedContent.image] : [];
      const copywritings = generatedContent.text ? [generatedContent.text] : [];
      await createDraft({
        product_id: selectedProduct || undefined,
        images,
        copywritings,
        dimensions: generatedContent.dimensions ? [generatedContent.dimensions] : [],
        image_prompts: generatedContent.image_prompt ? [generatedContent.image_prompt] : [],
        reference_product_images: generatedContent.reference_product_images || [],
        reference_scene_images: generatedContent.reference_scene_images || [],
      });
      invalidateCache('drafts');
      setSaveDraftStatus('success');
    } catch (error) {
      console.error('Failed to save draft:', error);
      setSaveDraftStatus('failed');
      alert(t('preview.saveFailed'));
    } finally {
      setIsSavingDraft(false);
    }
  };

  const togglePlatform = (platform: string) => {
    setSelectedPlatforms(prev => {
      if (prev.includes(platform)) {
        if (prev.length === 1) return prev;
        return prev.filter(p => p !== platform);
      }
      return [...prev, platform];
    });
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t('studio.title')}</h2>
          <p className="text-gray-500 mt-1">{t('studio.subtitle')}</p>
          {activeBrand && (
            <p className="text-xs text-indigo-600 mt-1">
              {t('studio.inheritedFrom', { brand: activeBrand.is_generic ? t('brands.generic') : activeBrand.name })}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => void handleRefresh()}
          disabled={refreshing || isGenerating}
          className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <LabelWithTooltip
              htmlFor="studio-product"
              label={t('fields.selectProduct')}
              tooltip={t('studio.tooltips.product')}
            />
            {productsLoading ? (
              <div className="flex items-center gap-2 text-sm text-gray-500 py-2">
                <RefreshCw className="w-4 h-4 animate-spin" />
                {t('preview.loadingProducts')}
              </div>
            ) : (
              <select
                id="studio-product"
                value={selectedProduct}
                onChange={(e) => setSelectedProduct(e.target.value)}
                disabled={refreshing}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50"
              >
                <option value="">{t('fields.selectProductPlaceholder')}</option>
                {products.map((product) => (
                  <option key={product.product_id} value={product.product_id}>
                    {product.product_name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <LabelWithTooltip
              label={t('fields.publishPlatforms')}
              tooltip={t('studio.tooltips.platforms')}
            />
            <div className="flex flex-wrap gap-2 mt-1">
              {PLATFORMS.map((p) => (
                <button
                  key={p}
                  onClick={() => togglePlatform(p)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    selectedPlatforms.includes(p)
                      ? 'bg-indigo-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 min-w-0 flex-1">
                <span className="text-sm font-medium text-gray-700">{t('preview.enableSceneReference')}</span>
                <HelpTooltip content={t('studio.tooltips.sceneReference')} />
              </div>
              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={useSceneReference}
                  onChange={() => setUseSceneReference(!useSceneReference)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-1.5 min-w-0 flex-1">
                <span className="text-sm font-medium text-gray-700">{t('preview.visionImagePrompt')}</span>
                <HelpTooltip content={t('studio.tooltips.visionPrompt')} />
              </div>
              <label className="relative inline-flex items-center cursor-pointer shrink-0">
                <input
                  type="checkbox"
                  checked={useVisionImagePrompt}
                  onChange={() => setUseVisionImagePrompt(!useVisionImagePrompt)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>
          </div>

          <ImageModelPicker
            value={{ image_provider_id: imageProviderId, image_model: imageModel }}
            onChange={(next) => {
              setImageProviderId(next.image_provider_id ?? null);
              setImageModel(next.image_model ?? null);
            }}
            disabled={isGenerating}
          />

          <div className="space-y-3">
            <button
              onClick={() => handleGenerate('all')}
              disabled={isGenerating || !selectedProduct || selectedPlatforms.length === 0}
              title={t('studio.tooltips.generateAll')}
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                isGenerating || !selectedProduct || selectedPlatforms.length === 0
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700'
              }`}
            >
              {isGenerating && generatingType === 'all' ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  {t('preview.generating')}
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  {t('preview.generateContent')}
                </>
              )}
            </button>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleGenerate('copywriting')}
                disabled={isGenerating || !selectedProduct || selectedPlatforms.length === 0}
                title={t('studio.tooltips.generateCopy')}
                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  isGenerating || !selectedProduct || selectedPlatforms.length === 0
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-green-600 text-white hover:bg-green-700'
                }`}
              >
                {isGenerating && generatingType === 'copywriting' ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  </>
                ) : (
                  <>
                    <FileText className="w-4 h-4" />
                    {t('preview.generateCopyOnly')}
                  </>
                )}
              </button>

              <button
                onClick={() => handleGenerate('image')}
                disabled={isGenerating || !selectedProduct || selectedPlatforms.length === 0}
                title={t('studio.tooltips.generateImage')}
                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  isGenerating || !selectedProduct || selectedPlatforms.length === 0
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-orange-600 text-white hover:bg-orange-700'
                }`}
              >
                {isGenerating && generatingType === 'image' ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  </>
                ) : (
                  <>
                    <Image className="w-4 h-4" />
                    {t('preview.generateImageOnly')}
                  </>
                )}
              </button>
            </div>

            {generatedContent && (generatedContent.text || generatedContent.image) && (
              <button
                type="button"
                onClick={() => void handleSaveDraft()}
                disabled={isSavingDraft}
                className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  isSavingDraft
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-emerald-600 text-white hover:bg-emerald-700'
                }`}
              >
                {isSavingDraft ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    {t('preview.saving')}
                  </>
                ) : (
                  <>
                    <BookmarkPlus className="w-5 h-5" />
                    {t('preview.saveToPending')}
                  </>
                )}
              </button>
            )}

            {generatedContent && generatedContent.text && (
              <button
                onClick={handlePublish}
                disabled={isPublishing || selectedPlatforms.length === 0}
                className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  isPublishing || selectedPlatforms.length === 0
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {isPublishing ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    {t('preview.publishing')}
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    {t('preview.publishTo', { platforms: selectedPlatforms.join(', ') })}
                  </>
                )}
              </button>
            )}
          </div>

          {generateStatus && (
            <div className={`p-4 rounded-lg ${
              generateStatus.status === 'SUCCESS' ? 'bg-green-50' :
              generateStatus.status === 'FAILURE' ? 'bg-red-50' : 'bg-yellow-50'
            }`}>
              <p className={`font-medium ${
                generateStatus.status === 'SUCCESS' ? 'text-green-700' :
                generateStatus.status === 'FAILURE' ? 'text-red-700' : 'text-yellow-700'
              }`}>
                {generateStatus.status === 'SUCCESS' ? t('preview.generateSuccess') :
                 generateStatus.status === 'FAILURE' ? t('preview.generateError') : t('preview.processing')}
              </p>
              {generateStatus.status === 'FAILURE' && generateStatus.result?.error && (
                <p className="text-sm text-red-600 mt-1">{generateStatus.result.error}</p>
              )}
            </div>
          )}

          {generatedContent?.warning && (
            <div className="p-4 rounded-lg bg-amber-50 border border-amber-200">
              <p className="font-medium text-amber-800">{t('pending.cdnFailed')}</p>
              <p className="text-sm text-amber-700 mt-1">{generatedContent.warning}</p>
            </div>
          )}

          {saveDraftStatus && (
            <div className={`p-4 rounded-lg flex items-center gap-2 ${
              saveDraftStatus === 'success' ? 'bg-green-50' : 'bg-red-50'
            }`}>
              {saveDraftStatus === 'success' ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-700">{t('preview.savedToPending')}</span>
                </>
              ) : (
                <span className="font-medium text-red-700">{t('preview.saveError')}</span>
              )}
            </div>
          )}

          {publishStatus && (
            <div className={`p-4 rounded-lg flex items-center gap-2 ${
              publishStatus === 'success' ? 'bg-green-50' : 'bg-red-50'
            }`}>
              {publishStatus === 'success' ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-700">{t('preview.publishSuccess')}</span>
                </>
              ) : (
                <>
                  <span className="font-medium text-red-700">{t('preview.publishFailed')}</span>
                </>
              )}
            </div>
          )}

          {generatedContent && (
            <ReferenceImagesDisplay
              productImages={generatedContent.reference_product_images}
              sceneImages={generatedContent.reference_scene_images}
              onPreview={setPreviewImage}
            />
          )}

          {generatedContent && (generatedContent.dimensions || generatedContent.image_prompt) && (
            <div className="border-2 border-red-400 rounded-xl p-4 bg-white">
              {generatedContent.dimensions && (
                <>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                    {t('fields.dimensionInfo')}
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    {DIMENSION_FIELDS.map((field) => (
                      <div key={field} className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 w-12">
                          {t(`dimensionTypes.${DIMENSION_FIELD_KEYS[field]}`)}
                        </span>
                        <span className="text-xs text-gray-800 truncate">
                          {generatedContent.dimensions![field]}
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}
              
              {generatedContent.image_prompt && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-600 mb-2">{t('fields.imagePrompt')}</h4>
                  <div className="text-xs text-gray-700 bg-gray-50 p-3 rounded-lg max-h-40 overflow-y-auto whitespace-pre-wrap">
                    {generatedContent.image_prompt}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="col-span-2">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 min-h-[500px]">
            {generatedContent ? (
              <div className="flex flex-col items-center">
                {generatedContent.image && (
                  <div className="w-full max-w-sm mb-6">
                    <p className="text-xs text-center text-gray-500 mb-2">{t('studio.phonePreview')}</p>
                    <div className="mx-auto w-[280px] rounded-[2rem] border-[10px] border-gray-900 bg-gray-900 shadow-xl overflow-hidden">
                      <div className="h-6 bg-gray-900 flex items-center justify-center">
                        <div className="w-16 h-1 rounded-full bg-gray-700" />
                      </div>
                      <div className="bg-white">
                        <img
                          src={generatedContent.image}
                          alt={t('preview.generatedAlt')}
                          className="w-full aspect-square object-cover"
                        />
                        {generatedContent.text && (
                          <p className="p-3 text-xs text-gray-800 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto">
                            {generatedContent.text}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
                {generatedContent.text && !generatedContent.image && (
                  <div className="w-full max-w-sm">
                    <p className="text-gray-800 text-center leading-relaxed whitespace-pre-wrap">
                      {generatedContent.text}
                    </p>
                  </div>
                )}
                {!generatedContent.image && !generatedContent.text && (
                  <div className="h-full flex flex-col items-center justify-center text-gray-400">
                    <ImageIcon className="w-20 h-20 mb-4" />
                    <p className="text-lg">{t('preview.previewArea')}</p>
                    <p className="text-sm mt-1">{t('preview.selectAndGenerate')}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <ImageIcon className="w-20 h-20 mb-4" />
                <p className="text-lg">{t('preview.previewArea')}</p>
                <p className="text-sm mt-1">{t('preview.selectAndGenerate')}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {previewImage && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] p-4">
            <button
              type="button"
              onClick={() => setPreviewImage(null)}
              className="absolute top-2 right-2 text-white hover:text-gray-300 z-10"
            >
              <X className="w-8 h-8" />
            </button>
            <img
              src={previewImage}
              alt={t('preview.referencePreviewAlt')}
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
}