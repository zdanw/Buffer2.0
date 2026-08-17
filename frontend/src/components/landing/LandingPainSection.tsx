import { ArrowRight, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useI18n } from '@/i18n/useI18n';

const PAIN_KEYS = ['landing.pain1', 'landing.pain2', 'landing.pain3'] as const;

export default function LandingPainSection() {
  const { t } = useI18n();

  return (
    <section className="relative py-14 sm:py-16 bg-white border-b border-canvas-border">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-14 items-center">
          <div>
            <p className="text-sm font-semibold text-forge-600 uppercase tracking-wider mb-3">
              {t('landing.painEyebrow')}
            </p>
            <h2 className="text-2xl sm:text-3xl font-bold text-ink-900 tracking-tight">
              {t('landing.painTitle')}
            </h2>
            <ul className="mt-6 space-y-4">
              {PAIN_KEYS.map((key) => (
                <li key={key} className="flex gap-3 text-ink-600">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-500">
                    <X className="w-3.5 h-3.5" strokeWidth={2.5} />
                  </span>
                  <span className="text-sm sm:text-base leading-relaxed">{t(key)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-forge-100 bg-gradient-to-br from-forge-50 to-white p-6 sm:p-8 shadow-card">
            <p className="text-sm font-semibold text-forge-700 uppercase tracking-wide mb-2">
              {t('landing.solutionEyebrow')}
            </p>
            <h3 className="text-xl sm:text-2xl font-bold text-ink-900 leading-snug">
              {t('landing.solutionTitle')}
            </h3>
            <p className="mt-3 text-ink-600 text-sm sm:text-base leading-relaxed">
              {t('landing.solutionBody')}
            </p>
            <Link
              to="/signup"
              className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-forge-600 hover:text-forge-700"
            >
              {t('landing.solutionCta')}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
