export type HelpArticleId =
  | 'quick-start'
  | 'onboarding'
  | 'brand-kits'
  | 'products'
  | 'visual-styles'
  | 'studio'
  | 'automations'
  | 'review'
  | 'calendar'
  | 'buffer'
  | 'image-models'
  | 'billing';

export type HelpFaqId =
  | 'what-is-pulseforge'
  | 'auto-vs-manual'
  | 'buffer-token'
  | 'credits'
  | 'cdn-publish'
  | 'generation-fails'
  | 'cron-format'
  | 'generic-brand'
  | 'logo-in-images'
  | 'languages';

export interface HelpArticleMeta {
  id: HelpArticleId;
  screenshot?: string;
  stepKeys?: string[];
  tipKeys?: string[];
}

export interface HelpSection {
  id: string;
  labelKey: string;
  articles: HelpArticleMeta[];
}

export interface HelpFaqItem {
  id: HelpFaqId;
  questionKey: string;
  answerKey: string;
}

export const HELP_SECTIONS: HelpSection[] = [
  {
    id: 'gettingStarted',
    labelKey: 'help.sections.gettingStarted',
    articles: [
      {
        id: 'quick-start',
        screenshot: 'studio.png',
        stepKeys: [
          'help.articles.quickStart.steps.1',
          'help.articles.quickStart.steps.2',
          'help.articles.quickStart.steps.3',
          'help.articles.quickStart.steps.4',
          'help.articles.quickStart.steps.5',
          'help.articles.quickStart.steps.6',
          'help.articles.quickStart.steps.7',
        ],
        tipKeys: ['help.articles.quickStart.tips.1', 'help.articles.quickStart.tips.2'],
      },
      {
        id: 'onboarding',
        screenshot: 'onboarding-wizard.png',
        stepKeys: [
          'help.articles.onboarding.steps.1',
          'help.articles.onboarding.steps.2',
          'help.articles.onboarding.steps.3',
          'help.articles.onboarding.steps.4',
        ],
        tipKeys: ['help.articles.onboarding.tips.1'],
      },
    ],
  },
  {
    id: 'contentSetup',
    labelKey: 'help.sections.contentSetup',
    articles: [
      { id: 'brand-kits', screenshot: 'brand.png', tipKeys: ['help.articles.brandKits.tips.1'] },
      { id: 'products', screenshot: 'products.png', tipKeys: ['help.articles.products.tips.1', 'help.articles.products.tips.2'] },
      { id: 'visual-styles', screenshot: 'visual-styles.png', tipKeys: ['help.articles.visualStyles.tips.1'] },
    ],
  },
  {
    id: 'createAndPublish',
    labelKey: 'help.sections.createAndPublish',
    articles: [
      { id: 'studio', screenshot: 'studio.png', tipKeys: ['help.articles.studio.tips.1', 'help.articles.studio.tips.2'] },
      { id: 'automations', screenshot: 'automations.png', tipKeys: ['help.articles.automations.tips.1'] },
      { id: 'review', screenshot: 'review.png', tipKeys: ['help.articles.review.tips.1'] },
      { id: 'calendar', screenshot: 'calendar.png' },
    ],
  },
  {
    id: 'integrations',
    labelKey: 'help.sections.integrations',
    articles: [
      { id: 'buffer', screenshot: 'buffer-accounts.png', stepKeys: [
        'help.articles.buffer.steps.1',
        'help.articles.buffer.steps.2',
        'help.articles.buffer.steps.3',
        'help.articles.buffer.steps.4',
      ] },
      { id: 'image-models', screenshot: 'account.png', tipKeys: ['help.articles.imageModels.tips.1'] },
      { id: 'billing', screenshot: 'account.png', tipKeys: ['help.articles.billing.tips.1'] },
    ],
  },
];

export const HELP_FAQ: HelpFaqItem[] = [
  { id: 'what-is-pulseforge', questionKey: 'help.faq.whatIsPulseforge.q', answerKey: 'help.faq.whatIsPulseforge.a' },
  { id: 'auto-vs-manual', questionKey: 'help.faq.autoVsManual.q', answerKey: 'help.faq.autoVsManual.a' },
  { id: 'buffer-token', questionKey: 'help.faq.bufferToken.q', answerKey: 'help.faq.bufferToken.a' },
  { id: 'credits', questionKey: 'help.faq.credits.q', answerKey: 'help.faq.credits.a' },
  { id: 'cdn-publish', questionKey: 'help.faq.cdnPublish.q', answerKey: 'help.faq.cdnPublish.a' },
  { id: 'generation-fails', questionKey: 'help.faq.generationFails.q', answerKey: 'help.faq.generationFails.a' },
  { id: 'cron-format', questionKey: 'help.faq.cronFormat.q', answerKey: 'help.faq.cronFormat.a' },
  { id: 'generic-brand', questionKey: 'help.faq.genericBrand.q', answerKey: 'help.faq.genericBrand.a' },
  { id: 'logo-in-images', questionKey: 'help.faq.logoInImages.q', answerKey: 'help.faq.logoInImages.a' },
  { id: 'languages', questionKey: 'help.faq.languages.q', answerKey: 'help.faq.languages.a' },
];

export const DEFAULT_HELP_ARTICLE: HelpArticleId = 'quick-start';

export function articleTitleKey(id: HelpArticleId): string {
  return `help.articles.${camelCase(id)}.title`;
}

export function articleSummaryKey(id: HelpArticleId): string {
  return `help.articles.${camelCase(id)}.summary`;
}

export function articleBodyKeys(id: HelpArticleId): string[] {
  const base = `help.articles.${camelCase(id)}.body`;
  return [`${base}.1`, `${base}.2`, `${base}.3`];
}

function camelCase(id: string): string {
  return id.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase());
}

export const ALL_ARTICLE_IDS: HelpArticleId[] = HELP_SECTIONS.flatMap((s) =>
  s.articles.map((a) => a.id),
);
