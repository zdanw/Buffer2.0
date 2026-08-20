import { useState } from 'react';
import { X } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

interface SubscribeCreditsModalProps {
  open: boolean;
  onClose: () => void;
  creditsRemaining: number;
  billingContact?: string | null;
}

function contactHref(contact: string): string {
  const c = contact.trim();
  if (/^https?:\/\//i.test(c)) return c;
  if (c.includes('@')) {
    return `mailto:${c}?subject=${encodeURIComponent('Platform image credit pack')}`;
  }
  return c;
}

export default function SubscribeCreditsModal({
  open,
  onClose,
  creditsRemaining,
  billingContact,
}: SubscribeCreditsModalProps) {
  const { t } = useI18n();
  if (!open) return null;

  const contact = (billingContact || '').trim();
  const href = contact ? contactHref(contact) : null;
  const isExternal = Boolean(href && /^https?:\/\//i.test(href));

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
          <li>{t('subscribeCredits.byokHint')}</li>
        </ul>

        <div className="flex flex-col sm:flex-row gap-2 pt-1">
          {href ? (
            <a
              href={href}
              {...(isExternal ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
              className="flex-1 text-center px-4 py-2.5 rounded-lg bg-forge-600 text-white text-sm font-medium hover:bg-forge-700"
            >
              {t('subscribeCredits.contactCta')}
            </a>
          ) : null}
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2.5 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50"
          >
            {t('common.close')}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Compact trigger button used near the image model picker. */
export function SubscribeCreditsButton({
  creditsRemaining,
  billingContact,
  className = '',
}: {
  creditsRemaining: number;
  billingContact?: string | null;
  className?: string;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={
          className ||
          'w-full px-3 py-2 rounded-lg text-sm font-medium border border-forge-200 bg-forge-50 text-forge-800 hover:bg-forge-100'
        }
      >
        {t('subscribeCredits.button')}
      </button>
      <SubscribeCreditsModal
        open={open}
        onClose={() => setOpen(false)}
        creditsRemaining={creditsRemaining}
        billingContact={billingContact}
      />
    </>
  );
}
