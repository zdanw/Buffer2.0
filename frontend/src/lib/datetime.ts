/** Backend DateTime is usually UTC without timezone; parse as UTC then display locally */

import type { Locale } from '@/i18n/types';
import { localeToIntl } from '@/i18n/localeUtils';

export function parseServerDate(value: string | Date | null | undefined): Date | null {
  if (value == null) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  const raw = String(value).trim();
  if (!raw) return null;

  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(raw)) {
    const d = new Date(raw);
    return Number.isNaN(d.getTime()) ? null : d;
  }

  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T');
  const d = new Date(`${normalized}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatServerDateTime(
  value: string | Date | null | undefined,
  locale: Locale,
  unknownLabel: string,
  options?: Intl.DateTimeFormatOptions,
): string {
  const d = parseServerDate(value);
  if (!d) return unknownLabel;
  return d.toLocaleString(
    localeToIntl(locale),
    options ?? {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    },
  );
}

export function formatServerDate(
  value: string | Date | null | undefined,
  locale: Locale,
  unknownLabel: string,
): string {
  const d = parseServerDate(value);
  if (!d) return unknownLabel;
  return d.toLocaleDateString(localeToIntl(locale));
}
