import { useEffect, useState } from 'react';
import { Plus, Trash2, RefreshCw, Star, X } from 'lucide-react';
import {
  listSystemImageProviders,
  createSystemImageProvider,
  updateSystemImageProvider,
  deleteSystemImageProvider,
  setSystemImageProviderDefault,
  type SystemImageProvider,
} from '@/api/systemImageProvider';
import type { ImageProviderType } from '@/api/imageProviders';
import { useI18n } from '@/i18n/useI18n';
import { notifyImageProvidersChanged } from '@/lib/imageProvidersEvents';
import { confirmDialog } from '@/lib/feedback';

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
  google_gemini: {
    base_url: 'https://generativelanguage.googleapis.com/v1beta',
    list: true,
  },
  agnes: {
    base_url: 'https://api.agnes-ai.cn/v1',
    list: true,
  },
};

const EMPTY = {
  name: '',
  provider_type: 'openai_compatible' as ImageProviderType,
  base_url: TYPE_PRESETS.openai_compatible.base_url,
  api_key: '',
  supports_list_models: TYPE_PRESETS.openai_compatible.list,
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

  const openCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY });
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
    setShowModal(true);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        provider_type: form.provider_type,
        base_url: form.base_url,
        supports_list_models: form.supports_list_models,
        default_model: form.default_model || null,
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
      setShowModal(false);
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
            className="bg-white rounded-xl shadow-xl w-full max-w-lg p-5 space-y-3"
          >
            <div className="flex justify-between items-center">
              <h2 className="font-semibold">
                {editingId ? t('common.edit') : t('common.add')}
              </h2>
              <button type="button" onClick={() => setShowModal(false)}>
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder={t('systemImageProviders.name')}
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            <select
              className="w-full border rounded-lg px-3 py-2 text-sm"
              value={form.provider_type}
              onChange={(e) => {
                const providerType = e.target.value as ImageProviderType;
                const preset = TYPE_PRESETS[providerType];
                setForm({
                  ...form,
                  provider_type: providerType,
                  base_url: preset.base_url,
                  supports_list_models: preset.list,
                  ...(providerType === 'agnes' && !form.default_model
                    ? { default_model: 'agnes-image-2.1-flash' }
                    : {}),
                });
              }}
            >
              {(Object.keys(TYPE_PRESETS) as ImageProviderType[]).map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder={t('systemImageProviders.baseUrl')}
              value={form.base_url}
              onChange={(e) => setForm({ ...form, base_url: e.target.value })}
              required
            />
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder={
                editingId
                  ? t('systemImageProviders.apiKeyKeep')
                  : t('systemImageProviders.apiKey')
              }
              value={form.api_key}
              onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              type="password"
            />
            <input
              className="w-full border rounded-lg px-3 py-2 text-sm"
              placeholder="Default model"
              value={form.default_model}
              onChange={(e) => setForm({ ...form, default_model: e.target.value })}
            />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              />
              {t('systemImageProviders.default')}
            </label>
            <button
              type="submit"
              disabled={saving}
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
