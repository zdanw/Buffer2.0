import { useI18n } from '@/i18n/useI18n';

interface BrandInheritanceHintProps {
  voice?: string | null;
  className?: string;
}

export default function BrandInheritanceHint({ voice, className = '' }: BrandInheritanceHintProps) {
  const { t } = useI18n();
  if (!voice?.trim()) {
    return (
      <p className={`text-xs text-gray-400 ${className}`}>
        {t('brands.noVoiceInherited')}
      </p>
    );
  }
  return (
    <p className={`text-xs text-gray-500 ${className}`}>
      {t('brands.inheritedVoice', { voice })}
    </p>
  );
}
