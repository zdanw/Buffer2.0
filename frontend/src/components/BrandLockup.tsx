import BrandLogo from '@/components/BrandLogo';
import PostenceWordmark from '@/components/PostenceWordmark';

type BrandLockupProps = {
  variant?: 'default' | 'inverse';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  wordmarkClassName?: string;
};

/** Icon + wordmark with aligned optical sizing. */
export default function BrandLockup({
  variant = 'default',
  size = 'md',
  className = '',
  wordmarkClassName = '',
}: BrandLockupProps) {
  const iconSize = size === 'sm' ? 'sm' : size === 'lg' ? 'lg' : 'md';
  const wordSize = size;

  return (
    <span className={`inline-flex items-center gap-2.5 min-w-0 ${className}`}>
      <BrandLogo size={iconSize} />
      <PostenceWordmark size={wordSize} variant={variant} className={wordmarkClassName} />
    </span>
  );
}
