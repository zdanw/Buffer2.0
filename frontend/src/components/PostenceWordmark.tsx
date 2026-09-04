type PostenceWordmarkProps = {
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  variant?: 'default' | 'inverse';
};

/** Wordmark height tuned to align cap-height with icon lockup. */
const heightClasses = {
  sm: 'h-[17px]',
  md: 'h-[20px]',
  lg: 'h-[23px]',
  xl: 'h-[26px]',
} as const;

export default function PostenceWordmark({
  className = '',
  size = 'md',
  variant = 'default',
}: PostenceWordmarkProps) {
  const src =
    variant === 'inverse'
      ? '/brand/postence-wordmark-inverse.png'
      : '/brand/postence-wordmark.png';

  return (
    <img
      src={src}
      alt="Postence"
      className={`w-auto shrink-0 object-contain ${heightClasses[size]} ${className}`}
      draggable={false}
    />
  );
}
