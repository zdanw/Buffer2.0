import { useEffect, useMemo, useState } from 'react';
import { Sparkles, Wand2, PenLine, ImageIcon } from 'lucide-react';
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

const FLOATING_EMOJI = ['✨', '💫', '🔥', '📸', '💕', '⭐', '🌸', '🎨'];

function SparkleParticle({ emoji, style }: { emoji: string; style: React.CSSProperties }) {
  return (
    <span
      className="absolute text-sm pointer-events-none preview-gen-rise"
      style={style}
      aria-hidden
    >
      {emoji}
    </span>
  );
}

function ForgeBuddy() {
  return (
    <div className="relative preview-gen-float">
      <div className="preview-gen-wiggle">
        <svg viewBox="0 0 120 120" className="w-24 h-24 drop-shadow-lg" aria-hidden>
          <defs>
            <linearGradient id="buddy-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#f47538" />
              <stop offset="50%" stopColor="#ec4899" />
              <stop offset="100%" stopColor="#a855f7" />
            </linearGradient>
            <filter id="buddy-glow">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <ellipse cx="60" cy="68" rx="42" ry="38" fill="url(#buddy-gradient)" filter="url(#buddy-glow)" />
          <ellipse cx="60" cy="72" rx="34" ry="30" fill="white" opacity="0.12" />
          <ellipse cx="44" cy="62" rx="10" ry="12" fill="white" className="preview-gen-blink" />
          <ellipse cx="76" cy="62" rx="10" ry="12" fill="white" className="preview-gen-blink" />
          <circle cx="47" cy="64" r="5" fill="#1a1a1a" />
          <circle cx="79" cy="64" r="5" fill="#1a1a1a" />
          <circle cx="49" cy="62" r="2" fill="white" />
          <circle cx="81" cy="62" r="2" fill="white" />
          <ellipse cx="38" cy="72" rx="6" ry="3.5" fill="#fda4af" opacity="0.7" />
          <ellipse cx="82" cy="72" rx="6" ry="3.5" fill="#fda4af" opacity="0.7" />
          <path
            d="M 48 82 Q 60 92 72 82"
            fill="none"
            stroke="#1a1a1a"
            strokeWidth="2.5"
            strokeLinecap="round"
          />
          <g className="preview-gen-wand">
            <rect x="88" y="28" width="4" height="22" rx="2" fill="#fcd34d" transform="rotate(25 90 39)" />
            <polygon
              points="98,18 102,28 94,28"
              fill="#fef08a"
              transform="rotate(25 98 23)"
            />
            <circle cx="100" cy="16" r="5" fill="#fde047" className="preview-gen-sparkle-pulse" />
          </g>
        </svg>
      </div>
      <div className="absolute -top-1 -right-2 preview-gen-orbit">
        <Sparkles className="w-5 h-5 text-yellow-300 drop-shadow" />
      </div>
      <div className="absolute -bottom-1 -left-3 preview-gen-orbit-reverse">
        <Sparkles className="w-4 h-4 text-pink-300 drop-shadow" />
      </div>
    </div>
  );
}

function TypeIcon({ generatingType }: { generatingType?: GeneratingType }) {
  if (generatingType === 'copywriting') {
    return <PenLine className="w-3.5 h-3.5" />;
  }
  if (generatingType === 'image') {
    return <ImageIcon className="w-3.5 h-3.5" />;
  }
  return <Wand2 className="w-3.5 h-3.5" />;
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

  const particles = useMemo(
    () =>
      FLOATING_EMOJI.map((emoji, i) => ({
        emoji,
        style: {
          left: `${8 + (i * 11) % 84}%`,
          bottom: `${12 + (i * 17) % 40}%`,
          animationDelay: `${i * 0.35}s`,
          animationDuration: `${2.8 + (i % 3) * 0.6}s`,
        } as React.CSSProperties,
      })),
    []
  );

  return (
    <div
      className="absolute inset-0 z-40 flex flex-col items-center justify-center overflow-hidden preview-gen-gradient"
      role="status"
      aria-live="polite"
      aria-label={t('preview.generating')}
    >
      <div className="absolute inset-0 preview-gen-shimmer pointer-events-none" />

      {particles.map((p) => (
        <SparkleParticle key={p.emoji + p.style.left} emoji={p.emoji} style={p.style} />
      ))}

      <div className="relative flex flex-col items-center px-6 text-center">
        <ForgeBuddy />

        <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/20 backdrop-blur-sm border border-white/30 text-white text-[10px] font-semibold tracking-wide uppercase">
          <TypeIcon generatingType={generatingType} />
          {t('preview.generating')}
        </div>

        <p
          key={messageIndex}
          className="mt-3 text-[13px] font-bold text-white drop-shadow-md preview-gen-message"
        >
          {t(messageKeys[messageIndex])}
        </p>

        <div className="flex items-center gap-1.5 mt-4">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="w-2 h-2 rounded-full bg-white preview-gen-dot"
              style={{ animationDelay: `${i * 0.2}s` }}
            />
          ))}
        </div>

        <div className="mt-5 w-44">
          <div className="flex items-center justify-between text-[10px] font-semibold text-white/90 mb-1.5">
            <span>{stageLabel ?? t('preview.generating')}</span>
            <span aria-hidden>{displayProgress}%</span>
          </div>
          <div
            className="h-1.5 rounded-full bg-white/20 overflow-hidden"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={displayProgress}
            aria-label={stageLabel ?? t('preview.generating')}
          >
            <div
              className="h-full rounded-full bg-white/90 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.max(displayProgress, 4)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
