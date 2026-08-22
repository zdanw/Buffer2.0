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
  const [subBusy, setSubBusy] = useState(false);

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

  const handleCancel = async () => {
    if (!window.confirm(t('subscribeCredits.cancelConfirm'))) return;
    setSubBusy(true);
    setError(null);
    try {
      const status = await cancelSubscription();
      setSub(status);
    } catch {
      setError(t('subscribeCredits.cancelFailed'));
    } finally {
      setSubBusy(false);
    }
  };

  const handleResume = async () => {
    setSubBusy(true);
    setError(null);
    try {
      const status = await resumeSubscription();
      setSub(status);
    } catch {
      setError(t('subscribeCredits.resumeFailed'));
    } finally {
      setSubBusy(false);
    }
  };

  const periodEndLabel = sub?.current_period_end
    ? formatServerDateTime(sub.current_period_end, locale, t('datetime.unknown'))
    : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="bg-white rounded-xl shadow-xl w-full max-w-md p-5 space-y-4"
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
          <li>{t('subscribeCredits.byokHint')}</li>
        </ul>

        {sub?.has_subscription ? (
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 space-y-2">
            <p className="text-sm text-gray-800">
              {sub.cancel_at_period_end
                ? t('subscribeCredits.pendingCancel', { date: periodEndLabel || '—' })
                : t('subscribeCredits.activeSub', { date: periodEndLabel || '—' })}
            </p>
            {sub.cancel_at_period_end ? (
              <button
                type="button"
                disabled={subBusy}
                onClick={() => void handleResume()}
                className="w-full px-3 py-2 rounded-lg text-sm font-medium border border-forge-200 bg-white text-forge-800 hover:bg-forge-50 disabled:opacity-60"
              >
                {subBusy ? t('common.loading') : t('subscribeCredits.resumeCta')}
              </button>
            ) : (
              <button
                type="button"
                disabled={subBusy}
                onClick={() => void handleCancel()}
                className="w-full px-3 py-2 rounded-lg text-sm font-medium border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-60"
              >
                {subBusy ? t('common.loading') : t('subscribeCredits.cancelCta')}
              </button>
            )}
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
