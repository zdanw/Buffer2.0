import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, PenLine } from 'lucide-react';
import type { ImageModelInfo } from '@/api/imageProviders';
import { useI18n } from '@/i18n/useI18n';

export const MODEL_CUSTOM_VALUE = '__custom__';

interface ModelIdSelectProps {
  models: ImageModelInfo[];
  value: string | null;
  isCustom: boolean;
  disabled?: boolean;
  onSelectPreset: (modelId: string) => void;
  onSelectCustom: () => void;
}

export default function ModelIdSelect({
  models,
  value,
  isCustom,
  disabled = false,
  onSelectPreset,
  onSelectCustom,
}: ModelIdSelectProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = models.find((m) => m.id === value);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  const triggerLabel = isCustom
    ? t('imageModelPicker.customModel')
    : selected?.id ?? value ?? t('imageModelPicker.selectModel');

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed disabled:hover:bg-gray-100"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 min-w-0 flex-1 text-left">
          {isCustom ? (
            <PenLine className="w-4 h-4 text-gray-400 shrink-0" strokeWidth={1.75} />
          ) : null}
          <span className="truncate font-medium text-gray-900">{triggerLabel}</span>
        </span>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && !disabled && (
        <ul
          className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg py-1 max-h-64 overflow-y-auto"
          role="listbox"
        >
          {models.map((model) => {
            const selectedItem = !isCustom && value === model.id;
            return (
              <li key={model.id} role="option" aria-selected={selectedItem}>
                <button
                  type="button"
                  className={`w-full px-3 py-2.5 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                    selectedItem ? 'bg-forge-50/60' : ''
                  }`}
                  onClick={() => {
                    onSelectPreset(model.id);
                    setOpen(false);
                  }}
                >
                  <div className="flex items-start gap-2 min-w-0">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-900 truncate">{model.id}</p>
                      {model.description ? (
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-2 leading-snug">
                          {model.description}
                        </p>
                      ) : null}
                    </div>
                    {selectedItem ? (
                      <Check className="w-4 h-4 text-forge-600 shrink-0 mt-0.5" />
                    ) : null}
                  </div>
                </button>
              </li>
            );
          })}
          <li role="option" aria-selected={isCustom}>
            <button
              type="button"
              className={`w-full px-3 py-2.5 text-left hover:bg-gray-50 focus:bg-gray-50 focus:outline-none flex items-center gap-2 ${
                isCustom ? 'bg-forge-50/60' : ''
              }`}
              onClick={() => {
                onSelectCustom();
                setOpen(false);
              }}
            >
              <PenLine className="w-4 h-4 text-gray-400 shrink-0" strokeWidth={1.75} />
              <span className="text-sm font-medium text-gray-900 flex-1">
                {t('imageModelPicker.customModel')}
              </span>
              {isCustom ? <Check className="w-4 h-4 text-forge-600 shrink-0" /> : null}
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}
