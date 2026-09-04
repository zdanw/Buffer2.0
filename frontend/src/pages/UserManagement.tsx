import { useState, useEffect } from 'react';
import { listUsers, createUser, updateUser, deleteUser } from '../api/auth';
import type { UserResponse, CreateUserData, UpdateUserData } from '../api/auth';
import { grantUserCredits } from '../api/credits';
import {
  listUserInvoices,
  refundUserInvoice,
  type BillingInvoice,
} from '../api/billing';
import { Plus, Edit2, Trash2, X, Check, UserCog, RefreshCw, Eye, EyeOff, Coins, Receipt } from 'lucide-react';
import {
  LIMITS,
  alertValidationErrors,
} from '@/lib/formValidation';
import { confirmDialog } from '@/lib/feedback';
import { useValidators } from '@/i18n/helpers';
import { toUserFacingMessage } from '@/lib/apiErrors';
import { useI18n } from '@/i18n/useI18n';
import { formatServerDateTime } from '@/lib/datetime';
import FormLabel from '@/components/FormLabel';
import FieldRequirementBadge from '@/components/FieldRequirementBadge';

const generateRandomPassword = (): string => {
 const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*';
 let password = '';
 for (let i = 0; i < 12; i++) {
 password += chars.charAt(Math.floor(Math.random() * chars.length));
 }
 return password;
};

function UserManagement() {
  const { t, locale } = useI18n();
  const { required, maxLen, minLen, emailFormat, usernameFormat } = useValidators();
  const [users, setUsers] = useState<UserResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [newUser, setNewUser] = useState<CreateUserData>({
    username: '',
    email: '',
    password: generateRandomPassword(),
    is_admin: false,
  });
  const [showPassword, setShowPassword] = useState(false);

  const [editForm, setEditForm] = useState<UpdateUserData>({
    email: '',
    password: '',
    is_active: true,
    is_admin: false,
  });
  const [grantUser, setGrantUser] = useState<UserResponse | null>(null);
  const [grantQty, setGrantQty] = useState('20');
  const [grantNote, setGrantNote] = useState('');
  const [granting, setGranting] = useState(false);
  const [refundUser, setRefundUser] = useState<UserResponse | null>(null);
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState(false);
  const [revokeCredits, setRevokeCredits] = useState(true);
  const [refundingId, setRefundingId] = useState<string | null>(null);

  const fetchUsers = async (opts?: { silent?: boolean }) => {
    try {
      if (opts?.silent) setRefreshing(true);
      else setLoading(true);
      const data = await listUsers();
      setUsers(data);
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('users.loadFailed')));
    } finally {
      if (opts?.silent) setRefreshing(false);
      else setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (
      alertValidationErrors([
        usernameFormat(t('users.username'), newUser.username),
        emailFormat(t('users.email'), newUser.email, true),
        required(t('users.password'), newUser.password),
        minLen(t('users.password'), newUser.password, LIMITS.password.min),
        maxLen(t('users.password'), newUser.password, LIMITS.password.max),
      ])
    ) {
      return;
    }

    try {
      setSaving(true);
      const userData = {
        ...newUser,
        email: newUser.email || undefined,
      };
      const created = await createUser(userData);
      setUsers((prev) => [...prev, created]);
      setShowCreateModal(false);
      setNewUser({ username: '', email: '', password: generateRandomPassword(), is_admin: false });
      setSuccess(t('users.createSuccess'));
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('users.createFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleEditUser = (user: UserResponse) => {
    setEditingUserId(user.user_id);
    setEditForm({
      email: user.email,
      password: '',
      is_active: user.is_active,
      is_admin: user.is_admin,
    });
    setError('');
    setSuccess('');
  };

  const handleSaveEdit = async (userId: string) => {
    setError('');
    setSuccess('');
    if (
      alertValidationErrors([
        emailFormat(t('users.email'), editForm.email, true),
        editForm.password
          ? minLen(t('users.password'), editForm.password, LIMITS.password.min)
          : null,
        editForm.password
          ? maxLen(t('users.password'), editForm.password, LIMITS.password.max)
          : null,
      ])
    ) {
      return;
    }

    try {
      setSaving(true);
      const updateData: UpdateUserData = { ...editForm };
      if (!updateData.password) {
        delete updateData.password;
      }
      const updated = await updateUser(userId, updateData);
      setUsers((prev) => prev.map((u) => (u.user_id === updated.user_id ? updated : u)));
      setEditingUserId(null);
      setSuccess(t('users.updateSuccess'));
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('users.updateFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteUser = async (userId: string) => {
    const ok = await confirmDialog({
      message: t('users.confirmDelete'),
      danger: true,
    });
    if (!ok) {
      return;
    }

    setError('');
    setSuccess('');
    setDeletingId(userId);

    try {
      await deleteUser(userId);
      setUsers((prev) => prev.filter((u) => u.user_id !== userId));
      setSuccess(t('users.deleteSuccess'));
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(toUserFacingMessage(err, t('users.deleteFailed')));
    } finally {
      setDeletingId(null);
    }
  };

  if (loading && users.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-forge-600"></div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">{t('users.title')}</h1>
          <p className="text-gray-500 mt-1">{t('users.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => void fetchUsers({ silent: true })}
            disabled={loading || refreshing}
            className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            {t('users.addUser')}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-4 bg-red-50 text-red-600 rounded-lg">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-4 bg-green-50 text-green-600 rounded-lg">
          {success}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.username')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.email')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.password')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.role')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.status')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.createdAt')}
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('users.grantCredits')}
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                {t('fields.actions')}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.user_id} className="hover:bg-gray-50">
                {editingUserId === user.user_id ? (
                  <>
                    <td className="px-6 py-4">
                      <span className="font-medium text-gray-900">{user.username}</span>
                    </td>
                    <td className="px-6 py-4">
                      <input
                        type="email"
                        value={editForm.email || ''}
                        onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                        maxLength={LIMITS.email}
                        className="w-full px-3 py-1 border border-gray-300 rounded-md text-sm"
                        placeholder={t('placeholders.users.email')}
                      />
                    </td>
                    <td className="px-6 py-4">
                      <input
                        type="password"
                        value={editForm.password || ''}
                        onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                        minLength={LIMITS.password.min}
                        maxLength={LIMITS.password.max}
                        className="w-full px-3 py-1 border border-gray-300 rounded-md text-sm"
                        placeholder={t('placeholders.users.passwordKeep')}
                      />
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={editForm.is_admin ? 'admin' : 'user'}
                        onChange={(e) => setEditForm({ ...editForm, is_admin: e.target.value === 'admin' })}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                      >
                        <option value="user">{t('users.regularUser')}</option>
                        <option value="admin">{t('users.admin')}</option>
                      </select>
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={editForm.is_active ? 'active' : 'inactive'}
                        onChange={(e) => setEditForm({ ...editForm, is_active: e.target.value === 'active' })}
                        className="px-3 py-1 border border-gray-300 rounded-md text-sm"
                      >
                        <option value="active">{t('users.enabled')}</option>
                        <option value="inactive">{t('users.disabled')}</option>
                      </select>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatServerDateTime(user.created_at, locale, t('datetime.unknown'))}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {t('users.creditsRemaining', {
                        n: user.image_credits_remaining ?? 0,
                      })}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleSaveEdit(user.user_id)}
                          disabled={saving}
                          className="p-1 text-green-600 hover:bg-green-50 rounded disabled:opacity-50"
                        >
                          {saving ? (
                            <RefreshCw className="w-5 h-5 animate-spin" />
                          ) : (
                            <Check className="w-5 h-5" />
                          )}
                        </button>
                        <button
                          onClick={() => setEditingUserId(null)}
                          disabled={saving}
                          className="p-1 text-gray-400 hover:bg-gray-100 rounded disabled:opacity-50"
                        >
                          <X className="w-5 h-5" />
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                          <UserCog className="w-4 h-4 text-forge-600" />
                        </div>
                        <span className="font-medium text-gray-900">{user.username}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {user.email || t('users.emptyEmail')}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500 font-mono">
                      {t('users.passwordMask')}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_admin
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {user.is_admin ? t('users.admin') : t('users.regularUser')}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {user.is_active ? t('users.enabled') : t('users.disabled')}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {formatServerDateTime(user.created_at, locale, t('datetime.unknown'))}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">
                      {t('users.creditsRemaining', {
                        n: user.image_credits_remaining ?? 0,
                      })}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => {
                            setGrantUser(user);
                            setGrantQty('20');
                            setGrantNote('');
                          }}
                          className="p-1 text-amber-600 hover:bg-amber-50 rounded"
                          title={t('users.grantCredits')}
                        >
                          <Coins className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => {
                            setRefundUser(user);
                            setRevokeCredits(true);
                            setInvoices([]);
                            setInvoicesLoading(true);
                            void listUserInvoices(user.user_id)
                              .then(setInvoices)
                              .catch(() => {
                                setError(t('users.refundLoadFailed'));
                                setInvoices([]);
                              })
                              .finally(() => setInvoicesLoading(false));
                          }}
                          className="p-1 text-rose-600 hover:bg-rose-50 rounded"
                          title={t('users.refundCredits')}
                        >
                          <Receipt className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleEditUser(user)}
                          className="p-1 text-forge-600 hover:bg-forge-50 rounded"
                        >
                          <Edit2 className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => handleDeleteUser(user.user_id)}
                          disabled={deletingId === user.user_id}
                          className="p-1 text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
                        >
                          {deletingId === user.user_id ? (
                            <RefreshCw className="w-5 h-5 animate-spin" />
                          ) : (
                            <Trash2 className="w-5 h-5" />
                          )}
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-md mx-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-800">{t('users.addNewUser')}</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <FormLabel label={t('users.username')} required htmlFor="create-user-username" />
                <input
                  id="create-user-username"
                  type="text"
                  value={newUser.username}
                  onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                  required
                  minLength={LIMITS.username.min}
                  maxLength={LIMITS.username.max}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                  placeholder={t('placeholders.users.username')}
                />
              </div>

              <div>
                <FormLabel label={t('users.email')} required={false} htmlFor="create-user-email" />
                <input
                  id="create-user-email"
                  type="email"
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  maxLength={LIMITS.email}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                  placeholder={t('placeholders.users.emailFull')}
                />
              </div>

              <div>
                <FormLabel label={t('users.password')} required htmlFor="create-user-password" />
                <div className="relative">
                  <input
                    id="create-user-password"
                    type={showPassword ? 'text' : 'password'}
                    value={newUser.password}
                    onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                    required
                    minLength={LIMITS.password.min}
                    maxLength={LIMITS.password.max}
                    className="w-full px-4 py-2 pr-28 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    placeholder={t('placeholders.users.autoPassword')}
                  />
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="p-1 text-gray-400 hover:text-gray-600"
                    >
                      {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                    <button
                      type="button"
                      onClick={() => setNewUser({ ...newUser, password: generateRandomPassword() })}
                      className="p-1 text-gray-400 hover:text-gray-600"
                      title={t('users.generatePassword')}
                    >
                      <RefreshCw className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_admin"
                  checked={newUser.is_admin}
                  onChange={(e) => setNewUser({ ...newUser, is_admin: e.target.checked })}
                  className="w-4 h-4 text-forge-600 border-gray-300 rounded focus:ring-forge-500"
                />
                <label htmlFor="is_admin" className="text-sm text-gray-700 inline-flex items-center gap-1.5">
                  {t('users.setAdmin')}
                  <FieldRequirementBadge required={false} />
                </label>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  disabled={saving}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? t('users.creating') : t('users.create')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {grantUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <form
            className="bg-white rounded-xl p-6 w-full max-w-md mx-4 space-y-3"
            onSubmit={async (e) => {
              e.preventDefault();
              const qty = Number(grantQty);
              if (!Number.isFinite(qty) || qty < 1) return;
              setGranting(true);
              setError('');
              try {
                await grantUserCredits(grantUser.user_id, qty, grantNote || undefined);
                setSuccess(t('users.grantSuccess'));
                setGrantUser(null);
                await fetchUsers({ silent: true });
              } catch (err: any) {
                setError(toUserFacingMessage(err, t('users.grantFailed')));
              } finally {
                setGranting(false);
              }
            }}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-800">
                {t('users.grantCredits')} — {grantUser.username}
              </h2>
              <button type="button" onClick={() => setGrantUser(null)}>
                <X className="w-6 h-6 text-gray-400" />
              </button>
            </div>
            <div>
              <FormLabel label={t('users.grantQuantity')} required htmlFor="grant-qty" className="block text-sm text-gray-700" />
              <input
                id="grant-qty"
                type="number"
                min={1}
                value={grantQty}
                onChange={(e) => setGrantQty(e.target.value)}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <FormLabel label={t('users.grantNote')} required={false} htmlFor="grant-note" className="block text-sm text-gray-700" />
              <input
                id="grant-note"
                type="text"
                value={grantNote}
                onChange={(e) => setGrantNote(e.target.value)}
                className="mt-1 w-full border rounded-lg px-3 py-2 text-sm"
              />
            </div>
            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => setGrantUser(null)}
                className="flex-1 px-4 py-2 border rounded-lg"
              >
                {t('common.cancel')}
              </button>
              <button
                type="submit"
                disabled={granting}
                className="flex-1 px-4 py-2 bg-forge-600 text-white rounded-lg disabled:opacity-50"
              >
                {t('common.save')}
              </button>
            </div>
          </form>
        </div>
      )}

      {refundUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg mx-4 space-y-3 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-800">
                {t('users.refundTitle')} — {refundUser.username}
              </h2>
              <button type="button" onClick={() => setRefundUser(null)}>
                <X className="w-6 h-6 text-gray-400" />
              </button>
            </div>
            <label className="flex items-start gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={revokeCredits}
                onChange={(e) => setRevokeCredits(e.target.checked)}
                className="mt-0.5"
              />
              <span>{t('users.refundRevokeLabel')}</span>
            </label>
            {invoicesLoading ? (
              <p className="text-sm text-gray-500">{t('common.loading')}</p>
            ) : invoices.length === 0 ? (
              <p className="text-sm text-gray-500">{t('users.refundEmpty')}</p>
            ) : (
              <ul className="space-y-2">
                {invoices.map((inv) => {
                  const amount = ((inv.amount_paid || 0) / 100).toFixed(2);
                  const cur = (inv.currency || 'usd').toUpperCase();
                  const isRefunded =
                    (inv.amount_paid || 0) > 0 &&
                    (inv.amount_refunded || 0) >= (inv.amount_paid || 0);
                  return (
                    <li
                      key={inv.invoice_id}
                      className="border border-gray-200 rounded-lg px-3 py-2 flex items-center justify-between gap-3"
                    >
                      <div className="min-w-0 text-sm">
                        <p className="font-medium text-gray-900">
                          {t('users.refundAmount')}: {amount} {cur}
                        </p>
                        <p className="text-gray-500 truncate">
                          {inv.created
                            ? formatServerDateTime(inv.created, locale, t('datetime.unknown'))
                            : inv.invoice_id}
                        </p>
                        <p className="text-gray-500">
                          {t('users.refundRemainingCredits', {
                            n: inv.grant_remaining ?? 0,
                          })}
                        </p>
                      </div>
                      {isRefunded ? (
                        <span className="shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium bg-gray-100 text-gray-700">
                          {t('users.refundedStatus')}
                        </span>
                      ) : (
                        <button
                          type="button"
                          disabled={!inv.refundable || refundingId === inv.invoice_id}
                          onClick={async () => {
                            if (!(await confirmDialog({
                              message: t('users.refundConfirm'),
                              danger: true,
                            }))) return;
                            setRefundingId(inv.invoice_id);
                            setError('');
                            void refundUserInvoice(
                              refundUser.user_id,
                              inv.invoice_id,
                              revokeCredits
                            )
                              .then(async () => {
                                setSuccess(t('users.refundSuccess'));
                                // Optimistic: mark this invoice refunded before re-fetch
                                setInvoices((prev) =>
                                  prev.map((row) =>
                                    row.invoice_id === inv.invoice_id
                                      ? {
                                          ...row,
                                          amount_refunded: row.amount_paid,
                                          refundable: false,
                                          grant_remaining: revokeCredits
                                            ? 0
                                            : row.grant_remaining,
                                        }
                                      : row
                                  )
                                );
                                try {
                                  const next = await listUserInvoices(refundUser.user_id);
                                  setInvoices(next);
                                } catch {
                                  /* keep optimistic row */
                                }
                                await fetchUsers({ silent: true });
                              })
                              .catch((err: any) => {
                                setError(toUserFacingMessage(err, t('users.refundFailed')));
                              })
                              .finally(() => setRefundingId(null));
                          }}
                          className="shrink-0 px-3 py-1.5 rounded-lg text-sm bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                        >
                          {refundingId === inv.invoice_id
                            ? t('users.refundBusy')
                            : inv.refundable
                              ? t('users.refundAction')
                              : t('users.refundNotRefundable')}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            <button
              type="button"
              onClick={() => setRefundUser(null)}
              className="w-full px-4 py-2 border rounded-lg text-sm"
            >
              {t('common.close')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserManagement;