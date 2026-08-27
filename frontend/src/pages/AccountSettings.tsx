import { useEffect, useState } from 'react';
import {
  CreditCard,
  ExternalLink,
  Lock,
  Mail,
  Receipt,
  Shield,
  Sparkles,
  UserRound,
} from 'lucide-react';
import {
  getCurrentUser,
  updateCurrentUser,
  type UserResponse,
} from '@/api/auth';
import {
  cancelSubscription,
  getSubscriptionStatus,
  listMyInvoices,
  resumeSubscription,
  type BillingInvoice,
  type SubscriptionItem,
  type SubscriptionStatus,
} from '@/api/billing';
import SubscribeCreditsModal from '@/components/SubscribeCreditsModal';
import { formatServerDateTime } from '@/lib/datetime';
import { confirmDialog } from '@/lib/feedback';
import { useI18n } from '@/i18n/useI18n';

function initialsFromUsername(username: string): string {
  const trimmed = username.trim();
  if (!trimmed) return '?';
  const parts = trimmed.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return trimmed.slice(0, 2).toUpperCase();
}

export default function AccountSettings() {
  const { t, locale } = useI18n();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);
  const [subBusy, setSubBusy] = useState(false);
  const [buyOpen, setBuyOpen] = useState(false);

  const load = async (opts?: { silent?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    setError(null);
    try {
      const [me, status, inv] = await Promise.all([
        getCurrentUser(),
        getSubscriptionStatus().catch(() => null),
        listMyInvoices().catch(() => [] as BillingInvoice[]),
      ]);
      setUser(me);
      setEmail(me.email || '');
      setSub(status);
      setInvoices(inv);
    } catch {
      if (!opts?.silent) setError(t('common.loadFailed'));
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [t]);

  const subscription: SubscriptionItem | null = sub?.subscriptions?.[0] ?? null;

  const packLabel = (item: SubscriptionItem) =>
    item.label || item.price_id || item.stripe_subscription_id;

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user) return;
    setSavingProfile(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: {
        email?: string;
        password?: string;
        current_password?: string;
      } = {};
      if (email.trim() !== (user.email || '')) {
        payload.email = email.trim();
      }
      if (newPassword) {
        payload.password = newPassword;
        payload.current_password = currentPassword;
      }
      if (!payload.email && !payload.password) {
        setSuccess(t('account.nothingToSave'));
        return;
      }
      const updated = await updateCurrentUser(payload);
      setUser(updated);
      setEmail(updated.email || '');
      setCurrentPassword('');
      setNewPassword('');
      setSuccess(t('account.profileSaved'));
    } catch (err: unknown) {
      const detail =
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(
        typeof detail === 'string' && detail
          ? detail
          : t('account.profileSaveFailed')
      );
    } finally {
      setSavingProfile(false);
    }
  };

  const handleCancelSub = async () => {
    if (!subscription) return;
    const label = packLabel(subscription);
    if (!(await confirmDialog({
      message: t('subscribeCredits.cancelConfirm', { pack: label }),
      danger: true,
    }))) return;
    setSubBusy(true);
    setError(null);
    try {
      const status = await cancelSubscription(subscription.stripe_subscription_id);
      setSub(status);
    } catch {
      setError(t('subscribeCredits.cancelFailed'));
    } finally {
      setSubBusy(false);
    }
  };

  const handleResumeSub = async () => {
    if (!subscription) return;
    setSubBusy(true);
    setError(null);
    try {
      const status = await resumeSubscription(subscription.stripe_subscription_id);
      setSub(status);
    } catch {
      setError(t('subscribeCredits.resumeFailed'));
    } finally {
      setSubBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full w-full flex items-center justify-center p-8">
        <div className="flex flex-col items-center gap-3">
          <div className="h-9 w-9 rounded-full border-2 border-forge-200 border-t-forge-600 animate-spin" />
          <p className="text-sm text-ink-500">{t('common.loading')}</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="h-full w-full p-6 lg:p-8">
        <p className="text-sm text-red-600">{error || t('common.loadFailed')}</p>
      </div>
    );
  }

  const periodEndLabel = subscription?.current_period_end
    ? formatServerDateTime(
        subscription.current_period_end,
        locale,
        t('datetime.unknown')
      )
    : '—';

  const credits = user.image_credits_remaining ?? 0;
  const roleLabel = user.is_admin ? t('account.roleAdmin') : t('account.roleUser');

  return (
    <div className="h-full w-full overflow-auto">
      <div className="w-full p-4 sm:p-6 lg:p-8 space-y-5 lg:space-y-6">
        {/* Hero identity strip — light, soft forge wash */}
        <section className="relative overflow-hidden rounded-2xl border border-canvas-border bg-white shadow-sm">
          <div
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                'linear-gradient(135deg, #fff7f0 0%, #ffffff 42%, #fef4ed 100%)',
            }}
          />
          <div
            className="absolute -right-16 -top-20 h-56 w-56 rounded-full pointer-events-none opacity-60"
            style={{
              background:
                'radial-gradient(circle, rgba(240,90,26,0.14), transparent 70%)',
            }}
          />
          <div
            className="absolute -left-10 bottom-0 h-40 w-40 rounded-full pointer-events-none opacity-50"
            style={{
              background:
                'radial-gradient(circle, rgba(240,90,26,0.08), transparent 70%)',
            }}
          />

          <div className="relative px-5 sm:px-7 py-5 sm:py-6">
            <div className="flex flex-col lg:flex-row lg:items-center gap-4 lg:gap-6">
              <div className="flex items-center gap-4 min-w-0 flex-1">
                <div className="relative shrink-0">
                  <div className="h-14 w-14 sm:h-16 sm:w-16 rounded-2xl bg-forge-600 text-white text-lg sm:text-xl font-bold flex items-center justify-center shadow-md ring-4 ring-white">
                    {initialsFromUsername(user.username)}
                  </div>
                  <span className="absolute -bottom-0.5 -right-0.5 h-4 w-4 rounded-full bg-emerald-500 ring-2 ring-white" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h1 className="text-xl sm:text-2xl font-semibold text-ink-900 truncate">
                      {user.username}
                    </h1>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-[var(--pf-forge-50)] text-forge-600 border border-[var(--pf-forge-100)]">
                      <Shield className="h-3 w-3" />
                      {roleLabel}
                    </span>
                  </div>
                  <p className="text-sm text-ink-500 truncate mt-0.5">{user.email}</p>
                  <p className="text-xs text-ink-400 mt-0.5">
                    {t('account.createdAt')}:{' '}
                    {formatServerDateTime(user.created_at, locale, t('datetime.unknown'))}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2.5 w-full lg:w-auto lg:min-w-[300px] shrink-0">
                <div className="rounded-xl bg-white px-3.5 py-3 border border-canvas-border shadow-sm">
                  <p className="text-[11px] font-medium text-ink-400 flex items-center gap-1">
                    <Sparkles className="h-3 w-3 text-forge-600" />
                    {t('account.creditsLabel')}
                  </p>
                  <p className="text-2xl font-bold text-ink-900 tabular-nums mt-0.5 leading-none">
                    {credits}
                    <span className="text-sm font-medium text-ink-400 ml-1">
                      {t('account.creditsUnit')}
                    </span>
                  </p>
                </div>
                <div className="rounded-xl bg-white px-3.5 py-3 border border-canvas-border shadow-sm">
                  <p className="text-[11px] font-medium text-ink-400 flex items-center gap-1">
                    <CreditCard className="h-3 w-3 text-forge-600" />
                    {t('account.planLabel')}
                  </p>
                  {subscription ? (
                    <>
                      <p className="text-sm font-semibold text-ink-900 truncate mt-1">
                        {packLabel(subscription)}
                      </p>
                      <p className="text-[11px] text-ink-400 mt-0.5 truncate">
                        {subscription.cancel_at_period_end
                          ? t('account.pendingCancel', { date: periodEndLabel })
                          : t('account.activeSubShort', { date: periodEndLabel })}
                      </p>
                    </>
                  ) : (
                    <p className="text-sm font-medium text-ink-500 mt-1">
                      {t('account.noSubscription')}
                    </p>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={!user.billing_enabled}
                title={!user.billing_enabled ? t('subscribeCredits.unavailable') : undefined}
                onClick={() => setBuyOpen(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium bg-forge-600 text-white hover:bg-forge-700 disabled:opacity-50 shadow-sm"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {t('account.manageCredits')}
              </button>
              {subscription ? (
                subscription.cancel_at_period_end ? (
                  <button
                    type="button"
                    disabled={subBusy}
                    onClick={() => void handleResumeSub()}
                    className="inline-flex items-center px-3.5 py-2 rounded-lg text-sm font-medium border border-canvas-border bg-white text-ink-900 hover:bg-gray-50 disabled:opacity-60"
                  >
                    {subBusy ? t('common.loading') : t('subscribeCredits.resumeCta')}
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={subBusy}
                    onClick={() => void handleCancelSub()}
                    className="inline-flex items-center px-3.5 py-2 rounded-lg text-sm font-medium border border-canvas-border bg-white text-ink-500 hover:bg-gray-50 hover:text-ink-900 disabled:opacity-60"
                  >
                    {subBusy
                      ? t('common.loading')
                      : t('subscribeCredits.cancelPackCta', {
                          pack: packLabel(subscription),
                        })}
                  </button>
                )
              ) : null}
            </div>
          </div>
        </section>

        {(error || success) && (
          <div
            className={`rounded-xl px-4 py-2.5 text-sm border ${
              error
                ? 'bg-red-50 border-red-100 text-red-700'
                : 'bg-emerald-50 border-emerald-100 text-emerald-800'
            }`}
          >
            {error || success}
          </div>
        )}

        {/* Two-column body */}
        <div className="grid grid-cols-1 xl:grid-cols-5 gap-5 lg:gap-6 items-start">
          {/* Profile */}
          <section className="xl:col-span-2 rounded-2xl border border-canvas-border bg-white shadow-sm overflow-hidden">
            <div className="px-5 py-3.5 border-b border-canvas-border flex items-center gap-2 bg-gradient-to-r from-[var(--pf-forge-50)] to-white">
              <div className="h-7 w-7 rounded-lg bg-forge-600/10 text-forge-600 flex items-center justify-center">
                <UserRound className="h-4 w-4" />
              </div>
              <h2 className="text-sm font-semibold text-ink-900">
                {t('account.profileSection')}
              </h2>
            </div>

            <form
              onSubmit={(e) => void handleSaveProfile(e)}
              className="p-5 space-y-4"
            >
              <div>
                <label className="block text-xs font-medium text-ink-500 mb-1.5">
                  {t('account.username')}
                </label>
                <div className="relative">
                  <UserRound className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-400" />
                  <input
                    type="text"
                    value={user.username}
                    disabled
                    className="w-full pl-9 pr-3 py-2 rounded-xl border border-canvas-border bg-[var(--pf-canvas)] text-sm text-ink-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-ink-500 mb-1.5">
                  {t('account.email')}
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-ink-400" />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 rounded-xl border border-canvas-border bg-white text-sm text-ink-900 focus:outline-none focus:ring-2 focus:ring-forge-500/30 focus:border-forge-500"
                    required
                  />
                </div>
              </div>

              <div className="rounded-xl border border-dashed border-canvas-border bg-[var(--pf-canvas)]/60 p-3.5 space-y-3">
                <p className="text-xs font-medium text-ink-500 flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5" />
                  {t('account.passwordSection')}
                </p>
                <div>
                  <label className="block text-xs text-ink-400 mb-1">
                    {t('account.currentPassword')}
                  </label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    autoComplete="current-password"
                    className="w-full px-3 py-2 rounded-xl border border-canvas-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-forge-500/30 focus:border-forge-500"
                    placeholder={t('account.passwordHint')}
                  />
                </div>
                <div>
                  <label className="block text-xs text-ink-400 mb-1">
                    {t('account.newPassword')}
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    autoComplete="new-password"
                    minLength={6}
                    className="w-full px-3 py-2 rounded-xl border border-canvas-border bg-white text-sm focus:outline-none focus:ring-2 focus:ring-forge-500/30 focus:border-forge-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={savingProfile}
                className="w-full inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl text-sm font-medium bg-forge-600 text-white hover:bg-forge-700 disabled:opacity-60 shadow-sm transition-colors"
              >
                {savingProfile ? t('common.saving') : t('common.save')}
              </button>
            </form>
          </section>

          {/* Invoices */}
          <section className="xl:col-span-3 rounded-2xl border border-canvas-border bg-white shadow-sm overflow-hidden flex flex-col min-h-[320px]">
            <div className="px-5 py-3.5 border-b border-canvas-border flex items-center justify-between gap-3 bg-gradient-to-r from-white to-[var(--pf-forge-50)]">
              <div className="flex items-center gap-2">
                <div className="h-7 w-7 rounded-lg bg-forge-600/10 text-forge-600 flex items-center justify-center">
                  <Receipt className="h-4 w-4" />
                </div>
                <h2 className="text-sm font-semibold text-ink-900">
                  {t('account.invoicesSection')}
                </h2>
              </div>
              {invoices.length > 0 ? (
                <span className="text-xs text-ink-400 tabular-nums">
                  {t('account.invoiceCount', { n: invoices.length })}
                </span>
              ) : null}
            </div>

            <div className="flex-1 p-4 sm:p-5 min-h-0">
              {invoices.length === 0 ? (
                <div className="h-full min-h-[220px] flex flex-col items-center justify-center text-center px-6">
                  <div className="h-12 w-12 rounded-2xl bg-[var(--pf-forge-50)] text-forge-600 flex items-center justify-center mb-3">
                    <Receipt className="h-5 w-5" />
                  </div>
                  <p className="text-sm font-medium text-ink-900">{t('account.noInvoices')}</p>
                  <p className="text-xs text-ink-400 mt-1 max-w-xs">
                    {t('account.noInvoicesHint')}
                  </p>
                  <button
                    type="button"
                    disabled={!user.billing_enabled}
                    onClick={() => setBuyOpen(true)}
                    className="mt-4 px-3.5 py-2 rounded-lg text-sm font-medium border border-canvas-border text-ink-900 hover:bg-gray-50 disabled:opacity-50"
                  >
                    {t('account.manageCredits')}
                  </button>
                </div>
              ) : (
                <ul className="divide-y divide-canvas-border rounded-xl border border-canvas-border overflow-hidden">
                  {[...invoices]
                    .sort((a, b) => {
                      const aTime = a.created ? new Date(a.created).getTime() : 0;
                      const bTime = b.created ? new Date(b.created).getTime() : 0;
                      return aTime - bTime;
                    })
                    .map((inv) => {
                    const amount = ((inv.amount_paid || 0) / 100).toFixed(2);
                    const cur = (inv.currency || 'usd').toUpperCase();
                    const refunded =
                      (inv.amount_paid || 0) > 0 &&
                      (inv.amount_refunded || 0) >= (inv.amount_paid || 0);
                    return (
                      <li
                        key={inv.invoice_id}
                        className="group flex items-center gap-3 bg-white hover:bg-[var(--pf-canvas)]/40 transition-colors px-3.5 py-3"
                      >
                        <div className="h-9 w-9 shrink-0 rounded-lg bg-white border border-canvas-border flex items-center justify-center text-forge-600 group-hover:border-forge-200">
                          <CreditCard className="h-4 w-4" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-ink-900 tabular-nums">
                            {amount} {cur}
                            {refunded ? (
                              <span className="ml-1.5 text-[11px] font-medium text-ink-400">
                                ({t('account.refunded')})
                              </span>
                            ) : (
                              <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700">
                                {t('account.paid')}
                              </span>
                            )}
                          </p>
                          <p className="text-xs text-ink-400 truncate mt-0.5">
                            {inv.created
                              ? formatServerDateTime(
                                  inv.created,
                                  locale,
                                  t('datetime.unknown')
                                )
                              : inv.invoice_id}
                            <span className="mx-1 opacity-40">·</span>
                            {t('account.invoiceCredits', {
                              n: inv.grant_remaining ?? 0,
                            })}
                          </p>
                        </div>
                        {inv.hosted_invoice_url ? (
                          <a
                            href={inv.hosted_invoice_url}
                            target="_blank"
                            rel="noreferrer"
                            className="shrink-0 inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-500 hover:text-forge-600 hover:bg-[var(--pf-forge-50)] transition-colors"
                          >
                            {t('account.viewInvoice')}
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {user.billing_contact ? (
              <div className="px-5 py-3 border-t border-canvas-border bg-[var(--pf-canvas)]/50">
                <p className="text-xs text-ink-400">
                  {t('account.billingContact', { email: user.billing_contact })}
                </p>
              </div>
            ) : null}
          </section>
        </div>
      </div>

      <SubscribeCreditsModal
        open={buyOpen}
        onClose={() => {
          setBuyOpen(false);
          void load({ silent: true });
        }}
        creditsRemaining={credits}
        billingEnabled={Boolean(user.billing_enabled)}
      />
    </div>
  );
}
