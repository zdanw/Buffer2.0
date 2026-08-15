import { APP_VERSION } from '@/version';

type VersionLabelProps = {
  variant?: 'sidebar' | 'light';
};

export default function VersionLabel({ variant = 'sidebar' }: VersionLabelProps) {
  const isLight = variant === 'light';

  return (
    <p
      className={`mt-2 text-center text-[10px] tracking-wide ${
        isLight ? 'text-gray-400' : 'text-indigo-400/70'
      }`}
    >
      v{APP_VERSION}
    </p>
  );
}
