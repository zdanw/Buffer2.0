import { Calendar, Image, Settings, Clock, LogOut, Users, Palette, Cpu, X, Layers, Package, PenLine, Share2 } from 'lucide-react';
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
  { id: 'studio', labelKey: 'nav.studio', icon: PenLine },
  { id: 'automations', labelKey: 'nav.automations', icon: Settings },
  { id: 'review', labelKey: 'nav.review', icon: Clock },
];

const insightsItems: NavItem[] = [
  { id: 'calendar', labelKey: 'nav.calendar', icon: Calendar },
];

const adminItems: NavItem[] = [
  { id: 'image-models', labelKey: 'nav.imageModels', icon: Cpu },
  { id: 'buffer-accounts', labelKey: 'nav.bufferAccounts', icon: Share2 },
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
        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-150 cursor-pointer ${
          isActive
            ? 'bg-white/10 text-white border-l-2 border-forge-500 pl-[10px]'
            : 'text-white/60 hover:bg-white/5 hover:text-white border-l-2 border-transparent pl-3'
        }`}
      >
        <Icon className="w-[18px] h-[18px] shrink-0" strokeWidth={1.75} />
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
        className={`app-sidebar z-50 flex w-60 shrink-0 flex-col bg-ink-900 p-5 transition-transform duration-200 ease-out fixed inset-y-0 left-0 lg:relative lg:min-h-screen lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="mb-8 flex items-start justify-between gap-2">
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2.5 tracking-tight">
              <BrandLogo size="md" className="bg-white/10 shadow-none ring-1 ring-white/10" />
              {t('brand.name')}
            </h1>
            <p className="text-white/45 text-xs mt-1.5 leading-snug">{t('brand.tagline')}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-white/50 hover:bg-white/10 hover:text-white lg:hidden"
            aria-label={t('nav.closeMenu')}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="space-y-6 flex-1 overflow-y-auto">
          {groups.map((group) => (
            <div key={group.labelKey}>
              <p className="px-3 mb-2 text-[11px] font-medium text-white/35">
                {t(group.labelKey)}
              </p>
              <div className="space-y-0.5">{group.items.map(renderItem)}</div>
            </div>
          ))}
        </nav>

        <div className="mt-auto pt-5 border-t border-white/10">
          <LanguageSwitcher />
          <button
            onClick={handleLogout}
            className="mt-3 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-white/50 hover:bg-white/5 hover:text-white/80 transition-colors duration-150 cursor-pointer text-sm"
          >
            <LogOut className="w-4 h-4" />
            <span className="font-medium">{t('nav.logout')}</span>
          </button>
          {isAdmin && (
            <p className="text-white/30 text-xs text-center mt-2">{t('nav.adminAccount')}</p>
          )}
        </div>
      </aside>
    </>
  );
}
