import { useEffect, useRef, useState } from 'react';
import { Plus, Trash2, RefreshCw, Star, X, ChevronDown, ChevronUp } from 'lucide-react';
import {
  listSystemImageProviders,
  createSystemImageProvider,
  updateSystemImageProvider,
  deleteSystemImageProvider,
  setSystemImageProviderDefault,
  type SystemImageProvider,
} from '@/api/systemImageProvider';
import {
  discoverImageProviderModels,
  type ImageProviderType,
  type ImageModelInfo,
} from '@/api/imageProviders';
import { useI18n } from '@/i18n/useI18n';
import { notifyImageProvidersChanged } from '@/lib/imageProvidersEvents';
import { confirmDialog } from '@/lib/feedback';
import FormLabel from '@/components/FormLabel';
import FieldRequirementBadge from '@/components/FieldRequirementBadge';
import { examplesForProviderType } from '@/lib/imageProviderExamples';
import { IMAGE_PROVIDER_PRESETS, presetForType } from '@/lib/imageProviderPresets';

const EMPTY = {
  name: '',
  provider_type: 'openai_compatible' as ImageProviderType,
  base_url: IMAGE_PROVIDER_PRESETS.openai_compatible.base_url,
  api_key: '',
  supports_list_models: IMAGE_PROVIDER_PRESETS.openai_compatible.supports_list_models,
  default_model: '',
  is_active: true,
  is_default: true,
};

export default function SystemImageProviderSettings() {
  const { t } = useI18n();
  const [rows, setRows] = useState<SystemImageProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY });
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [discovering, setDiscovering] = useState(false);
  const [discoverMessage, setDiscoverMessage] = useState<string | null>(null);
  const [discoveredModels, setDiscoveredModels] = useState<ImageModelInfo[]>([]);
  const [manualModelId, setManualModelId] = useState('');
  const [apiKeyTouched, setApiKeyTouched] = useState(false);
  const [apiKeyEditable, setApiKeyEditable] = useState(false);
  const discoverSeq = useRef(0);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setRows(await listSystemImageProviders());
    } catch (e: unknown) {
      const detail =
        e && typeof e === 'object' && 'response' in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || t('systemImageProviders.loadFailed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const runDiscover = async () => {
    const trimmed = form.api_key.trim();
    if (!trimmed || trimmed.length < 8) {
      setDiscoveredModels([]);
      setDiscoverMessage(null);
      return;
    }
    const seq = ++discoverSeq.current;
    setDiscovering(true);
    try {
      const res = await discoverImageProviderModels({
        provider_type: form.provider_type,
        api_key: trimmed,
        base_url: form.base_url,
        supports_list_models: form.supports_list_models,
      });
      if (seq !== discoverSeq.current) return;
      setDiscoveredModels(res.models);
      setDiscoverMessage(res.message || null);
      if (res.base_url) setForm((f) => ({ ...f, base_url: res.base_url! }));
      if (res.models.length > 0 && !form.default_model) {
        setForm((f) => ({ ...f, default_model: res.models[0].id }));
      }
    } catch {
      if (seq !== discoverSeq.current) return;
      setDiscoveredModels([]);
      setDiscoverMessage(t('imageProviders.discover.failed'));
    } finally {
      if (seq === discoverSeq.current) setDiscovering(false);
    }
  };

  useEffect(() => {
    if (!showModal || !apiKeyTouched || !form.api_key.trim()) return;
    const timer = window.setTimeout(() => void runDiscover(), 500);
    return () => window.clearTimeout(timer);
  }, [showModal, apiKeyTouched, form.api_key, form.provider_type, form.base_url]);

  const closeModal = () => {
    discoverSeq.current += 1;
    setShowModal(false);
    setDiscoveredModels([]);
    setDiscoverMessage(null);
  };

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY });
    setDiscoveredModels([]);
    setDiscoverMessage(null);
    setManualModelId('');
    setShowAdvanced(false);
    setApiKeyTouched(false);
    setApiKeyEditable(false);
    discoverSeq.current += 1;
    setShowModal(true);
  };

  const openEdit = (row: SystemImageProvider) => {
    setEditingId(row.id);
    setForm({
      name: row.name,
      provider_type: row.provider_type,
      base_url: row.base_url,
      api_key: '',
      supports_list_models: row.supports_list_models,
      default_model: row.default_model || '',
      is_active: row.is_active,
      is_default: row.is_default,
    });
    setDiscoveredModels([]);
    setDiscoverMessage(null);
    setManualModelId('');
    setShowAdvanced(false);
    setApiKeyTouched(false);
    setApiKeyEditable(false);
    discoverSeq.current += 1;
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const preset = presetForType(form.provider_type);
      const defaultModel = form.default_model?.trim() || discoveredModels[0]?.id || manualModelId.trim() || null;
      if (!defaultModel) {
        setError(t('imageProviders.validation.modelRequired'));
        setSaving(false);
        return;
      }
      const body: Record<string, unknown> = {
        name: form.name,
        provider_type: form.provider_type,
        base_url: form.base_url || preset.base_url,
        supports_list_models: form.supports_list_models ?? preset.supports_list_models,
        default_model: defaultModel,
        is_active: form.is_active,
        is_default: form.is_default,
      };
      if (editingId) {
        if (form.api_key.trim()) body.api_key = form.api_key.trim();
        await updateSystemImageProvider(editingId, body);
      } else {
        if (!form.api_key.trim()) {
          setError(t('systemImageProviders.apiKeyRequired'));
          setSaving(false);
          return;
        }
        body.api_key = form.api_key.trim();
        await createSystemImageProvider(body);
      }
      closeModal();
      notifyImageProvidersChanged();
      await load();
    } catch (err: unknown) {
      const detail =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      setError(detail || t('systemImageProviders.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            {t('systemImageProviders.title')}
          </h1>
          <p className="text-sm text-gray-500 mt-1">{t('systemImageProviders.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void load()}
            className="px-3 py-2 border rounded-lg text-sm text-gray-700 hover:bg-gray-50"
          >
            <RefreshCw className={`w-4 h-4 inline ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="px-3 py-2 bg-forge-600 text-white rounded-lg text-sm hover:bg-forge-700 flex items-center gap-1"
          >
            <Plus className="w-4 h-4" />
            {t('common.add')}
          </button>
        </div>
      </div>

      {error ? (
        <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-gray-500">{t('common.loading')}</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-gray-500">{t('systemImageProviders.empty')}</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => (
            <li
              key={row.id}
              className="bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-center justify-between gap-3"
            >
              <div>
                <div className="font-medium text-gray-900 flex items-center gap-2">
                  {row.name}
                  {row.is_default ? (
                    <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                  ) : null}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {row.provider_type} · {row.default_model || '—'} · {row.api_key_masked}
                </div>
              </div>
              <div className="flex gap-2">
                {!row.is_default ? (
                  <button
                    type="button"
                    className="text-xs px-2 py-1 border rounded-lg"
                    onClick={async () => {
                      await setSystemImageProviderDefault(row.id);
                      notifyImageProvidersChanged();
                      await load();
                    }}
                  >
                    {t('systemImageProviders.setDefault')}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="text-xs px-2 py-1 border rounded-lg"
                  onClick={() => openEdit(row)}
                >
                  {t('common.edit')}
                </button>
                <button
                  type="button"
                  className="text-xs px-2 py-1 border rounded-lg text-red-600"
                  onClick={async () => {
                    if (!(await confirmDialog({
                      message: t('systemImageProviders.confirmDelete'),
                      danger: true,
                    }))) return;
                    await deleteSystemImageProvider(row.id);
                    notifyImageProvidersChanged();
                    await load();
                  }}
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {showModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form
            onSubmit={handleSave}
            className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5 space-y-3 max-h-[90vh] overflow-y-auto"
          >
            <div className="flex justify-between items-center">
              <h2 className="font-semibold">
                {editingId ? t('common.edit') : t('common.add')}
              </h2>
              <button type="button" onClick={closeModal}>
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            <div>
              <FormLabel label={t('imageProviders.fields.name.label')} required htmlFor="system-provider-name" className="text-xs text-gray-600 mb-1" />
              <input
                id="system-provider-name"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder={examplesForProviderType(form.provider_type).name}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
            </div>
            <div>
              <FormLabel label={t('imageProviders.fields.type.label')} required htmlFor="system-provider-type" className="text-xs text-gray-600 mb-1" />
            <select
              id="system-provider-type"
              className="w-full border rounded-lg px-3 py-2 text-sm"
              value={form.provider_type}
              onChange={(e) => {
                const providerType = e.target.value as ImageProviderType;
                const preset = presetForType(providerType);
                setForm({
                  ...form,
                  provider_type: providerType,
                  base_url: preset.base_url,
                  supports_list_models: preset.supports_list_models,
                  default_model: providerType === 'agnes' ? 'agnes-image-2.1-flash' : '',
                });
                setDiscoveredModels([]);
              }}
            >
              {(Object.keys(IMAGE_PROVIDER_PRESETS) as ImageProviderType[]).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
            </div>
            <div>
              <FormLabel
                label={t('imageProviders.fields.apiKey.label')}
                required={!editingId}
                htmlFor="system-provider-api-key"
                className="text-xs text-gray-600 mb-1"
              />
            <input
              id="system-provider-api-key"
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder={examplesForProviderType(form.provider_type).apiKey}
              value={form.api_key}
              readOnly={!apiKeyEditable}
              onFocus={() => setApiKeyEditable(true)}
              onChange={(e) => {
                setApiKeyTouched(true);
                setForm({ ...form, api_key: e.target.value });
              }}
              type="password"
              autoComplete="new-password"
              data-1p-ignore
            />
            </div>
            {discovering ? (
              <p className="text-xs text-gray-500 flex items-center gap-1">
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                {t('imageProviders.discover.loading')}
              </p>
            ) : discoverMessage ? (
              <p className="text-xs text-amber-700">{discoverMessage}</p>
            ) : null}
            {discoveredModels.length > 0 ? (
              <div>
                <FormLabel label={t('imageProviders.fields.defaultModel.label')} required htmlFor="system-provider-model-select" className="text-xs text-gray-600 mb-1" />
              <select
                id="system-provider-model-select"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                value={form.default_model}
                onChange={(e) => setForm({ ...form, default_model: e.target.value })}
              >
                {discoveredModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id}
                  </option>
                ))}
              </select>
              </div>
            ) : (
              <div>
                <FormLabel label={t('imageProviders.fields.defaultModel.label')} required htmlFor="system-provider-model-input" className="text-xs text-gray-600 mb-1" />
              <input
                id="system-provider-model-input"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder={examplesForProviderType(form.provider_type).defaultModel}
                value={form.default_model || manualModelId}
                onChange={(e) => {
                  setManualModelId(e.target.value);
                  setForm({ ...form, default_model: e.target.value });
                }}
                autoComplete="off"
                data-1p-ignore
              />
              </div>
            )}
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="flex items-center gap-1 text-xs text-gray-600"
            >
              {showAdvanced ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              {t('imageProviders.advancedSettings')}
            </button>
            {showAdvanced ? (
              <div>
                <FormLabel label={t('imageProviders.fields.baseUrl.label')} required={false} htmlFor="system-provider-base-url" className="text-xs text-gray-600 mb-1" />
              <input
                id="system-provider-base-url"
                className="w-full border rounded-lg px-3 py-2 text-sm"
                placeholder={examplesForProviderType(form.provider_type).baseUrl}
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              />
              </div>
            ) : null}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              />
              <span className="inline-flex items-center gap-1.5">
                {t('systemImageProviders.default')}
                <FieldRequirementBadge required={false} />
              </span>
            </label>
            <button
              type="submit"
              disabled={saving || discovering}
              className="w-full py-2 bg-forge-600 text-white rounded-lg text-sm disabled:opacity-50"
            >
              {t('common.save')}
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
