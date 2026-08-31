import type { OfferingType } from '@/api/products';

/** Friendly picker values. SaaS is not a separate choice. */
export const VISUAL_SETUP_CHOICES = [
  'physical_product',
  'software',
  'service',
  'digital_product',
  'event_or_experience',
  'mixed',
] as const;

export type VisualSetupChoice = (typeof VISUAL_SETUP_CHOICES)[number];

/** Auto-detect first; maps to backend `unknown`. */
export const VISUAL_SETUP_MENU = ['unknown', ...VISUAL_SETUP_CHOICES] as const;

export type VisualSetupMenuItem = (typeof VISUAL_SETUP_MENU)[number];

export function visualSetupChoiceKey(
  value: string | null | undefined,
): VisualSetupChoice | null {
  if (!value || value === 'unknown') return null;
  if (value === 'saas' || value === 'software') return 'software';
  if ((VISUAL_SETUP_CHOICES as readonly string[]).includes(value)) {
    return value as VisualSetupChoice;
  }
  return null;
}

/** Keep existing saas unless the user picks a different friendly type or Auto-detect. */
export function persistVisualSetupChoice(
  current: OfferingType | undefined,
  picked: VisualSetupMenuItem,
): OfferingType {
  if (picked === 'unknown') {
    return 'unknown';
  }
  if (picked === 'software' && current === 'saas') {
    return 'saas';
  }
  return picked;
}
