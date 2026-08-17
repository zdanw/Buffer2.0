import type { SVGProps } from 'react';

type StatusTone = 'light' | 'dark';
type StatusBarSize = 'md' | 'sm';

const STATUS_BAR_METRICS: Record<
  StatusBarSize,
  { cellular: { w: number; h: number }; wifi: { w: number; h: number }; battery: { w: number; h: number }; gap: string }
> = {
  md: {
    cellular: { w: 17, h: 11 },
    wifi: { w: 15, h: 11 },
    battery: { w: 27, h: 13 },
    gap: 'gap-[5px]',
  },
  sm: {
    cellular: { w: 10, h: 7 },
    wifi: { w: 9, h: 6 },
    battery: { w: 16, h: 8 },
    gap: 'gap-[2px]',
  },
};

type StatusBarIconsProps = {
  tone?: StatusTone;
  size?: StatusBarSize;
  className?: string;
};

function toneColor(tone: StatusTone) {
  return tone === 'light' ? '#FFFFFF' : '#000000';
}

/** iOS-style status glyphs (not third-party brands). */
export function CellularIcon({
  tone = 'dark',
  size = 'md',
  className = '',
  ...props
}: SVGProps<SVGSVGElement> & { tone?: StatusTone; size?: StatusBarSize }) {
  const fill = toneColor(tone);
  const { w, h } = STATUS_BAR_METRICS[size].cellular;
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 17 11"
      className={`shrink-0 ${className}`}
      aria-hidden
      {...props}
    >
      <rect x={0} y={7} width={3} height={4} rx={0.75} fill={fill} />
      <rect x={4.5} y={5} width={3} height={6} rx={0.75} fill={fill} />
      <rect x={9} y={2.5} width={3} height={8.5} rx={0.75} fill={fill} />
      <rect x={13.5} y={0} width={3} height={11} rx={0.75} fill={fill} />
    </svg>
  );
}

export function WifiIcon({
  tone = 'dark',
  size = 'md',
  className = '',
  ...props
}: SVGProps<SVGSVGElement> & { tone?: StatusTone; size?: StatusBarSize }) {
  const fill = toneColor(tone);
  const { w, h } = STATUS_BAR_METRICS[size].wifi;
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 15 11"
      className={`shrink-0 ${className}`}
      aria-hidden
      {...props}
    >
      <path
        fill={fill}
        d="M7.5 10.25a1.25 1.25 0 1 0 0-2.5 1.25 1.25 0 0 0 0 2.5z"
      />
      <path
        fill={fill}
        d="M3.86 7.13a6.92 6.92 0 0 1 7.28 0 1 1 0 1 0 1.06-1.69 8.92 8.92 0 0 0-9.34 0 1 1 0 1 0 1.06 1.69z"
      />
      <path
        fill={fill}
        d="M1.28 4.38a11.62 11.62 0 0 1 15.44 0 1 1 0 0 0 1.32-1.5 13.62 13.62 0 0 0-18.04 0 1 1 0 0 0 1.32 1.5z"
      />
    </svg>
  );
}

export function BatteryIcon({
  tone = 'dark',
  size = 'md',
  className = '',
  ...props
}: SVGProps<SVGSVGElement> & { tone?: StatusTone; size?: StatusBarSize }) {
  const stroke = toneColor(tone);
  const fill = toneColor(tone);
  const { w, h } = STATUS_BAR_METRICS[size].battery;
  return (
    <svg
      width={w}
      height={h}
      viewBox="0 0 27 13"
      className={`shrink-0 ${className}`}
      aria-hidden
      {...props}
    >
      <rect
        x={0.5}
        y={0.5}
        width={22}
        height={12}
        rx={3}
        fill="none"
        stroke={stroke}
        strokeWidth={1}
      />
      <rect x={2.5} y={2.5} width={17} height={8} rx={2} fill={fill} />
      <path
        fill={fill}
        d="M24.5 4.5v4c.7-.3 1.2-.9 1.2-1.8s-.5-1.5-1.2-1.8z"
      />
    </svg>
  );
}

export default function StatusBarIcons({
  tone = 'dark',
  size = 'md',
  className = '',
}: StatusBarIconsProps) {
  const metrics = STATUS_BAR_METRICS[size];
  return (
    <div className={`flex items-center ${metrics.gap} ${className}`}>
      <CellularIcon tone={tone} size={size} />
      <WifiIcon tone={tone} size={size} />
      <BatteryIcon tone={tone} size={size} />
    </div>
  );
}
