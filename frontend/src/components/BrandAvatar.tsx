interface BrandAvatarProps {
  name: string;
  logoUrl?: string | null;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'h-8 w-8 text-xs',
  md: 'h-10 w-10 text-sm',
  lg: 'h-12 w-12 text-base',
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export default function BrandAvatar({ name, logoUrl, size = 'md', className = '' }: BrandAvatarProps) {
  const sizeClass = sizeClasses[size];

  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt=""
        className={`${sizeClass} rounded-lg object-cover border border-gray-200 bg-white shrink-0 ${className}`}
      />
    );
  }

  return (
    <span
      className={`${sizeClass} inline-flex items-center justify-center rounded-lg bg-forge-100 text-forge-700 font-semibold shrink-0 ${className}`}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}
