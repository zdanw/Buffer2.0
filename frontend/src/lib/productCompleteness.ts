import type { Product } from '@/api/products';

export function isProductIncomplete(product: Product): boolean {
  const images = product.product_images;
  return !Array.isArray(images) || images.length === 0;
}

export function productImageCount(product: Product): number {
  return Array.isArray(product.product_images) ? product.product_images.length : 0;
}
