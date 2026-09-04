type BrandLogoProps = {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'filled';
  className?: string;
};

const sizeClasses = {
  sm: 'h-7 w-7',
  md: 'h-8 w-8',
  lg: 'h-9 w-9',
  xl: 'h-10 w-10',
} as const;

const iconSrc = {
  default: '/brand/postence-icon.png',
  filled: '/brand/postence-icon-filled.png',
} as const;

/** Postence monogram — default for marketing, filled for in-app chrome. */
export default function BrandLogo({
  size = 'md',
  variant = 'default',
  className = '',
}: BrandLogoProps) {
  return (
    <img
      src={iconSrc[variant]}
      alt=""
      aria-hidden="true"
      className={`shrink-0 object-contain ${sizeClasses[size]} ${className}`}
      draggable={false}
    />
  );
}
