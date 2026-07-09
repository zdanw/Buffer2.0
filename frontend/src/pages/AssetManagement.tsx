import { useState, useEffect } from 'react';
import { Plus, Upload, Trash2, Eye, Edit2, X } from 'lucide-react';
import type { Product, ProductCreate } from '@/api/products';
import { getProducts, getProduct, createProduct, updateProduct, deleteProduct, uploadProductImages, deleteProductImage } from '@/api/products';

export default function AssetManagement() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState<ProductCreate>({
    product_name: '',
    category: '',
    description: '',
    selling_points: [],
    brand_voice: '',
  });

  useEffect(() => {
    loadProducts();
  }, []);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const data = await getProducts();
      setProducts(data);
    } catch (error) {
      console.error('Failed to load products:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (isEdit && selectedProduct) {
        const updated = await updateProduct(selectedProduct.product_id, formData);
        setSelectedProduct(updated);
        setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
      } else {
        const created = await createProduct(formData);
        setProducts(prev => [...prev, created]);
      }
      setShowModal(false);
      setFormData({ product_name: '', category: '', description: '', selling_points: [], brand_voice: '' });
    } catch (error) {
      console.error('Failed to save product:', error);
    }
  };

  const handleDelete = async (productId: string) => {
    if (confirm('确定删除该产品及其所有图片吗？')) {
      try {
        await deleteProduct(productId);
        if (selectedProduct?.product_id === productId) {
          setSelectedProduct(null);
        }
        setProducts(prev => prev.filter(p => p.product_id !== productId));
      } catch (error) {
        console.error('Failed to delete product:', error);
      }
    }
  };

  const handleImageUpload = async (e: React.ChangeEvent<HTMLInputElement>, imageType: 'product' | 'scene') => {
    if (!e.target.files || !selectedProduct) return;
    const files = Array.from(e.target.files);
    
    try {
      const response = await uploadProductImages(selectedProduct.product_id, files, imageType);
      if (response.failed && response.failed.length > 0) {
        alert(`${response.uploaded.length} 张图片上传成功，${response.failed.length} 张失败: ${response.failed.join(', ')}`);
      }
    } catch (error) {
      console.error('Failed to upload images:', error);
    } finally {
      const updated = await getProduct(selectedProduct.product_id);
      setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
      setSelectedProduct(updated);
    }
  };

  const handleImageDelete = async (imageId: string) => {
    if (!selectedProduct) return;
    if (confirm('确定删除该图片吗？')) {
      try {
        await deleteProductImage(selectedProduct.product_id, imageId);
      } catch (error) {
        console.error('Failed to delete image:', error);
      } finally {
        const updated = await getProduct(selectedProduct.product_id);
        setProducts(prev => prev.map(p => p.product_id === updated.product_id ? updated : p));
        setSelectedProduct(updated);
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
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">素材管理</h2>
          <p className="text-gray-500 mt-1">管理产品和图片素材</p>
        </div>
        <button
          onClick={() => openModal()}
          className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          添加产品
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-1">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-800 mb-4">产品列表</h3>
            <div className="space-y-2">
              {loading ? (
                <div className="flex justify-center py-8">
                  <div className="w-6 h-6 border-2 border-indigo-600 border-t-transparent rounded-full animate-spin"></div>
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
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                  >
                    <Trash2 className="w-5 h-5" />
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
                    <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                      <Upload className="w-4 h-4" />
                      <span>上传产品图像</span>
                      <input
                        type="file"
                        multiple
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e, 'product')}
                        className="hidden"
                      />
                    </label>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-3">产品图像</h4>
                    <div className="grid grid-cols-3 gap-3">
                      {(Array.isArray(selectedProduct.product_images) ? selectedProduct.product_images : []).map((image) => (
                        <div key={image.image_id} className="relative group">
                          <img
                            src={image.cdn_url}
                            alt=""
                            className="w-full aspect-square object-cover rounded-lg"
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                            <button className="p-2 bg-white rounded-full text-gray-800 hover:bg-gray-100">
                              <Eye className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleImageDelete(image.image_id)}
                              className="p-2 bg-white rounded-full text-red-600 hover:bg-red-100"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="mb-3">
                    <label className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer">
                      <Upload className="w-4 h-4" />
                      <span>上传场景图像</span>
                      <input
                        type="file"
                        multiple
                        accept="image/*"
                        onChange={(e) => handleImageUpload(e, 'scene')}
                        className="hidden"
                      />
                    </label>
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-800 mb-3">场景图像</h4>
                    <div className="grid grid-cols-3 gap-3">
                      {(Array.isArray(selectedProduct.scene_images) ? selectedProduct.scene_images : []).map((image) => (
                        <div key={image.image_id} className="relative group">
                          <img
                            src={image.cdn_url}
                            alt=""
                            className="w-full aspect-square object-cover rounded-lg"
                          />
                          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                            <button className="p-2 bg-white rounded-full text-gray-800 hover:bg-gray-100">
                              <Eye className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleImageDelete(image.image_id)}
                              className="p-2 bg-white rounded-full text-red-600 hover:bg-red-100"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">产品名称</label>
                  <input
                    type="text"
                    value={formData.product_name}
                    onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
                  <input
                    type="text"
                    value={formData.category}
                    onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    rows={3}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">卖点</label>
                  <input
                    type="text"
                    value={(formData.selling_points || []).join(',')}
                    onChange={(e) => setFormData({ ...formData, selling_points: e.target.value.split(',').map(t => t.trim()) })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="用逗号分隔"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">品牌调性</label>
                  <input
                    type="text"
                    value={formData.brand_voice}
                    onChange={(e) => setFormData({ ...formData, brand_voice: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  {isEdit ? '保存修改' : '添加产品'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function Image(props: { className?: string }) {
  return (
    <svg className={props.className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}