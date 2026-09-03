import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  listImageProviders,
  getImageSizeCapabilities,
  type ImageProvider,
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
import { onImageProvidersChanged } from '@/lib/imageProvidersEvents';

const CUSTOM_VALUE = ASPECT_RATIO_CUSTOM_VALUE;
const SIZE_INPUT_RE = /^(\d{2,5})[xX*](\d{2,5})$/;
const PLATFORM_KEY = '__platform__';
const providerKey = (id: string) => `__provider__:${id}`;

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
  /** When true, re-fetch providers on Studio navigation; keep platform default unless user picked BYOK. */
  preferGlobalDefault?: boolean;
}

function normalizeSizeInput(raw: string): string | null {
  const m = raw.trim().match(SIZE_INPUT_RE);
  if (!m) return null;
  return `${Number(m[1])}x${Number(m[2])}`;
}

function platformOptionLabel(
  summary: SystemProviderSummary | null,
  t: (key: string, vars?: Record<string, string | number>) => string
): string {
  if (!summary?.has_provider) return t('imageModelPicker.systemDefault');
  const name = summary.name?.trim();
  const model = summary.default_model?.trim();
  if (name && model) {
    return t('imageModelPicker.systemDefaultDetail', { name, model });
  }
  if (name) return t('imageModelPicker.systemDefaultNameOnly', { name });
  if (model) return t('imageModelPicker.systemDefaultModelOnly', { model });
  return t('imageModelPicker.systemDefault');
}

function providerOptionLabel(
  provider: ImageProvider,
  t: (key: string, vars?: Record<string, string | number>) => string
): string {
  const model = provider.default_model?.trim();
  const suffix = provider.is_default ? t('imageModelPicker.defaultSuffix') : '';
  const name = `${provider.name}${suffix}`;
  if (model) {
    return t('imageModelPicker.platformActiveDetail', { name, model });
  }
  return t('imageModelPicker.platformActiveName', { name });
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
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [providers, setProviders] = useState<ImageProvider[]>([]);
  const [sizes, setSizes] = useState<ImageSizeOption[]>([]);
  const [defaultSize, setDefaultSize] = useState('2048x2048');
  const [allowCustom, setAllowCustom] = useState(true);
  const [customDraft, setCustomDraft] = useState('');
  const [forceCustom, setForceCustom] = useState(false);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [loadingSystemSummary, setLoadingSystemSummary] = useState(true);
  const [loadingSizes, setLoadingSizes] = useState(false);
  const [creditsRemaining, setCreditsRemaining] = useState(0);
  const [checkoutBanner, setCheckoutBanner] = useState<string | null>(null);
  const [systemSummary, setSystemSummary] = useState<SystemProviderSummary | null>(null);
  const [modeInitialized, setModeInitialized] = useState(false);
  const valueRef = useRef(value);
  valueRef.current = value;
  const defaultSizeRef = useRef(defaultSize);
  defaultSizeRef.current = defaultSize;
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const mode: ImageProviderMode =
    value.image_provider_mode === 'byok' || value.image_provider_id
      ? 'byok'
      : 'platform';
  const usingPlatformDefault = mode === 'platform';

  const loadBilling = async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoadingSystemSummary(true);
    try {
      const [me, summary] = await Promise.all([
        getCurrentUser(),
        getSystemImageProviderSummary(),
      ]);
      setCreditsRemaining(me.image_credits_remaining ?? 0);
      setSystemSummary(summary);
    } catch (e) {
      console.error('Failed to load image credits / system provider:', e);
      setCreditsRemaining(0);
      setSystemSummary({ has_provider: false });
    } finally {
      if (!opts?.silent) setLoadingSystemSummary(false);
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
    const checkout = searchParams.get('checkout');
    if (checkout !== 'success' && checkout !== 'cancel') return;
    setCheckoutBanner(
      checkout === 'success'
        ? t('subscribeCredits.checkoutSuccess')
        : t('subscribeCredits.checkoutCancel')
    );
    if (checkout === 'success') {
      void loadBilling({ silent: true });
    }
    const next = new URLSearchParams(searchParams);
    next.delete('checkout');
    navigate(
      { pathname: location.pathname, search: next.toString() ? `?${next}` : '' },
      { replace: true }
    );
  }, [searchParams, navigate, location.pathname, t]);

  useEffect(() => {
    return onImageProvidersChanged(() => {
      void loadProviders({ silent: true });
      void loadBilling({ silent: true });
    });
  }, []);

  useEffect(() => {
    if (!preferGlobalDefault) return;
    const onStudio =
      location.pathname === '/studio' || location.pathname === '/preview';
    if (!onStudio) return;
    void loadProviders({ silent: true });
    void loadBilling({ silent: true });
  }, [preferGlobalDefault, location.pathname]);

  useEffect(() => {
    if (loadingProviders || loadingSystemSummary || modeInitialized) return;
    if (systemSummary === null) return;
    const current = valueRef.current;
    if (current.image_provider_mode || current.image_provider_id) {
      setModeInitialized(true);
      return;
    }
    onChangeRef.current({
      ...current,
      image_provider_mode: 'platform',
      image_provider_id: null,
      image_model: null,
      image_size: current.image_size || defaultSizeRef.current,
    });
    setModeInitialized(true);
  }, [loadingProviders, loadingSystemSummary, systemSummary, modeInitialized]);

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
          image_provider_mode: 'platform',
        });
      }
      return;
    }
    const valid = providers.some((p) => p.id === current.image_provider_id);
    if (!valid && current.image_provider_id) {
      onChangeRef.current({
        ...current,
        image_provider_id: null,
        image_model: null,
        image_size: current.image_size || defaultSizeRef.current,
        image_provider_mode: 'platform',
      });
    }
  }, [loadingProviders, providers, mode]);

  const selectedProvider = providers.find((p) => p.id === value.image_provider_id);
  const platformModelId =
    usingPlatformDefault && systemSummary?.has_provider
      ? systemSummary.default_model?.trim() || null
      : null;
  const effectiveModelId = usingPlatformDefault
    ? platformModelId || value.image_model
    : selectedProvider?.default_model?.trim() || value.image_model;

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoadingSizes(true);
      try {
        const res = await getImageSizeCapabilities({
          provider_id: mode === 'platform' ? undefined : value.image_provider_id,
          model: effectiveModelId,
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
  }, [mode, value.image_provider_id, effectiveModelId]);

  const currentSize = value.image_size || defaultSize;
  const presetSet = new Set(sizes.map((s) => s.size));
  const isCustom =
    allowCustom && (forceCustom || (!!value.image_size && !presetSet.has(value.image_size)));
  const selectValue = isCustom ? CUSTOM_VALUE : currentSize;
  const customNormalized = normalizeSizeInput(customDraft);
  const customInvalid = isCustom && customDraft.trim().length > 0 && !customNormalized;
  const pickerLoading = loadingProviders || loadingSystemSummary;

  const selectedKey = usingPlatformDefault
    ? PLATFORM_KEY
    : value.image_provider_id
      ? providerKey(value.image_provider_id)
      : PLATFORM_KEY;

  const hasConfiguredModels =
    systemSummary?.has_provider || providers.some((p) => p.default_model?.trim());

  const wrapClass = compact
    ? 'space-y-2'
    : 'bg-white rounded-xl shadow-sm border border-gray-200 p-4 space-y-3';

  const showPlatformExhausted =
    usingPlatformDefault &&
    systemSummary?.has_provider &&
    creditsRemaining <= 0 &&
    !pickerLoading;

  const selectedLabel = pickerLoading
    ? t('imageModelPicker.loadingOption')
    : usingPlatformDefault || !selectedProvider
      ? platformOptionLabel(systemSummary, t)
      : providerOptionLabel(selectedProvider, t);

  const handleModelSelect = (key: string) => {
    if (key === PLATFORM_KEY) {
      onChange({
        ...value,
        image_provider_mode: 'platform',
        image_provider_id: null,
        image_model: null,
        image_size: value.image_size || defaultSize,
      });
      return;
    }
    const providerId = key.startsWith('__provider__:') ? key.slice('__provider__:'.length) : null;
    const provider = providers.find((p) => p.id === providerId);
    if (!provider) return;
    onChange({
      ...value,
      image_provider_mode: 'byok',
      image_provider_id: provider.id,
      image_model: provider.default_model?.trim() || null,
      image_size: value.image_size || defaultSize,
    });
  };

  return (
    <div className={wrapClass}>
      {!compact && (
        <LabelWithTooltip
          label={t('imageModelPicker.title')}
          tooltip={t('imageModelPicker.tooltips.title')}
          required={false}
        />
      )}

      <div>
        <select
          value={selectedKey}
          disabled={disabled || pickerLoading || !hasConfiguredModels}
          onChange={(e) => handleModelSelect(e.target.value)}
          title={selectedLabel}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-forge-500 focus:border-transparent disabled:bg-gray-100"
        >
          {pickerLoading ? (
            <option value={PLATFORM_KEY}>{t('imageModelPicker.loadingOption')}</option>
          ) : (
            <>
              <option value={PLATFORM_KEY}>{platformOptionLabel(systemSummary, t)}</option>
              {providers.map((p) => (
                <option key={p.id} value={providerKey(p.id)}>
                  {providerOptionLabel(p, t)}
                </option>
              ))}
            </>
          )}
        </select>
        {!pickerLoading && !hasConfiguredModels ? (
          <p className="text-xs text-gray-400 mt-1">
            {t('imageModelPicker.noProviders')}{' '}
            <Link to="/image-models" className="underline text-forge-700">
              {t('imageModelPicker.goAddProvider')}
            </Link>
          </p>
        ) : null}
        {checkoutBanner ? (
          <p className="text-sm text-forge-800 bg-forge-50 border border-forge-200 rounded-lg px-3 py-2 mt-2">
            {checkoutBanner}
          </p>
        ) : null}
        {showPlatformExhausted ? (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            {t('imageModelPicker.creditsExhausted')}{' '}
            <Link to="/image-models" className="underline font-medium text-amber-900">
              {t('imageModelPicker.goAddProvider')}
            </Link>
          </p>
        ) : null}
        {usingPlatformDefault && systemSummary && !systemSummary.has_provider && !pickerLoading ? (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            {t('imageModelPicker.systemUnavailable')}
          </p>
        ) : null}
        {usingPlatformDefault &&
        systemSummary?.has_provider &&
        !platformModelId &&
        !pickerLoading ? (
          <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mt-2">
            {t('imageModelPicker.systemModelNotConfigured')}
          </p>
        ) : null}
      </div>

      <div>
        <LabelWithTooltip
          label={`${t('imageModelPicker.aspectRatio')}${loadingSizes ? ` ${t('imageModelPicker.loading')}` : ''}`}
          tooltip={t('imageModelPicker.tooltips.aspectRatio')}
          required={false}
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
