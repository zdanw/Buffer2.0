import { useEffect, useMemo, useState } from 'react';
import { ImageIcon, PenLine } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

type ProgressStage =
  | 'starting'
  | 'resolving_references'
  | 'queued'
  | 'copywriting'
  | 'image_prompt'
  | 'image_generation'
  | 'finalizing'
  | 'done';

const PROGRESS_STAGES = new Set<string>([
  'starting',
  'resolving_references',
  'queued',
  'copywriting',
  'image_prompt',
  'image_generation',
  'finalizing',
  'done',
]);

type GeneratingType = 'all' | 'copywriting' | 'image' | string | null;

interface PreviewGeneratingAnimationProps {
  generatingType?: GeneratingType;
  progress?: number;
  stage?: string | null;
}

function TypeIcon({ generatingType }: { generatingType?: GeneratingType }) {
  if (generatingType === 'copywriting') {
    return <PenLine className="w-3.5 h-3.5" />;
  }
  if (generatingType === 'image') {
    return <ImageIcon className="w-3.5 h-3.5" />;
  }
  return <PenLine className="w-3.5 h-3.5" />;
}

/** Living Signal motif: one source idea branching to channel outputs. */
function SignalVisual() {
  return (
    <div className="relative w-28 h-28" aria-hidden="true">
      <svg viewBox="0 0 112 112" className="w-full h-full">
        <circle cx="56" cy="56" r="6" fill="#F5F1E8" className="preview-signal-pulse" />
        <circle cx="56" cy="56" r="14" fill="none" stroke="rgba(245,241,232,0.15)" strokeWidth="1" />
        <path
          d="M56 50 L56 22"
          stroke="#e85736"
          strokeWidth="2"
          strokeLinecap="round"
          className="preview-signal-line"
          style={{ animationDelay: '0s' }}
        />
        <path
          d="M60 54 L88 68"
          stroke="#406BFF"
          strokeWidth="2"
          strokeLinecap="round"
          className="preview-signal-line"
          style={{ animationDelay: '0.4s' }}
        />
        <path
          d="M52 54 L24 68"
          stroke="#91B89A"
          strokeWidth="2"
          strokeLinecap="round"
          className="preview-signal-line"
          style={{ animationDelay: '0.8s' }}
        />
        <circle cx="56" cy="18" r="4" fill="#e85736" opacity="0.9" />
        <circle cx="92" cy="70" r="4" fill="#406BFF" opacity="0.9" />
        <circle cx="20" cy="70" r="4" fill="#91B89A" opacity="0.9" />
      </svg>
    </div>
  );
}

export default function PreviewGeneratingAnimation({
  generatingType,
  progress = 0,
  stage = null,
}: PreviewGeneratingAnimationProps) {
  const { t } = useI18n();
  const [messageIndex, setMessageIndex] = useState(0);

  const displayProgress = Math.max(0, Math.min(100, Math.round(progress)));
  const stageLabel =
    stage && PROGRESS_STAGES.has(stage)
      ? t(`preview.progressStage.${stage}` as `preview.progressStage.${ProgressStage}`)
      : null;

  const messageKeys = useMemo(() => {
    if (generatingType === 'copywriting') {
      return [
        'preview.generatingCopy1',
        'preview.generatingCopy2',
        'preview.generatingCopy3',
        'preview.generatingCopy4',
      ] as const;
    }
    if (generatingType === 'image') {
      return [
        'preview.generatingImage1',
        'preview.generatingImage2',
        'preview.generatingImage3',
        'preview.generatingImage4',
      ] as const;
    }
    return [
      'preview.generatingAll1',
      'preview.generatingAll2',
      'preview.generatingAll3',
      'preview.generatingAll4',
    ] as const;
  }, [generatingType]);

  useEffect(() => {
    setMessageIndex(0);
    const interval = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % messageKeys.length);
    }, 2400);
    return () => clearInterval(interval);
  }, [messageKeys]);

  return (
    <div
      className="absolute inset-0 z-40 flex flex-col items-center justify-center overflow-hidden preview-gen-surface"
      role="status"
      aria-live="polite"
      aria-label={t('preview.generating')}
    >
      <div className="absolute inset-0 preview-gen-shimmer pointer-events-none" />

      <div className="relative flex flex-col items-center px-6 text-center">
        <SignalVisual />

        <div className="mt-5 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 backdrop-blur-sm border border-white/15 text-white/90 text-[10px] font-semibold tracking-wide uppercase">
          <TypeIcon generatingType={generatingType} />
          {t('preview.generating')}
        </div>

        <p
          key={messageIndex}
          className="mt-3 text-[13px] font-medium text-white/95 preview-gen-message max-w-[200px] leading-snug"
        >
          {t(messageKeys[messageIndex])}
        </p>

        <div className="flex items-center gap-1.5 mt-4">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-1.5 h-1.5 rounded-full bg-forge-500 preview-gen-dot"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>

        <div className="mt-5 w-44">
          <div className="flex items-center justify-between text-[10px] font-medium text-white/70 mb-1.5">
            <span>{stageLabel ?? t('preview.generating')}</span>
            <span aria-hidden>{displayProgress}%</span>
          </div>
          <div
            className="h-1 rounded-full bg-white/10 overflow-hidden"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={displayProgress}
            aria-label={stageLabel ?? t('preview.generating')}
          >
            <div
              className="h-full rounded-full bg-forge-500 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.max(displayProgress, 4)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
