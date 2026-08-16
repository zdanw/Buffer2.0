import { APP_VERSION } from '@/version';

type VersionLabelProps = {
  variant?: 'sidebar' | 'light';
};

export default function VersionLabel({ variant = 'sidebar' }: VersionLabelProps) {
  const isLight = variant === 'light';

  return (
    <p
      className={`mt-2 text-center text-[10px] tracking-wide ${
        isLight ? 'text-ink-400' : 'text-white/30'
      }`}
    >
      v{APP_VERSION}
    </p>
  );
}
