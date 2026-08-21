const BRAND_DRAFT_KEY = 'pulseforge:draft:brand-form';
const PRODUCT_DRAFT_KEY = 'pulseforge:draft:product-form';
const DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000;

interface DraftEnvelope<T> {
  savedAt: number;
  data: T;
}

function readDraft<T>(key: string): T | null {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const envelope = JSON.parse(raw) as DraftEnvelope<T>;
    if (Date.now() - envelope.savedAt > DRAFT_MAX_AGE_MS) {
      sessionStorage.removeItem(key);
      return null;
    }
    return envelope.data;
  } catch {
    return null;
  }
}

function writeDraft<T>(key: string, data: T): void {
  try {
    const envelope: DraftEnvelope<T> = { savedAt: Date.now(), data };
    sessionStorage.setItem(key, JSON.stringify(envelope));
  } catch {
    /* quota or private mode — ignore */
  }
}

function clearDraft(key: string): void {
  try {
    sessionStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

export type BrandFormDraft = {
  form: Record<string, unknown>;
  activeTab: string;
  isEdit: boolean;
  editingId: string | null;
  logoPreview: string | null;
};

export type ProductFormDraft = {
  formData: Record<string, unknown>;
  isEdit: boolean;
  selectedProductId: string | null;
};

export function loadBrandFormDraft(): BrandFormDraft | null {
  return readDraft<BrandFormDraft>(BRAND_DRAFT_KEY);
}

export function saveBrandFormDraft(draft: BrandFormDraft): void {
  writeDraft(BRAND_DRAFT_KEY, draft);
}

export function clearBrandFormDraft(): void {
  clearDraft(BRAND_DRAFT_KEY);
}

export function loadProductFormDraft(): ProductFormDraft | null {
  return readDraft<ProductFormDraft>(PRODUCT_DRAFT_KEY);
}

export function saveProductFormDraft(draft: ProductFormDraft): void {
  writeDraft(PRODUCT_DRAFT_KEY, draft);
}

export function clearProductFormDraft(): void {
  clearDraft(PRODUCT_DRAFT_KEY);
}
