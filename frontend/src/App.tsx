import { lazy, Suspense, useState, useEffect, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import BrandLogo from './components/BrandLogo';
import ApiConnectionBanner from './components/ApiConnectionBanner';
import BrandSelectorBar from './components/BrandSelectorBar';
import TopBarActions from './components/TopBarActions';
import OnboardingWizard from './components/OnboardingWizard';
import OnboardingChecklist from './components/OnboardingChecklist';
import { useI18n } from './i18n/useI18n';
import { useOnboarding } from './hooks/useOnboarding';
import { BrandProvider, useBrandContext } from './context/BrandContext';
import { getCurrentUser, getToken, claimOnboardingReward } from './api/auth';
import type { UserResponse } from './api/auth';
import { toast } from './lib/feedback';

const BrandManagement = lazy(() => import('./pages/BrandManagement'));
const AssetManagement = lazy(() => import('./pages/AssetManagement'));
const DimensionManagement = lazy(() => import('./pages/DimensionManagement'));
const TaskConfiguration = lazy(() => import('./pages/TaskConfiguration'));
const PendingRelease = lazy(() => import('./pages/PendingRelease'));
const Studio = lazy(() => import('./pages/Studio'));
const PublishCalendar = lazy(() => import('./pages/PublishCalendar'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const AccountSettings = lazy(() => import('./pages/AccountSettings'));
const ImageProviderSettings = lazy(() => import('./pages/ImageProviderSettings'));
const SystemImageProviderSettings = lazy(() => import('./pages/SystemImageProviderSettings'));
const BufferAccountSettings = lazy(() => import('./pages/BufferAccountSettings'));
const VisionModelPlayground = lazy(() => import('./pages/VisionModelPlayground'));
const Login = lazy(() => import('./pages/Login'));
const Signup = lazy(() => import('./pages/Signup'));
const Landing = lazy(() => import('./pages/Landing'));

const TAB_ROUTES: Record<string, string> = {
  brand: '/brand',
  products: '/products',
  'visual-styles': '/visual-styles',
  studio: '/studio',
  automations: '/automations',
  review: '/review',
  calendar: '/calendar',
  'image-models': '/image-models',
  'buffer-accounts': '/buffer-accounts',
  account: '/account',
  'system-image': '/system-image',
  users: '/users',
  ...(import.meta.env.DEV ? { 'vision-playground': '/vision-playground' } : {}),
};

const ROUTE_TABS: Record<string, string> = {
  '/brand': 'brand',
  '/products': 'products',
  '/assets': 'products',
  '/visual-styles': 'visual-styles',
  '/dimensions': 'visual-styles',
  '/studio': 'studio',
  '/preview': 'studio',
  '/automations': 'automations',
  '/tasks': 'automations',
  '/review': 'review',
  '/pending': 'review',
  '/calendar': 'calendar',
  '/image-models': 'image-models',
  '/buffer-accounts': 'buffer-accounts',
  '/account': 'account',
  '/system-image': 'system-image',
  '/users': 'users',
  ...(import.meta.env.DEV ? { '/vision-playground': 'vision-playground' } : {}),
};

const LEGACY_REDIRECTS: Record<string, string> = {
  '/assets': '/products',
  '/dimensions': '/visual-styles',
  '/preview': '/studio',
  '/tasks': '/automations',
  '/pending': '/review',
};

const ADMIN_TABS = new Set(['system-image', 'users']);

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-forge-600" />
    </div>
  );
}

function AppShellFallback() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-forge-600" />
    </div>
  );
}

function lazyPanel<P extends object = object>(
  id: string,
  activeTab: string,
  mountedTabs: Set<string>,
  Page: ComponentType<P>,
  pageProps?: P,
) {
  if (!mountedTabs.has(id)) return null;
  return (
    <div
      key={id}
      className={activeTab === id ? 'h-full' : 'hidden'}
      aria-hidden={activeTab !== id}
    >
      <Suspense fallback={<PageFallback />}>
        <Page {...(pageProps as P)} />
      </Suspense>
    </div>
  );
}

function LegacyRedirect() {
  const location = useLocation();
  const target = LEGACY_REDIRECTS[location.pathname];
  if (target) {
    return <Navigate to={{ pathname: target, search: location.search }} replace />;
  }
  return <Navigate to="/studio" replace />;
}

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { brands, loadError, refreshBrands, loading: brandsLoading } = useBrandContext();
  const { shouldShowOnboarding, skipOnboarding, markComplete } = useOnboarding();
  const initialTab = ROUTE_TABS[location.pathname] || 'studio';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [mountedTabs, setMountedTabs] = useState(() => new Set<string>([initialTab]));
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const refreshCurrentUser = async () => {
    try {
      const user = await getCurrentUser();
      setCurrentUser(user);
    } catch (err) {
      console.error('Failed to fetch current user:', err);
    }
  };

  useEffect(() => {
    const fetchCurrentUser = async () => {
      setLoading(true);
      try {
        await refreshCurrentUser();
      } finally {
        setLoading(false);
      }
    };
    void fetchCurrentUser();
  }, []);

  useEffect(() => {
    const handler = () => {
      void refreshCurrentUser();
    };
    window.addEventListener('pulseforge:refresh-user', handler);
    return () => window.removeEventListener('pulseforge:refresh-user', handler);
  }, []);

  useEffect(() => {
    const tab = ROUTE_TABS[location.pathname] || 'studio';
    if (ADMIN_TABS.has(tab) && !currentUser?.is_admin) {
      navigate({ pathname: '/studio', search: '' }, { replace: true });
      return;
    }
    setActiveTab(tab);
    setMountedTabs((prev) => {
      if (prev.has(tab)) return prev;
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  }, [location.pathname, currentUser?.is_admin, navigate]);

  const handleTabChange = (tab: string) => {
    if (ADMIN_TABS.has(tab) && !currentUser?.is_admin) {
      return;
    }
    setActiveTab(tab);
    setMountedTabs((prev) => {
      if (prev.has(tab)) return prev;
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
    const route = TAB_ROUTES[tab];
    if (route) {
      navigate({ pathname: route, search: '' });
    }
    setSidebarOpen(false);
  };

  const hasBrand = brands.some((b) => !b.is_generic);
  const hasProduct = brands.some((b) => b.product_count > 0);
  const hasGenerated = Boolean(currentUser?.has_generated_content);

  useEffect(() => {
    if (!currentUser || !hasBrand || !hasProduct || !hasGenerated) return;
    if (currentUser.onboarding_reward_claimed) return;

    void claimOnboardingReward()
      .then((res) => {
        if (res.granted > 0) {
          toast.success(t('onboarding.rewardGranted', { n: res.granted }));
        }
        return refreshCurrentUser();
      })
      .catch((err) => {
        console.error('Failed to claim onboarding reward:', err);
      });
  }, [currentUser, hasBrand, hasProduct, hasGenerated, t]);

  if (loading) {
    return <AppShellFallback />;
  }

  return (
    <div className="flex min-h-screen bg-canvas">
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isAdmin={currentUser?.is_admin || false}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="flex-1 min-w-0 flex flex-col min-h-screen">
        <div className="sticky top-0 z-30 border-b border-canvas-border bg-white">
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 lg:px-6">
            <div className="flex min-w-0 items-center gap-3 lg:hidden">
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                className="rounded-lg p-2 text-gray-600 hover:bg-gray-100"
                aria-label={t('nav.openMenu')}
              >
                <Menu className="h-5 w-5" />
              </button>
              <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-gray-900">
                <BrandLogo size="sm" />
                {t('brand.name')}
              </span>
            </div>
            <div className="hidden lg:block flex-1" aria-hidden />
            <TopBarActions />
          </div>
          <BrandSelectorBar />
        </div>
        {loadError === 'connection' && (
          <ApiConnectionBanner onRetry={() => void refreshBrands()} loading={brandsLoading} />
        )}
        <div className="flex-1 overflow-auto">
          {lazyPanel('brand', activeTab, mountedTabs, BrandManagement)}
          {lazyPanel('products', activeTab, mountedTabs, AssetManagement)}
          {lazyPanel('visual-styles', activeTab, mountedTabs, DimensionManagement, {
            isAdmin: currentUser?.is_admin || false,
          })}
          {lazyPanel('automations', activeTab, mountedTabs, TaskConfiguration)}
          {lazyPanel('review', activeTab, mountedTabs, PendingRelease)}
          {lazyPanel('studio', activeTab, mountedTabs, Studio, {
            isPageActive: activeTab === 'studio',
          })}
          {lazyPanel('calendar', activeTab, mountedTabs, PublishCalendar)}
          {lazyPanel('image-models', activeTab, mountedTabs, ImageProviderSettings)}
          {lazyPanel('buffer-accounts', activeTab, mountedTabs, BufferAccountSettings)}
          {lazyPanel('account', activeTab, mountedTabs, AccountSettings)}
          {currentUser?.is_admin
            ? lazyPanel('system-image', activeTab, mountedTabs, SystemImageProviderSettings)
            : null}
          {currentUser?.is_admin
            ? lazyPanel('users', activeTab, mountedTabs, UserManagement)
            : null}
          {import.meta.env.DEV
            ? lazyPanel('vision-playground', activeTab, mountedTabs, VisionModelPlayground)
            : null}
        </div>
      </main>

      {shouldShowOnboarding && (
        <OnboardingWizard
          onSkip={skipOnboarding}
          onComplete={markComplete}
          onGoStudio={() => {
            void markComplete();
            handleTabChange('studio');
          }}
        />
      )}

      <OnboardingChecklist
        hasBrand={hasBrand}
        hasProduct={hasProduct}
        hasGenerated={hasGenerated}
        onNavigate={handleTabChange}
      />
    </div>
  );
}

function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = getToken();
  if (!token) {
    return <Navigate to="/login" />;
  }
  return <>{children}</>;
}

function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const token = getToken();
  if (token) {
    return <Navigate to="/studio" replace />;
  }
  return <>{children}</>;
}

function App() {
  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={
            <Suspense fallback={<AppShellFallback />}>
              <Landing />
            </Suspense>
          }
        />
        <Route
          path="/login"
          element={
            <PublicOnlyRoute>
              <Suspense fallback={<AppShellFallback />}>
                <Login />
              </Suspense>
            </PublicOnlyRoute>
          }
        />
        <Route
          path="/signup"
          element={
            <PublicOnlyRoute>
              <Suspense fallback={<AppShellFallback />}>
                <Signup />
              </Suspense>
            </PublicOnlyRoute>
          }
        />
        {Object.entries(LEGACY_REDIRECTS).map(([from]) => (
          <Route key={from} path={from} element={<LegacyRedirect />} />
        ))}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <BrandProvider>
                <AppContent />
              </BrandProvider>
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
