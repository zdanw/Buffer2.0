import { HelpCircle } from 'lucide-react';

type LabelWithTooltipProps = {
  label: string;
  tooltip: string;
  htmlFor?: string;
};

export default function LabelWithTooltip({ label, tooltip, htmlFor }: LabelWithTooltipProps) {
  return (
    <div className="mb-1 flex items-center gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      <span className="group relative inline-flex">
        <button
          type="button"
          tabIndex={0}
          className="rounded text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          aria-label={tooltip}
        >
          <HelpCircle className="h-4 w-4" />
        </button>
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-lg bg-gray-900 px-3 py-2 text-left text-xs leading-relaxed text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
        >
          {tooltip}
        </span>
      </span>
    </div>
  );
}
