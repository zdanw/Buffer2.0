import FieldRequirementBadge from './FieldRequirementBadge';
import HelpTooltip from './HelpTooltip';

type LabelWithTooltipProps = {
  label: string;
  tooltip: string;
  htmlFor?: string;
  required?: boolean;
};

export default function LabelWithTooltip({
  label,
  tooltip,
  htmlFor,
  required,
}: LabelWithTooltipProps) {
  return (
    <div className="mb-1 flex items-center gap-1.5 flex-wrap">
      <label htmlFor={htmlFor} className="text-sm font-medium text-gray-700">
        {label}
      </label>
      {required !== undefined ? <FieldRequirementBadge required={required} /> : null}
      <HelpTooltip content={tooltip} />
    </div>
  );
}
