import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import type { ImageSizeOption } from '@/api/imageProviders';
import AspectRatioGlyph, { parseSizeString } from '@/components/AspectRatioGlyph';
import { useI18n } from '@/i18n/useI18n';

export const ASPECT_RATIO_CUSTOM_VALUE = '__custom__';

interface AspectRatioSelectProps {
  sizes: ImageSizeOption[];
  value: string;
  currentSize: string;
  isCustom: boolean;
  allowCustom: boolean;
  disabled?: boolean;
  onChange: (value: string) => void;
}

function OptionLabel({
  label,
  width,
  height,
  selected,
}: {
  label: string;
  width?: number;
  height?: number;
  selected?: boolean;
}) {
  return (
    <span className="flex items-center gap-3 min-w-0 flex-1">
      <AspectRatioGlyph width={width} height={height} />
      <span className="min-w-0 text-left leading-snug">
        <span className="font-medium text-gray-900">{label}</span>
        {width && height ? (
          <span className="text-gray-500 ml-1.5 text-xs tabular-nums">
            {width}×{height}
          </span>
        ) : null}
      </span>
      {selected ? <Check className="w-4 h-4 text-forge-600 shrink-0" /> : null}
    </span>
  );
}

export default function AspectRatioSelect({
  sizes,
  value,
  currentSize,
  isCustom,
  allowCustom,
  disabled = false,
  onChange,
}: AspectRatioSelectProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const selectedPreset = sizes.find((s) => s.size === value);
  const customDims = isCustom ? parseSizeString(currentSize) : null;

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
    ? t('imageModelPicker.customSize')
    : selectedPreset?.label ?? currentSize;

  const triggerWidth = isCustom ? customDims?.width : selectedPreset?.width;
  const triggerHeight = isCustom ? customDims?.height : selectedPreset?.height;

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
        <span className="flex items-center gap-3 min-w-0 flex-1">
          {isCustom ? (
            <AspectRatioGlyph variant="custom" />
          ) : (
            <AspectRatioGlyph width={triggerWidth} height={triggerHeight} />
          )}
          <span className="min-w-0 text-left truncate">
            <span className="font-medium text-gray-900">{triggerLabel}</span>
            {triggerWidth && triggerHeight ? (
              <span className="text-gray-500 ml-1.5 text-xs tabular-nums">
                {triggerWidth}×{triggerHeight}
              </span>
            ) : null}
          </span>
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
          {sizes.map((size) => {
            const selected = !isCustom && value === size.size;
            return (
              <li key={size.size} role="option" aria-selected={selected}>
                <button
                  type="button"
                  className={`w-full px-3 py-2.5 text-sm hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                    selected ? 'bg-forge-50/60' : ''
                  }`}
                  onClick={() => {
                    onChange(size.size);
                    setOpen(false);
                  }}
                >
                  <OptionLabel
                    label={size.label}
                    width={size.width}
                    height={size.height}
                    selected={selected}
                  />
                </button>
              </li>
            );
          })}
          {allowCustom && (
            <li role="option" aria-selected={isCustom}>
              <button
                type="button"
                className={`w-full px-3 py-2.5 text-sm hover:bg-gray-50 focus:bg-gray-50 focus:outline-none ${
                  isCustom ? 'bg-forge-50/60' : ''
                }`}
                onClick={() => {
                  onChange(ASPECT_RATIO_CUSTOM_VALUE);
                  setOpen(false);
                }}
              >
                <span className="flex items-center gap-3 min-w-0 flex-1">
                  <AspectRatioGlyph variant="custom" />
                  <span className="font-medium text-gray-900">{t('imageModelPicker.customSize')}</span>
                  {isCustom ? <Check className="w-4 h-4 text-forge-600 shrink-0 ml-auto" /> : null}
                </span>
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
