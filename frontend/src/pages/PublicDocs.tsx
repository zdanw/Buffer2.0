import { Link, Navigate, useLocation } from 'react-router-dom';
import { BookOpen, ChevronRight } from 'lucide-react';
import BrandLogo from '@/components/BrandLogo';
import HelpArticleBody from '@/components/help/HelpArticleBody';
import LandingFooter from '@/components/landing/LandingFooter';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import { usePageMeta } from '@/hooks/usePageMeta';
import { useI18n } from '@/i18n/useI18n';
import {
  ALL_ARTICLE_IDS,
  HELP_FAQ,
  HELP_SECTIONS,
  articleSummaryKey,
  articleTitleKey,
  type HelpArticleId,
} from '@/content/help/structure';

function isArticleId(slug: string): slug is HelpArticleId {
  return (ALL_ARTICLE_IDS as string[]).includes(slug);
}

function PublicDocsShell({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();

  return (
    <div className="min-h-screen bg-canvas text-ink-900 flex flex-col">
      <header className="sticky top-0 z-50 border-b border-canvas-border bg-white/90 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <BrandLogo size="md" />
            <span className="font-bold text-lg tracking-tight hidden sm:inline">{t('brand.name')}</span>
          </Link>
          <nav className="flex items-center gap-3 sm:gap-5 text-sm">
            <Link to="/docs" className="text-ink-600 hover:text-ink-900 font-medium">
              {t('help.title')}
            </Link>
            <Link to="/docs/faq" className="text-ink-600 hover:text-ink-900">
              {t('help.faqTitle')}
            </Link>
            <LanguageSwitcher compact variant="light" />
            <Link
              to="/signup"
              className="hidden sm:inline font-semibold bg-forge-600 text-white px-4 py-2 rounded-lg hover:bg-forge-700 transition-colors"
            >
              {t('landing.getStarted')}
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">{children}</main>
      <LandingFooter />
    </div>
  );
}

function DocsIndex() {
  const { t } = useI18n();

  usePageMeta({
    title: t('help.title'),
    description: t('help.subtitle'),
    canonicalPath: '/docs',
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: t('help.title'),
      description: t('help.subtitle'),
      hasPart: ALL_ARTICLE_IDS.map((id) => ({
        '@type': 'Article',
        name: t(articleTitleKey(id)),
      })),
    },
  });

  return (
    <PublicDocsShell>
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-xl bg-forge-100 text-forge-600 flex items-center justify-center">
            <BookOpen className="w-6 h-6" strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{t('help.title')}</h1>
            <p className="text-ink-500 mt-1">{t('help.subtitle')}</p>
          </div>
        </div>

        <p className="text-sm text-ink-500 mb-8 max-w-2xl">{t('help.publicIndexHint')}</p>

        <div className="grid gap-10 md:grid-cols-2">
          {HELP_SECTIONS.map((section) => (
            <section key={section.id}>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-400 mb-3">
                {t(section.labelKey)}
              </h2>
              <ul className="space-y-2">
                {section.articles.map((article) => (
                  <li key={article.id}>
                    <Link
                      to={`/docs/${article.id}`}
                      className="group flex items-start gap-2 rounded-xl border border-canvas-border bg-white p-4 hover:border-forge-200 hover:shadow-card transition-all"
                    >
                      <ChevronRight className="w-4 h-4 text-forge-500 mt-0.5 shrink-0" />
                      <div>
                        <h3 className="font-semibold text-ink-900 group-hover:text-forge-700">
                          {t(articleTitleKey(article.id))}
                        </h3>
                        <p className="text-sm text-ink-500 mt-1 line-clamp-2">
                          {t(articleSummaryKey(article.id))}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>

        <div className="mt-12 rounded-2xl border border-forge-200 bg-forge-50 p-6 sm:p-8">
          <h2 className="text-lg font-bold text-ink-900">{t('help.faqTitle')}</h2>
          <p className="text-sm text-ink-600 mt-2 mb-4">{t('help.publicFaqHint')}</p>
          <Link
            to="/docs/faq"
            className="inline-flex items-center gap-2 text-sm font-semibold text-forge-700 hover:text-forge-800"
          >
            {t('help.openFaq')}
            <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </PublicDocsShell>
  );
}

function DocsArticle({ slug }: { slug: HelpArticleId }) {
  const { t } = useI18n();
  const meta = HELP_SECTIONS.flatMap((s) => s.articles).find((a) => a.id === slug);
  const title = t(articleTitleKey(slug));
  const summary = t(articleSummaryKey(slug));

  usePageMeta({
    title,
    description: summary,
    canonicalPath: `/docs/${slug}`,
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'TechArticle',
      headline: title,
      description: summary,
      publisher: { '@type': 'Organization', name: 'Postence' },
    },
  });

  return (
    <PublicDocsShell>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <nav className="text-sm text-ink-500 mb-6" aria-label="Breadcrumb">
          <Link to="/docs" className="hover:text-forge-600">
            {t('help.title')}
          </Link>
          <span className="mx-2">/</span>
          <span className="text-ink-700">{title}</span>
        </nav>

        <article className="bg-white rounded-2xl border border-canvas-border shadow-card p-6 sm:p-8">
          <HelpArticleBody articleId={slug} meta={meta} t={t} headingLevel="h1" />
        </article>

        <p className="mt-8 text-center text-sm text-ink-500">
          <Link to="/signup" className="font-semibold text-forge-600 hover:text-forge-700">
            {t('landing.getStarted')}
          </Link>
          {' · '}
          <Link to="/docs" className="hover:text-ink-700">
            {t('help.backToIndex')}
          </Link>
        </p>
      </div>
    </PublicDocsShell>
  );
}

function DocsFaq() {
  const { t } = useI18n();

  usePageMeta({
    title: t('help.faqTitle'),
    description: t('help.publicFaqHint'),
    canonicalPath: '/docs/faq',
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: HELP_FAQ.map((item) => ({
        '@type': 'Question',
        name: t(item.questionKey),
        acceptedAnswer: { '@type': 'Answer', text: t(item.answerKey) },
      })),
    },
  });

  return (
    <PublicDocsShell>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        <nav className="text-sm text-ink-500 mb-6">
          <Link to="/docs" className="hover:text-forge-600">
            {t('help.title')}
          </Link>
          <span className="mx-2">/</span>
          <span className="text-ink-700">{t('help.faqTitle')}</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight mb-8">{t('help.faqTitle')}</h1>

        <div className="space-y-4">
          {HELP_FAQ.map((item) => (
            <details
              key={item.id}
              className="group bg-white rounded-xl border border-canvas-border open:shadow-card"
              open
            >
              <summary className="cursor-pointer list-none px-5 py-4 font-medium text-ink-900 flex items-center justify-between gap-4">
                {t(item.questionKey)}
                <ChevronRight className="w-4 h-4 text-ink-400 group-open:rotate-90 transition-transform shrink-0" />
              </summary>
              <div className="px-5 pb-4 text-sm text-ink-600 leading-relaxed border-t border-canvas-border pt-3">
                {t(item.answerKey)}
              </div>
            </details>
          ))}
        </div>
      </div>
    </PublicDocsShell>
  );
}

export default function PublicDocs() {
  const { pathname } = useLocation();

  if (pathname === '/docs' || pathname === '/docs/') {
    return <DocsIndex />;
  }
  if (pathname === '/docs/faq') {
    return <DocsFaq />;
  }

  const match = pathname.match(/^\/docs\/([^/]+)$/);
  if (match && isArticleId(match[1])) {
    return <DocsArticle slug={match[1]} />;
  }

  return <Navigate to="/docs" replace />;
}
