type BrandLogoProps = {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
};

const sizeClasses = {
  sm: 'h-7 w-7',
  md: 'h-9 w-9',
  lg: 'h-12 w-12',
  xl: 'h-16 w-16',
} as const;

/** Compact P monogram with signal accent — used in nav, auth, and favicon contexts. */
export default function BrandLogo({
  size = 'md',
  className = '',
}: BrandLogoProps) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 ${sizeClasses[size]} ${className}`}
      role="img"
      aria-label="Postence"
    >
      <rect width="32" height="32" rx="7" fill="#0B0D14" />
      <path
        d="M9 8h7.5c3.6 0 6 2.2 6 5.5S20.1 19 16.5 19H13v5H9V8z"
        fill="#F5F1E8"
      />
      <path
        d="M13 12.5h4c1.8 0 3 1 3 2.5s-1.2 2.5-3 2.5h-4v-5z"
        fill="#0B0D14"
      />
      <path
        d="M22 22.5c2.5 0 4.5-1.2 4.5-3.5"
        stroke="#FF4D3D"
        strokeWidth="1.5"
        strokeLinecap="round"
        className="animate-landing-signal"
      />
      <circle cx="26.5" cy="18.5" r="1.25" fill="#406BFF" />
    </svg>
  );
}
