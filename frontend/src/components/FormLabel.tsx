import FieldRequirementBadge from './FieldRequirementBadge';

type FormLabelProps = {
  label: string;
  htmlFor?: string;
  required: boolean;
  className?: string;
};

export default function FormLabel({
  label,
  htmlFor,
  required,
  className = 'mb-1 flex items-center gap-1.5 text-sm font-medium text-gray-700',
}: FormLabelProps) {
  return (
    <label htmlFor={htmlFor} className={`${className} inline-flex items-baseline flex-wrap gap-x-1 gap-y-0.5`}>
      <span className="inline-flex items-baseline gap-0.5">
        {label}
        {required ? <FieldRequirementBadge required /> : null}
      </span>
      {!required ? <FieldRequirementBadge required={false} /> : null}
    </label>
  );
}
