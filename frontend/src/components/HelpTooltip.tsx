import { useCallback, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { HelpCircle } from 'lucide-react';

type HelpTooltipProps = {
  content: string;
  className?: string;
};

export default function HelpTooltip({ content, className = '' }: HelpTooltipProps) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipId = useId();

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const width = 256;
    const margin = 8;
    const left = Math.min(
      Math.max(margin, rect.left + rect.width / 2 - width / 2),
      window.innerWidth - width - margin,
    );
    const below = rect.bottom + margin;
    const estimatedHeight = 80;
    const top =
      below + estimatedHeight > window.innerHeight - margin
        ? rect.top - estimatedHeight - margin
        : below;

    setCoords({ top: Math.max(margin, top), left });
  }, []);

  const show = () => {
    updatePosition();
    setOpen(true);
  };

  const hide = () => setOpen(false);

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
        aria-label={content}
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
            className="pointer-events-none fixed z-[200] w-64 rounded-lg bg-gray-900 px-3 py-2 text-left text-xs leading-relaxed text-white shadow-lg"
            style={{ top: coords.top, left: coords.left }}
          >
            {content}
          </div>,
          document.body,
        )}
    </>
  );
}
