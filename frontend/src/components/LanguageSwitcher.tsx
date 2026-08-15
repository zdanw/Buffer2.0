import { useI18n } from '@/i18n/useI18n';
import type { Locale } from '@/i18n/types';
import VersionLabel from './VersionLabel';

const OPTIONS: { value: Locale; labelKey: string }[] = [
  { value: 'en', labelKey: 'common.english' },
  { value: 'zh', labelKey: 'common.chinese' },
];

type LanguageSwitcherProps = {
  compact?: boolean;
  variant?: 'sidebar' | 'light';
};

export default function LanguageSwitcher({ compact = false, variant = 'sidebar' }: LanguageSwitcherProps) {
  const { locale, setLocale, t } = useI18n();
  const isLight = variant === 'light';

  return (
    <div className={compact ? '' : isLight ? 'mt-4 border-t border-gray-200 pt-4' : 'mt-4 border-t border-white/10 pt-4'}>
      {!compact && (
        <p className={`mb-2 text-center text-xs ${isLight ? 'text-gray-500' : 'text-indigo-400'}`}>
          {t('common.language')}
        </p>
      )}
      <div className={`flex rounded-lg p-1 ${isLight ? 'bg-gray-100' : 'bg-white/5'}`}>
        {OPTIONS.map((opt) => {
          const active = locale === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => setLocale(opt.value)}
              className={`flex-1 rounded-md px-2 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? isLight
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'bg-white/15 text-white shadow-sm'
                  : isLight
                    ? 'text-gray-600 hover:bg-white/60'
                    : 'text-indigo-300 hover:bg-white/5 hover:text-white'
              }`}
            >
              {t(opt.labelKey)}
            </button>
          );
        })}
      </div>
      <VersionLabel variant={variant} />
    </div>
  );
}
