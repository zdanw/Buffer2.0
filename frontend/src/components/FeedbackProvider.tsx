import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { X } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';
import {
  bindFeedbackApi,
  type ConfirmOptions,
  type PromptOptions,
  type ToastTone,
} from '@/lib/feedback';

type ToastItem = {
  id: number;
  message: string;
  tone: ToastTone;
};

type ConfirmState = ConfirmOptions & {
  resolve: (value: boolean) => void;
};

type PromptState = PromptOptions & {
  resolve: (value: string | null) => void;
};

const TOAST_MS = 4500;

const TONE_CLASS: Record<ToastTone, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  error: 'border-red-200 bg-red-50 text-red-900',
  info: 'border-forge-200 bg-forge-50 text-forge-900',
};

export default function FeedbackProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirmState, setConfirmState] = useState<ConfirmState | null>(null);
  const [promptState, setPromptState] = useState<PromptState | null>(null);
  const [promptValue, setPromptValue] = useState('');
  const idRef = useRef(0);
  const promptInputRef = useRef<HTMLInputElement>(null);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (message: string, tone: ToastTone = 'info') => {
      const id = ++idRef.current;
      setToasts((prev) => [...prev.slice(-4), { id, message, tone }]);
      window.setTimeout(() => dismissToast(id), TOAST_MS);
    },
    [dismissToast]
  );

  const confirm = useCallback((options: ConfirmOptions) => {
    return new Promise<boolean>((resolve) => {
      setConfirmState({ ...options, resolve });
    });
  }, []);

  const prompt = useCallback((options: PromptOptions) => {
    return new Promise<string | null>((resolve) => {
      setPromptValue('');
      setPromptState({ ...options, resolve });
    });
  }, []);

  useEffect(() => {
    bindFeedbackApi({ toast: pushToast, confirm, prompt });
    return () => bindFeedbackApi(null);
  }, [pushToast, confirm, prompt]);

  useEffect(() => {
    if (!promptState) return;
    const timer = window.setTimeout(() => promptInputRef.current?.focus(), 0);
    return () => window.clearTimeout(timer);
  }, [promptState]);

  const closeConfirm = (value: boolean) => {
    confirmState?.resolve(value);
    setConfirmState(null);
  };

  const closePrompt = (value: string | null) => {
    promptState?.resolve(value);
    setPromptState(null);
    setPromptValue('');
  };

  const promptReady = useMemo(() => {
    if (!promptState) return false;
    if (promptState.expectedValue != null) {
      return promptValue === promptState.expectedValue;
    }
    return promptValue.trim().length > 0;
  }, [promptState, promptValue]);

  return (
    <>
      {children}

      <div
        className="pointer-events-none fixed bottom-20 right-4 z-[80] flex w-full max-w-sm flex-col gap-2"
        aria-live="polite"
      >
        {toasts.map((item) => (
          <div
            key={item.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg ${TONE_CLASS[item.tone]}`}
          >
            <p className="flex-1 whitespace-pre-wrap">{item.message}</p>
            <button
              type="button"
              onClick={() => dismissToast(item.id)}
              className="shrink-0 rounded p-0.5 opacity-60 hover:opacity-100"
              aria-label={t('common.close')}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      {confirmState ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
          >
            {confirmState.title ? (
              <h3 className="mb-2 text-lg font-semibold text-gray-900">{confirmState.title}</h3>
            ) : null}
            <p className="whitespace-pre-wrap text-sm text-gray-700">{confirmState.message}</p>
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => closeConfirm(false)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                {confirmState.cancelLabel || t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={() => closeConfirm(true)}
                className={`rounded-lg px-4 py-2 text-sm text-white ${
                  confirmState.danger
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-forge-600 hover:bg-forge-700'
                }`}
              >
                {confirmState.confirmLabel || t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {promptState ? (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 p-4">
          <div
            role="dialog"
            aria-modal="true"
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
          >
            {promptState.title ? (
              <h3 className="mb-2 text-lg font-semibold text-gray-900">{promptState.title}</h3>
            ) : null}
            <p className="mb-4 whitespace-pre-wrap text-sm text-gray-700">{promptState.message}</p>
            <input
              ref={promptInputRef}
              type="text"
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder={promptState.placeholder}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-forge-500 focus:ring-2 focus:ring-forge-200"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && promptReady) closePrompt(promptValue);
                if (e.key === 'Escape') closePrompt(null);
              }}
            />
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => closePrompt(null)}
                className="rounded-lg border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                {promptState.cancelLabel || t('common.cancel')}
              </button>
              <button
                type="button"
                disabled={!promptReady}
                onClick={() => closePrompt(promptValue)}
                className={`rounded-lg px-4 py-2 text-sm text-white ${
                  promptReady
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'cursor-not-allowed bg-gray-300 text-gray-500'
                }`}
              >
                {promptState.confirmLabel || t('common.confirm')}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
