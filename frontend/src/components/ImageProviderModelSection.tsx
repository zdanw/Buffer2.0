import { AlertCircle, RefreshCw } from 'lucide-react';
import type { ImageModelInfo } from '@/api/imageProviders';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import LoadingIndicator from '@/components/LoadingIndicator';
import { useI18n } from '@/i18n/useI18n';

export type DiscoverStatus = 'idle' | 'loading' | 'success' | 'failed';

type ImageProviderModelSectionProps = {
  keepingExistingKey: boolean;
  apiKey: string;
  apiKeyTouched: boolean;
  defaultModel: string;
  onDefaultModelChange: (value: string) => void;
  modelPlaceholder: string;
  discoverStatus: DiscoverStatus;
  discoverMessage: string | null;
  discoveredModels: ImageModelInfo[];
  showManualModel: boolean;
  onUseManualModel: () => void;
  onRetryDiscover: () => void;
};

export default function ImageProviderModelSection({
  keepingExistingKey,
  apiKey,
  apiKeyTouched,
  defaultModel,
  onDefaultModelChange,
  modelPlaceholder,
  discoverStatus,
  discoverMessage,
  discoveredModels,
  showManualModel,
  onUseManualModel,
  onRetryDiscover,
}: ImageProviderModelSectionProps) {
  const { t } = useI18n();
  const trimmedKey = apiKey.trim();
  const hasDiscoverableKey = trimmedKey.length >= 8;

  if (keepingExistingKey) {
    return (
      <div>
        <LabelWithTooltip
          htmlFor="provider-default-model"
          label={t('imageProviders.fields.defaultModel.label')}
          tooltip={t('imageProviders.fields.defaultModel.tooltip')}
          required
        />
        <p className="text-xs text-gray-500 mb-2">{t('imageProviders.discover.editSavedHint')}</p>
        <input
          id="provider-default-model"
          value={defaultModel}
          onChange={(e) => onDefaultModelChange(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg font-mono text-sm"
          autoComplete="off"
          data-1p-ignore
          placeholder={modelPlaceholder}
          required
        />
      </div>
    );
  }

  if (!hasDiscoverableKey) {
    return (
      <div
        className="rounded-lg border border-dashed border-gray-200 bg-gray-50 px-4 py-5 text-center"
        role="status"
      >
        <p className="text-sm text-gray-600">{t('imageProviders.discover.waitForKey')}</p>
      </div>
    );
  }

  if (discoverStatus === 'loading' || (discoverStatus === 'idle' && apiKeyTouched)) {
    return (
      <LoadingIndicator
        label={t('imageProviders.discover.loading')}
        className="rounded-lg border border-gray-200 bg-gray-50 py-8"
      />
    );
  }

  if (discoverStatus === 'success' && discoveredModels.length > 0 && !showManualModel) {
    return (
      <div className="space-y-3">
        <LabelWithTooltip
          label={t('imageProviders.fields.availableModels.label')}
          tooltip={t('imageProviders.fields.availableModels.tooltip')}
          required
        />
        <ul className="space-y-1 max-h-48 overflow-y-auto border border-gray-200 rounded-lg p-2">
          {discoveredModels.map((m) => (
            <li key={m.id}>
              <label className="flex items-start gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 cursor-pointer">
                <input
                  type="radio"
                  name="default-model"
                  checked={defaultModel === m.id}
                  onChange={() => onDefaultModelChange(m.id)}
                  className="mt-1"
                />
                <span className="min-w-0">
                  <span className="font-mono text-sm text-gray-900 break-all">{m.id}</span>
                  {m.owned_by ? (
                    <span className="block text-xs text-gray-400">{m.owned_by}</span>
                  ) : null}
                </span>
              </label>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={onUseManualModel}
          className="text-xs text-gray-500 hover:text-forge-700 underline underline-offset-2"
        >
          {t('imageProviders.discover.useManualInstead')}
        </button>
      </div>
    );
  }

  const failureMessage =
    discoverMessage ||
    (discoverStatus === 'success' && discoveredModels.length === 0
      ? t('imageProviders.discover.emptyList')
      : t('imageProviders.discover.failed'));

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 flex items-start gap-2">
        <AlertCircle className="w-4 h-4 text-amber-700 mt-0.5 shrink-0" />
        <div className="min-w-0 space-y-2">
          <p className="text-sm text-amber-800">{failureMessage}</p>
          <button
            type="button"
            onClick={onRetryDiscover}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-900 hover:text-amber-950"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            {t('imageProviders.discover.retry')}
          </button>
        </div>
      </div>

      <div>
        <LabelWithTooltip
          htmlFor="provider-default-model"
          label={t('imageProviders.fields.customModel.label')}
          tooltip={t('imageProviders.fields.customModel.tooltip')}
          required
        />
        <input
          id="provider-default-model"
          value={defaultModel}
          onChange={(e) => onDefaultModelChange(e.target.value)}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg font-mono text-sm"
          autoComplete="off"
          data-1p-ignore
          placeholder={modelPlaceholder}
          required
        />
        <p className="text-xs text-gray-500 mt-1.5">{t('imageProviders.discover.manualHint')}</p>
      </div>
    </div>
  );
}
