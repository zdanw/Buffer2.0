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
    <label htmlFor={htmlFor} className={className}>
      {label}
      <FieldRequirementBadge required={required} />
    </label>
  );
}
