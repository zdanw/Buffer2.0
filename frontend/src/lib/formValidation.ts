/** Field length limits aligned with backend SQLAlchemy columns */

import { toast } from '@/lib/feedback';

export const LIMITS = {
  productName: 255,
  category: 100,
  brandVoice: 5000,
  sellingPointsJoined: 500,
  description: 5000,
  taskName: 255,
  cron: 100,
  dimensionItemId: 100,
  dimensionName: 500,
  productType: 100,
  username: { min: 3, max: 50 },
  password: { min: 6, max: 128 },
  email: 100,
  referenceImageCount: { min: 1, max: 10 },
  runCount: { min: 1, max: 5 },
  generateImageCount: { min: 1, max: 10 },
  generateCopyCount: { min: 1, max: 10 },
} as const;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const ITEM_ID_RE = /^[a-zA-Z0-9_-]+$/;

export type TranslateFn = (key: string, params?: Record<string, string | number>) => string;

export function createValidators(t: TranslateFn) {
  const required = (label: string, value: string | undefined | null): string | null => {
    if (value == null || !String(value).trim()) return t('validation.required', { label });
    return null;
  };

  const maxLen = (label: string, value: string | undefined | null, max: number): string | null => {
    if (value == null || value === '') return null;
    if (value.length > max) return t('validation.maxLen', { label, max, current: value.length });
    return null;
  };

  const minLen = (label: string, value: string | undefined | null, min: number): string | null => {
    if (value == null || value === '') return null;
    if (value.length < min) return t('validation.minLen', { label, min, current: value.length });
    return null;
  };

  const emailFormat = (label: string, value: string | undefined | null, optional = false): string | null => {
    if (value == null || !value.trim()) return optional ? null : t('validation.required', { label });
    if (value.length > LIMITS.email) return t('validation.maxLenSimple', { label, max: LIMITS.email });
    if (!EMAIL_RE.test(value.trim())) return t('validation.emailFormat', { label });
    return null;
  };

  const cronFormat = (value: string | undefined | null): string | null => {
    const cronLabel = t('validation.cronLabel');
    const err = required(cronLabel, value) || maxLen(cronLabel, value, LIMITS.cron);
    if (err) return err;
    const parts = value!.trim().split(/\s+/);
    if (parts.length !== 5) return t('validation.cronParts');
    return null;
  };

  const intInRange = (
    label: string,
    value: number | undefined | null,
    min: number,
    max: number,
  ): string | null => {
    if (value == null || !Number.isFinite(value) || !Number.isInteger(value)) {
      return t('validation.integer', { label });
    }
    if (value < min || value > max) return t('validation.range', { label, min, max });
    return null;
  };

  const itemIdFormat = (value: string | undefined | null): string | null => {
    const label = t('validation.dimensionItemIdLabel');
    const err = required(label, value) || maxLen(label, value, LIMITS.dimensionItemId);
    if (err) return err;
    if (!ITEM_ID_RE.test(value!.trim())) return t('validation.itemIdFormat');
    return null;
  };

  return { required, maxLen, minLen, emailFormat, cronFormat, intInRange, itemIdFormat };
}

/** Show validation errors; returns true if submission should abort */
export function alertValidationErrors(errors: Array<string | null | undefined>): boolean {
  const messages = errors.filter((e): e is string => Boolean(e));
  if (messages.length === 0) return false;
  toast.error(messages.join('\n'));
  return true;
}
