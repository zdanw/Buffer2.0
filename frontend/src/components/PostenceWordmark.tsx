type PostenceWordmarkProps = {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
};

const sizeClasses = {
  sm: 'text-base',
  md: 'text-lg',
  lg: 'text-xl',
} as const;

/**
 * Typographic wordmark: subtle weight transition at the post→presence seam (T→E).
 * The signal underline marks the internal name concept without splitting the word.
 */
export default function PostenceWordmark({
  className = '',
  size = 'md',
}: PostenceWordmarkProps) {
  return (
    <span
      className={`inline-flex items-baseline font-bold tracking-tight text-ink-900 ${sizeClasses[size]} ${className}`}
      aria-label="Postence"
    >
      <span className="font-semibold">Post</span>
      <span className="relative font-bold">
        ence
        <span
          className="absolute -bottom-0.5 left-0 right-0 h-[2px] rounded-full bg-gradient-to-r from-forge-500 via-signal-500 to-transparent"
          aria-hidden="true"
        />
      </span>
    </span>
  );
}
