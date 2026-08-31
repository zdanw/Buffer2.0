import HelpScreenshot from '@/components/help/HelpScreenshot';
import type { HelpArticleMeta } from '@/content/help/structure';
import {
  articleBodyKeys,
  articleSummaryKey,
  articleTitleKey,
  type HelpArticleId,
} from '@/content/help/structure';

type HelpArticleBodyProps = {
  articleId: HelpArticleId;
  meta: HelpArticleMeta | undefined;
  t: (key: string, params?: Record<string, string | number>) => string;
  headingLevel?: 'h1' | 'h2';
};

export default function HelpArticleBody({
  articleId,
  meta,
  t,
  headingLevel = 'h2',
}: HelpArticleBodyProps) {
  const TitleTag = headingLevel;

  return (
    <>
      <TitleTag className="text-xl sm:text-2xl font-bold text-ink-900 tracking-tight">
        {t(articleTitleKey(articleId))}
      </TitleTag>
      <p className="mt-2 text-ink-500 leading-relaxed">{t(articleSummaryKey(articleId))}</p>

      {meta?.screenshot ? (
        <HelpScreenshot
          src={`/docs/screenshots/${meta.screenshot}`}
          alt={t('help.screenshotAlt', { page: t(articleTitleKey(articleId)) })}
          caption={t('help.screenshotCaption', { page: t(articleTitleKey(articleId)) })}
        />
      ) : null}

      <div className="prose prose-sm max-w-none mt-6 space-y-4 text-ink-700 leading-relaxed">
        {articleBodyKeys(articleId).map((key) => {
          const text = t(key);
          if (!text || text === key) return null;
          return <p key={key}>{text}</p>;
        })}
      </div>

      {meta?.stepKeys && meta.stepKeys.length > 0 ? (
        <section className="mt-8">
          <h3 className="text-sm font-semibold text-ink-900 mb-3">{t('help.stepsTitle')}</h3>
          <ol className="space-y-3">
            {meta.stepKeys.map((key, index) => (
              <li key={key} className="flex gap-3 text-sm text-ink-700">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-forge-100 text-forge-700 text-xs font-bold flex items-center justify-center">
                  {index + 1}
                </span>
                <span className="pt-0.5 leading-relaxed">{t(key)}</span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      {meta?.tipKeys && meta.tipKeys.length > 0 ? (
        <section className="mt-8 rounded-xl bg-amber-50 border border-amber-100 p-4">
          <h3 className="text-sm font-semibold text-amber-900 mb-2">{t('help.tipsTitle')}</h3>
          <ul className="space-y-2 text-sm text-amber-900/90">
            {meta.tipKeys.map((key) => (
              <li key={key} className="flex gap-2">
                <span className="text-amber-500">•</span>
                <span>{t(key)}</span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}
