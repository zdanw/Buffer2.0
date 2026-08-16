import type { ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
  refreshing?: boolean;
  actions?: ReactNode;
}

export default function PageHeader({
  title,
  subtitle,
  onRefresh,
  refreshing = false,
  actions,
}: PageHeaderProps) {
  const { t } = useI18n();

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink-900">{title}</h1>
        {subtitle && <p className="text-ink-500 mt-1 text-sm">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 px-3 py-2 border border-canvas-border rounded-lg text-sm text-ink-700 hover:bg-white hover:shadow-card transition-shadow"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">{t('common.refresh')}</span>
          </button>
        )}
        {actions}
      </div>
    </div>
  );
}
