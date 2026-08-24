export type LogoInImages = 'preserve' | 'omit' | 'composite';

export function resolveEffectiveLogoMode(
  brand?: { logo_in_images?: string | null } | null,
  product?: { has_on_body_branding?: boolean } | null,
): LogoInImages {
  if (product?.has_on_body_branding === false) return 'omit';
  const mode = (brand?.logo_in_images || 'preserve') as LogoInImages;
  if (mode === 'omit' || mode === 'composite') return mode;
  return 'preserve';
}
