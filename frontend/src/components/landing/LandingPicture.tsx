type LandingAsset = 'hero' | 'workflow';

const META: Record<
  LandingAsset,
  { webp: string; fallback: string; fallbackType: 'jpeg' | 'png'; width: number; height: number }
> = {
  hero: {
    webp: '/landing/hero.webp',
    fallback: '/landing/hero.jpg',
    fallbackType: 'jpeg',
    width: 1024,
    height: 576,
  },
  workflow: {
    webp: '/landing/workflow.webp',
    fallback: '/landing/workflow.png',
    fallbackType: 'png',
    width: 1920,
    height: 1080,
  },
};

interface LandingPictureProps {
  asset: LandingAsset;
  className?: string;
  alt?: string;
  loading?: 'lazy' | 'eager';
}

/** WebP-first landing imagery with optimized fallbacks */
export default function LandingPicture({
  asset,
  className = '',
  alt = '',
  loading = 'lazy',
}: LandingPictureProps) {
  const { webp, fallback, width, height } = META[asset];

  return (
    <picture>
      <source srcSet={webp} type="image/webp" />
      <img
        src={fallback}
        alt={alt}
        width={width}
        height={height}
        loading={loading}
        decoding="async"
        className={className}
      />
    </picture>
  );
}
