import { BookOpen } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useI18n } from '@/i18n/useI18n';

export default function TopBarHelpLink() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const isActive = pathname === '/help';

  return (
    <button
      type="button"
      onClick={() => navigate('/help')}
      className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
        isActive
          ? 'bg-forge-50 text-forge-700 ring-1 ring-forge-200'
          : 'text-ink-600 hover:bg-ink-50 hover:text-ink-900'
      }`}
      aria-current={isActive ? 'page' : undefined}
    >
      <BookOpen className="h-4 w-4 shrink-0" strokeWidth={1.75} aria-hidden />
      <span className="hidden sm:inline">{t('nav.help')}</span>
    </button>
  );
}
