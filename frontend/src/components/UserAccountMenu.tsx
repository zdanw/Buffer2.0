import { useEffect, useRef, useState } from 'react';
import { LogOut, UserRound } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { clearAuth, getCurrentUser, type UserResponse } from '@/api/auth';
import { useI18n } from '@/i18n/useI18n';

function initialsFromUsername(username: string): string {
  const trimmed = username.trim();
  if (!trimmed) return '?';
  const parts = trimmed.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return trimmed.slice(0, 2).toUpperCase();
}

export default function UserAccountMenu() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  const isAccountActive = pathname === '/account';

  const goAccount = () => {
    setOpen(false);
    navigate('/account');
  };

  const logout = () => {
    setOpen(false);
    clearAuth();
    window.location.href = '/login';
  };

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t('nav.userMenu', { name: user.username })}
        className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ring-1 ${
          isAccountActive
            ? 'bg-forge-100 text-forge-800 ring-forge-300'
            : 'bg-ink-100 text-ink-700 ring-ink-200 hover:bg-ink-200'
        }`}
      >
        {initialsFromUsername(user.username)}
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-52 rounded-xl border border-canvas-border bg-white py-1 shadow-lg"
        >
          <div className="border-b border-canvas-border px-3 py-2.5">
            <p className="truncate text-sm font-semibold text-ink-900">{user.username}</p>
            <p className="truncate text-xs text-ink-500">{user.email}</p>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={goAccount}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-ink-700 hover:bg-ink-50"
          >
            <UserRound className="h-4 w-4 shrink-0 text-ink-400" strokeWidth={1.75} />
            {t('nav.account')}
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={logout}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-ink-700 hover:bg-ink-50"
          >
            <LogOut className="h-4 w-4 shrink-0 text-ink-400" strokeWidth={1.75} />
            {t('nav.logout')}
          </button>
        </div>
      ) : null}
    </div>
  );
}
