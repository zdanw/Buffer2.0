import { useState, useEffect } from 'react';
import { Play, RefreshCw, Image as ImageIcon, FileText, Image } from 'lucide-react';
import type { Product } from '@/api/products';
import { getProducts } from '@/api/products';
import { generateContent, generateCopywriting, generateImage, getGenerateStatus } from '@/api/generate';
import type { GenerateRequest, GenerateStatus } from '@/api/generate';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];

export default function ContentPreview() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<string>('');
  const [platform, setPlatform] = useState('instagram');
  const [useSceneReference, setUseSceneReference] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatingType, setGeneratingType] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [generateStatus, setGenerateStatus] = useState<GenerateStatus | null>(null);
  const [generatedContent, setGeneratedContent] = useState<{ text: string; image: string } | null>(null);

  useEffect(() => {
    loadProducts();
  }, []);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>;
    if (taskId && isGenerating) {
      interval = setInterval(async () => {
        try {
          const status = await getGenerateStatus(taskId);
          setGenerateStatus(status);
          
          if (status.status === 'SUCCESS') {
            setIsGenerating(false);
            clearInterval(interval);
            if (status.result) {
              setGeneratedContent({
                text: status.result.text || generatedContent?.text || '',
                image: status.result.image || generatedContent?.image || ''
              });
            }
          } else if (status.status === 'FAILURE') {
            setIsGenerating(false);
            clearInterval(interval);
          }
        } catch (error) {
          console.error('Failed to check status:', error);
        }
      }, 3000);
    }
    return () => clearInterval(interval);
  }, [taskId, isGenerating, generatedContent]);

  const loadProducts = async () => {
    try {
      const data = await getProducts();
      setProducts(data);
      if (data.length > 0) {
        setSelectedProduct(data[0].product_id);
      }
    } catch (error) {
      console.error('Failed to load products:', error);
    }
  };

  const handleGenerate = async (type: 'all' | 'copywriting' | 'image') => {
    if (!selectedProduct) return;
    
    setIsGenerating(true);
    setGeneratingType(type);
    
    if (type === 'copywriting') {
      setGeneratedContent(prev => ({ text: '', image: prev?.image || '' }));
    } else if (type === 'image') {
      setGeneratedContent(prev => ({ text: prev?.text || '', image: '' }));
    } else {
      setGeneratedContent(null);
    }
    
    setGenerateStatus(null);

    try {
      const request: GenerateRequest = {
        product_id: selectedProduct,
        platform,
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
    }
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
            <label className="block text-sm font-medium text-gray-700 mb-2">发布平台</label>
            <div className="flex flex-wrap gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPlatform(p)}
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                    platform === p
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm font-medium text-gray-700">启用场景图像参考</span>
              <button
                onClick={() => setUseSceneReference(!useSceneReference)}
                className={`relative w-12 h-6 rounded-full transition-colors ${
                  useSceneReference ? 'bg-indigo-600' : 'bg-gray-300'
                }`}
              >
                <span
                  className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                    useSceneReference ? 'translate-x-7' : 'translate-x-1'
                  }`}
                />
              </button>
            </label>
            <p className="text-xs text-gray-500 mt-2">开启后将从场景图像中选择参考图，结合产品图像进行生成</p>
          </div>

          <div className="space-y-3">
            <button
              onClick={() => handleGenerate('all')}
              disabled={isGenerating || !selectedProduct}
              className={`w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                isGenerating || !selectedProduct
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
                disabled={isGenerating || !selectedProduct}
                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  isGenerating || !selectedProduct
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
                disabled={isGenerating || !selectedProduct}
                className={`flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all ${
                  isGenerating || !selectedProduct
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