import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import type { OfferingType } from '@/api/products';
import {
  persistVisualSetupChoice,
  VISUAL_SETUP_MENU,
  visualSetupChoiceKey,
  type VisualSetupChoice,
  type VisualSetupMenuItem,
} from '@/lib/visualSetup';
import { useI18n } from '@/i18n/useI18n';

interface VisualSetupRowProps {
  value: OfferingType | undefined;
  suggestion?: string | null;
  onChange: (value: OfferingType) => void;
}

export default function VisualSetupRow({
  value,
  suggestion,
  onChange,
}: VisualSetupRowProps) {
  const { t } = useI18n();
  const listboxId = useId();
  const triggerId = useId();
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);

  const current = (value || 'unknown') as OfferingType;
  const explicit = visualSetupChoiceKey(current);
  const suggested = !explicit ? visualSetupChoiceKey(suggestion) : null;
  const display = explicit || suggested;

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!wrapRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointer);
    return () => document.removeEventListener('mousedown', onPointer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const idx = explicit
      ? VISUAL_SETUP_MENU.indexOf(explicit)
      : VISUAL_SETUP_MENU.indexOf('unknown');
    setHighlight(idx >= 0 ? idx : 0);
  }, [open, explicit]);

  const pick = (choice: VisualSetupMenuItem) => {
    onChange(persistVisualSetupChoice(current, choice));
    setOpen(false);
    buttonRef.current?.focus();
  };

  const labelFor = (choice: VisualSetupChoice) =>
    t(`assets.visualSetupChoices.${choice}`);

  const menuLabel = (item: VisualSetupMenuItem) =>
    item === 'unknown' ? t('assets.visualSetupAutoDetect') : labelFor(item);

  const valueText = display
    ? suggested
      ? `${labelFor(display)} · ${t('assets.visualSetupSuggested')}`
      : labelFor(display)
    : t('assets.visualSetupAutoDetect');

  const moveHighlight = (delta: number) => {
    setHighlight((prev) => {
      return (prev + delta + VISUAL_SETUP_MENU.length) % VISUAL_SETUP_MENU.length;
    });
  };

  const onTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      moveHighlight(event.key === 'ArrowDown' ? 1 : -1);
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (open) {
        pick(VISUAL_SETUP_MENU[highlight]);
      } else {
        setOpen(true);
      }
      return;
    }
    if (event.key === 'Escape') {
      event.preventDefault();
      setOpen(false);
    }
  };

  const isSelected = (item: VisualSetupMenuItem) =>
    item === 'unknown' ? !explicit : explicit === item;

  return (
    <div ref={wrapRef} className="relative isolate">
      <LabelWithTooltip
        htmlFor={triggerId}
        label={t('assets.visualSetup')}
        tooltip={t('assets.tooltips.visualSetup')}
      />
      <button
        id={triggerId}
        ref={buttonRef}
        type="button"
        className="w-full px-3 py-1.5 border border-gray-300 rounded-lg bg-white text-left flex items-center justify-between gap-3 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-forge-500 focus:border-transparent"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onTriggerKeyDown}
      >
        <span className="min-w-0 truncate text-sm text-gray-800">
          {valueText}
        </span>
        <span className="shrink-0 inline-flex items-center gap-1 text-sm font-medium text-forge-600">
          {t('assets.visualSetupChange')}
          <ChevronDown className={`w-4 h-4 text-gray-400 ${open ? 'rotate-180' : ''}`} />
        </span>
      </button>
      {!display ? (
        <p className="mt-1 text-xs text-gray-500">{t('assets.visualSetupHint')}</p>
      ) : null}
      {open && (
        <ul
          id={listboxId}
          role="listbox"
          aria-labelledby={triggerId}
          className="absolute left-0 right-0 z-30 mt-1 max-h-56 overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
        >
          {VISUAL_SETUP_MENU.map((item, index) => {
            const selected = isSelected(item);
            const highlighted = highlight === index;
            return (
              <li key={item} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  tabIndex={-1}
                  onMouseEnter={() => setHighlight(index)}
                  onClick={() => pick(item)}
                  className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm ${
                    highlighted ? 'bg-forge-50 text-gray-900' : 'text-gray-700'
                  } hover:bg-forge-50 focus:bg-forge-50 focus:outline-none`}
                >
                  <span>{menuLabel(item)}</span>
                  {selected ? (
                    <Check className="w-4 h-4 shrink-0 text-forge-600" aria-hidden />
                  ) : (
                    <span className="w-4 h-4 shrink-0" aria-hidden />
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
