import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Play, RefreshCw, Image as ImageIcon, FileText, Image, Send, CheckCircle } from 'lucide-react';
import type { Product } from '@/api/products';
import { getProducts } from '@/api/products';
import { generateContent, generateCopywriting, generateImage, getGenerateStatus } from '@/api/generate';
import type { GenerateRequest, GenerateStatus, DimensionInfo } from '@/api/generate';
import { publishContent } from '@/api/publish';
import { cachedFetch } from '@/lib/staticCache';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];
const STORAGE_KEY = 'bebcare_content_preview_state';

interface PreviewState {
  selectedProduct: string;
  selectedPlatforms: string[];
  useSceneReference: boolean;
  generatedContent: { text: string; image: string; dimensions?: DimensionInfo; image_prompt?: string } | null;
  taskId: string | null;
  isGenerating: boolean;
  generatingType: string | null;
}

const loadStateFromStorage = (): PreviewState => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      return JSON.parse(saved);
    }
  } catch (e) {
    console.error('Failed to load state from localStorage:', e);
  }
  return {
    selectedProduct: '',
    selectedPlatforms: ['instagram'],
    useSceneReference: false,
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

export default function ContentPreview() {
  const [searchParams, setSearchParams] = useSearchParams();
  const savedState = loadStateFromStorage();
  
  const [products, setProducts] = useState<Product[]>([]);
  
  const urlProductId = searchParams.get('product_id');
  const urlPlatforms = searchParams.get('platform')?.split(',') || [];
  
  const initialProduct = urlProductId || savedState.selectedProduct;
  const initialPlatforms = urlPlatforms.length > 0 ? urlPlatforms.filter(p => PLATFORMS.includes(p)) : savedState.selectedPlatforms;
  
  const [selectedProduct, setSelectedProduct] = useState<string>(initialProduct);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(initialPlatforms);
  const [useSceneReference, setUseSceneReference] = useState(savedState.useSceneReference);
  const [isGenerating, setIsGenerating] = useState(savedState.isGenerating);
  const [generatingType, setGeneratingType] = useState<string | null>(savedState.generatingType);
  const [taskId, setTaskId] = useState<string | null>(savedState.taskId);
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus | null>(null);
  const [generatedContent, setGeneratedContent] = useState<{ text: string; image: string; dimensions?: DimensionInfo; image_prompt?: string } | null>(savedState.generatedContent);
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishStatus, setPublishStatus] = useState<string | null>(null);

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    saveStateToStorage({
      selectedProduct,
      selectedPlatforms,
      useSceneReference,
      generatedContent,
      taskId,
      isGenerating,
      generatingType,
    });
  }, [selectedProduct, selectedPlatforms, useSceneReference, generatedContent, taskId, isGenerating, generatingType]);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (selectedProduct) {
      params['product_id'] = selectedProduct;
    }
    if (selectedPlatforms.length > 0) {
      params['platform'] = selectedPlatforms.join(',');
    }
    setSearchParams(params);
  }, [selectedProduct, selectedPlatforms, setSearchParams]);

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
                dimensions: status.result?.dimensions,
                image_prompt: status.result?.image_prompt
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

  const loadProducts = async () => {
    try {
      const data = await cachedFetch('products:list:100', async () => {
        const response = await getProducts(1, 100);
        return response.data;
      });
      setProducts(data);
      // 仅在没有已选产品时设默认，避免覆盖 URL / localStorage
      setSelectedProduct((prev) => prev || (data[0]?.product_id ?? ''));
    } catch (error) {
      console.error('Failed to load products:', error);
    }
  };

  const handleGenerate = async (type: 'all' | 'copywriting' | 'image') => {
    if (!selectedProduct) {
      alert('请先选择产品');
      return;
    }
    if (selectedPlatforms.length === 0) {
      alert('请至少选择一个发布平台');
      return;
    }
    if (isGenerating) return;
    
    setIsGenerating(true);
    setGeneratingType(type);
    setPublishStatus(null);
    setTaskId(null);
    
    if (type === 'copywriting') {
      setGeneratedContent(prev => ({ text: '', image: prev?.image || '', dimensions: prev?.dimensions, image_prompt: prev?.image_prompt }));
    } else if (type === 'image') {
      setGeneratedContent(prev => ({ text: prev?.text || '', image: '', dimensions: prev?.dimensions, image_prompt: prev?.image_prompt }));
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
      alert('生成请求失败，请稍后重试');
    }
  };

  const handlePublish = async () => {
    if (!generatedContent || !generatedContent.text) {
      alert('请先生成文案后再发布');
      return;
    }
    if (selectedPlatforms.length === 0) {
      alert('请至少选择一个发布平台');
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
      alert('发布失败，请重试');
    } finally {
      setIsPublishing(false);
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
          <h2 className="text-2xl font-bold text-gray-900">内容预览</h2>
          <p className="text-gray-500 mt-1">生成并预览社媒内容</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">选择产品</label>
            <select
              value={selectedProduct}
              onChange={(e) => setSelectedProduct(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            >
              <option value="">请选择产品</option>
              {products.map((product) => (
                <option key={product.product_id} value={product.product_id}>
                  {product.product_name}
                </option>
              ))}
            </select>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">发布平台 (多选)</label>
            <div className="flex flex-wrap gap-2">
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
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-gray-700">启用场景图像参考</div>
                <p className="text-xs text-gray-500 mt-1">开启后将从场景图像中选择参考图，结合产品图像进行生成</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
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

          <div className="space-y-3">
            <button
              onClick={() => handleGenerate('all')}
              disabled={isGenerating || !selectedProduct || selectedPlatforms.length === 0}
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                isGenerating || !selectedProduct || selectedPlatforms.length === 0
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-indigo-600 text-white hover:bg-indigo-700'
              }`}
            >
              {isGenerating && generatingType === 'all' ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  生成中...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  生成内容
                </>
              )}
            </button>

            <div className="grid grid-cols-2 gap-3">
              <button
                onClick={() => handleGenerate('copywriting')}
                disabled={isGenerating || !selectedProduct || selectedPlatforms.length === 0}
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
                    仅生成文案
                  </>
                )}
              </button>

              <button
                onClick={() => handleGenerate('image')}
                disabled={isGenerating || !selectedProduct || selectedPlatforms.length === 0}
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
                    仅生成图片
                  </>
                )}
              </button>
            </div>

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
                    发布中...
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    发布到 {selectedPlatforms.join(', ')}
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
                {generateStatus.status === 'SUCCESS' ? '生成成功' :
                 generateStatus.status === 'FAILURE' ? '生成失败' : '处理中...'}
              </p>
            </div>
          )}

          {publishStatus && (
            <div className={`p-4 rounded-lg flex items-center gap-2 ${
              publishStatus === 'success' ? 'bg-green-50' : 'bg-red-50'
            }`}>
              {publishStatus === 'success' ? (
                <>
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-700">发布成功</span>
                </>
              ) : (
                <>
                  <span className="font-medium text-red-700">发布失败</span>
                </>
              )}
            </div>
          )}

          {generatedContent && (generatedContent.dimensions || generatedContent.image_prompt) && (
            <div className="border-2 border-red-400 rounded-xl p-4 bg-white">
              {generatedContent.dimensions && (
                <>
                  <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                    <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                    维度信息
                  </h3>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">场景</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.scene}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">光线</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.lighting}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">风格</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.style}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">构图</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.composition}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">细节</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.details}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">画质</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.quality}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-12">视角</span>
                      <span className="text-xs text-gray-800 truncate">{generatedContent.dimensions.viewpoint}</span>
                    </div>
                  </div>
                </>
              )}
              
              {generatedContent.image_prompt && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-600 mb-2">图像提示词</h4>
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
                    <img
                      src={generatedContent.image}
                      alt="Generated"
                      className="w-full aspect-square object-cover rounded-lg shadow-md"
                    />
                  </div>
                )}
                {generatedContent.text && (
                  <div className="w-full max-w-sm">
                    <p className="text-gray-800 text-center leading-relaxed whitespace-pre-wrap">
                      {generatedContent.text}
                    </p>
                  </div>
                )}
                {!generatedContent.image && !generatedContent.text && (
                  <div className="h-full flex flex-col items-center justify-center text-gray-400">
                    <ImageIcon className="w-20 h-20 mb-4" />
                    <p className="text-lg">预览区域</p>
                    <p className="text-sm mt-1">选择产品并点击生成按钮</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <ImageIcon className="w-20 h-20 mb-4" />
                <p className="text-lg">预览区域</p>
                <p className="text-sm mt-1">选择产品并点击生成按钮</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}