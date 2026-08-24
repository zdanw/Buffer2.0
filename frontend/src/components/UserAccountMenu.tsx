import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCurrentUser, type UserResponse } from '@/api/auth';

function initialsFromUsername(username: string): string {
  const trimmed = username.trim();
  if (!trimmed) return '?';
  const parts = trimmed.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return trimmed.slice(0, 2).toUpperCase();
}

/** Top-bar avatar: navigates to the account / billing profile page. */
export default function UserAccountMenu() {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    void getCurrentUser()
      .then((me) => {
        if (!cancelled) setUser(me);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!user) return null;

  return (
    <div className="shrink-0">
      <button
        type="button"
        onClick={() => navigate('/account')}
        title={user.username}
        aria-label={user.username}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-forge-600 text-xs font-semibold text-white ring-1 ring-forge-700/20 hover:bg-forge-700 transition-colors"
      >
        {initialsFromUsername(user.username)}
      </button>
    </div>
  );
}
