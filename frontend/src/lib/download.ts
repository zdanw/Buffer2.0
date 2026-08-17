/**
 * Download an image URL. Falls back to opening in a new tab if direct download is blocked (e.g. CORS).
 */
export async function downloadImage(url: string, filename = 'generated-image.jpg'): Promise<void> {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error('fetch failed');
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(objectUrl);
  } catch {
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.target = '_blank';
    anchor.rel = 'noopener noreferrer';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  }
}
