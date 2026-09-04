import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import BrandLogo from '@/components/BrandLogo';
import PostenceWordmark from '@/components/PostenceWordmark';
import LandingFooter from '@/components/landing/LandingFooter';
import LandingBentoGrid from '@/components/landing/LandingBentoGrid';
import LandingHeroVisual from '@/components/landing/LandingHeroVisual';
import LandingMarquee from '@/components/landing/LandingMarquee';
import LandingPainSection from '@/components/landing/LandingPainSection';
import LandingAudienceSection from '@/components/landing/LandingAudienceSection';
import { useI18n } from '@/i18n/useI18n';
import { usePageMeta } from '@/hooks/usePageMeta';

export default function Landing() {
  const { t } = useI18n();
  const [heroTitleKey] = useState<'landing.heroTitle1'>('landing.heroTitle1');

  usePageMeta({
    title: 'Postence — AI social presence system',
    description:
      'Postence learns your brand, finds what is worth saying, and turns ideas into platform-native social content for Instagram, TikTok, and Facebook—with review and publishing control.',
    canonicalPath: '/',
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: 'Postence',
      applicationCategory: 'BusinessApplication',
      description:
        'AI social presence system that turns company knowledge into continuous, platform-native content.',
    },
  });

  return (
    <div className="min-h-screen bg-paper text-ink-900">
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        <div className="absolute top-[-12%] right-[-8%] w-[50%] h-[40%] rounded-full bg-signal-50/60 blur-[100px] animate-landing-glow" />
        <div className="absolute bottom-[-8%] left-[-8%] w-[40%] h-[35%] rounded-full bg-forge-100/40 blur-[90px] animate-landing-float-slow" />
      </div>

      <header className="sticky top-0 z-50 border-b border-canvas-border bg-paper-elevated/90 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3.5 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2 shrink-0 min-w-0">
            <BrandLogo size="md" />
            <PostenceWordmark size="lg" className="hidden sm:inline-flex" />
          </Link>
          <nav className="hidden md:flex items-center gap-6 text-sm text-ink-500">
            <a href="#showcase" className="hover:text-ink-900 transition-colors">{t('landing.navShowcase')}</a>
            <a href="#for-teams" className="hover:text-ink-900 transition-colors">{t('landing.navForTeams')}</a>
            <a href="#how-it-works" className="hover:text-ink-900 transition-colors">{t('landing.navHow')}</a>
          </nav>
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="hidden sm:inline text-sm font-medium text-ink-600 hover:text-ink-900 px-3 py-2 transition-colors"
            >
              {t('landing.signIn')}
            </Link>
            <Link
              to="/signup"
              className="text-sm font-semibold bg-forge-500 text-white px-4 py-2.5 rounded-lg hover:bg-forge-600 transition-all shadow-md shadow-forge-500/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 focus-visible:ring-offset-2"
            >
              {t('landing.getStarted')}
            </Link>
          </div>
        </div>
      </header>

      <section className="relative">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-12 pb-12 sm:pt-16 lg:pt-20 lg:pb-16">
          <div className="grid lg:grid-cols-2 gap-10 lg:gap-14 items-center">
            <div className="relative z-10">
              <p className="text-sm font-semibold text-forge-600 tracking-wide mb-4">
                {t('brand.tagline')}
              </p>
              <h1 className="text-fluid-4xl sm:text-fluid-5xl font-bold tracking-tight leading-[1.08] text-ink-900">
                {t(heroTitleKey)}
              </h1>
              <p className="mt-5 text-fluid-lg text-ink-500 leading-relaxed max-w-lg">
                {t('landing.heroSubtitle')}
              </p>

              <div className="mt-8">
                <Link
                  to="/signup"
                  className="inline-flex items-center justify-center gap-2 bg-forge-500 text-white font-semibold px-7 py-3.5 rounded-xl hover:bg-forge-600 transition-all text-base shadow-lg shadow-forge-500/20 hover:scale-[1.02] active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 focus-visible:ring-offset-2"
                >
                  {t('landing.getStarted')}
                  <ArrowRight className="w-5 h-5" />
                </Link>
                <p className="mt-4 text-sm text-ink-400">{t('landing.heroTrustLine')}</p>
              </div>
            </div>

            <div className="relative z-10 lg:pl-4 flex items-center justify-center">
              <LandingHeroVisual />
            </div>
          </div>
        </div>

        <LandingMarquee className="relative z-20" />
      </section>

      <LandingPainSection />
      <LandingAudienceSection />

      <section id="showcase" className="relative py-16 sm:py-20 bg-paper-elevated border-y border-canvas-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
            <div>
              <h2 className="text-fluid-2xl sm:text-fluid-3xl font-bold tracking-tight text-ink-900">
                {t('landing.showcaseTitle')}
              </h2>
              <p className="text-ink-500 mt-2 max-w-xl">{t('landing.showcaseSubtitle')}</p>
            </div>
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 text-sm font-semibold text-forge-600 hover:text-forge-700 transition-colors shrink-0"
            >
              {t('landing.exploreAll')}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
          <LandingBentoGrid />
        </div>
      </section>

      <section className="relative py-14 sm:py-16 overflow-hidden bg-midnight text-white">
        <div className="absolute inset-0 opacity-30 pointer-events-none" aria-hidden="true">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[300px] rounded-full bg-signal-500/20 blur-[100px]" />
        </div>
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 text-center">
          <p className="text-sm font-medium text-ink-400 mb-4 uppercase tracking-wider">
            {t('landing.socialProof')}
          </p>
          <blockquote className="max-w-2xl mx-auto">
            <p className="text-fluid-2xl sm:text-fluid-3xl text-white font-semibold leading-relaxed">
              &ldquo;{t('landing.testimonialQuote')}&rdquo;
            </p>
            <footer className="mt-4 text-sm text-ink-400">{t('landing.testimonialAuthor')}</footer>
          </blockquote>
        </div>
      </section>

      <section id="how-it-works" className="py-16 sm:py-20 bg-paper">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="text-fluid-2xl sm:text-fluid-3xl font-bold text-ink-900">{t('landing.howTitle')}</h2>
          <p className="text-ink-500 mt-2 max-w-xl mx-auto">{t('landing.howSubtitle')}</p>
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            {[
              { n: '01', key: 'landing.step1Title' },
              { n: '02', key: 'landing.step2Title' },
              { n: '03', key: 'landing.step3Title' },
              { n: '04', key: 'landing.step4Title' },
            ].map((step) => (
              <div
                key={step.key}
                className="px-5 py-3 rounded-xl border border-canvas-border bg-paper-elevated text-sm font-semibold text-ink-700 hover:border-signal-200 hover:bg-signal-50/50 transition-colors"
              >
                <span className="text-forge-600 mr-2">{step.n}</span>
                {t(step.key)}
              </div>
            ))}
          </div>
          <Link
            to="/signup"
            className="mt-10 inline-flex items-center gap-2 bg-forge-500 text-white font-semibold px-8 py-3.5 rounded-xl hover:bg-forge-600 transition-colors shadow-md shadow-forge-500/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 focus-visible:ring-offset-2"
          >
            {t('landing.getStarted')}
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      <section className="relative overflow-hidden border-t border-canvas-border bg-midnight">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20 text-center">
          <h2 className="text-fluid-3xl sm:text-fluid-4xl font-bold tracking-tight text-white">
            {t('landing.ctaTitle')}
          </h2>
          <p className="text-ink-400 mt-4 max-w-md mx-auto">{t('landing.ctaSubtitle')}</p>
          <Link
            to="/signup"
            className="mt-8 inline-flex items-center gap-2 bg-forge-500 text-white font-semibold px-10 py-4 rounded-xl hover:bg-forge-600 transition-all text-base shadow-lg shadow-forge-500/25 hover:scale-[1.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-500 focus-visible:ring-offset-2 focus-visible:ring-offset-midnight"
          >
            {t('landing.getStarted')}
            <ArrowRight className="w-5 h-5" />
          </Link>
          <p className="mt-4 text-xs text-ink-500">{t('landing.heroNote')}</p>
        </div>
      </section>

      <LandingFooter />

      <div className="fixed bottom-0 inset-x-0 z-40 p-3 bg-paper-elevated/95 border-t border-canvas-border backdrop-blur sm:hidden">
        <Link
          to="/signup"
          className="flex items-center justify-center gap-2 w-full bg-forge-500 text-white font-semibold py-3 rounded-xl shadow-lg shadow-forge-500/20"
        >
          {t('landing.stickyCta')}
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
