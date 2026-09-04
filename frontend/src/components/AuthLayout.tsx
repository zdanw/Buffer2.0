import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Check } from 'lucide-react';
import BrandLogo from '@/components/BrandLogo';
import PostenceWordmark from '@/components/PostenceWordmark';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { useI18n } from '@/i18n/useI18n';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

const PANEL_POINTS = ['auth.panelPoint1', 'auth.panelPoint2', 'auth.panelPoint3'] as const;

export default function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  const { t } = useI18n();

  return (
    <div className="min-h-screen flex bg-canvas">
      <div
        className="hidden lg:flex lg:w-[44%] flex-col justify-between p-10 xl:p-14 border-r border-canvas-border bg-gradient-to-br from-paper-elevated via-canvas to-signal-50/30"
      >
        <div>
          <Link to="/" className="flex items-center gap-3 hover:opacity-90 transition-opacity">
            <BrandLogo size="md" />
            <PostenceWordmark size="lg" />
          </Link>
          <span className="mt-6 inline-flex items-center px-3 py-1 rounded-full bg-white border border-canvas-border text-ink-600 text-xs font-semibold uppercase tracking-wide shadow-sm">
            {t('auth.audienceBadge')}
          </span>
        </div>

        <div className="max-w-md">
          <h2 className="text-2xl xl:text-3xl font-bold tracking-tight leading-tight text-ink-900 font-editorial">
            {t('auth.panelTitle')}
          </h2>
          <p className="mt-4 text-ink-600 text-sm leading-relaxed">{t('auth.panelSubtitle')}</p>

          <ul className="mt-8 space-y-3">
            {PANEL_POINTS.map((key) => (
              <li key={key} className="flex items-start gap-2.5 text-sm text-ink-700">
                <Check className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" strokeWidth={2.5} />
                <span>{t(key)}</span>
              </li>
            ))}
          </ul>

          <div className="mt-8 rounded-xl border border-canvas-border bg-white/80 px-4 py-3 text-sm">
            <span className="font-semibold text-ink-900">{t('auth.panelStat')}</span>
            <span className="text-ink-500"> — {t('auth.panelStatContext')}</span>
          </div>
        </div>

        <p className="text-xs text-ink-400">{t('brand.tagline')}</p>
      </div>

      <div className="flex-1 flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <div className="lg:hidden flex justify-center mb-8">
            <Link to="/" className="flex items-center gap-2.5">
              <BrandLogo size="lg" />
              <PostenceWordmark size="lg" />
            </Link>
          </div>

          <div className="bg-white rounded-2xl shadow-card border border-canvas-border p-8">
            <div className="mb-6">
              <h1 className="text-2xl font-bold tracking-tight text-ink-900">{title}</h1>
              {subtitle && <p className="text-ink-500 mt-1 text-sm leading-relaxed">{subtitle}</p>}
            </div>
            {children}
          </div>

          <div className="mt-6">
            <LanguageSwitcher compact variant="light" />
          </div>
        </div>
      </div>
    </div>
  );
}
