import ImageModelPicker from '@/components/ImageModelPicker';
import { useI18n } from '@/i18n/useI18n';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];

export interface CreatePanelProps {
  selectedPlatforms: string[];
  onPlatformsChange: (platforms: string[]) => void;
  useSceneReference: boolean;
  onUseSceneReferenceChange: (value: boolean) => void;
  useVisionImagePrompt: boolean;
  onUseVisionImagePromptChange: (value: boolean) => void;
  imageProviderId: string | null;
  imageModel: string | null;
  onImageProviderChange: (id: string | null) => void;
  onImageModelChange: (model: string | null) => void;
  compact?: boolean;
}

export default function CreatePanel({
  selectedPlatforms,
  onPlatformsChange,
  useSceneReference,
  onUseSceneReferenceChange,
  useVisionImagePrompt,
  onUseVisionImagePromptChange,
  imageProviderId,
  imageModel,
  onImageProviderChange,
  onImageModelChange,
  compact = false,
}: CreatePanelProps) {
  const { t } = useI18n();

  const togglePlatform = (platform: string) => {
    if (selectedPlatforms.includes(platform)) {
      onPlatformsChange(selectedPlatforms.filter((p) => p !== platform));
    } else {
      onPlatformsChange([...selectedPlatforms, platform]);
    }
  };

  return (
    <div className={`space-y-4 ${compact ? '' : 'bg-white rounded-xl border border-gray-200 p-4'}`}>
      <div>
        <div className="text-sm font-medium text-gray-700 mb-2">{t('preview.platform')}</div>
        <div className="flex flex-wrap gap-2">
          {PLATFORMS.map((platform) => (
            <button
              key={platform}
              type="button"
              onClick={() => togglePlatform(platform)}
              className={`px-3 py-1.5 rounded-lg text-sm capitalize transition-colors cursor-pointer ${
                selectedPlatforms.includes(platform)
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {platform}
            </button>
          ))}
        </div>
      </div>

      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={useSceneReference}
          onChange={(e) => onUseSceneReferenceChange(e.target.checked)}
          className="mt-1 rounded border-gray-300 text-indigo-600"
        />
        <div>
          <div className="text-sm font-medium text-gray-700">{t('preview.enableSceneReference')}</div>
          <p className="text-xs text-gray-500 mt-1">{t('preview.sceneRefHint')}</p>
        </div>
      </label>

      <label className="flex items-start gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={useVisionImagePrompt}
          onChange={(e) => onUseVisionImagePromptChange(e.target.checked)}
          className="mt-1 rounded border-gray-300 text-indigo-600"
        />
        <div>
          <div className="text-sm font-medium text-gray-700">{t('preview.visionImagePrompt')}</div>
          <p className="text-xs text-gray-500 mt-1">{t('preview.visionHint')}</p>
        </div>
      </label>

      <ImageModelPicker
        value={{ image_provider_id: imageProviderId, image_model: imageModel }}
        onChange={(next) => {
          onImageProviderChange(next.image_provider_id ?? null);
          onImageModelChange(next.image_model ?? null);
        }}
      />
    </div>
  );
}
