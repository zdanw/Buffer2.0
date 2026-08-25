import { useI18n } from '@/i18n/useI18n';

const SPINNER_SIZE = {
  sm: 'h-5 w-5 border',
  md: 'h-9 w-9 border-2',
  lg: 'h-12 w-12 border-2',
} as const;

interface LoadingIndicatorProps {
  size?: keyof typeof SPINNER_SIZE;
  /** Pass false to hide the caption. */
  label?: string | false;
  className?: string;
}

export default function LoadingIndicator({
  size = 'md',
  label,
  className = '',
}: LoadingIndicatorProps) {
  const { t } = useI18n();
  const caption = label === false ? null : (label ?? t('common.loading'));

  return (
    <div className={`flex flex-col items-center gap-3 ${className}`} role="status" aria-live="polite">
      <div
        className={`${SPINNER_SIZE[size]} rounded-full border-forge-200 border-t-forge-600 animate-spin`}
        aria-hidden
      />
      {caption ? <p className="text-sm text-ink-500">{caption}</p> : null}
    </div>
  );
}
