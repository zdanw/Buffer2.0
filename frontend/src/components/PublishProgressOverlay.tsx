import { useState } from 'react';
import { useI18n } from '@/i18n/useI18n';

export type PublishPhase = 'prepare' | 'upload' | 'publish' | 'done';

const PHASE_ORDER: PublishPhase[] = ['prepare', 'upload', 'publish', 'done'];

type OverlayState = { open: boolean; phase: PublishPhase; platforms: string[] };

interface PublishProgressOverlayProps {
  open: boolean;
  phase: PublishPhase;
  platforms?: string[];
}

export default function PublishProgressOverlay({
  open,
  phase,
  platforms = [],
}: PublishProgressOverlayProps) {
  const { t } = useI18n();
  if (!open) return null;

  const labels: Record<PublishPhase, string> = {
    prepare: t('publishProgress.prepare'),
    upload: t('publishProgress.upload'),
    publish:
      platforms.length > 0
        ? t('publishProgress.publishTo', { platforms: platforms.join(', ') })
        : t('publishProgress.publish'),
    done: t('publishProgress.done'),
  };

  const activeIndex = PHASE_ORDER.indexOf(phase);

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center bg-black/45 p-4">
      <div
        role="status"
        aria-live="polite"
        className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl"
      >
        <div className="mb-5 flex items-center gap-3">
          <div
            className="h-9 w-9 shrink-0 animate-spin rounded-full border-2 border-forge-200 border-t-forge-600"
            aria-hidden
          />
          <div>
            <h3 className="text-base font-semibold text-gray-900">{t('publishProgress.title')}</h3>
            <p className="text-sm text-gray-600">{labels[phase]}</p>
          </div>
        </div>

        <ol className="space-y-2">
          {PHASE_ORDER.map((step, index) => {
            const done = index < activeIndex || phase === 'done';
            const current = index === activeIndex && phase !== 'done';
            return (
              <li key={step} className="flex items-center gap-2 text-sm">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-medium ${
                    done
                      ? 'bg-emerald-100 text-emerald-700'
                      : current
                        ? 'bg-forge-100 text-forge-700'
                        : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {done ? '✓' : index + 1}
                </span>
                <span className={done || current ? 'text-gray-800' : 'text-gray-400'}>
                  {labels[step]}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/** Advance staged phases while a single publish request is in flight. */
export function usePublishPhaseRunner() {
  const [overlay, setOverlay] = useState<OverlayState>({
    open: false,
    phase: 'prepare',
    platforms: [],
  });

  const runPublishWithProgress = async <T,>(
    fn: () => Promise<T>,
    platforms: string[]
  ): Promise<T> => {
    setOverlay({ open: true, phase: 'prepare', platforms });
    const t1 = window.setTimeout(
      () => setOverlay((p) => (p.open ? { ...p, phase: 'upload' } : p)),
      600
    );
    const t2 = window.setTimeout(
      () => setOverlay((p) => (p.open ? { ...p, phase: 'publish' } : p)),
      1600
    );
    try {
      const result = await fn();
      setOverlay((p) => ({ ...p, phase: 'done' }));
      await new Promise((r) => window.setTimeout(r, 450));
      return result;
    } finally {
      window.clearTimeout(t1);
      window.clearTimeout(t2);
      setOverlay({ open: false, phase: 'prepare', platforms: [] });
    }
  };

  return { publishOverlay: overlay, runPublishWithProgress };
}
