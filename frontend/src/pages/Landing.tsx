import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import BrandLogo from '@/components/BrandLogo';
import LandingFooter from '@/components/landing/LandingFooter';
import LandingBentoGrid from '@/components/landing/LandingBentoGrid';
import LandingHeroVisual from '@/components/landing/LandingHeroVisual';
import { pickRandomHeroTitleKey } from '@/components/landing/landingHeroTitles';
import LandingMarquee from '@/components/landing/LandingMarquee';
import LandingPicture from '@/components/landing/LandingPicture';
import LandingPainSection from '@/components/landing/LandingPainSection';
import LandingAudienceSection from '@/components/landing/LandingAudienceSection';
import { useI18n } from '@/i18n/useI18n';

export default function Landing() {
  const { t } = useI18n();
  const [heroTitleKey] = useState(pickRandomHeroTitleKey);

  return (
    <div className="min-h-screen bg-canvas text-ink-900">
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-[-15%] right-[-5%] w-[55%] h-[45%] rounded-full bg-forge-200/50 blur-[100px] animate-landing-glow" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[45%] h-[40%] rounded-full bg-orange-100/60 blur-[90px] animate-landing-float-slow" />
      </div>

      <header className="sticky top-0 z-50 border-b border-canvas-border bg-white/90 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <BrandLogo size="md" />
            <span className="font-bold text-lg tracking-tight hidden sm:inline text-ink-900">
              {t('brand.name')}
            </span>
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
              className="text-sm font-semibold bg-forge-600 text-white px-4 py-2.5 rounded-lg hover:bg-forge-700 transition-all shadow-md shadow-forge-600/20"
            >
              {t('landing.getStarted')}
            </Link>
          </div>
        </div>
      </header>

      <section className="relative">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 pt-10 pb-12 sm:pt-14 lg:pt-16 lg:pb-16">
          <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
            <div className="relative z-10">
              <h1 className="text-4xl sm:text-5xl lg:text-[3.5rem] font-bold tracking-tight leading-[1.05] text-ink-900">
                {t(heroTitleKey)}
              </h1>
              <p className="mt-5 text-lg text-ink-500 leading-relaxed max-w-lg">
                {t('landing.heroSubtitle')}
              </p>

              <div className="mt-8">
                <Link
                  to="/signup"
                  className="inline-flex items-center justify-center gap-2 bg-forge-600 text-white font-semibold px-7 py-3.5 rounded-xl hover:bg-forge-700 transition-all text-base shadow-lg shadow-forge-600/20 hover:scale-[1.02] active:scale-[0.98]"
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

      <section id="showcase" className="relative py-16 sm:py-20 bg-white border-y border-canvas-border">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-8">
            <div>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-ink-900">
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

      <section className="relative py-12 overflow-hidden">
        <LandingPicture
          asset="workflow"
          className="absolute inset-0 w-full h-full object-cover opacity-[0.35] pointer-events-none scale-105"
        />
        <div className="absolute inset-0 bg-canvas/75 pointer-events-none" />
        <div className="relative max-w-6xl mx-auto px-4 sm:px-6">
          <p className="text-center text-sm font-medium text-ink-400 mb-6 uppercase tracking-wider">
            {t('landing.socialProof')}
          </p>
          <blockquote className="max-w-2xl mx-auto text-center">
            <p className="text-xl sm:text-2xl text-ink-900 font-medium leading-relaxed">
              &ldquo;{t('landing.testimonialQuote')}&rdquo;
            </p>
            <footer className="mt-4 text-sm text-ink-500">{t('landing.testimonialAuthor')}</footer>
          </blockquote>
        </div>
      </section>

      <section id="how-it-works" className="py-16 sm:py-20 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="text-2xl sm:text-3xl font-bold text-ink-900">{t('landing.howTitle')}</h2>
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
                className="px-5 py-3 rounded-xl border border-canvas-border bg-canvas text-sm font-semibold text-ink-700 hover:border-forge-300 hover:bg-forge-50 transition-colors"
              >
                <span className="text-forge-600 mr-2">{step.n}</span>
                {t(step.key)}
              </div>
            ))}
          </div>
          <Link
            to="/signup"
            className="mt-10 inline-flex items-center gap-2 bg-forge-600 text-white font-semibold px-8 py-3.5 rounded-xl hover:bg-forge-700 transition-colors shadow-md shadow-forge-600/15"
          >
            {t('landing.getStarted')}
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      <section className="relative overflow-hidden border-t border-canvas-border bg-forge-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-20 text-center">
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-ink-900">{t('landing.ctaTitle')}</h2>
          <p className="text-ink-500 mt-4 max-w-md mx-auto">{t('landing.ctaSubtitle')}</p>
          <Link
            to="/signup"
            className="mt-8 inline-flex items-center gap-2 bg-forge-600 text-white font-semibold px-10 py-4 rounded-xl hover:bg-forge-700 transition-all text-base shadow-lg shadow-forge-600/20 hover:scale-[1.02]"
          >
            {t('landing.getStarted')}
            <ArrowRight className="w-5 h-5" />
          </Link>
          <p className="mt-4 text-xs text-ink-400">{t('landing.heroNote')}</p>
        </div>
      </section>

      <LandingFooter />

      <div className="fixed bottom-0 inset-x-0 z-40 p-3 bg-white/95 border-t border-canvas-border backdrop-blur sm:hidden">
        <Link
          to="/signup"
          className="flex items-center justify-center gap-2 w-full bg-forge-600 text-white font-semibold py-3 rounded-xl shadow-lg shadow-forge-600/20"
        >
          {t('landing.stickyCta')}
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
