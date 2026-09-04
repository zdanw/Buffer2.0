import { Calendar, Image, Settings, Clock, Users, Palette, Cpu, X, Layers, Package, PenLine, Share2, Bot, History } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';
import LanguageSwitcher from './LanguageSwitcher';
import BrandLogo from './BrandLogo';
import PostenceWordmark from './PostenceWordmark';

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

const settingsItems: NavItem[] = [
  { id: 'image-models', labelKey: 'nav.imageModels', icon: Cpu },
  { id: 'buffer-accounts', labelKey: 'nav.bufferAccounts', icon: Share2 },
];

const adminItems: NavItem[] = [
  { id: 'system-image', labelKey: 'nav.systemImage', icon: Cpu },
  { id: 'users', labelKey: 'nav.users', icon: Users },
  { id: 'generation-history', labelKey: 'nav.generationHistory', icon: History },
];

const devItems: NavItem[] = [
  { id: 'vision-playground', labelKey: 'nav.visionPlayground', icon: Bot },
];

export default function Sidebar({ activeTab, onTabChange, isAdmin, isOpen = false, onClose }: SidebarProps) {
  const { t } = useI18n();

  const groups: NavGroup[] = [
    { labelKey: 'nav.groups.content', items: contentItems },
    { labelKey: 'nav.groups.create', items: createItems },
    { labelKey: 'nav.groups.insights', items: insightsItems },
    { labelKey: 'nav.groups.settings', items: settingsItems },
  ];

  if (isAdmin) {
    groups.push({ labelKey: 'nav.groups.admin', items: adminItems });
  }

  if (import.meta.env.DEV) {
    groups.push({ labelKey: 'nav.groups.dev', items: devItems });
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
        className={`app-sidebar z-50 flex w-60 shrink-0 flex-col bg-ink-900 p-5 h-screen max-h-screen transition-transform duration-200 ease-out fixed inset-y-0 left-0 lg:sticky lg:top-0 lg:self-start lg:inset-auto ${
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="mb-8 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex items-start gap-2 min-w-0">
              <BrandLogo size="md" variant="filled" className="mt-0.5" />
              <div className="min-w-0">
                <PostenceWordmark size="lg" variant="inverse" />
                <p className="text-white/45 text-xs mt-1 leading-snug">{t('brand.tagline')}</p>
              </div>
            </div>
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

        <nav className="sidebar-nav-scroll space-y-6 flex-1 min-h-0">
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
          {isAdmin ? (
            <p className="text-white/30 text-xs text-center mt-3">{t('nav.adminAccount')}</p>
          ) : null}
        </div>
      </aside>
    </>
  );
}
