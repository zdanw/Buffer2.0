import { Calendar, Image, Settings, Sparkles, Clock, LogOut, Users, Palette, Cpu, X } from 'lucide-react';
import { clearAuth } from '../api/auth';
import { useI18n } from '@/i18n/useI18n';
import LanguageSwitcher from './LanguageSwitcher';
import BrandLogo from './BrandLogo';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  isAdmin: boolean;
  isOpen?: boolean;
  onClose?: () => void;
}

const baseMenuItems = [
  { id: 'assets', labelKey: 'nav.assets', icon: Image },
  { id: 'dimensions', labelKey: 'nav.dimensions', icon: Palette },
  { id: 'tasks', labelKey: 'nav.tasks', icon: Settings },
  { id: 'pending', labelKey: 'nav.pending', icon: Clock },
  { id: 'preview', labelKey: 'nav.preview', icon: Sparkles },
  { id: 'calendar', labelKey: 'nav.calendar', icon: Calendar },
];

const adminMenuItems = [
  { id: 'image-models', labelKey: 'nav.imageModels', icon: Cpu },
  { id: 'users', labelKey: 'nav.users', icon: Users },
];

export default function Sidebar({ activeTab, onTabChange, isAdmin, isOpen = false, onClose }: SidebarProps) {
  const { t } = useI18n();

  const handleLogout = () => {
    clearAuth();
    window.location.href = '/login';
  };

  const menuItems = isAdmin ? [...baseMenuItems, ...adminMenuItems] : baseMenuItems;

  return (
    <>
      {isOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
          aria-label={t('nav.closeMenu')}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-gradient-to-b from-indigo-900 to-purple-900 p-6 transition-transform duration-200 lg:static lg:z-auto lg:min-h-screen lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
      <div className="mb-8 flex items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2.5">
            <BrandLogo size="md" />
            {t('brand.name')}
          </h1>
          <p className="text-indigo-300 text-sm mt-1">{t('brand.tagline')}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 text-indigo-300 hover:bg-white/10 hover:text-white lg:hidden"
          aria-label={t('nav.closeMenu')}
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      
      <nav className="space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-white/10 text-white shadow-lg shadow-indigo-500/25'
                  : 'text-indigo-300 hover:bg-white/5 hover:text-white'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span className="font-medium">{t(item.labelKey)}</span>
            </button>
          );
        })}
      </nav>
      
      <div className="mt-auto pt-8 border-t border-white/10">
        <LanguageSwitcher />
        <button
          onClick={handleLogout}
          className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-red-300 hover:bg-red-500/10 hover:text-red-200 transition-all duration-200"
        >
          <LogOut className="w-5 h-5" />
          <span className="font-medium">{t('nav.logout')}</span>
        </button>
        {isAdmin && (
          <p className="text-purple-400 text-xs text-center mt-2">{t('nav.adminAccount')}</p>
        )}
        <p className="text-indigo-400 text-xs text-center mt-4">Version 2.0</p>
      </div>
    </aside>
    </>
  );
}
