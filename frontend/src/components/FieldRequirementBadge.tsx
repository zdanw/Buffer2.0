import { useI18n } from '@/i18n/useI18n';

type FieldRequirementBadgeProps = {
  required: boolean;
};

export default function FieldRequirementBadge({ required }: FieldRequirementBadgeProps) {
  const { t } = useI18n();
  return (
    <span
      className={`text-xs font-normal ${required ? 'text-red-600' : 'text-gray-400'}`}
      aria-hidden
    >
      {required ? t('common.fieldRequired') : t('common.fieldOptional')}
    </span>
  );
}
