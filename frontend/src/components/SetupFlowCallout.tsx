import { ArrowRight, ExternalLink } from 'lucide-react';

interface SetupFlowCalloutProps {
  title: string;
  description: string;
  actionLabel: string;
  onAction: () => void;
  learnMoreUrl?: string;
  learnMoreLabel?: string;
  variant?: 'info' | 'warning';
  openActionInNewTab?: boolean;
}

export default function SetupFlowCallout({
  title,
  description,
  actionLabel,
  onAction,
  learnMoreUrl,
  learnMoreLabel,
  variant = 'info',
  openActionInNewTab = false,
}: SetupFlowCalloutProps) {
  const styles =
    variant === 'warning'
      ? 'border-amber-200 bg-amber-50 text-amber-900'
      : 'border-forge-200 bg-forge-50 text-forge-900';

  return (
    <div className={`rounded-lg border p-3 text-sm ${styles}`}>
      <p className="font-medium">{title}</p>
      <p className="mt-1 text-xs leading-relaxed opacity-90">{description}</p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={onAction}
          className="inline-flex items-center gap-1.5 rounded-lg bg-forge-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-forge-700"
        >
          {actionLabel}
          {openActionInNewTab ? (
            <ExternalLink className="h-3.5 w-3.5" />
          ) : (
            <ArrowRight className="h-3.5 w-3.5" />
          )}
        </button>
        {learnMoreUrl && learnMoreLabel && (
          <a
            href={learnMoreUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-forge-700 hover:text-forge-800 underline-offset-2 hover:underline"
          >
            {learnMoreLabel}
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </div>
  );
}
