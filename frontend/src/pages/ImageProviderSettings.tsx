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

const TYPE_PRESETS: Record<ImageProviderType, { label: string; base_url: string; list: boolean }> = {
  openai_compatible: {
    label: 'OpenAI 兼容',
    base_url: 'https://api.openai.com/v1',
    list: true,
  },
  doubao_ark: {
    label: '豆包 Ark',
    base_url: 'https://ark.cn-beijing.volces.com/api/v3/images/generations',
    list: false,
  },
  aliyun_maas: {
    label: '阿里云 MaaS 图生图',
    base_url:
      'https://ws-lxvmitlmy9ln8pda.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
    list: true,
  },
};

export default function ImageProviderSettings() {
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

  const load = async (opts?: { silent?: boolean }) => {
    try {
      if (!opts?.silent) setLoading(true);
      const data = await listImageProviders();
      setProviders(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || '加载失败');
    } finally {
      if (!opts?.silent) setLoading(false);
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
      setError('名称与 Base URL 必填');
      return;
    }
    if (!editingId && !form.api_key.trim()) {
      setError('创建时必须填写 API Key');
      return;
    }

    try {
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
        setSuccess('已更新');
      } else {
        const created = await createImageProvider({
          ...form,
          default_model: form.default_model || null,
          manual_models: form.manual_models || [],
        });
        setProviders((prev) => [created, ...prev]);
        setSuccess('已创建');
      }
      setShowModal(false);
      setTimeout(() => setSuccess(''), 2500);
      void load({ silent: true });
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setError(Array.isArray(detail) ? detail[0]?.msg : detail || '保存失败');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除该 Provider？')) return;
    try {
      await deleteImageProvider(id);
      setProviders((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      setError(err.response?.data?.detail || '删除失败');
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
      setError(err.response?.data?.detail || '测试失败');
    } finally {
      setTestingId(null);
    }
  };

  if (loading) {
    return (
      <div className="p-6 flex justify-center">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-600" />
      </div>
    );
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">图像模型</h2>
          <p className="text-gray-500 mt-1">配置图像生成 Provider（API Key 加密存储于服务端）</p>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => void load()}
            className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200"
          >
            <RefreshCw className="w-4 h-4" />
            刷新
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
          >
            <Plus className="w-5 h-5" />
            添加 Provider
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
            className="bg-white rounded-xl border border-gray-200 p-5 flex justify-between items-start"
          >
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-semibold text-gray-900">{p.name}</h3>
                {p.is_default && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-indigo-100 text-indigo-700">默认</span>
                )}
                {!p.is_active && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">停用</span>
                )}
                <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
                  {TYPE_PRESETS[p.provider_type]?.label || p.provider_type}
                </span>
              </div>
              <p className="text-sm text-gray-500 break-all">{p.base_url}</p>
              <p className="text-xs text-gray-400 mt-1">
                Key: {p.api_key_masked}
                {p.default_model ? ` · 默认: ${p.default_model}` : ''}
                {(p.manual_models?.length || 0) > 0
                  ? ` · 手动模型 ${p.manual_models!.length} 个`
                  : ''}
              </p>
            </div>
            <div className="flex gap-2 ml-4 shrink-0">
              <button
                type="button"
                onClick={() => void handleTest(p.id)}
                disabled={testingId === p.id}
                className="p-2 text-gray-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg"
                title="测试连接"
              >
                {testingId === p.id ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Zap className="w-5 h-5" />
                )}
              </button>
              <button
                type="button"
                onClick={() => openEdit(p)}
                className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg"
              >
                <Edit2 className="w-5 h-5" />
              </button>
              <button
                type="button"
                onClick={() => void handleDelete(p.id)}
                className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
              >
                <Trash2 className="w-5 h-5" />
              </button>
            </div>
          </div>
        ))}

        {providers.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
            尚未配置图像 Provider。未配置时仍使用环境变量中的豆包。
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold">
                {editingId ? '编辑 Provider' : '添加 Provider'}
              </h3>
              <button type="button" onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">名称</label>
                <input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">类型</label>
                <select
                  value={form.provider_type}
                  onChange={(e) => {
                    const t = e.target.value as ImageProviderType;
                    const preset = TYPE_PRESETS[t];
                    setForm({
                      ...form,
                      provider_type: t,
                      base_url: preset.base_url,
                      supports_list_models: preset.list,
                    });
                  }}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                >
                  {(Object.keys(TYPE_PRESETS) as ImageProviderType[]).map((k) => (
                    <option key={k} value={k}>
                      {TYPE_PRESETS[k].label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Base URL</label>
                <input
                  value={form.base_url}
                  onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API Key {editingId ? '（留空则不修改）' : ''}
                </label>
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={form.api_key}
                    onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg pr-10"
                    autoComplete="off"
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
                <label className="block text-sm font-medium text-gray-700 mb-1">默认 Model ID</label>
                <input
                  value={form.default_model || ''}
                  onChange={(e) => setForm({ ...form, default_model: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  placeholder="如 qwen-image-2.0 / qwen-image-edit（图生图）"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  手动模型列表
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  同一 Provider / API Key 下可维护多个 Model ID；点击模型 ID 弹出说明文档
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
                    placeholder="Model ID，如 qwen-image-2.0"
                  />
                  <textarea
                    value={newModelDesc}
                    onChange={(e) => setNewModelDesc(e.target.value)}
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="模型描述（可选）：用途、分辨率、是否支持图生图等"
                  />
                  <button
                    type="button"
                    onClick={addManualModel}
                    className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm"
                  >
                    添加到列表
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
                          className="text-left flex-1 font-mono text-sm text-indigo-700 hover:text-indigo-900 hover:underline break-all"
                          title="点击查看说明文档"
                        >
                          {m.id}
                          {m.description ? (
                            <span className="ml-2 text-xs text-gray-400 font-sans">有说明</span>
                          ) : null}
                        </button>
                        <button
                          type="button"
                          onClick={() => removeManualModel(m.id)}
                          className="text-gray-400 hover:text-red-600 shrink-0"
                          title="移除"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-gray-400">暂无手动模型，可先添加常用图生图 Model ID</p>
                )}
              </div>

              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={!!form.supports_list_models}
                  onChange={(e) => setForm({ ...form, supports_list_models: e.target.checked })}
                />
                支持 GET /models 拉取列表
              </label>

              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={!!form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                />
                设为全局默认
              </label>

              <label className="flex items-center gap-2 text-sm text-gray-700">
                <input
                  type="checkbox"
                  checked={form.is_active !== false}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                />
                启用
              </label>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  保存
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
                <h4 className="text-lg font-semibold text-gray-900">模型说明</h4>
                <p className="font-mono text-sm text-indigo-700 break-all mt-1">{docModelId}</p>
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
              placeholder="在此填写模型说明文档：用途、分辨率、图生图能力、注意事项等"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                type="button"
                onClick={closeModelDoc}
                className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                取消
              </button>
              <button
                type="button"
                onClick={saveModelDoc}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
              >
                确定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
