import { AlertCircle, RefreshCw } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

interface ApiConnectionBannerProps {
  onRetry?: () => void;
  loading?: boolean;
}

export default function ApiConnectionBanner({ onRetry, loading = false }: ApiConnectionBannerProps) {
  const { t } = useI18n();

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 lg:px-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex gap-3 min-w-0">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-amber-900">{t('api.bannerTitle')}</p>
            <p className="text-sm text-amber-800 mt-1 leading-relaxed">{t('api.bannerBody')}</p>
            <p className="text-xs text-amber-700 mt-2 font-mono bg-amber-100/80 rounded px-2 py-1 inline-block">
              {t('api.bannerCommand')}
            </p>
          </div>
        </div>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            disabled={loading}
            className="inline-flex items-center gap-2 shrink-0 px-3 py-2 text-sm font-medium rounded-lg border border-amber-300 bg-white text-amber-900 hover:bg-amber-100 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {t('api.retry')}
          </button>
        )}
      </div>
    </div>
  );
}
