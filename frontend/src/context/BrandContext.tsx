import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { GENERIC_BRAND_ID, getBrands, type BrandSummary } from '@/api/brands';

const STORAGE_KEY = 'pulseforge_active_brand_id';

interface BrandContextValue {
  brands: BrandSummary[];
  activeBrandId: string | null;
  activeBrand: BrandSummary | null;
  loading: boolean;
  brandFilterLoading: boolean;
  loadError: string | null;
  setActiveBrandId: (id: string | null) => void;
  setBrandFilterLoading: (loading: boolean) => void;
  refreshBrands: () => Promise<void>;
}

const BrandContext = createContext<BrandContextValue | null>(null);

export function BrandProvider({ children }: { children: ReactNode }) {
  const [brands, setBrands] = useState<BrandSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [brandFilterLoading, setBrandFilterLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeBrandId, setActiveBrandIdState] = useState<string | null>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored || null;
  });

  const refreshBrands = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await getBrands();
      setBrands(data);
    } catch (err) {
      console.error('Failed to load brands:', err);
      setBrands([]);
      setLoadError('connection');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshBrands();
  }, [refreshBrands]);

  const setActiveBrandId = useCallback((id: string | null) => {
    setBrandFilterLoading(true);
    setActiveBrandIdState(id);
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const activeBrand = useMemo(
    () => brands.find((b) => b.brand_id === activeBrandId) ?? null,
    [brands, activeBrandId]
  );

  const value = useMemo(
    () => ({
      brands,
      activeBrandId,
      activeBrand,
      loading,
      brandFilterLoading,
      loadError,
      setActiveBrandId,
      setBrandFilterLoading,
      refreshBrands,
    }),
    [brands, activeBrandId, activeBrand, loading, brandFilterLoading, loadError, setActiveBrandId, refreshBrands]
  );

  return <BrandContext.Provider value={value}>{children}</BrandContext.Provider>;
}

export function useBrandContext() {
  const ctx = useContext(BrandContext);
  if (!ctx) {
    throw new Error('useBrandContext must be used within BrandProvider');
  }
  return ctx;
}

export function useBrandFilterBrandId(): string | undefined {
  const { activeBrandId } = useBrandContext();
  return activeBrandId || undefined;
}

export { GENERIC_BRAND_ID };
