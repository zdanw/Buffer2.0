export type ToastTone = 'success' | 'error' | 'info';

export type ConfirmOptions = {
  title?: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
};

export type PromptOptions = {
  title?: string;
  message: string;
  placeholder?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** If set, Confirm stays disabled until input equals this value. */
  expectedValue?: string;
};

export type FeedbackApi = {
  toast: (message: string, tone?: ToastTone) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  prompt: (options: PromptOptions) => Promise<string | null>;
};

let api: FeedbackApi | null = null;

export function bindFeedbackApi(next: FeedbackApi | null) {
  api = next;
}

function requireApi(): FeedbackApi {
  if (!api) {
    throw new Error('FeedbackProvider is not mounted');
  }
  return api;
}

export const toast = {
  success(message: string) {
    requireApi().toast(message, 'success');
  },
  error(message: string) {
    requireApi().toast(message, 'error');
  },
  info(message: string) {
    requireApi().toast(message, 'info');
  },
};

export function confirmDialog(options: ConfirmOptions): Promise<boolean> {
  return requireApi().confirm(options);
}

export function promptDialog(options: PromptOptions): Promise<string | null> {
  return requireApi().prompt(options);
}
