import { useCallback, useEffect, useState } from 'react';
import { completeOnboarding, getCurrentUser, type UserResponse } from '@/api/auth';

const SKIP_KEY = 'pulseforge_onboarding_skipped';

export function useOnboarding() {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [skipped, setSkipped] = useState(() => localStorage.getItem(SKIP_KEY) === '1');
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const u = await getCurrentUser();
      setUser(u);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const shouldShowOnboarding = !loading && !skipped && !user?.onboarding_completed_at;

  const skipOnboarding = useCallback(() => {
    localStorage.setItem(SKIP_KEY, '1');
    setSkipped(true);
  }, []);

  const markComplete = useCallback(async () => {
    await completeOnboarding();
    localStorage.removeItem(SKIP_KEY);
    setSkipped(false);
    await refresh();
  }, [refresh]);

  return {
    user,
    loading,
    shouldShowOnboarding,
    skipOnboarding,
    markComplete,
    refresh,
  };
}
