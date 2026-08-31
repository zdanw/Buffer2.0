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
    <div className="mb-1 flex items-baseline gap-1 flex-wrap">
      <label htmlFor={htmlFor} className="text-sm font-medium text-gray-700 inline-flex items-baseline gap-0.5">
        {label}
        {required === true ? <FieldRequirementBadge required /> : null}
      </label>
      {required === false ? <FieldRequirementBadge required={false} /> : null}
      <HelpTooltip content={tooltip} />
    </div>
  );
}
