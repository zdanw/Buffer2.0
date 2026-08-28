import HelpTooltip from '@/components/HelpTooltip';
import FieldRequirementBadge from '@/components/FieldRequirementBadge';
import { useI18n } from '@/i18n/useI18n';
import type { ImageGenerationControlValues } from '@/lib/imageGenerationControls';
import { STUDIO_REFERENCE_COUNT_MAX } from '@/lib/imageGenerationControls';

type ToggleKey = Exclude<keyof ImageGenerationControlValues, 'reference_count'>;

interface ToggleSpec {
  field: ToggleKey;
  labelKey: string;
  tooltipKey: string;
}

const TOGGLES: ToggleSpec[] = [
  {
    field: 'use_scene_reference',
    labelKey: 'preview.enableSceneReference',
    tooltipKey: 'studio.tooltips.sceneReference',
  },
  {
    field: 'use_vision_image_prompt',
    labelKey: 'preview.visionImagePrompt',
    tooltipKey: 'studio.tooltips.visionPrompt',
  },
  {
    field: 'realistic_placement',
    labelKey: 'studio.realisticPlacement',
    tooltipKey: 'studio.tooltips.realisticPlacement',
  },
];

interface ImageGenerationControlsProps {
  value: ImageGenerationControlValues;
  onChange: (next: ImageGenerationControlValues) => void;
  disabled?: boolean;
  showReferenceCount?: boolean;
}

const REFERENCE_COUNT_OPTIONS = Array.from({ length: STUDIO_REFERENCE_COUNT_MAX }, (_, i) => i + 1);

export default function ImageGenerationControls({
  value,
  onChange,
  disabled = false,
  showReferenceCount = false,
}: ImageGenerationControlsProps) {
  const { t } = useI18n();

  const toggle = (field: ToggleKey) => {
    if (disabled) return;
    onChange({ ...value, [field]: !value[field] });
  };

  return (
    <>
      {showReferenceCount && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-sm font-medium text-gray-700">{t('studio.referenceImageCount')}</span>
            <FieldRequirementBadge required={false} />
            <HelpTooltip content={t('studio.tooltips.referenceImageCount')} />
          </div>
          <select
            value={Math.min(value.reference_count, STUDIO_REFERENCE_COUNT_MAX)}
            onChange={(e) =>
              onChange({ ...value, reference_count: parseInt(e.target.value, 10) || 1 })
            }
            disabled={disabled}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {REFERENCE_COUNT_OPTIONS.map((count) => (
              <option key={count} value={count}>
                {t('studio.referenceImageCountOption', { count })}
              </option>
            ))}
          </select>
        </div>
      )}
      {TOGGLES.map(({ field, labelKey, tooltipKey }) => {
        const compareLocksVision =
          field === 'use_vision_image_prompt' &&
          value.use_scene_reference &&
          (value.compare_scene_pipelines ?? true);
        return (
        <div
          key={field}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-4"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className="text-sm font-medium text-gray-700">{t(labelKey)}</span>
              <FieldRequirementBadge required={false} />
              <HelpTooltip content={t(tooltipKey)} />
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={value[field]}
                onChange={() => toggle(field)}
                disabled={disabled || compareLocksVision}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-forge-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-forge-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
            </label>
          </div>
        </div>
      );
      })}
      {value.use_scene_reference && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className="text-sm font-medium text-gray-700">
                {t('studio.compareScenePipelines')}
              </span>
              <FieldRequirementBadge required={false} />
              <HelpTooltip content={t('studio.tooltips.compareScenePipelines')} />
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={value.compare_scene_pipelines ?? true}
                onChange={() =>
                  onChange({
                    ...value,
                    compare_scene_pipelines: !(value.compare_scene_pipelines ?? true),
                  })
                }
                disabled={disabled}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-forge-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-forge-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
            </label>
          </div>
        </div>
      )}
    </>
  );
}
