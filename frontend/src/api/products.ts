import axiosInstance from './axiosInstance';

export interface Product {
  product_id: string;
  product_name: string;
  category: string;
  description: string;
  tags: string[];
  brand_voice: string;
  created_at: string;
  updated_at: string;
  product_images: ProductImage[];
  scene_images: ProductImage[];
}

export interface ProductImage {
  image_id: string;
  cdn_url: string;
  phash: string;
  width: number;
  height: number;
  image_type: string;
  uploaded_at: string;
}

export interface ProductCreate {
  product_name: string;
  category: string;
  description?: string;
  tags?: string[];
  brand_voice?: string;
}

export const getProducts = async (): Promise<Product[]> => {
  const response = await axiosInstance.get('/products');
  return response.data;
};

export const getCategories = async (): Promise<string[]> => {
  const response = await axiosInstance.get('/products/categories');
  return response.data.categories;
};

export const getProduct = async (productId: string): Promise<Product> => {
  const response = await axiosInstance.get(`/products/${productId}`);
  return response.data;
};

export const createProduct = async (data: ProductCreate): Promise<Product> => {
  const response = await axiosInstance.post('/products', data);
  return response.data;
};

export const updateProduct = async (productId: string, data: ProductCreate): Promise<Product> => {
  const response = await axiosInstance.put(`/products/${productId}`, data);
  return response.data;
};

export const deleteProduct = async (productId: string): Promise<void> => {
  await axiosInstance.delete(`/products/${productId}`);
};

export const uploadProductImages = async (productId: string, files: File[], imageType: 'product' | 'scene' = 'product'): Promise<{ product_id: string; uploaded: ProductImage[] }> => {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });
  
  const response = await axiosInstance.post(`/products/${productId}/images?image_type=${imageType}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getProductImages = async (productId: string): Promise<{ product_id: string; images: ProductImage[] }> => {
  const response = await axiosInstance.get(`/products/${productId}/images`);
  return response.data;
};

export const deleteProductImage = async (productId: string, imageId: string): Promise<void> => {
  await axiosInstance.delete(`/products/${productId}/images/${imageId}`);
};