import HelpTooltip from '@/components/HelpTooltip';
import { useI18n } from '@/i18n/useI18n';
import type { ImageGenerationControlValues } from '@/lib/imageGenerationControls';

type ControlKey = keyof ImageGenerationControlValues;

interface ToggleSpec {
  field: ControlKey;
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
}

export default function ImageGenerationControls({
  value,
  onChange,
  disabled = false,
}: ImageGenerationControlsProps) {
  const { t } = useI18n();

  const toggle = (field: ControlKey) => {
    if (disabled) return;
    onChange({ ...value, [field]: !value[field] });
  };

  return (
    <>
      {TOGGLES.map(({ field, labelKey, tooltipKey }) => (
        <div
          key={field}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-4"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className="text-sm font-medium text-gray-700">{t(labelKey)}</span>
              <HelpTooltip content={t(tooltipKey)} />
            </div>
            <label className="relative inline-flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={value[field]}
                onChange={() => toggle(field)}
                disabled={disabled}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-forge-100 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-forge-600 peer-disabled:opacity-50 peer-disabled:cursor-not-allowed"></div>
            </label>
          </div>
        </div>
      ))}
    </>
  );
}
