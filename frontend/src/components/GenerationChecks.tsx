import { useId, useState } from 'react';
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
  CircleOff,
  Info,
  Loader2,
  MinusCircle,
  ShieldAlert,
  SkipForward,
} from 'lucide-react';
import type { GenerationDiagnostics } from '@/api/generate';
import { useI18n } from '@/i18n/useI18n';

const GROUP_ORDER = ['references', 'intelligence', 'protections', 'quality', 'diversity', 'delivery'] as const;

const STATUS_CLASS: Record<string, string> = {
  passed: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  active: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  applied: 'bg-indigo-50 text-indigo-800 border-indigo-200',
  warning: 'bg-amber-50 text-amber-900 border-amber-200',
  skipped: 'bg-amber-50 text-amber-900 border-amber-200',
  fallback: 'bg-amber-50 text-amber-900 border-amber-200',
  blocked: 'bg-red-50 text-red-800 border-red-200',
  unavailable: 'bg-red-50 text-red-800 border-red-200',
  off: 'bg-gray-100 text-gray-600 border-gray-200',
};

function StatusIcon({ status }: { status: string }) {
  const cls = 'w-3 h-3 shrink-0';
  if (status === 'passed' || status === 'active') return <CheckCircle2 className={cls} aria-hidden />;
  if (status === 'applied') return <Info className={cls} aria-hidden />;
  if (status === 'warning' || status === 'skipped' || status === 'fallback')
    return <AlertTriangle className={cls} aria-hidden />;
  if (status === 'blocked' || status === 'unavailable') return <Ban className={cls} aria-hidden />;
  if (status === 'off') return <CircleOff className={cls} aria-hidden />;
  return <MinusCircle className={cls} aria-hidden />;
}

function messageFor(
  t: (key: string, params?: Record<string, string | number>) => string,
  key: string,
  params?: Record<string, string | number>,
) {
  const translated = t(`diagnostics.messages.${key}`, params);
  if (translated === `diagnostics.messages.${key}`) return t('diagnostics.messages.generic');
  return translated;
}

export default function GenerationChecks({
  diagnostics,
  className = '',
}: {
  diagnostics?: GenerationDiagnostics | null;
  className?: string;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [techOpen, setTechOpen] = useState(false);
  const detailsId = useId();

  if (!diagnostics) {
    return null;
  }

  const heading =
    diagnostics.state === 'planned'
      ? t('diagnostics.plannedChecks')
      : diagnostics.state === 'running'
        ? t('diagnostics.runningChecks')
        : t('diagnostics.generationResults');

  return (
    <section className={`mb-3 ${className}`} aria-label={t('diagnostics.generationChecks')}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <h4 className="text-[11px] font-semibold uppercase tracking-wide text-gray-600">
          {t('diagnostics.generationChecks')}
        </h4>
        <span className="text-[10px] text-gray-500">{heading}</span>
      </div>

      {diagnostics.state === 'running' && (
        <p className="flex items-center gap-1.5 text-[11px] text-gray-500 mb-2">
          <Loader2 className="w-3 h-3 animate-spin" aria-hidden />
          {t('diagnostics.loading')}
        </p>
      )}

      {!diagnostics.has_history ? (
        <p className="text-[11px] text-gray-500 italic mb-2">{t('diagnostics.messages.no_detailed_history')}</p>
      ) : (
        <ul className="space-y-1">
          {diagnostics.summary.slice(0, 6).map((row) => (
            <li key={row.key} className="min-w-0">
              <div className="flex items-start gap-1.5">
                <span className="text-[10px] font-semibold text-gray-500 w-[4.5rem] shrink-0 pt-0.5">
                  {t(`diagnostics.groups.${row.key}`)}
                </span>
                <span
                  className={`inline-flex items-center gap-1 max-w-full min-w-0 rounded-full border px-1.5 py-0.5 text-[10px] font-medium leading-snug ${STATUS_CLASS[row.status] || STATUS_CLASS.off}`}
                >
                  <StatusIcon status={row.status} />
                  <span className="sr-only">{t(`diagnostics.status.${row.status}`)}</span>
                  <span className="truncate">
                    {t(`diagnostics.status.${row.status}`)}
                    {' · '}
                    {messageFor(t, row.message_key, row.params as Record<string, string | number>)}
                  </span>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-gray-600 hover:text-gray-900"
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={() => setOpen((value) => !value)}
      >
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
        {t('diagnostics.viewDetails')}
      </button>

      {open && (
        <div id={detailsId} className="mt-2 space-y-2 border-t border-gray-100 pt-2">
          {GROUP_ORDER.map((key) => {
            const group = diagnostics.groups[key];
            if (!group) return null;
            return (
              <div key={key}>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500 mb-1">
                  {t(`diagnostics.groups.${key}`)}
                </p>
                <ul className="space-y-0.5">
                  {(group.items.length ? group.items : [{ code: 'empty', status: group.status, params: {} }]).map(
                    (item, index) => (
                      <li key={`${item.code}-${index}`} className="text-[11px] text-gray-700 leading-snug break-words">
                        <span className="inline-flex items-center gap-1">
                          <StatusIcon status={item.status} />
                          {t(`diagnostics.status.${item.status}`)}
                          {' — '}
                          {messageFor(t, item.code, item.params as Record<string, string | number>)}
                        </span>
                      </li>
                    ),
                  )}
                </ul>
              </div>
            );
          })}

          {diagnostics.technical ? (
            <div>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-[11px] font-medium text-gray-600"
                aria-expanded={techOpen}
                onClick={() => setTechOpen((value) => !value)}
              >
                <ShieldAlert className="w-3 h-3" aria-hidden />
                {t('diagnostics.technicalDetails')}
                <SkipForward className="w-3 h-3" aria-hidden />
              </button>
              {techOpen && (
                <pre className="mt-1 text-[10px] text-gray-600 bg-gray-50 border border-gray-100 rounded-md p-2 overflow-x-auto max-h-40 whitespace-pre-wrap break-all">
                  {JSON.stringify(diagnostics.technical, null, 2)}
                </pre>
              )}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
