import { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';
import { formatServerDateTime } from '@/lib/datetime';
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
  useEffect(() => {
    if (!open) {
      setBuyingId(null);
      return;
    }
    let cancelled = false;
    setBuyingId(null);
    setLoading(true);
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
    if (!window.confirm(t('subscribeCredits.cancelConfirm', { pack: label }))) return;
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-4 max-h-[90vh] overflow-y-auto"
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
          <p className="text-sm text-gray-500">{t('common.loading')}</p>
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
    </div>
  );
}

/** Compact trigger button used near the image model picker. */
export function SubscribeCreditsButton({
  creditsRemaining,
  billingEnabled,
  className = '',
}: {
  creditsRemaining: number;
  billingEnabled: boolean;
  className?: string;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        disabled={!billingEnabled}
        onClick={() => setOpen(true)}
        title={!billingEnabled ? t('subscribeCredits.unavailable') : undefined}
        className={
          className ||
          'w-full px-3 py-2 rounded-lg text-sm font-medium border border-forge-200 bg-forge-50 text-forge-800 hover:bg-forge-100 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-forge-50'
        }
      >
        {t('subscribeCredits.button')}
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
