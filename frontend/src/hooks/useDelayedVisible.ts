import { useEffect, useState } from 'react';

/** Avoid flashing loaders on fast responses. */
export function useDelayedVisible(active: boolean, delayMs = 300): boolean {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!active) {
      setVisible(false);
      return;
    }
    const timer = window.setTimeout(() => setVisible(true), delayMs);
    return () => window.clearTimeout(timer);
  }, [active, delayMs]);

  return active && visible;
}
