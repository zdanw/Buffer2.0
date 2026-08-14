import HelpTooltip from './HelpTooltip';

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
      <HelpTooltip content={tooltip} />
    </div>
  );
}
