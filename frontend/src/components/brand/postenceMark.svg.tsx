/** Postence monogram — continuous open-loop P with signal nodes (matches brand concept). */
export const POSTENCE_MARK_VIEWBOX = '0 0 32 32';

export function PostenceMarkPaths({ animated = false }: { animated?: boolean }) {
  const signalClass = animated ? 'animate-landing-signal' : undefined;

  return (
    <>
      <rect width="32" height="32" rx="7.5" fill="#0B0D14" />
      <path
        d="M10.5 23V9.75C10.5 9.75 10.5 9.75 17.25 9.75C21.75 9.75 24.25 12.35 24.25 16.1C24.25 19.55 22.1 22.35 18.35 22.85"
        stroke="#F5F1E8"
        strokeWidth="2.65"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="10.5" cy="17.25" r="1.85" fill="#406BFF" />
      <circle
        cx="22.15"
        cy="19.35"
        r="1.85"
        fill="#e85736"
        className={signalClass}
      />
    </>
  );
}
