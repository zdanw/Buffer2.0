type BrandLogoProps = {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  imageClassName?: string;
};

const sizeClasses = {
  sm: 'h-7 w-7',
  md: 'h-9 w-9',
  lg: 'h-12 w-12',
  xl: 'h-16 w-16',
} as const;

export default function BrandLogo({
  size = 'md',
  className = '',
  imageClassName = '',
}: BrandLogoProps) {
  return (
    <img
      src="/pulseforge-logo.png"
      alt="PulseForge"
      className={`rounded-lg object-contain bg-white shadow-sm ${sizeClasses[size]} ${className} ${imageClassName}`}
    />
  );
}
