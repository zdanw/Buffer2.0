import { Building2, Rocket, Users } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

const AUDIENCES = [
  { icon: Building2, titleKey: 'landing.audience1Title', descKey: 'landing.audience1Desc' },
  { icon: Rocket, titleKey: 'landing.audience2Title', descKey: 'landing.audience2Desc' },
  { icon: Users, titleKey: 'landing.audience3Title', descKey: 'landing.audience3Desc' },
] as const;

export default function LandingAudienceSection() {
  const { t } = useI18n();

  return (
    <section id="for-teams" className="py-14 sm:py-16 bg-paper border-b border-canvas-border">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="text-center max-w-2xl mx-auto mb-10">
          <p className="text-sm font-semibold text-forge-600 uppercase tracking-wider mb-2">
            {t('landing.audienceEyebrow')}
          </p>
          <h2 className="text-2xl sm:text-3xl font-bold text-ink-900 tracking-tight">
            {t('landing.audienceTitle')}
          </h2>
          <p className="mt-3 text-ink-500">{t('landing.audienceSubtitle')}</p>
        </div>

        <div className="grid sm:grid-cols-3 gap-4 sm:gap-6">
          {AUDIENCES.map(({ icon: Icon, titleKey, descKey }) => (
            <div
              key={titleKey}
              className="rounded-2xl border border-canvas-border bg-white p-5 sm:p-6 shadow-card hover:border-forge-200 transition-colors"
            >
              <div className="w-10 h-10 rounded-xl bg-forge-50 border border-forge-100 flex items-center justify-center mb-4">
                <Icon className="w-5 h-5 text-forge-600" strokeWidth={1.75} />
              </div>
              <h3 className="font-bold text-ink-900 text-sm sm:text-base">{t(titleKey)}</h3>
              <p className="mt-2 text-ink-500 text-sm leading-relaxed">{t(descKey)}</p>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-sm text-ink-400 max-w-xl mx-auto">
          {t('landing.urgencyNote')}
        </p>
      </div>
    </section>
  );
}
