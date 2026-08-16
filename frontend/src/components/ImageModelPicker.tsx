import { useEffect, useState } from 'react';
import {
  listImageProviders,
  listProviderModels,
  type ImageProvider,
  type ImageModelInfo,
} from '@/api/imageProviders';
import { useI18n } from '@/i18n/useI18n';
import LabelWithTooltip from '@/components/LabelWithTooltip';

export interface ImageModelSelection {
  image_provider_id?: string | null;
  image_model?: string | null;
}

interface ImageModelPickerProps {
  value: ImageModelSelection;
  onChange: (next: ImageModelSelection) => void;
  disabled?: boolean;
  compact?: boolean;
}

export default function ImageModelPicker({
  value,
  onChange,
  disabled = false,
  compact = false,
}: ImageModelPickerProps) {
  const { t } = useI18n();
  const [providers, setProviders] = useState<ImageProvider[]>([]);
  const [models, setModels] = useState<ImageModelInfo[]>([]);
  const [hint, setHint] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);

  useEffect(() => {
    void (async () => {
      setLoadingProviders(true);
      try {
        const list = await listImageProviders();
        setProviders(list.filter((p) => p.is_active));
      } catch (e) {
        console.error('Failed to load image providers:', e);
      } finally {
        setLoadingProviders(false);
      }
    })();
  }, []);

  useEffect(() => {
    const providerId = value.image_provider_id;
    if (!providerId) {
      setModels([]);
      setHint(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      setLoadingModels(true);
      try {
        const res = await listProviderModels(providerId);
        if (cancelled) return;
        setModels(res.models);
        setHint(res.message || null);
        const provider = providers.find((p) => p.id === providerId);
        if (!value.image_model && provider?.default_model) {
          onChange({ ...value, image_model: provider.default_model });
        }
      } catch (e) {
        if (!cancelled) {
          setModels([]);
          setHint(t('imageModelPicker.fetchFailed'));
        }
      } finally {
        if (!cancelled) setLoadingModels(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only refetch when provider changes
  }, [value.image_provider_id]);

  const selected = models.find((m) => m.id === value.image_model);

  const wrapClass = compact
    ? 'space-y-2'
    : 'bg-white rounded-xl shadow-sm border border-gray-200 p-4 space-y-3';

  return (
    <div className={wrapClass}>
      {!compact && (
        <LabelWithTooltip
          label={t('imageModelPicker.title')}
          tooltip={t('imageModelPicker.tooltips.title')}
        />
      )}

      <div>
        <LabelWithTooltip
          label={`${t('imageModelPicker.provider')}${loadingProviders ? ` ${t('imageModelPicker.loading')}` : ''}`}
          tooltip={t('imageModelPicker.tooltips.provider')}
        />
        <select
          value={value.image_provider_id || ''}
          disabled={disabled || loadingProviders}
          onChange={(e) => {
            const id = e.target.value || null;
            const provider = providers.find((p) => p.id === id);
            onChange({
              image_provider_id: id,
              image_model: provider?.default_model || null,
            });
          }}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100"
        >
          <option value="">{t('imageModelPicker.systemDefault')}</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {p.is_default ? t('imageModelPicker.defaultSuffix') : ''}
            </option>
          ))}
        </select>
      </div>

      <div>
        <LabelWithTooltip
          label={`${t('imageModelPicker.modelId')}${loadingModels ? ` ${t('imageModelPicker.loading')}` : ''}`}
          tooltip={t('imageModelPicker.tooltips.modelId')}
        />
        {models.length > 0 ? (
          <select
            value={value.image_model || ''}
            disabled={disabled || !value.image_provider_id}
            onChange={(e) =>
              onChange({ ...value, image_model: e.target.value || null })
            }
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100"
          >
            <option value="">{t('imageModelPicker.selectOrManual')}</option>
            {models.map((m) => (
              <option key={m.id} value={m.id} title={m.description || undefined}>
                {m.id}
              </option>
            ))}
          </select>
        ) : null}
        <input
          type="text"
          value={value.image_model || ''}
          disabled={disabled || !value.image_provider_id}
          onChange={(e) =>
            onChange({ ...value, image_model: e.target.value || null })
          }
          placeholder={
            value.image_provider_id
              ? t('placeholders.imageModelPicker.manualModel')
              : t('placeholders.imageModelPicker.selectProviderFirst')
          }
          className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100"
        />
        {selected?.description && (
          <p className="text-xs text-gray-500 mt-1 whitespace-pre-wrap">{selected.description}</p>
        )}
        {hint && <p className="text-xs text-amber-600 mt-1">{hint}</p>}
      </div>
    </div>
  );
}
