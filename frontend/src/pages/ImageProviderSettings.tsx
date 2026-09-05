import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Plus,
  Edit2,
  Trash2,
  X,
  RefreshCw,
  Check,
  Zap,
  Star,
  Eye,
  EyeOff,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import {
  listImageProviders,
  createImageProvider,
  updateImageProvider,
  deleteImageProvider,
  testImageProvider,
  discoverImageProviderModels,
  type ImageProvider,
  type ImageProviderCreate,
  type ImageProviderType,
  type ImageModelInfo,
} from '@/api/imageProviders';
import {
  getSystemImageProviderSummary,
  type SystemProviderSummary,
} from '@/api/systemImageProvider';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import FieldRequirementBadge from '@/components/FieldRequirementBadge';
import HelpTooltip from '@/components/HelpTooltip';
import ImageProviderModelSection, {
  type DiscoverStatus,
} from '@/components/ImageProviderModelSection';
import { sanitizeMessage, toUserFacingMessage } from '@/lib/apiErrors';
import { useI18n } from '@/i18n/useI18n';
import { notifyImageProvidersChanged } from '@/lib/imageProvidersEvents';
import { confirmDialog } from '@/lib/feedback';
import { examplesForProviderType } from '@/lib/imageProviderExamples';
import { IMAGE_PROVIDER_PRESETS, presetForType } from '@/lib/imageProviderPresets';

const EMPTY_FORM: ImageProviderCreate = {
  name: '',
  provider_type: 'openai_compatible',
  base_url: IMAGE_PROVIDER_PRESETS.openai_compatible.base_url,
  api_key: '',
  supports_list_models: IMAGE_PROVIDER_PRESETS.openai_compatible.supports_list_models,
  default_model: '',
  manual_models: [],
  is_active: true,
  is_default: false,
};

export default function ImageProviderSettings() {
  const { t } = useI18n();
  const [providers, setProviders] = useState<ImageProvider[]>([]);
  const [platformPreset, setPlatformPreset] = useState<SystemProviderSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ImageProviderCreate>({ ...EMPTY_FORM });
  const [showKey, setShowKey] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testingId, setTestingId] = useState<string | null>(null);
  const [settingDefaultId, setSettingDefaultId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [discoverStatus, setDiscoverStatus] = useState<DiscoverStatus>('idle');
  const [discoverMessage, setDiscoverMessage] = useState<string | null>(null);
  const [discoveredModels, setDiscoveredModels] = useState<ImageModelInfo[]>([]);
  const [showManualModel, setShowManualModel] = useState(false);
  const [apiKeyTouched, setApiKeyTouched] = useState(false);
  const [apiKeyEditable, setApiKeyEditable] = useState(false);
  const discoverSeq = useRef(0);

  const providerTypeLabel = (type: ImageProviderType) =>
    t(`imageProviders.providerTypes.${type}`);

  const applyTypePreset = (providerType: ImageProviderType) => {
    const preset = presetForType(providerType);
    return {
      provider_type: providerType,
      base_url: preset.base_url,
      supports_list_models: preset.supports_list_models,
    };
  };

  const load = async () => {
    try {
      setLoading(true);
      const [data, summary] = await Promise.all([
        listImageProviders(),
        getSystemImageProviderSummary().catch(() => ({ has_provider: false as const })),
      ]);
      setProviders(data);
      setPlatformPreset(summary.has_provider ? summary : null);
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('common.loadFailed')));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const resetDiscoverState = () => {
    setDiscoverMessage(null);
    setDiscoveredModels([]);
    setDiscoverStatus('idle');
    setShowManualModel(false);
  };

  const runDiscover = useCallback(
    async (apiKey: string, snapshot: ImageProviderCreate) => {
      const trimmed = apiKey.trim();
      if (!trimmed || trimmed.length < 8) {
        resetDiscoverState();
        return;
      }
      const seq = ++discoverSeq.current;
      setDiscovering(true);
      setDiscoverStatus('loading');
      setDiscoverMessage(null);
      setShowManualModel(false);
      try {
        const res = await discoverImageProviderModels({
          provider_type: snapshot.provider_type,
          api_key: trimmed,
          base_url: snapshot.base_url || presetForType(snapshot.provider_type).base_url,
          supports_list_models: snapshot.supports_list_models,
        });
        if (seq !== discoverSeq.current) return;

        if (res.ok && res.models.length > 0) {
          setDiscoveredModels(res.models);
          setDiscoverStatus('success');
          setDiscoverMessage(sanitizeMessage(res.message, '') || null);
          setForm((prev) => {
            const next = { ...prev };
            if (res.base_url) next.base_url = res.base_url;
            if (res.supports_list_models != null) {
              next.supports_list_models = res.supports_list_models;
            }
            const stillValid = res.models.some((m) => m.id === next.default_model);
            if (!stillValid) {
              next.default_model = res.models[0].id;
            }
            return next;
          });
        } else {
          setDiscoveredModels([]);
          setDiscoverStatus('failed');
          setShowManualModel(true);
          setDiscoverMessage(
            sanitizeMessage(
              res.message,
              res.models.length === 0
                ? t('imageProviders.discover.emptyList')
                : t('imageProviders.discover.failed'),
            ),
          );
          setForm((prev) => {
            const next = { ...prev };
            if (res.base_url) next.base_url = res.base_url;
            if (res.supports_list_models != null) {
              next.supports_list_models = res.supports_list_models;
            }
            return next;
          });
        }
      } catch (err: any) {
        if (seq !== discoverSeq.current) return;
        setDiscoveredModels([]);
        setDiscoverStatus('failed');
        setShowManualModel(true);
        setDiscoverMessage(
          toUserFacingMessage(err, t('imageProviders.discover.failed')),
        );
      } finally {
        if (seq === discoverSeq.current) setDiscovering(false);
      }
    },
    [t]
  );

  useEffect(() => {
    if (!showModal || !apiKeyTouched) return;
    if (editingId && !form.api_key.trim()) return;
    const trimmed = form.api_key.trim();
    if (!trimmed || trimmed.length < 8) {
      resetDiscoverState();
      return;
    }
    setDiscoverStatus('loading');
    const timer = window.setTimeout(() => {
      void runDiscover(form.api_key, form);
    }, 500);
    return () => window.clearTimeout(timer);
  }, [
    showModal,
    apiKeyTouched,
    editingId,
    form.api_key,
    form.provider_type,
    form.base_url,
    form.supports_list_models,
    runDiscover,
  ]);

  const keepingExistingKey = Boolean(editingId && !form.api_key.trim());

  const closeModal = () => {
    discoverSeq.current += 1;
    setShowModal(false);
    resetDiscoverState();
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM });
    setShowKey(false);
    setShowAdvanced(false);
    setApiKeyTouched(false);
    setApiKeyEditable(false);
    resetDiscoverState();
    discoverSeq.current += 1;
    setShowModal(true);
  };

  const openEdit = (p: ImageProvider) => {
    setEditingId(p.id);
    setForm({
      name: p.name,
      provider_type: p.provider_type,
      base_url: p.base_url,
      api_key: '',
      supports_list_models: p.supports_list_models,
      default_model: p.default_model || '',
      is_active: p.is_active,
      is_default: p.is_default,
    });
    setShowKey(false);
    setShowAdvanced(false);
    setApiKeyTouched(false);
    setApiKeyEditable(false);
    resetDiscoverState();
    discoverSeq.current += 1;
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim()) {
      setError(t('imageProviders.validation.nameRequired'));
      return;
    }
    if (!editingId && !form.api_key.trim()) {
      setError(t('imageProviders.validation.apiKeyRequired'));
      return;
    }
    if (discovering || (!keepingExistingKey && form.api_key.trim().length >= 8 && discoverStatus === 'loading')) {
      setError(t('imageProviders.discover.loading'));
      return;
    }

    const preset = presetForType(form.provider_type);
    const defaultModel = form.default_model?.trim() || discoveredModels[0]?.id || null;
    if (!defaultModel) {
      setError(t('imageProviders.validation.modelRequired'));
      return;
    }

    try {
      setSaving(true);
      const shared = {
        name: form.name.trim(),
        provider_type: form.provider_type,
        base_url: form.base_url?.trim() || preset.base_url,
        supports_list_models: form.supports_list_models ?? preset.supports_list_models,
        default_model: defaultModel,
        is_active: form.is_active,
        is_default: form.is_default,
      };

      if (editingId) {
        const payload: Record<string, unknown> = { ...shared };
        if (form.api_key.trim()) payload.api_key = form.api_key.trim();
        const updated = await updateImageProvider(editingId, payload);
        setProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
        setSuccess(t('common.updated'));
      } else {
        const created = await createImageProvider({
          ...shared,
          api_key: form.api_key.trim(),
        });
        setProviders((prev) => [created, ...prev]);
        setSuccess(t('common.created'));
      }
      closeModal();
      setTimeout(() => setSuccess(''), 2500);
      void load();
      notifyImageProvidersChanged();
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('common.saveFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    const ok = await confirmDialog({
      message: t('imageProviders.confirmDelete'),
      danger: true,
    });
    if (!ok) return;
    setDeletingId(id);
    try {
      await deleteImageProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
      notifyImageProvidersChanged();
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('common.deleteFailed')));
    } finally {
      setDeletingId(null);
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const res = await testImageProvider(id);
      if (res.ok) setSuccess(sanitizeMessage(res.message, t('common.updated')));
      else setError(sanitizeMessage(res.message, t('imageProviders.test.failed')));
      setTimeout(() => {
        setSuccess('');
        setError('');
      }, 4000);
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('imageProviders.test.failed')));
    } finally {
      setTestingId(null);
    }
  };

  const handleSetDefault = async (p: ImageProvider) => {
    if (p.is_system || p.is_default) return;
    setSettingDefaultId(p.id);
    setError('');
    try {
      await updateImageProvider(p.id, { is_default: true });
      setProviders((prev) =>
        prev.map((row) => ({
          ...row,
          is_default: row.id === p.id,
        }))
      );
      setSuccess(t('imageProviders.setDefaultSuccess'));
      setTimeout(() => setSuccess(''), 2500);
      notifyImageProvidersChanged();
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('common.saveFailed')));
    } finally {
      setSettingDefaultId(null);
    }
  };

  const providerExamples = examplesForProviderType(form.provider_type);

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-forge-600" />
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-xl font-bold text-gray-900 sm:text-2xl">{t('imageProviders.title')}</h2>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">{t('imageProviders.subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2 sm:gap-3">
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 bg-forge-600 text-white px-3 py-2 sm:px-4 rounded-lg hover:bg-forge-700 text-sm"
          >
            <Plus className="w-5 h-5" />
            {t('imageProviders.addProvider')}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}
      {success && (
        <div className="mb-4 px-4 py-3 bg-green-50 text-green-700 rounded-lg text-sm flex items-center gap-2">
          <Check className="w-4 h-4" />
          {success}
        </div>
      )}

      <div className="space-y-3">
        {platformPreset?.has_provider && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h3 className="font-semibold text-gray-900">{platformPreset.name}</h3>
                <span className="px-2 py-0.5 text-xs rounded-full bg-forge-100 text-forge-700">
                  {t('imageProviders.systemDefault')}
                </span>
                {platformPreset.provider_type && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                    {providerTypeLabel(platformPreset.provider_type as ImageProviderType)}
                  </span>
                )}
              </div>
              {platformPreset.default_model ? (
                <p className="text-xs text-gray-400 mt-1">
                  {t('imageProviders.defaultModel')}: {platformPreset.default_model}
                </p>
              ) : null}
            </div>
          </div>
        )}

        {providers.map((p) => (
          <div
            key={p.id}
            className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h3 className="font-semibold text-gray-900">{p.name}</h3>
                {p.is_system && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-forge-100 text-forge-700">
                    {t('imageProviders.systemDefault')}
                  </span>
                )}
                {!p.is_system && p.is_default && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-forge-100 text-forge-700">{t('common.default')}</span>
                )}
                {!p.is_active && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">{t('common.disabled')}</span>
                )}
                <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                  {providerTypeLabel(p.provider_type)}
                </span>
              </div>
              <p className="text-sm text-gray-500 break-all">{p.base_url}</p>
              <p className="text-xs text-gray-400 mt-1">
                {t('imageProviders.keyLabel')}: {p.api_key_masked}
                {p.default_model ? ` · ${t('imageProviders.defaultModel')}: ${p.default_model}` : ''}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
              {!p.is_system && (
                <button
                  type="button"
                  onClick={() => void handleSetDefault(p)}
                  disabled={p.is_default || settingDefaultId === p.id}
                  className={`p-2 rounded-lg disabled:cursor-default ${
                    p.is_default
                      ? 'text-forge-600 bg-forge-50'
                      : 'text-gray-500 hover:text-forge-600 hover:bg-forge-50'
                  }`}
                  title={
                    p.is_default
                      ? t('imageProviders.currentDefault')
                      : t('imageProviders.fields.isDefault.label')
                  }
                >
                  {settingDefaultId === p.id ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <Star className={`w-5 h-5 ${p.is_default ? 'fill-current' : ''}`} />
                  )}
                </button>
              )}
              <button
                type="button"
                onClick={() => void handleTest(p.id)}
                disabled={testingId === p.id}
                className="p-2 text-gray-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg"
                title={t('imageProviders.testConnection')}
              >
                {testingId === p.id ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Zap className="w-5 h-5" />
                )}
              </button>
              {!p.is_system && (
                <>
                  <button
                    type="button"
                    onClick={() => openEdit(p)}
                    className="p-2 text-gray-500 hover:text-forge-600 hover:bg-forge-50 rounded-lg"
                  >
                    <Edit2 className="w-5 h-5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(p.id)}
                    disabled={deletingId === p.id}
                    className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50"
                  >
                    {deletingId === p.id ? (
                      <RefreshCw className="w-5 h-5 animate-spin" />
                    ) : (
                      <Trash2 className="w-5 h-5" />
                    )}
                  </button>
                </>
              )}
            </div>
          </div>
        ))}

        {providers.length === 0 && !platformPreset?.has_provider && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
            {t('imageProviders.emptyState')}
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-4 sm:p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold">
                {editingId ? t('imageProviders.editProvider') : t('imageProviders.addProvider')}
              </h3>
              <button
                type="button"
                onClick={closeModal}
                className="text-gray-400 hover:text-gray-600"
                aria-label={t('common.close')}
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <LabelWithTooltip
                  htmlFor="provider-name"
                  label={t('imageProviders.fields.name.label')}
                  tooltip={t('imageProviders.fields.name.tooltip')}
                  required
                />
                <input
                  id="provider-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  required
                  placeholder={providerExamples.name}
                />
              </div>

              <div>
                <LabelWithTooltip
                  htmlFor="provider-type"
                  label={t('imageProviders.fields.type.label')}
                  tooltip={t('imageProviders.fields.type.tooltip')}
                  required
                />
                <select
                  id="provider-type"
                  value={form.provider_type}
                  onChange={(e) => {
                    const providerType = e.target.value as ImageProviderType;
                    setForm({
                      ...form,
                      ...applyTypePreset(providerType),
                      default_model: '',
                    });
                    resetDiscoverState();
                    if (form.api_key.trim().length >= 8) {
                      setApiKeyTouched(true);
                    }
                  }}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                >
                  {(Object.keys(IMAGE_PROVIDER_PRESETS) as ImageProviderType[]).map((k) => (
                    <option key={k} value={k}>
                      {providerTypeLabel(k)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <LabelWithTooltip
                  htmlFor="provider-api-key"
                  label={t('imageProviders.fields.apiKey.label')}
                  tooltip={t('imageProviders.fields.apiKey.tooltip')}
                  required={!editingId}
                />
                <div className="relative">
                  <input
                    id="provider-api-key"
                    type={showKey ? 'text' : 'password'}
                    value={form.api_key}
                    readOnly={!apiKeyEditable}
                    onFocus={() => setApiKeyEditable(true)}
                    onChange={(e) => {
                      setApiKeyTouched(true);
                      setForm({ ...form, api_key: e.target.value });
                    }}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg pr-10"
                    autoComplete="new-password"
                    data-1p-ignore
                    placeholder={providerExamples.apiKey}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <ImageProviderModelSection
                keepingExistingKey={keepingExistingKey}
                apiKey={form.api_key}
                apiKeyTouched={apiKeyTouched}
                defaultModel={form.default_model || ''}
                onDefaultModelChange={(default_model) => setForm({ ...form, default_model })}
                modelPlaceholder={providerExamples.defaultModel}
                discoverStatus={discoverStatus}
                discoverMessage={discoverMessage}
                discoveredModels={discoveredModels}
                showManualModel={showManualModel}
                onUseManualModel={() => {
                  setShowManualModel(true);
                  setForm((prev) => ({ ...prev, default_model: '' }));
                }}
                onRetryDiscover={() => {
                  setApiKeyTouched(true);
                  void runDiscover(form.api_key, form);
                }}
              />

              <div>
                <button
                  type="button"
                  onClick={() => setShowAdvanced((v) => !v)}
                  className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900"
                >
                  {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  {t('imageProviders.advancedSettings')}
                </button>
                {showAdvanced ? (
                  <div className="mt-3 space-y-3 border border-gray-100 rounded-lg p-3 bg-gray-50">
                    <div>
                      <LabelWithTooltip
                        htmlFor="provider-base-url"
                        label={t('imageProviders.fields.baseUrl.label')}
                        tooltip={t('imageProviders.fields.baseUrl.tooltip')}
                        required={false}
                      />
                      <input
                        id="provider-base-url"
                        value={form.base_url}
                        onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
                        placeholder={providerExamples.baseUrl}
                      />
                    </div>
                    <label className="flex items-start gap-2 text-sm text-gray-700">
                      <input
                        type="checkbox"
                        checked={!!form.supports_list_models}
                        onChange={(e) =>
                          setForm({ ...form, supports_list_models: e.target.checked })
                        }
                        className="mt-0.5"
                      />
                      <span className="flex-1 inline-flex items-center gap-1.5 flex-wrap">
                        {t('imageProviders.fields.supportsListModels.label')}
                        <FieldRequirementBadge required={false} />
                        <HelpTooltip content={t('imageProviders.fields.supportsListModels.tooltip')} />
                      </span>
                    </label>
                  </div>
                ) : null}
              </div>

              <label className="flex items-start gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={!!form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  className="mt-0.5"
                />
                <span className="flex-1 inline-flex items-center gap-1.5 flex-wrap">
                  {t('imageProviders.fields.isDefault.label')}
                  <FieldRequirementBadge required={false} />
                  <HelpTooltip content={t('imageProviders.fields.isDefault.tooltip')} />
                </span>
              </label>

              <label className="flex items-start gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.is_active !== false}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="mt-0.5"
                />
                <span className="flex-1 inline-flex items-center gap-1.5 flex-wrap">
                  {t('imageProviders.fields.isActive.label')}
                  <FieldRequirementBadge required={false} />
                  <HelpTooltip content={t('imageProviders.fields.isActive.tooltip')} />
                </span>
              </label>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={saving}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving || discovering || (!keepingExistingKey && discoverStatus === 'loading')}
                  className="px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? t('common.saving') : t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
