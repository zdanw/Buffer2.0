import { useEffect, useState } from 'react';
import {
  Plus,
  Edit2,
  Trash2,
  X,
  RefreshCw,
  Check,
  Zap,
  Eye,
  EyeOff,
} from 'lucide-react';
import {
  listImageProviders,
  createImageProvider,
  updateImageProvider,
  deleteImageProvider,
  testImageProvider,
  type ImageProvider,
  type ImageProviderCreate,
  type ImageProviderType,
  type ManualModelEntry,
} from '@/api/imageProviders';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import HelpTooltip from '@/components/HelpTooltip';
import { useI18n } from '@/i18n/useI18n';

const EMPTY_FORM: ImageProviderCreate = {
  name: '',
  provider_type: 'openai_compatible',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  supports_list_models: true,
  default_model: '',
  manual_models: [],
  is_active: true,
  is_default: false,
};

const TYPE_PRESETS: Record<ImageProviderType, { base_url: string; list: boolean }> = {
  openai_compatible: {
    base_url: 'https://api.openai.com/v1',
    list: true,
  },
  doubao_ark: {
    base_url: 'https://ark.cn-beijing.volces.com/api/v3/images/generations',
    list: false,
  },
  aliyun_maas: {
    base_url:
      'https://ws-lxvmitlmy9ln8pda.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
    list: true,
  },
};

export default function ImageProviderSettings() {
  const { t } = useI18n();
  const [providers, setProviders] = useState<ImageProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ImageProviderCreate>({ ...EMPTY_FORM });
  const [newModelId, setNewModelId] = useState('');
  const [newModelDesc, setNewModelDesc] = useState('');
  const [docModelId, setDocModelId] = useState<string | null>(null);
  const [docDraft, setDocDraft] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [testingId, setTestingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const providerTypeLabel = (type: ImageProviderType) =>
    t(`imageProviders.providerTypes.${type}`);

  const load = async (opts?: { silent?: boolean }) => {
    try {
      if (opts?.silent) setRefreshing(true);
      else setLoading(true);
      const data = await listImageProviders();
      setProviders(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.loadFailed'));
    } finally {
      if (opts?.silent) setRefreshing(false);
      else setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, manual_models: [] });
    setNewModelId('');
    setNewModelDesc('');
    setDocModelId(null);
    setDocDraft('');
    setShowKey(false);
    setShowModal(true);
  };

  const openEdit = (p: ImageProvider) => {
    setEditingId(p.id);
    const models: ManualModelEntry[] = (p.manual_models || []).map((m) =>
      typeof m === 'string'
        ? { id: m, description: '' }
        : { id: m.id, description: m.description || '' }
    );
    setForm({
      name: p.name,
      provider_type: p.provider_type,
      base_url: p.base_url,
      api_key: '',
      supports_list_models: p.supports_list_models,
      default_model: p.default_model || '',
      manual_models: models,
      is_active: p.is_active,
      is_default: p.is_default,
    });
    setNewModelId('');
    setNewModelDesc('');
    setDocModelId(null);
    setDocDraft('');
    setShowKey(false);
    setShowModal(true);
  };

  const addManualModel = () => {
    const mid = newModelId.trim();
    if (!mid) return;
    const current = form.manual_models || [];
    if (current.some((m) => m.id === mid)) {
      setNewModelId('');
      setNewModelDesc('');
      return;
    }
    setForm({
      ...form,
      manual_models: [
        ...current,
        { id: mid, description: newModelDesc.trim() || null },
      ],
    });
    setNewModelId('');
    setNewModelDesc('');
  };

  const openModelDoc = (m: ManualModelEntry) => {
    setDocModelId(m.id);
    setDocDraft(m.description || '');
  };

  const closeModelDoc = () => {
    setDocModelId(null);
    setDocDraft('');
  };

  const saveModelDoc = () => {
    if (!docModelId) return;
    updateManualModelDesc(docModelId, docDraft);
    closeModelDoc();
  };

  const updateManualModelDesc = (mid: string, description: string) => {
    setForm({
      ...form,
      manual_models: (form.manual_models || []).map((m) =>
        m.id === mid ? { ...m, description } : m
      ),
    });
  };

  const removeManualModel = (mid: string) => {
    setForm({
      ...form,
      manual_models: (form.manual_models || []).filter((m) => m.id !== mid),
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!form.name.trim() || !form.base_url.trim()) {
      setError(t('imageProviders.validation.nameAndUrlRequired'));
      return;
    }
    if (!editingId && !form.api_key.trim()) {
      setError(t('imageProviders.validation.apiKeyRequired'));
      return;
    }

    try {
      setSaving(true);
      if (editingId) {
        const payload: Record<string, unknown> = {
          name: form.name,
          provider_type: form.provider_type,
          base_url: form.base_url,
          supports_list_models: form.supports_list_models,
          default_model: form.default_model || null,
          manual_models: form.manual_models || [],
          is_active: form.is_active,
          is_default: form.is_default,
        };
        if (form.api_key.trim()) payload.api_key = form.api_key.trim();
        const updated = await updateImageProvider(editingId, payload);
        setProviders((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
        setSuccess(t('common.updated'));
      } else {
        const created = await createImageProvider({
          ...form,
          default_model: form.default_model || null,
          manual_models: form.manual_models || [],
        });
        setProviders((prev) => [created, ...prev]);
        setSuccess(t('common.created'));
      }
      setShowModal(false);
      setTimeout(() => setSuccess(''), 2500);
      void load({ silent: true });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg : detail || t('common.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('imageProviders.confirmDelete'))) return;
    setDeletingId(id);
    try {
      await deleteImageProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      setError(err.response?.data?.detail || t('common.deleteFailed'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const res = await testImageProvider(id);
      if (res.ok) setSuccess(res.message);
      else setError(res.message);
      setTimeout(() => {
        setSuccess('');
        setError('');
      }, 4000);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('imageProviders.test.failed'));
    } finally {
      setTestingId(null);
    }
  };

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
            onClick={() => void load({ silent: true })}
            disabled={refreshing || loading}
            className="flex items-center gap-2 bg-gray-100 text-gray-700 px-3 py-2 sm:px-4 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
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
                {(p.manual_models?.length || 0) > 0
                  ? ` · ${t('imageProviders.manualModelsCount').replace('{{count}}', String(p.manual_models!.length))}`
                  : ''}
              </p>
            </div>
            <div className="flex gap-2 shrink-0">
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

        {providers.length === 0 && (
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
                onClick={() => setShowModal(false)}
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
                />
                <input
                  id="provider-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  required
                  placeholder={t('placeholders.imageProviders.name')}
                />
              </div>

              <div>
                <LabelWithTooltip
                  htmlFor="provider-type"
                  label={t('imageProviders.fields.type.label')}
                  tooltip={t('imageProviders.fields.type.tooltip')}
                />
                <select
                  id="provider-type"
                  value={form.provider_type}
                  onChange={(e) => {
                    const providerType = e.target.value as ImageProviderType;
                    const preset = TYPE_PRESETS[providerType];
                    setForm({
                      ...form,
                      provider_type: providerType,
                      base_url: preset.base_url,
                      supports_list_models: preset.list,
                    });
                  }}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                >
                  {(Object.keys(TYPE_PRESETS) as ImageProviderType[]).map((k) => (
                    <option key={k} value={k}>
                      {providerTypeLabel(k)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <LabelWithTooltip
                  htmlFor="provider-base-url"
                  label={t('imageProviders.fields.baseUrl.label')}
                  tooltip={t('imageProviders.fields.baseUrl.tooltip')}
                />
                <input
                  id="provider-base-url"
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  required
                  placeholder={t('placeholders.imageProviders.baseUrl')}
                />
              </div>

              <div>
                <LabelWithTooltip
                  htmlFor="provider-api-key"
                  label={editingId ? t('imageProviders.fields.apiKey.labelOptional') : t('imageProviders.fields.apiKey.label')}
                  tooltip={t('imageProviders.fields.apiKey.tooltip')}
                />
                <div className="relative">
                  <input
                    id="provider-api-key"
                    type={showKey ? 'text' : 'password'}
                    value={form.api_key}
                    onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg pr-10"
                    autoComplete="off"
                    placeholder={t('placeholders.imageProviders.apiKey')}
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

              <div>
                <LabelWithTooltip
                  htmlFor="provider-default-model"
                  label={t('imageProviders.fields.defaultModel.label')}
                  tooltip={t('imageProviders.fields.defaultModel.tooltip')}
                />
                <input
                  id="provider-default-model"
                  value={form.default_model || ''}
                  onChange={(e) => setForm({ ...form, default_model: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  placeholder={t('placeholders.imageProviders.defaultModel')}
                />
              </div>

              <div>
                <LabelWithTooltip
                  label={t('imageProviders.fields.manualModels.label')}
                  tooltip={t('imageProviders.fields.manualModels.tooltip')}
                />
                <p className="text-xs text-gray-500 mb-2">
                  {t('imageProviders.fields.manualModels.hint')}
                </p>
                <div className="space-y-2 mb-2">
                  <input
                    value={newModelId}
                    onChange={(e) => setNewModelId(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addManualModel();
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder={t('placeholders.imageProviders.modelId')}
                  />
                  <textarea
                    value={newModelDesc}
                    onChange={(e) => setNewModelDesc(e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder={t('placeholders.imageProviders.modelNotes')}
                  />
                  <button
                    type="button"
                    onClick={addManualModel}
                    className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
                  >
                    {t('imageProviders.fields.manualModels.addToList')}
                  </button>
                </div>
                {(form.manual_models || []).length > 0 ? (
                  <ul className="space-y-1 max-h-56 overflow-y-auto border border-gray-100 rounded-lg p-2">
                    {(form.manual_models || []).map((m) => (
                      <li
                        key={m.id}
                        className="flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg bg-gray-50"
                      >
                        <button
                          type="button"
                          onClick={() => openModelDoc(m)}
                          className="text-left flex-1 font-mono text-sm text-forge-700 hover:text-ink-900 hover:underline break-all"
                          title={t('imageProviders.fields.manualModels.viewDoc')}
                        >
                          {m.id}
                          {m.description ? (
                            <span className="ml-2 text-xs text-gray-400 font-sans">
                              {t('imageProviders.fields.manualModels.hasDoc')}
                            </span>
                          ) : null}
                        </button>
                        <button
                          type="button"
                          onClick={() => removeManualModel(m.id)}
                          className="text-gray-400 hover:text-red-600 shrink-0"
                          title={t('imageProviders.fields.manualModels.remove')}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-400">{t('imageProviders.fields.manualModels.empty')}</p>
                )}
              </div>

              <label className="flex items-start gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={!!form.supports_list_models}
                  onChange={(e) => setForm({ ...form, supports_list_models: e.target.checked })}
                  className="mt-0.5"
                />
                <span className="flex-1 inline-flex items-center gap-1.5 flex-wrap">
                  {t('imageProviders.fields.supportsListModels.label')}
                  <HelpTooltip content={t('imageProviders.fields.supportsListModels.tooltip')} />
                </span>
              </label>

              <label className="flex items-start gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={!!form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  className="mt-0.5"
                />
                <span className="flex-1 inline-flex items-center gap-1.5 flex-wrap">
                  {t('imageProviders.fields.isDefault.label')}
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
                  <HelpTooltip content={t('imageProviders.fields.isActive.tooltip')} />
                </span>
              </label>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  disabled={saving}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? t('common.saving') : t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {docModelId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
          <div className="bg-white rounded-xl p-5 w-full max-w-md shadow-xl mx-4">
            <div className="flex justify-between items-start gap-3 mb-4">
              <div>
                <h4 className="text-lg font-semibold text-gray-900">{t('imageProviders.modelDoc.title')}</h4>
                <p className="font-mono text-sm text-forge-700 break-all mt-1">{docModelId}</p>
              </div>
              <button
                type="button"
                onClick={closeModelDoc}
                className="text-gray-400 hover:text-gray-600 shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <textarea
              value={docDraft}
              onChange={(e) => setDocDraft(e.target.value)}
              rows={8}
              autoFocus
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
              placeholder={t('placeholders.imageProviders.modelDoc')}
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={closeModelDoc}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={saveModelDoc}
                className="px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700"
              >
                {t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
