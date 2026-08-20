import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  listImageProviders,
  listProviderModels,
  getImageSizeCapabilities,
  type ImageProvider,
  type ImageModelInfo,
  type ImageSizeOption,
} from '@/api/imageProviders';
import { getCurrentUser } from '@/api/auth';
import {
  getSystemImageProviderSummary,
  type SystemProviderSummary,
} from '@/api/systemImageProvider';
import { useI18n } from '@/i18n/useI18n';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import AspectRatioSelect, { ASPECT_RATIO_CUSTOM_VALUE } from '@/components/AspectRatioSelect';
import AspectRatioGlyph, { parseSizeString } from '@/components/AspectRatioGlyph';
import ModelIdSelect from '@/components/ModelIdSelect';
import { onImageProvidersChanged } from '@/lib/imageProvidersEvents';
import { SubscribeCreditsButton } from '@/components/SubscribeCreditsModal';

const CUSTOM_VALUE = ASPECT_RATIO_CUSTOM_VALUE;
const SIZE_INPUT_RE = /^(\d{2,5})[xX*](\d{2,5})$/;

export type ImageProviderMode = 'platform' | 'byok';

export interface ImageModelSelection {
  image_provider_id?: string | null;
  image_model?: string | null;
  image_size?: string | null;
  image_provider_mode?: ImageProviderMode | null;
}

interface ImageModelPickerProps {
  value: ImageModelSelection;
  onChange: (next: ImageModelSelection) => void;
  disabled?: boolean;
  compact?: boolean;
  preferGlobalDefault?: boolean;
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
  preferGlobalDefault = false,
}: ImageModelPickerProps) {
  const { t } = useI18n();
  const location = useLocation();
  const [providers, setProviders] = useState<ImageProvider[]>([]);
  const [models, setModels] = useState<ImageModelInfo[]>([]);
  const [sizes, setSizes] = useState<ImageSizeOption[]>([]);
  const [defaultSize, setDefaultSize] = useState('2048x2048');
  const [allowCustom, setAllowCustom] = useState(true);
  const [customDraft, setCustomDraft] = useState('');
  const [forceCustom, setForceCustom] = useState(false);
  const [forceCustomModel, setForceCustomModel] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [loadingSizes, setLoadingSizes] = useState(false);
  const [creditsRemaining, setCreditsRemaining] = useState(0);
  const [billingContact, setBillingContact] = useState<string | null>(null);
  const [systemSummary, setSystemSummary] = useState<SystemProviderSummary | null>(null);
  const [modeInitialized, setModeInitialized] = useState(false);
  const lastGlobalDefaultIdRef = useRef<string | null>(null);
  const valueRef = useRef(value);
  valueRef.current = value;
  const defaultSizeRef = useRef(defaultSize);
  defaultSizeRef.current = defaultSize;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const mode: ImageProviderMode = value.image_provider_mode === 'platform' ? 'platform' : 'byok';
  const hasSystem = Boolean(systemSummary?.has_provider);
  const platformEnabled = hasSystem && creditsRemaining > 0;

  const loadBilling = async () => {
    try {
      const [me, summary] = await Promise.all([
        getCurrentUser(),
        getSystemImageProviderSummary(),
      ]);
      setCreditsRemaining(me.image_credits_remaining ?? 0);
      setBillingContact(me.billing_contact ?? null);
      setSystemSummary(summary);
    } catch (e) {
      console.error('Failed to load image credits / system provider:', e);
      setCreditsRemaining(0);
      setSystemSummary({ has_provider: false });
    }
  };

  const loadProviders = async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoadingProviders(true);
    try {
      const list = await listImageProviders();
      setProviders(list.filter((p) => p.is_active && !p.is_system));
    } catch (e) {
      console.error('Failed to load image providers:', e);
      setProviders([]);
    } finally {
      setLoadingProviders(false);
    }
  };

  useEffect(() => {
    void loadProviders();
    void loadBilling();
  }, []);

  useEffect(() => {
    return onImageProvidersChanged(() => {
      void loadProviders({ silent: true });
      void loadBilling();
    });
  }, []);

  useEffect(() => {
    if (!preferGlobalDefault) return;
    const onStudio =
      location.pathname === '/studio' || location.pathname === '/preview';
    if (!onStudio) return;
    void loadProviders({ silent: true });
    void loadBilling();
  }, [preferGlobalDefault, location.pathname]);

  // Default mode once billing + providers known
  useEffect(() => {
    if (loadingProviders || modeInitialized) return;
    if (systemSummary === null) return;
    const current = valueRef.current;
    if (current.image_provider_mode) {
      setModeInitialized(true);
      return;
    }
    const nextMode: ImageProviderMode =
      systemSummary.has_provider && creditsRemaining > 0 ? 'platform' : 'byok';
    const preferred = providers.find((p) => p.is_default) || providers[0];
    onChangeRef.current({
      ...current,
      image_provider_mode: nextMode,
      image_provider_id:
        nextMode === 'byok' ? preferred?.id ?? null : systemSummary.id ?? null,
      image_model:
        nextMode === 'platform'
          ? systemSummary.default_model ?? null
          : preferred?.default_model ?? null,
      image_size: current.image_size || defaultSizeRef.current,
    });
    setModeInitialized(true);
  }, [loadingProviders, systemSummary, creditsRemaining, providers, modeInitialized]);

  // BYOK: keep provider selection valid
  useEffect(() => {
    if (loadingProviders || mode !== 'byok') return;
    const current = valueRef.current;
    if (providers.length === 0) {
      if (current.image_provider_id) {
        onChangeRef.current({
          ...current,
          image_provider_id: null,
          image_model: null,
          image_size: current.image_size || null,
          image_provider_mode: 'byok',
        });
      }
      lastGlobalDefaultIdRef.current = null;
      return;
    }
    const preferred = providers.find((p) => p.is_default) || providers[0];
    const valid = providers.some((p) => p.id === current.image_provider_id);
    if (preferGlobalDefault) {
      const defaultChanged = lastGlobalDefaultIdRef.current !== preferred.id;
      lastGlobalDefaultIdRef.current = preferred.id;
      if (!valid || defaultChanged) {
        onChangeRef.current({
          ...current,
          image_provider_mode: 'byok',
          image_provider_id: preferred.id,
          image_model: preferred.default_model || null,
          image_size: current.image_size || defaultSizeRef.current,
        });
      }
      return;
    }
    if (!valid) {
      onChangeRef.current({
        ...current,
        image_provider_mode: 'byok',
        image_provider_id: preferred.id,
        image_model: preferred.default_model || null,
        image_size: current.image_size || defaultSizeRef.current,
      });
    }
  }, [loadingProviders, providers, preferGlobalDefault, mode]);

  useEffect(() => {
    if (mode === 'platform') {
      const manual = (systemSummary?.manual_models || []).map((m) => ({
        id: m.id,
        description: m.description ?? undefined,
        source: 'manual' as const,
      }));
      setModels(manual);
      setHint(null);
      setLoadingModels(false);
      if (!value.image_model && systemSummary?.default_model) {
        onChange({
          ...value,
          image_provider_mode: 'platform',
          image_provider_id: systemSummary.id ?? null,
          image_model: systemSummary.default_model,
        });
      }
      return;
    }
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
        setForceCustomModel(false);
        const provider = providers.find((p) => p.id === providerId);
        if (!value.image_model && provider?.default_model) {
          onChange({ ...value, image_model: provider.default_model });
        }
      } catch {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, value.image_provider_id, systemSummary?.id]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoadingSizes(true);
      try {
        const res = await getImageSizeCapabilities({
          provider_id: mode === 'platform' ? undefined : value.image_provider_id,
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, value.image_provider_id, value.image_model]);

  const setMode = (next: ImageProviderMode) => {
    if (next === 'platform') {
      onChange({
        ...value,
        image_provider_mode: 'platform',
        image_provider_id: systemSummary?.id ?? null,
        image_model: systemSummary?.default_model ?? null,
      });
      return;
    }
    const preferred = providers.find((p) => p.is_default) || providers[0];
    onChange({
      ...value,
      image_provider_mode: 'byok',
      image_provider_id: preferred?.id ?? null,
      image_model: preferred?.default_model ?? null,
    });
  };

  const selected = models.find((m) => m.id === value.image_model);
  const modelIdSet = new Set(models.map((m) => m.id));
  const isCustomModel =
    models.length === 0 ||
    forceCustomModel ||
    (value.image_model ? !modelIdSet.has(value.image_model) : false);
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

  // Credits exhausted only when remaining is actually 0 (do not conflate with missing system provider).
  const showExhaustedBanner =
    creditsRemaining <= 0 && providers.length === 0 && !loadingProviders;
  // System provider missing: explain why "平台额度" is disabled even if remaining > 0.
  const showSystemUnavailable =
    !hasSystem && !loadingProviders && systemSummary !== null;
  const showByokEmpty =
    mode === 'byok' && providers.length === 0 && !loadingProviders;

  const modelDisabled =
    disabled || (mode === 'byok' ? !value.image_provider_id : !hasSystem);

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
          label={t('imageModelPicker.source')}
          tooltip={t('imageModelPicker.tooltips.source')}
        />
        <div className="mt-1 flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            disabled={disabled || !platformEnabled}
            onClick={() => setMode('platform')}
            className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${
              mode === 'platform'
                ? 'border-forge-500 bg-forge-50 text-forge-800'
                : 'border-gray-300 bg-white text-gray-700'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {t('imageModelPicker.sourcePlatform', { n: creditsRemaining })}
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setMode('byok')}
            className={`flex-1 px-3 py-2 rounded-lg text-sm border transition-colors ${
              mode === 'byok'
                ? 'border-forge-500 bg-forge-50 text-forge-800'
                : 'border-gray-300 bg-white text-gray-700'
            }`}
          >
            {t('imageModelPicker.sourceByok')}
          </button>
        </div>
        {mode === 'platform' && platformEnabled ? (
          <p className="text-xs text-gray-500 mt-1">{t('imageModelPicker.willConsumeOne')}</p>
        ) : null}
        <div className="mt-2">
          <SubscribeCreditsButton
            creditsRemaining={creditsRemaining}
            billingContact={billingContact}
          />
        </div>
        {showExhaustedBanner ? (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            {t('imageModelPicker.creditsExhausted')}{' '}
            <Link to="/image-models" className="underline font-medium text-amber-900">
              {t('imageModelPicker.goAddProvider')}
            </Link>
          </p>
        ) : null}
        {showSystemUnavailable ? (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            {t('imageModelPicker.systemUnavailable')}
          </p>
        ) : null}
      </div>

      {mode === 'byok' ? (
        <div>
          <LabelWithTooltip
            label={`${t('imageModelPicker.provider')}${loadingProviders ? ` ${t('imageModelPicker.loading')}` : ''}`}
            tooltip={t('imageModelPicker.tooltips.provider')}
          />
          {showByokEmpty ? (
            <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-1">
              {t('imageModelPicker.noProviders')}{' '}
              <Link
                to="/image-models"
                className="underline font-medium text-amber-900 hover:text-amber-950"
              >
                {t('imageModelPicker.goAddProvider')}
              </Link>
            </p>
          ) : (
            <select
              value={value.image_provider_id || ''}
              disabled={disabled || loadingProviders || providers.length === 0}
              onChange={(e) => {
                const id = e.target.value || null;
                const provider = providers.find((p) => p.id === id);
                onChange({
                  ...value,
                  image_provider_mode: 'byok',
                  image_provider_id: id,
                  image_model: provider?.default_model || null,
                  image_size: value.image_size || defaultSize,
                });
                setForceCustomModel(false);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100"
            >
              {loadingProviders && !value.image_provider_id ? (
                <option value="">{t('imageModelPicker.loading')}</option>
              ) : null}
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                  {p.is_default ? t('imageModelPicker.defaultSuffix') : ''}
                </option>
              ))}
            </select>
          )}
        </div>
      ) : null}

      <div>
        <LabelWithTooltip
          label={`${t('imageModelPicker.modelId')}${loadingModels ? ` ${t('imageModelPicker.loading')}` : ''}`}
          tooltip={t('imageModelPicker.tooltips.modelId')}
        />
        {models.length > 0 ? (
          <ModelIdSelect
            models={models}
            value={value.image_model ?? null}
            isCustom={isCustomModel}
            disabled={modelDisabled}
            onSelectPreset={(modelId) => {
              setForceCustomModel(false);
              onChange({ ...value, image_model: modelId });
            }}
            onSelectCustom={() => setForceCustomModel(true)}
          />
        ) : null}
        {isCustomModel && (
          <input
            type="text"
            value={value.image_model || ''}
            disabled={modelDisabled}
            onChange={(e) => {
              setForceCustomModel(true);
              onChange({ ...value, image_model: e.target.value || null });
            }}
            placeholder={
              mode === 'platform' || value.image_provider_id
                ? t('placeholders.imageModelPicker.manualModel')
                : t('placeholders.imageModelPicker.selectProviderFirst')
            }
            className={`w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100 ${
              models.length > 0 ? 'mt-2' : ''
            }`}
          />
        )}
        {selected?.description && !isCustomModel && (
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
            <p className={`text-xs mt-1 ${customInvalid ? 'text-amber-600' : 'text-gray-500'}`}>
              {t('imageModelPicker.customSizeHint')}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
