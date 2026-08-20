/** Notify Studio / pickers that image-provider list or default changed. */

export const IMAGE_PROVIDERS_CHANGED_EVENT = 'pulseforge:image-providers-changed';

export function notifyImageProvidersChanged(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(IMAGE_PROVIDERS_CHANGED_EVENT));
}

export function onImageProvidersChanged(handler: () => void): () => void {
  window.addEventListener(IMAGE_PROVIDERS_CHANGED_EVENT, handler);
  return () => window.removeEventListener(IMAGE_PROVIDERS_CHANGED_EVENT, handler);
}
