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
  AlertCircle,
} from 'lucide-react';
import {
  listBufferAccounts,
  createBufferAccount,
  updateBufferAccount,
  deleteBufferAccount,
  testBufferAccount,
  type BufferAccount,
  type BufferAccountCreate,
} from '@/api/bufferAccounts';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import { useI18n } from '@/i18n/useI18n';

const EMPTY_FORM: BufferAccountCreate = {
  name: '',
  api_token: '',
  is_active: true,
};

function formatApiDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === 'string') return first;
    if (first && typeof first === 'object' && 'msg' in first) {
      return String((first as { msg: unknown }).msg);
    }
  }
  return fallback;
}

export default function BufferAccountSettings() {
  const { t } = useI18n();
  const [accounts, setAccounts] = useState<BufferAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<BufferAccountCreate>({ ...EMPTY_FORM });
  const [showToken, setShowToken] = useState(false);
  const [formError, setFormError] = useState('');
  const [alertError, setAlertError] = useState('');
  const [success, setSuccess] = useState('');
  const [testingId, setTestingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const showAlert = (message: string) => {
    setAlertError(message);
  };

  const load = async (opts?: { silent?: boolean }) => {
    try {
      if (opts?.silent) setRefreshing(true);
      else setLoading(true);
      const data = await listBufferAccounts();
      setAccounts(data);
    } catch (err: any) {
      showAlert(formatApiDetail(err.response?.data?.detail, t('common.loadFailed')));
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
    setForm({ ...EMPTY_FORM });
    setShowToken(false);
    setFormError('');
    setShowModal(true);
  };

  const openEdit = (account: BufferAccount) => {
    setEditingId(account.id);
    setForm({
      name: account.name,
      api_token: '',
      is_active: account.is_active,
    });
    setShowToken(false);
    setFormError('');
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    if (!form.name.trim()) {
      setFormError(t('bufferAccounts.validation.nameRequired'));
      return;
    }
    if (!editingId && !form.api_token.trim()) {
      setFormError(t('bufferAccounts.validation.tokenRequired'));
      return;
    }

    try {
      setSaving(true);
      if (editingId) {
        const payload: Record<string, unknown> = {
          name: form.name.trim(),
          is_active: form.is_active,
        };
        if (form.api_token.trim()) {
          payload.api_token = form.api_token.trim();
        }
        await updateBufferAccount(editingId, payload);
        setSuccess(t('common.updated'));
      } else {
        await createBufferAccount({
          name: form.name.trim(),
          api_token: form.api_token.trim(),
          is_active: form.is_active ?? true,
        });
        setSuccess(t('common.created'));
      }
      setShowModal(false);
      setTimeout(() => setSuccess(''), 2500);
      void load({ silent: true });
    } catch (err: any) {
      const message = formatApiDetail(err.response?.data?.detail, t('common.saveFailed'));
      setFormError(message);
      showAlert(message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('bufferAccounts.confirmDelete'))) return;
    setDeletingId(id);
    try {
      await deleteBufferAccount(id);
      setAccounts((prev) => prev.filter((a) => a.id !== id));
    } catch (err: any) {
      showAlert(formatApiDetail(err.response?.data?.detail, t('common.deleteFailed')));
    } finally {
      setDeletingId(null);
    }
  };

  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      const res = await testBufferAccount(id);
      if (res.ok) {
        setSuccess(res.message);
        setTimeout(() => setSuccess(''), 4000);
      } else {
        showAlert(res.message || t('bufferAccounts.test.failed'));
      }
      void load({ silent: true });
    } catch (err: any) {
      showAlert(formatApiDetail(err.response?.data?.detail, t('bufferAccounts.test.failed')));
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
          <h2 className="text-xl font-bold text-gray-900 sm:text-2xl">
            {t('bufferAccounts.title')}
          </h2>
          <p className="text-gray-500 mt-1 text-sm sm:text-base">
            {t('bufferAccounts.subtitle')}
          </p>
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
            {t('bufferAccounts.addAccount')}
          </button>
        </div>
      </div>

      {success && (
        <div className="mb-4 px-4 py-3 bg-green-50 text-green-700 rounded-lg text-sm flex items-center gap-2">
          <Check className="w-4 h-4" />
          {success}
        </div>
      )}

      <div className="space-y-3">
        {accounts.map((account) => (
          <div
            key={account.id}
            className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4 sm:flex-row sm:justify-between sm:items-start"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <h3 className="font-semibold text-gray-900">{account.name}</h3>
                {!account.is_active && (
                  <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-500">
                    {t('common.disabled')}
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-500">
                {account.buffer_email || t('bufferAccounts.noEmail')}
              </p>
              <p className="text-xs text-gray-400 mt-1">
                {t('bufferAccounts.tokenLabel')}: {account.api_token_masked}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(account.brands || []).length === 0 ? (
                  <span className="text-xs text-gray-400">
                    {t('bufferAccounts.noBrandsBound')}
                  </span>
                ) : (
                  account.brands.map((b) => (
                    <span
                      key={b.brand_id}
                      className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-700"
                    >
                      {b.name}
                    </span>
                  ))
                )}
              </div>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                type="button"
                onClick={() => void handleTest(account.id)}
                disabled={testingId === account.id}
                className="p-2 text-gray-500 hover:text-amber-600 hover:bg-amber-50 rounded-lg"
                title={t('bufferAccounts.testConnection')}
              >
                {testingId === account.id ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Zap className="w-5 h-5" />
                )}
              </button>
              <button
                type="button"
                onClick={() => openEdit(account)}
                className="p-2 text-gray-500 hover:text-forge-600 hover:bg-forge-50 rounded-lg"
              >
                <Edit2 className="w-5 h-5" />
              </button>
              <button
                type="button"
                onClick={() => void handleDelete(account.id)}
                disabled={deletingId === account.id}
                className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50"
              >
                {deletingId === account.id ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Trash2 className="w-5 h-5" />
                )}
              </button>
            </div>
          </div>
        ))}

        {accounts.length === 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
            {t('bufferAccounts.emptyState')}
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-4 sm:p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold">
                {editingId
                  ? t('bufferAccounts.editAccount')
                  : t('bufferAccounts.addAccount')}
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
              {formError && (
                <div className="px-4 py-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                  <span>{formError}</span>
                </div>
              )}

              <div>
                <LabelWithTooltip
                  htmlFor="buffer-name"
                  label={t('bufferAccounts.fields.name.label')}
                  tooltip={t('bufferAccounts.fields.name.tooltip')}
                />
                <input
                  id="buffer-name"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg"
                  required
                  placeholder={t('placeholders.bufferAccounts.name')}
                />
              </div>

              <div>
                <LabelWithTooltip
                  htmlFor="buffer-token"
                  label={
                    editingId
                      ? t('bufferAccounts.fields.token.labelOptional')
                      : t('bufferAccounts.fields.token.label')
                  }
                  tooltip={t('bufferAccounts.fields.token.tooltip')}
                />
                <div className="relative">
                  <input
                    id="buffer-token"
                    type={showToken ? 'text' : 'password'}
                    value={form.api_token}
                    onChange={(e) => setForm({ ...form, api_token: e.target.value })}
                    className="w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg"
                    required={!editingId}
                    placeholder={
                      editingId
                        ? t('bufferAccounts.fields.token.keepPlaceholder')
                        : t('placeholders.bufferAccounts.token')
                    }
                    autoComplete="off"
                  />
                  <button
                    type="button"
                    onClick={() => setShowToken((v) => !v)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
                    aria-label={showToken ? t('common.close') : t('common.preview')}
                  >
                    {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.is_active !== false}
                  onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                  className="rounded border-gray-300 text-forge-600 focus:ring-forge-500"
                />
                <span className="text-sm text-gray-700">
                  {t('bufferAccounts.fields.isActive.label')}
                </span>
              </label>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50"
                >
                  {saving ? t('common.saving') : t('common.save')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {alertError && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="buffer-error-title"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-lg sm:p-6">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded-full bg-red-50 p-2 text-red-600">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 id="buffer-error-title" className="text-lg font-semibold text-gray-900">
                  {t('bufferAccounts.errorDialog.title')}
                </h3>
                <p className="mt-2 text-sm text-gray-600 break-words whitespace-pre-wrap">
                  {alertError}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAlertError('')}
                className="text-gray-400 hover:text-gray-600"
                aria-label={t('common.close')}
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setAlertError('')}
                className="rounded-lg bg-forge-600 px-4 py-2 text-sm text-white hover:bg-forge-700"
              >
                {t('bufferAccounts.errorDialog.ok')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
