import { ExternalLink } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

const BUFFER_API_SETTINGS_URL = 'https://publish.buffer.com/settings/api';
const BUFFER_API_HELP_URL = 'https://support.buffer.com/article/984-how-to-create-your-buffer-api-key';

interface BufferTokenGuideProps {
  compact?: boolean;
}

export default function BufferTokenGuide({ compact = false }: BufferTokenGuideProps) {
  const { t } = useI18n();

  return (
    <div className={compact ? 'text-sm' : ''}>
      {!compact && (
        <>
          <h4 className="font-semibold text-gray-900 text-sm">{t('bufferAccounts.tokenGuide.title')}</h4>
          <p className="mt-2 text-sm text-gray-600">{t('bufferAccounts.tokenGuide.intro')}</p>
        </>
      )}
      <ol
        className={`space-y-1.5 text-gray-700 list-decimal list-inside ${
          compact ? 'mt-2 text-xs' : 'mt-3 text-sm'
        }`}
      >
        <li>{t('bufferAccounts.tokenGuide.steps.signIn')}</li>
        <li>{t('bufferAccounts.tokenGuide.steps.openSettings')}</li>
        <li>{t('bufferAccounts.tokenGuide.steps.personalAccess')}</li>
        <li>{t('bufferAccounts.tokenGuide.steps.generate')}</li>
        <li>{t('bufferAccounts.tokenGuide.steps.paste')}</li>
      </ol>
      <p className={`text-gray-500 ${compact ? 'mt-2 text-xs' : 'mt-3 text-xs'}`}>
        {t('bufferAccounts.tokenGuide.notes')}
      </p>
      <div className={`flex flex-wrap gap-3 ${compact ? 'mt-3' : 'mt-4'}`}>
        <a
          href={BUFFER_API_SETTINGS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-forge-700 hover:text-forge-800"
        >
          {t('bufferAccounts.tokenGuide.openApiSettings')}
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
        <a
          href={BUFFER_API_HELP_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-800"
        >
          {t('bufferAccounts.tokenGuide.helpArticle')}
          <ExternalLink className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}
