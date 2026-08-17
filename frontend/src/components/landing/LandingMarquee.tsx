import { useI18n } from '@/i18n/useI18n';

const ITEM_KEYS = [
  'landing.marquee1',
  'landing.marquee2',
  'landing.marquee3',
  'landing.marquee4',
  'landing.marquee5',
  'landing.marquee6',
] as const;

export default function LandingMarquee() {
  const { t } = useI18n();
  const items = ITEM_KEYS.map((key) => t(key));

  return (
    <div className="relative border-y border-canvas-border bg-white overflow-hidden">
      <div className="flex animate-landing-marquee whitespace-nowrap py-3">
        {[...items, ...items].map((item, i) => (
          <span
            key={`${item}-${i}`}
            className="mx-6 text-sm font-medium text-ink-500 flex items-center gap-2 shrink-0"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-forge-500" />
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
