import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import type { DimensionInfo, GenerationDiagnostics } from '@/api/generate';
import GenerationChecks from '@/components/GenerationChecks';
import { formatDimensionDisplayValue, NULL_DIMENSION_LABEL, areDimensionsAllNull } from '@/lib/dimensionDisplay';
import { useI18n } from '@/i18n/useI18n';

const DIMENSION_FIELD_KEYS: Record<string, string> = {
  scene: 'scenes',
  lighting: 'lighting',
  style: 'styles',
  composition: 'compositions',
  details: 'details',
  quality: 'quality',
  viewpoint: 'viewpoints',
};

const DIMENSION_FIELDS = [
  'scene',
  'lighting',
  'style',
  'composition',
  'details',
  'quality',
  'viewpoint',
] as const;

interface DimensionInfoDisplayProps {
  dimensions?: DimensionInfo | null;
  diagnostics?: GenerationDiagnostics | null;
  className?: string;
}

async function copyToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

export default function DimensionInfoDisplay({
  dimensions,
  diagnostics,
  className = '',
}: DimensionInfoDisplayProps) {
  const { t } = useI18n();
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const emptyDimensions = !dimensions || areDimensionsAllNull(dimensions);

  if (emptyDimensions && !diagnostics) {
    return null;
  }

  const markCopied = (key: string) => {
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey(null), 1500);
  };

  const handleCopyField = async (field: string, value: string) => {
    await copyToClipboard(value);
    markCopied(field);
  };

  const handleCopyAll = async () => {
    if (!dimensions) return;
    const lines = DIMENSION_FIELDS.map((field) => {
      const value = formatDimensionDisplayValue(dimensions[field]);
      return `${t(`dimensionTypes.${DIMENSION_FIELD_KEYS[field]}`)}: ${value}`;
    }).join('\n\n');
    await copyToClipboard(lines);
    markCopied('all');
  };

  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <span className="w-2 h-2 bg-red-500 rounded-full shrink-0" />
          {t('fields.dimensionInfo')}
        </h3>
        {!emptyDimensions && (
          <button
            type="button"
            onClick={() => void handleCopyAll()}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          >
            {copiedKey === 'all' ? (
              <Check className="w-3 h-3 text-green-600" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
            {t('common.copyAll')}
          </button>
        )}
      </div>

      <GenerationChecks diagnostics={diagnostics} />

      {!emptyDimensions && dimensions ? (
        <div className="space-y-1.5">
          {DIMENSION_FIELDS.map((field) => {
            const value = formatDimensionDisplayValue(dimensions[field]);
            const isNull = value === NULL_DIMENSION_LABEL;
            return (
              <div
                key={field}
                className="group rounded-md border border-gray-100 bg-gray-50/90 px-2.5 py-1.5"
              >
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
                    {t(`dimensionTypes.${DIMENSION_FIELD_KEYS[field]}`)}
                  </span>
                  <button
                    type="button"
                    onClick={() => void handleCopyField(field, value)}
                    className="p-1 rounded text-gray-400 hover:text-gray-600 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity shrink-0"
                    title={t('common.copy')}
                  >
                    {copiedKey === field ? (
                      <Check className="w-3 h-3 text-green-600" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
                <p
                  className={`text-[11px] leading-snug break-words select-text ${
                    isNull ? 'text-gray-400 italic' : 'text-gray-800'
                  }`}
                >
                  {value}
                </p>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

export function CopyablePromptBlock({
  label,
  text,
  className = '',
}: {
  label: string;
  text: string;
  className?: string;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await copyToClipboard(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className={className}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h4 className="text-xs font-medium text-gray-600">{label}</h4>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        >
          {copied ? <Check className="w-3 h-3 text-green-600" /> : <Copy className="w-3 h-3" />}
          {t('common.copy')}
        </button>
      </div>
      <div className="text-xs text-gray-700 bg-gray-50 p-3 rounded-lg max-h-40 overflow-y-auto whitespace-pre-wrap break-words select-text border border-gray-100">
        {text}
      </div>
    </div>
  );
}
