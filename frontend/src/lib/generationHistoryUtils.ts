/** Extract product/scene CDN URLs from a reference_manifest JSON blob. */
export function refsFromManifest(manifest?: Record<string, unknown> | null): {
  product: string[];
  scene: string[];
} {
  const items = Array.isArray(manifest?.items)
    ? (manifest.items as Array<{ cdn_url?: string; image_type?: string }>)
    : [];
  const product: string[] = [];
  const scene: string[] = [];
  for (const item of items) {
    const url = item.cdn_url?.trim();
    if (!url) continue;
    if (item.image_type === 'scene') scene.push(url);
    else product.push(url);
  }
  return { product, scene };
}

export function listRunSummary(
  item: { status: string; source: string; credits_charged: number },
  creditsLabel: (n: number) => string,
): string {
  return `${item.status} · ${item.source} · ${creditsLabel(item.credits_charged)}`;
}
