import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type PointerEvent as ReactPointerEvent, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

const TOOLTIP_WIDTH = 280;
const VIEWPORT_MARGIN = 8;
const OVERFLOW_EPSILON = 1;

function subtreeOverflows(el: HTMLElement): boolean {
  if (el.scrollWidth > el.clientWidth + OVERFLOW_EPSILON) return true;
  if (el.scrollHeight > el.clientHeight + OVERFLOW_EPSILON) return true;
  for (let i = 0; i < el.children.length; i += 1) {
    const child = el.children[i];
    if (child instanceof HTMLElement && subtreeOverflows(child)) return true;
  }
  return false;
}

export default function OverflowHoverTooltip({
  text,
  className = '',
  children,
}: {
  text: string;
  className?: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipId = useId();

  const canOpen = useCallback(() => {
    if (!text.trim()) return false;
    const el = triggerRef.current;
    return Boolean(el && subtreeOverflows(el));
  }, [text]);

  const updatePosition = useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const left = Math.min(
      Math.max(VIEWPORT_MARGIN, rect.left),
      Math.max(VIEWPORT_MARGIN, window.innerWidth - TOOLTIP_WIDTH - VIEWPORT_MARGIN),
    );
    const estimatedHeight = Math.min(280, 40 + Math.ceil(text.length / 36) * 18);
    const below = rect.bottom + VIEWPORT_MARGIN;
    const top =
      below + estimatedHeight > window.innerHeight - VIEWPORT_MARGIN
        ? rect.top - estimatedHeight - VIEWPORT_MARGIN
        : below;
    setCoords({ top: Math.max(VIEWPORT_MARGIN, top), left });
  }, [text]);

  const hide = useCallback(() => setOpen(false), []);

  const show = useCallback(() => {
    if (!canOpen()) return;
    window.dispatchEvent(new Event('pf-overflow-tooltip-show'));
    updatePosition();
    setOpen(true);
  }, [canOpen, updatePosition]);

  useEffect(() => {
    const closeFromOther = () => setOpen(false);
    window.addEventListener('pf-overflow-tooltip-show', closeFromOther);
    return () => window.removeEventListener('pf-overflow-tooltip-show', closeFromOther);
  }, []);

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

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      hide();
    };
    const onPointerDown = (event: globalThis.PointerEvent) => {
      const node = event.target as Node | null;
      if (node && triggerRef.current?.contains(node)) return;
      hide();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [hide, open]);

  const onPointerUp = (event: ReactPointerEvent<HTMLSpanElement>) => {
    if (event.pointerType === 'mouse') return;
    if (open) {
      hide();
      return;
    }
    show();
  };

  return (
    <>
      <span
        ref={triggerRef}
        tabIndex={0}
        data-testid="overflow-tooltip-trigger"
        className={className}
        aria-describedby={open ? tooltipId : undefined}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onPointerUp={onPointerUp}
      >
        {children}
      </span>
      {open &&
        typeof document !== 'undefined' &&
        createPortal(
          <div
            id={tooltipId}
            role="tooltip"
            data-testid="overflow-tooltip"
            className="pointer-events-none fixed z-[200] max-w-[280px] rounded-lg bg-gray-900 px-3 py-2 text-left text-xs leading-relaxed text-white shadow-lg whitespace-pre-wrap break-words"
            style={{ top: coords.top, left: coords.left, width: TOOLTIP_WIDTH }}
          >
            {text}
          </div>,
          document.body,
        )}
    </>
  );
}
