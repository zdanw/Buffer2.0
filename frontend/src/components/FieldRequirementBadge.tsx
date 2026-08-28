import { useI18n } from '@/i18n/useI18n';

type FieldRequirementBadgeProps = {
  required: boolean;
};

/** Subtle required/optional marker shared across all forms. */
export default function FieldRequirementBadge({ required }: FieldRequirementBadgeProps) {
  const { t } = useI18n();

  if (required) {
    return (
      <>
        <span className="text-gray-400 font-normal leading-none select-none" aria-hidden>
          *
        </span>
        <span className="sr-only">{t('common.fieldRequired')}</span>
      </>
    );
  }

  return (
    <span className="text-[11px] font-normal text-gray-400 leading-none select-none">
      ({t('common.fieldOptional')})
    </span>
  );
}
