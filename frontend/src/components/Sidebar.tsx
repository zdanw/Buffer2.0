import { Calendar, Image, Settings, Sparkles, Clock, LogOut, Users, Palette, Cpu, X, Layers, Package } from 'lucide-react';
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

interface NavItem {
  id: string;
  labelKey: string;
  icon: typeof Image;
}

interface NavGroup {
  labelKey: string;
  items: NavItem[];
}

const contentItems: NavItem[] = [
  { id: 'brand', labelKey: 'nav.brand', icon: Layers },
  { id: 'products', labelKey: 'nav.products', icon: Package },
  { id: 'visual-styles', labelKey: 'nav.visualStyles', icon: Palette },
];

const createItems: NavItem[] = [
  { id: 'studio', labelKey: 'nav.studio', icon: Sparkles },
  { id: 'automations', labelKey: 'nav.automations', icon: Settings },
  { id: 'review', labelKey: 'nav.review', icon: Clock },
];

const insightsItems: NavItem[] = [
  { id: 'calendar', labelKey: 'nav.calendar', icon: Calendar },
];

const adminItems: NavItem[] = [
  { id: 'image-models', labelKey: 'nav.imageModels', icon: Cpu },
  { id: 'users', labelKey: 'nav.users', icon: Users },
];

export default function Sidebar({ activeTab, onTabChange, isAdmin, isOpen = false, onClose }: SidebarProps) {
  const { t } = useI18n();

  const handleLogout = () => {
    clearAuth();
    window.location.href = '/login';
  };

  const groups: NavGroup[] = [
    { labelKey: 'nav.groups.content', items: contentItems },
    { labelKey: 'nav.groups.create', items: createItems },
    { labelKey: 'nav.groups.insights', items: insightsItems },
  ];

  if (isAdmin) {
    groups.push({ labelKey: 'nav.groups.settings', items: adminItems });
  }

  const renderItem = (item: NavItem) => {
    const Icon = item.icon;
    const isActive = activeTab === item.id;
    return (
      <button
        key={item.id}
        onClick={() => onTabChange(item.id)}
        className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all duration-200 cursor-pointer ${
          isActive
            ? 'bg-white/10 text-white shadow-lg shadow-indigo-500/25'
            : 'text-indigo-300 hover:bg-white/5 hover:text-white'
        }`}
      >
        <Icon className="w-5 h-5 shrink-0" />
        <span className="font-medium text-sm">{t(item.labelKey)}</span>
      </button>
    );
  };

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
        <div className="mb-6 flex items-start justify-between gap-2">
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

        <nav className="space-y-5 flex-1 overflow-y-auto">
          {groups.map((group) => (
            <div key={group.labelKey}>
              <p className="px-4 mb-2 text-[10px] font-semibold uppercase tracking-wider text-indigo-400/80">
                {t(group.labelKey)}
              </p>
              <div className="space-y-1">{group.items.map(renderItem)}</div>
            </div>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-white/10">
          <LanguageSwitcher />
          <button
            onClick={handleLogout}
            className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-red-300 hover:bg-red-500/10 hover:text-red-200 transition-all duration-200 cursor-pointer"
          >
            <LogOut className="w-5 h-5" />
            <span className="font-medium">{t('nav.logout')}</span>
          </button>
          {isAdmin && (
            <p className="text-purple-400 text-xs text-center mt-2">{t('nav.adminAccount')}</p>
          )}
        </div>
      </aside>
    </>
  );
}
