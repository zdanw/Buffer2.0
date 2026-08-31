import { Link } from 'react-router-dom';
import BrandLogo from '@/components/BrandLogo';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { useI18n } from '@/i18n/useI18n';

const PRODUCT_LINKS = [
  { href: '#showcase', labelKey: 'landing.navShowcase' },
  { href: '#for-teams', labelKey: 'landing.navForTeams' },
  { href: '#how-it-works', labelKey: 'landing.navHow' },
] as const;

export default function LandingFooter() {
  const { t } = useI18n();
  const year = new Date().getFullYear();

  return (
    <footer className="border-t border-canvas-border bg-white pb-24 sm:pb-0" role="contentinfo">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-12 sm:py-14">
        <div className="grid gap-10 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2 lg:col-span-2">
            <Link to="/" className="inline-flex items-center gap-2.5">
              <BrandLogo size="md" />
              <span className="font-bold text-lg tracking-tight text-ink-900">{t('brand.name')}</span>
            </Link>
            <p className="mt-4 text-sm text-ink-500 leading-relaxed max-w-md">
              {t('landing.footerDescription')}
            </p>
            <p className="mt-3 text-xs text-ink-400 leading-relaxed max-w-md">
              {t('landing.footerPlatforms')}
            </p>
          </div>

          <nav aria-label={t('landing.footerProductNav')}>
            <h2 className="text-sm font-semibold text-ink-900">{t('landing.footerProductHeading')}</h2>
            <ul className="mt-4 space-y-2.5">
              {PRODUCT_LINKS.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    className="text-sm text-ink-500 hover:text-forge-600 transition-colors"
                  >
                    {t(link.labelKey)}
                  </a>
                </li>
              ))}
            </ul>
          </nav>

          <nav aria-label={t('landing.footerAccountNav')}>
            <h2 className="text-sm font-semibold text-ink-900">{t('landing.footerAccountHeading')}</h2>
            <ul className="mt-4 space-y-2.5">
              <li>
                <Link
                  to="/signup"
                  className="text-sm text-ink-500 hover:text-forge-600 transition-colors"
                >
                  {t('landing.getStarted')}
                </Link>
              </li>
              <li>
                <Link
                  to="/login"
                  className="text-sm text-ink-500 hover:text-forge-600 transition-colors"
                >
                  {t('landing.signIn')}
                </Link>
              </li>
            </ul>
          </nav>
        </div>

        <div className="mt-10 pt-6 border-t border-canvas-border flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs text-ink-400 text-center sm:text-left">
            {t('landing.footerCopyright', { year })}
          </p>
          <LanguageSwitcher compact variant="light" />
        </div>
      </div>
    </footer>
  );
}
