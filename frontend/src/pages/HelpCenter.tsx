import { useMemo, useState } from 'react';
import { BookOpen, ChevronRight, Search } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useI18n } from '@/i18n/useI18n';
import HelpArticleBody from '@/components/help/HelpArticleBody';
import {
  DEFAULT_HELP_ARTICLE,
  HELP_FAQ,
  HELP_SECTIONS,
  articleSummaryKey,
  articleTitleKey,
  type HelpArticleId,
} from '@/content/help/structure';

export default function HelpCenter() {
  const { t } = useI18n();
  const [activeArticle, setActiveArticle] = useState<HelpArticleId>(DEFAULT_HELP_ARTICLE);
  const [query, setQuery] = useState('');
  const [faqOpen, setFaqOpen] = useState<string | null>(HELP_FAQ[0]?.id ?? null);

  const filteredSections = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return HELP_SECTIONS;
    return HELP_SECTIONS.map((section) => ({
      ...section,
      articles: section.articles.filter((article) => {
        const title = t(articleTitleKey(article.id)).toLowerCase();
        const summary = t(articleSummaryKey(article.id)).toLowerCase();
        return title.includes(q) || summary.includes(q) || article.id.includes(q);
      }),
    })).filter((section) => section.articles.length > 0);
  }, [query, t]);

  const activeMeta = HELP_SECTIONS.flatMap((s) => s.articles).find((a) => a.id === activeArticle);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      <header className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-forge-100 text-forge-600 flex items-center justify-center">
            <BookOpen className="w-5 h-5" strokeWidth={1.75} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-ink-900 tracking-tight">{t('help.title')}</h1>
            <p className="text-sm text-ink-500 mt-0.5">{t('help.subtitle')}</p>
          </div>
        </div>
        <div className="relative mt-4 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('help.searchPlaceholder')}
            className="w-full pl-9 pr-3 py-2.5 text-sm rounded-lg border border-canvas-border bg-white focus:outline-none focus:ring-2 focus:ring-forge-500/30 focus:border-forge-400"
          />
        </div>
        <p className="mt-3 text-xs text-ink-400">
          {t('help.publicIndexHint')}{' '}
          <Link to="/docs" className="text-forge-600 hover:underline font-medium">
            {t('help.openPublicDocs')}
          </Link>
        </p>
      </header>

      <div className="grid lg:grid-cols-[240px_1fr] gap-8 items-start">
        <nav className="lg:sticky lg:top-4 space-y-6">
          {filteredSections.length === 0 ? (
            <p className="text-sm text-ink-500">{t('help.noResults')}</p>
          ) : (
            filteredSections.map((section) => (
              <div key={section.id}>
                <h2 className="text-xs font-semibold uppercase tracking-wide text-ink-400 mb-2 px-2">
                  {t(section.labelKey)}
                </h2>
                <ul className="space-y-0.5">
                  {section.articles.map((article) => {
                    const isActive = article.id === activeArticle;
                    return (
                      <li key={article.id}>
                        <button
                          type="button"
                          onClick={() => setActiveArticle(article.id)}
                          className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                            isActive
                              ? 'bg-forge-50 text-forge-800 font-medium'
                              : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900'
                          }`}
                        >
                          <ChevronRight
                            className={`w-3.5 h-3.5 shrink-0 transition-opacity ${isActive ? 'opacity-100' : 'opacity-0'}`}
                          />
                          {t(articleTitleKey(article.id))}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))
          )}
        </nav>

        <article className="min-w-0">
          <div className="bg-white rounded-2xl border border-canvas-border shadow-card p-6 sm:p-8">
            <HelpArticleBody
              articleId={activeArticle}
              meta={activeMeta}
              t={t}
              headingLevel="h2"
            />
          </div>

          <section className="mt-10">
            <h2 className="text-lg font-bold text-ink-900 mb-4">{t('help.faqTitle')}</h2>
            <div className="space-y-2">
              {HELP_FAQ.map((item) => {
                const open = faqOpen === item.id;
                return (
                  <div
                    key={item.id}
                    className="bg-white rounded-xl border border-canvas-border overflow-hidden"
                  >
                    <button
                      type="button"
                      onClick={() => setFaqOpen(open ? null : item.id)}
                      className="w-full flex items-center justify-between gap-4 px-5 py-4 text-left text-sm font-medium text-ink-900 hover:bg-ink-50 transition-colors"
                    >
                      {t(item.questionKey)}
                      <ChevronRight
                        className={`w-4 h-4 shrink-0 text-ink-400 transition-transform ${open ? 'rotate-90' : ''}`}
                      />
                    </button>
                    {open ? (
                      <div className="px-5 pb-4 text-sm text-ink-600 leading-relaxed border-t border-canvas-border pt-3">
                        {t(item.answerKey)}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </section>
        </article>
      </div>
    </div>
  );
}
