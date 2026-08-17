import { useEffect, useState } from 'react';
import {
  listImageProviders,
  listProviderModels,
  getImageSizeCapabilities,
  type ImageProvider,
  type ImageModelInfo,
  type ImageSizeOption,
} from '@/api/imageProviders';
import { useI18n } from '@/i18n/useI18n';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import AspectRatioSelect, { ASPECT_RATIO_CUSTOM_VALUE } from '@/components/AspectRatioSelect';
import AspectRatioGlyph, { parseSizeString } from '@/components/AspectRatioGlyph';

const CUSTOM_VALUE = ASPECT_RATIO_CUSTOM_VALUE;
const SIZE_INPUT_RE = /^(\d{2,5})[xX*](\d{2,5})$/;

export interface ImageModelSelection {
  image_provider_id?: string | null;
  image_model?: string | null;
  image_size?: string | null;
}

interface ImageModelPickerProps {
  value: ImageModelSelection;
  onChange: (next: ImageModelSelection) => void;
  disabled?: boolean;
  compact?: boolean;
}

function normalizeSizeInput(raw: string): string | null {
  const m = raw.trim().match(SIZE_INPUT_RE);
  if (!m) return null;
  return `${Number(m[1])}x${Number(m[2])}`;
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
  const [sizes, setSizes] = useState<ImageSizeOption[]>([]);
  const [defaultSize, setDefaultSize] = useState('2048x2048');
  const [allowCustom, setAllowCustom] = useState(true);
  const [customDraft, setCustomDraft] = useState('');
  const [forceCustom, setForceCustom] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [loadingSizes, setLoadingSizes] = useState(false);

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

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoadingSizes(true);
      try {
        const res = await getImageSizeCapabilities({
          provider_id: value.image_provider_id,
          model: value.image_model,
        });
        if (cancelled) return;
        setSizes(res.supported_sizes);
        setDefaultSize(res.default_size);
        setAllowCustom(res.allow_custom !== false);
        const presets = new Set(res.supported_sizes.map((s) => s.size));
        if (!value.image_size) {
          onChange({ ...value, image_size: res.default_size });
        } else if (!presets.has(value.image_size)) {
          setForceCustom(true);
          setCustomDraft(value.image_size);
        }
      } catch (e) {
        if (!cancelled) {
          console.error('Failed to load image size capabilities:', e);
          setSizes([]);
        }
      } finally {
        if (!cancelled) setLoadingSizes(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refetch on provider/model
  }, [value.image_provider_id, value.image_model]);

  const selected = models.find((m) => m.id === value.image_model);
  const currentSize = value.image_size || defaultSize;
  const presetSet = new Set(sizes.map((s) => s.size));
  const isCustom =
    allowCustom && (forceCustom || (!!value.image_size && !presetSet.has(value.image_size)));
  const selectValue = isCustom ? CUSTOM_VALUE : currentSize;
  const customNormalized = normalizeSizeInput(customDraft);
  const customInvalid = isCustom && customDraft.trim().length > 0 && !customNormalized;

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
              image_size: value.image_size || defaultSize,
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

      <div>
        <LabelWithTooltip
          label={`${t('imageModelPicker.aspectRatio')}${loadingSizes ? ` ${t('imageModelPicker.loading')}` : ''}`}
          tooltip={t('imageModelPicker.tooltips.aspectRatio')}
        />
        <AspectRatioSelect
          sizes={sizes}
          value={selectValue}
          currentSize={currentSize}
          isCustom={isCustom}
          allowCustom={allowCustom}
          disabled={disabled || loadingSizes || (sizes.length === 0 && !allowCustom)}
          onChange={(next) => {
            if (next === CUSTOM_VALUE) {
              setForceCustom(true);
              setCustomDraft(value.image_size || customDraft || '');
              return;
            }
            setForceCustom(false);
            onChange({ ...value, image_size: next || defaultSize });
          }}
        />
        {isCustom && (
          <>
            <div className="mt-2 flex items-center gap-2">
              {customNormalized ? (
                <AspectRatioGlyph
                  width={parseSizeString(customNormalized)?.width}
                  height={parseSizeString(customNormalized)?.height}
                />
              ) : (
                <AspectRatioGlyph variant="custom" />
              )}
              <input
                type="text"
                value={customDraft}
                disabled={disabled}
                onChange={(e) => {
                  const raw = e.target.value;
                  setCustomDraft(raw);
                  setForceCustom(true);
                  const normalized = normalizeSizeInput(raw);
                  if (normalized) {
                    onChange({ ...value, image_size: normalized });
                  }
                }}
                placeholder={t('placeholders.imageModelPicker.customSize')}
                className="flex-1 min-w-0 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100"
              />
            </div>
            {customInvalid ? (
              <p className="text-xs text-amber-600 mt-1">{t('imageModelPicker.customSizeHint')}</p>
            ) : (
              <p className="text-xs text-gray-500 mt-1">{t('imageModelPicker.customSizeHint')}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
