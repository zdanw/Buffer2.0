import type { TranslateFn } from '@/i18n/types';

type AxiosLikeError = {
  response?: {
    status?: number;
    data?: { detail?: unknown };
  };
  message?: string;
  code?: string;
};

const BLOCKED_PATTERNS: RegExp[] = [
  /scripts[/\\]/i,
  /\.ps1\b/i,
  /\.sh\b/i,
  /\bpython\s+/i,
  /\bnpm\s+/i,
  /\byarn\s+/i,
  /\bpnpm\s+/i,
  /dev\s+proxy/i,
  /localhost:/i,
  /127\.0\.0\.1/i,
  /\buvicorn\b/i,
  /\bECONNREFUSED\b/i,
  /Traceback\b/i,
  /File "/i,
  /\bat line \d+/i,
  /HTTPConnectionPool/i,
  /^Network Error$/i,
  /timeout of \d+ms exceeded/i,
  /Request failed with status code \d+/i,
];

const ERROR_CATEGORY_KEYS: Record<string, string> = {
  generate_task_failed: 'errors.categories.generateTaskFailed',
  scheduler_image_failed: 'errors.categories.schedulerImageFailed',
  quality_pre_generation: 'errors.categories.qualityPreGeneration',
};

function isJsonBlob(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) {
    return false;
  }
  try {
    JSON.parse(trimmed);
    return true;
  } catch {
    return false;
  }
}

function isBlockedMessage(value: string): boolean {
  if (isJsonBlob(value)) {
    return true;
  }
  return BLOCKED_PATTERNS.some((pattern) => pattern.test(value));
}

export function normalizeApiDetail(detail: unknown): string | undefined {
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim();
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string' && item.trim()) {
          return item.trim();
        }
        if (item && typeof item === 'object' && 'msg' in item) {
          const msg = (item as { msg?: unknown }).msg;
          return typeof msg === 'string' && msg.trim() ? msg.trim() : undefined;
        }
        return undefined;
      })
      .filter((msg): msg is string => Boolean(msg));
    if (messages.length > 0) {
      return messages.join('; ');
    }
  }
  return undefined;
}

export function extractApiDetail(error: unknown): string | undefined {
  if (!error || typeof error !== 'object' || !('response' in error)) {
    return undefined;
  }
  const detail = (error as AxiosLikeError).response?.data?.detail;
  return normalizeApiDetail(detail);
}

export function isConnectionError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }
  const axiosError = error as AxiosLikeError;
  const status = axiosError.response?.status;
  if (status === 502 || status === 503 || status === 504) {
    return true;
  }
  if (!axiosError.response) {
    return true;
  }
  const message = typeof axiosError.message === 'string' ? axiosError.message : '';
  if (message.toLowerCase().includes('timeout')) {
    return true;
  }
  if (axiosError.code === 'ECONNABORTED') {
    return true;
  }
  return false;
}

export function sanitizeMessage(raw: string | undefined | null, fallback: string): string {
  if (!raw || !raw.trim()) {
    return fallback;
  }
  const trimmed = raw.trim();
  if (isBlockedMessage(trimmed)) {
    return fallback;
  }
  return trimmed;
}

export function errorCategoryI18nKey(code: string | null | undefined): string | null {
  if (!code || !code.trim()) {
    return null;
  }
  return ERROR_CATEGORY_KEYS[code.trim()] ?? null;
}

export function mapErrorCategory(
  code: string | null | undefined,
  t: TranslateFn,
  fallback: string,
): string {
  const key = errorCategoryI18nKey(code);
  if (key) {
    return t(key);
  }
  return fallback;
}

export function toUserFacingMessage(
  error: unknown,
  fallback: string,
  options?: { statusAware?: boolean },
): string {
  if (isConnectionError(error)) {
    return fallback;
  }

  const detail = extractApiDetail(error);
  if (detail) {
    return sanitizeMessage(detail, fallback);
  }

  if (options?.statusAware && error && typeof error === 'object' && 'response' in error) {
    const status = (error as AxiosLikeError).response?.status;
    if (status === 413) {
      return fallback;
    }
  }

  return fallback;
}
