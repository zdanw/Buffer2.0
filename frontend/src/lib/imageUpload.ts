/** Vercel serverless proxy limit is ~4.5 MB; stay under for the whole multipart body. */
export const MAX_IMAGE_FILE_BYTES = 4 * 1024 * 1024;
export const MAX_IMAGE_BATCH_BYTES = 4 * 1024 * 1024;

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) {
    const mb = bytes / (1024 * 1024);
    return `${mb % 1 === 0 ? mb : mb.toFixed(1)} MB`;
  }
  return `${Math.max(1, Math.ceil(bytes / 1024))} KB`;
}

export const MAX_IMAGE_FILE_LABEL = formatFileSize(MAX_IMAGE_FILE_BYTES);

export type ImageUploadValidationError = 'empty' | 'fileTooLarge' | 'batchTooLarge';

type ValidateResult =
  | { ok: true; files: File[] }
  | {
      ok: false;
      error: ImageUploadValidationError;
      oversized?: File[];
      totalBytes?: number;
    };

export function validateImageFiles(files: File[]): ValidateResult {
  if (files.length === 0) {
    return { ok: false, error: 'empty' };
  }

  const oversized = files.filter((f) => f.size > MAX_IMAGE_FILE_BYTES);
  if (oversized.length > 0) {
    return { ok: false, error: 'fileTooLarge', oversized };
  }

  const totalBytes = files.reduce((sum, f) => sum + f.size, 0);
  if (totalBytes > MAX_IMAGE_BATCH_BYTES) {
    return { ok: false, error: 'batchTooLarge', totalBytes };
  }

  return { ok: true, files };
}

export function getUploadErrorMessage(error: unknown, fallback: string): string {
  const response = (error as { response?: { status?: number; data?: { detail?: string } } })?.response;
  if (response?.status === 413) {
    return `Upload too large (max ${MAX_IMAGE_FILE_LABEL} per request).`;
  }
  const detail = response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}
