/**
 * Tabs where the global brand selector affects visible data.
 *
 * Show the bar only when changing brand filters the current page:
 * - Studio: product list + preview voice
 * - Products: product list + defaults for new products
 * - Review: draft list (via product → brand)
 * - Calendar: scheduled/executed items (via product → brand)
 *
 * Hidden elsewhere: brand catalog itself, user-wide settings (image models,
 * buffer, account), shared visual-style catalog, help, admin (users, platform
 * image), and automations (tasks are user-scoped; task picker has its own filter).
 */
export const BRAND_SELECTOR_TABS = new Set([
  'studio',
  'products',
  'review',
  'calendar',
]);

export function showsBrandSelector(tab: string): boolean {
  return BRAND_SELECTOR_TABS.has(tab);
}
