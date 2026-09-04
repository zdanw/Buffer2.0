import { useEffect, useLayoutEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { CreditCard, X } from 'lucide-react';
import { getCurrentUser } from '@/api/auth';
import LoadingIndicator from '@/components/LoadingIndicator';
import { useI18n } from '@/i18n/useI18n';
import { onImageProvidersChanged } from '@/lib/imageProvidersEvents';
import { formatServerDateTime } from '@/lib/datetime';
import { confirmDialog } from '@/lib/feedback';
import {
  cancelSubscription,
  createCheckoutSession,
  getSubscriptionStatus,
  listCreditPacks,
  resumeSubscription,
  type CreditPack,
  type SubscriptionItem,
  type SubscriptionStatus,
} from '@/api/billing';

interface SubscribeCreditsModalProps {
  open: boolean;
  onClose: () => void;
  creditsRemaining: number;
  billingEnabled: boolean;
}

export default function SubscribeCreditsModal({
  open,
  onClose,
  creditsRemaining,
  billingEnabled,
}: SubscribeCreditsModalProps) {
  const { t, locale } = useI18n();
  const [packs, setPacks] = useState<CreditPack[]>([]);
  const [loading, setLoading] = useState(false);
  const [buyingId, setBuyingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sub, setSub] = useState<SubscriptionStatus | null>(null);
  const [subBusyId, setSubBusyId] = useState<string | null>(null);

  // Modal stays mounted while closed; clear checkout UI state so reopen is clickable.
  useLayoutEffect(() => {
    if (!open) {
      setBuyingId(null);
      setLoading(false);
      return;
    }
    setLoading(true);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setBuyingId(null);
    setError(null);
    void Promise.all([listCreditPacks(), getSubscriptionStatus()])
      .then(([packsRes, status]) => {
        if (cancelled) return;
        setPacks(packsRes.packs);
        setSub(status);
      })
      .catch(() => {
        if (!cancelled) setError(t('subscribeCredits.loadFailed'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, t]);

  // Browser back from Stripe can restore this page from bfcache with buyingId still set.
  useEffect(() => {
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) setBuyingId(null);
    };
    window.addEventListener('pageshow', onPageShow);
    return () => window.removeEventListener('pageshow', onPageShow);
  }, []);

  if (!open) return null;

  const packLabelFor = (item: SubscriptionItem) =>
    item.label ||
    packs.find((p) => p.price_id === item.price_id)?.label ||
    item.price_id ||
    item.stripe_subscription_id;

  const handleBuy = async (priceId: string) => {
    setBuyingId(priceId);
    setError(null);
    try {
      const { url } = await createCheckoutSession(priceId);
      window.location.assign(url);
    } catch {
      setError(t('subscribeCredits.checkoutFailed'));
      setBuyingId(null);
    }
  };

  const handleCancel = async (item: SubscriptionItem) => {
    const label = packLabelFor(item);
    if (!(await confirmDialog({
      message: t('subscribeCredits.cancelConfirm', { pack: label }),
      danger: true,
    }))) return;
    setSubBusyId(item.stripe_subscription_id);
    setError(null);
    try {
      const status = await cancelSubscription(item.stripe_subscription_id);
      setSub(status);
    } catch {
      setError(t('subscribeCredits.cancelFailed'));
    } finally {
      setSubBusyId(null);
    }
  };

  const handleResume = async (item: SubscriptionItem) => {
    setSubBusyId(item.stripe_subscription_id);
    setError(null);
    try {
      const status = await resumeSubscription(item.stripe_subscription_id);
      setSub(status);
    } catch {
      setError(t('subscribeCredits.resumeFailed'));
    } finally {
      setSubBusyId(null);
    }
  };

  const subscriptions = sub?.subscriptions ?? [];

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 sm:p-6"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-4 max-h-[min(90vh,calc(100vh-2rem))] overflow-y-auto"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {t('subscribeCredits.title')}
            </h2>
            <p className="text-sm text-gray-500 mt-1">
              {t('subscribeCredits.remaining', { n: creditsRemaining })}
            </p>
          </div>
          <button type="button" onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-gray-700 leading-relaxed">{t('subscribeCredits.body')}</p>
        <ul className="text-sm text-gray-600 list-disc pl-5 space-y-1">
          <li>{t('subscribeCredits.packHint')}</li>
          <li>{t('subscribeCredits.cancelPolicy')}</li>
          <li>{t('subscribeCredits.switchPolicy')}</li>
          <li>{t('subscribeCredits.byokHint')}</li>
        </ul>

        {subscriptions.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-medium text-gray-800">
              {t('subscribeCredits.mySubscriptions')}
            </p>
            {subscriptions.map((item) => {
              const label = packLabelFor(item);
              const periodEndLabel = item.current_period_end
                ? formatServerDateTime(
                    item.current_period_end,
                    locale,
                    t('datetime.unknown')
                  )
                : null;
              const busy = subBusyId === item.stripe_subscription_id;
              return (
                <div
                  key={item.stripe_subscription_id}
                  className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 space-y-2"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-900">{label}</p>
                    <p className="text-sm text-gray-700 mt-0.5">
                      {item.cancel_at_period_end
                        ? t('subscribeCredits.pendingCancel', {
                            date: periodEndLabel || '—',
                          })
                        : t('subscribeCredits.activeSub', {
                            date: periodEndLabel || '—',
                          })}
                    </p>
                  </div>
                  {item.cancel_at_period_end ? (
                    <button
                      type="button"
                      disabled={subBusyId !== null}
                      onClick={() => void handleResume(item)}
                      className="w-full px-3 py-2 rounded-lg text-sm font-medium border border-forge-200 bg-white text-forge-800 hover:bg-forge-50 disabled:opacity-60"
                    >
                      {busy ? t('common.loading') : t('subscribeCredits.resumeCta')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={subBusyId !== null}
                      onClick={() => void handleCancel(item)}
                      className="w-full px-3 py-2 rounded-lg text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-60"
                    >
                      {busy
                        ? t('common.loading')
                        : t('subscribeCredits.cancelPackCta', { pack: label })}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ) : null}

        {!billingEnabled ? (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            {t('subscribeCredits.unavailable')}
          </p>
        ) : loading ? (
          <LoadingIndicator size="sm" className="py-6" />
        ) : (
          <div className="space-y-2">
            {packs.map((pack) => (
              <button
                key={pack.price_id}
                type="button"
                disabled={buyingId !== null}
                onClick={() => void handleBuy(pack.price_id)}
                className="w-full flex items-center justify-between gap-3 px-4 py-2.5 rounded-lg bg-forge-600 text-white text-sm font-medium hover:bg-forge-700 disabled:opacity-60"
              >
                <span className="text-left">{pack.label}</span>
                <span className="opacity-90 shrink-0 font-semibold">
                  {buyingId === pack.price_id
                    ? t('subscribeCredits.redirecting')
                    : pack.price_display || t('subscribeCredits.buyCta', { n: pack.credits })}
                </span>
              </button>
            ))}
            {packs.length === 0 ? (
              <p className="text-sm text-gray-500">{t('subscribeCredits.noPacks')}</p>
            ) : null}
          </div>
        )}

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <button
          type="button"
          onClick={onClose}
          className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50"
        >
          {t('common.close')}
        </button>
      </div>
    </div>,
    document.body,
  );
}

/** Compact trigger button; fetches billing state when props are omitted. */
export function SubscribeCreditsButton({
  creditsRemaining: creditsProp,
  billingEnabled: billingProp,
  className = '',
  variant = 'block',
}: {
  creditsRemaining?: number;
  billingEnabled?: boolean;
  className?: string;
  variant?: 'block' | 'inline';
}) {
  const { t } = useI18n();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [open, setOpen] = useState(false);
  const selfFetch = creditsProp === undefined;
  const [creditsRemaining, setCreditsRemaining] = useState(creditsProp ?? 0);
  const [billingEnabled, setBillingEnabled] = useState(billingProp ?? false);

  const loadBilling = async () => {
    try {
      const me = await getCurrentUser();
      setCreditsRemaining(me.image_credits_remaining ?? 0);
      setBillingEnabled(Boolean(me.billing_enabled));
    } catch {
      setCreditsRemaining(0);
      setBillingEnabled(false);
    }
  };

  useEffect(() => {
    if (!selfFetch) return;
    void loadBilling();
    return onImageProvidersChanged(() => {
      void loadBilling();
    });
  }, [selfFetch]);

  useEffect(() => {
    if (selfFetch) return;
    setCreditsRemaining(creditsProp ?? 0);
    setBillingEnabled(billingProp ?? false);
  }, [creditsProp, billingProp, selfFetch]);

  useEffect(() => {
    if (!selfFetch) return;
    const checkout = searchParams.get('checkout');
    if (checkout !== 'success' && checkout !== 'cancel') return;
    if (checkout === 'success') {
      void loadBilling();
    }
    const next = new URLSearchParams(searchParams);
    next.delete('checkout');
    navigate(
      { pathname: location.pathname, search: next.toString() ? `?${next}` : '' },
      { replace: true }
    );
  }, [searchParams, navigate, location.pathname, selfFetch]);

  const defaultClassName =
    variant === 'inline'
      ? 'inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg px-3.5 text-sm font-medium bg-forge-600 text-white hover:bg-forge-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-forge-600 whitespace-nowrap'
      : 'w-full px-3 py-2 rounded-lg text-sm font-medium border border-forge-200 bg-forge-50 text-forge-800 hover:bg-forge-100 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-forge-50';

  const label =
    variant === 'inline' ? t('subscribeCredits.buttonShort') : t('subscribeCredits.button');

  return (
    <>
      <button
        type="button"
        disabled={!billingEnabled}
        onClick={() => setOpen(true)}
        aria-label={variant === 'inline' ? label : undefined}
        title={
          !billingEnabled
            ? t('subscribeCredits.unavailable')
            : variant === 'inline'
              ? t('subscribeCredits.remaining', { n: creditsRemaining })
              : undefined
        }
        className={className || defaultClassName}
      >
        {variant === 'inline' ? (
          <CreditCard className="w-3.5 h-3.5 shrink-0 opacity-90" aria-hidden />
        ) : null}
        <span className={variant === 'inline' ? 'hidden min-[420px]:inline' : undefined}>
          {label}
        </span>
      </button>
      <SubscribeCreditsModal
        open={open}
        onClose={() => setOpen(false)}
        creditsRemaining={creditsRemaining}
        billingEnabled={billingEnabled}
      />
    </>
  );
}
