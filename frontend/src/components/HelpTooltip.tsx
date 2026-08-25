import { useCallback, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { HelpCircle } from 'lucide-react';

type HelpTooltipProps = {
  content: string;
  className?: string;
};

const TOOLTIP_WIDTH = 320;

function estimateTooltipHeight(content: string): number {
  const paragraphs = content.split('\n\n').filter(Boolean);
  let height = 16; // vertical padding
  for (const para of paragraphs) {
    const lines = Math.max(1, Math.ceil(para.length / 42));
    height += lines * 18 + 8;
  }
  return Math.min(360, height);
}

function TooltipBody({ content }: { content: string }) {
  const paragraphs = content.split('\n\n').filter(Boolean);

  return (
    <>
      {paragraphs.map((para, i) => {
        const trimmed = para.trim();
        const isExample = /^(Example|例|Tip|提示|Off|关闭|On|开启)/i.test(trimmed);
        return (
          <p
            key={i}
            className={
              i > 0
                ? isExample
                  ? 'mt-2 border-t border-gray-700 pt-2 text-gray-300'
                  : 'mt-2'
                : ''
            }
          >
            {trimmed}
          </p>
        );
      })}
    </>
  );
}

export default function HelpTooltip({ content, className = '' }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipId = useId();

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const width = TOOLTIP_WIDTH;
    const margin = 8;
    const left = Math.min(
      Math.max(margin, rect.left + rect.width / 2 - width / 2),
      window.innerWidth - width - margin,
    );
    const below = rect.bottom + margin;
    const estimatedHeight = estimateTooltipHeight(content);
    const top =
      below + estimatedHeight > window.innerHeight - margin
        ? rect.top - estimatedHeight - margin
        : below;

    setCoords({ top: Math.max(margin, top), left });
  }, [content]);

  const show = () => {
    updatePosition();
    setOpen(true);
  };

  const hide = () => setOpen(false);

  const ariaLabel = content.split('\n\n')[0]?.trim() ?? content;

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    const onReposition = () => updatePosition();
    window.addEventListener('scroll', onReposition, true);
    window.addEventListener('resize', onReposition);
    return () => {
      window.removeEventListener('scroll', onReposition, true);
      window.removeEventListener('resize', onReposition);
    };
  }, [open, updatePosition]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        tabIndex={0}
        className={`rounded text-gray-400 hover:text-gray-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-forge-500 ${className}`}
        aria-label={ariaLabel}
        aria-describedby={open ? tooltipId : undefined}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={() => (open ? hide() : show())}
      >
        <HelpCircle className="h-4 w-4" />
      </button>
      {open &&
        createPortal(
          <div
            id={tooltipId}
            role="tooltip"
            className="pointer-events-none fixed z-[200] w-80 rounded-lg bg-gray-900 px-3 py-2.5 text-left text-xs leading-relaxed text-white shadow-lg"
            style={{ top: coords.top, left: coords.left }}
          >
            <TooltipBody content={content} />
          </div>,
          document.body,
        )}
    </>
  );
}
