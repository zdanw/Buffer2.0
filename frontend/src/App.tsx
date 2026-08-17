import { lazy, Suspense, useState, useEffect, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import BrandLogo from './components/BrandLogo';
import ApiConnectionBanner from './components/ApiConnectionBanner';
import BrandSelectorBar from './components/BrandSelectorBar';
import OnboardingWizard from './components/OnboardingWizard';
import OnboardingChecklist from './components/OnboardingChecklist';
import { useI18n } from './i18n/useI18n';
import { useOnboarding } from './hooks/useOnboarding';
import { BrandProvider, useBrandContext } from './context/BrandContext';
import { getCurrentUser, getToken } from './api/auth';
import type { UserResponse } from './api/auth';

const BrandManagement = lazy(() => import('./pages/BrandManagement'));
const AssetManagement = lazy(() => import('./pages/AssetManagement'));
const DimensionManagement = lazy(() => import('./pages/DimensionManagement'));
const TaskConfiguration = lazy(() => import('./pages/TaskConfiguration'));
const PendingRelease = lazy(() => import('./pages/PendingRelease'));
const Studio = lazy(() => import('./pages/Studio'));
const PublishCalendar = lazy(() => import('./pages/PublishCalendar'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const ImageProviderSettings = lazy(() => import('./pages/ImageProviderSettings'));
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
  users: '/users',
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
  '/users': 'users',
};

const LEGACY_REDIRECTS: Record<string, string> = {
  '/assets': '/products',
  '/dimensions': '/visual-styles',
  '/preview': '/studio',
  '/tasks': '/automations',
  '/pending': '/review',
};

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
  return <Navigate to="/products" replace />;
}

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { brands, loadError, refreshBrands, loading: brandsLoading } = useBrandContext();
  const { shouldShowOnboarding, skipOnboarding, markComplete } = useOnboarding();
  const initialTab = ROUTE_TABS[location.pathname] || 'products';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [mountedTabs, setMountedTabs] = useState(() => new Set<string>([initialTab]));
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    const fetchCurrentUser = async () => {
      try {
        const user = await getCurrentUser();
        setCurrentUser(user);
      } catch (err) {
        console.error('Failed to fetch current user:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchCurrentUser();
  }, []);

  useEffect(() => {
    const tab = ROUTE_TABS[location.pathname] || 'products';
    setActiveTab(tab);
    setMountedTabs((prev) => {
      if (prev.has(tab)) return prev;
      const next = new Set(prev);
      next.add(tab);
      return next;
    });
  }, [location.pathname]);

  const handleTabChange = (tab: string) => {
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

  if (loading) {
    return <AppShellFallback />;
  }

  const hasBrand = brands.some((b) => !b.is_generic);
  const hasProduct = brands.some((b) => b.product_count > 0);

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
        <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-canvas-border bg-canvas px-4 py-3 lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-gray-600 hover:bg-gray-200"
            aria-label={t('nav.openMenu')}
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            <BrandLogo size="sm" />
            {t('brand.name')}
          </span>
        </div>
        {loadError === 'connection' && (
          <ApiConnectionBanner onRetry={() => void refreshBrands()} loading={brandsLoading} />
        )}
        <BrandSelectorBar />
        <div className="flex-1 overflow-auto">
          {lazyPanel('brand', activeTab, mountedTabs, BrandManagement)}
          {lazyPanel('products', activeTab, mountedTabs, AssetManagement)}
          {lazyPanel('visual-styles', activeTab, mountedTabs, DimensionManagement, {
            isAdmin: currentUser?.is_admin || false,
          })}
          {lazyPanel('automations', activeTab, mountedTabs, TaskConfiguration)}
          {lazyPanel('review', activeTab, mountedTabs, PendingRelease)}
          {lazyPanel('studio', activeTab, mountedTabs, Studio)}
          {lazyPanel('calendar', activeTab, mountedTabs, PublishCalendar)}
          {currentUser?.is_admin
            ? lazyPanel('image-models', activeTab, mountedTabs, ImageProviderSettings)
            : null}
          {currentUser?.is_admin
            ? lazyPanel('users', activeTab, mountedTabs, UserManagement)
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
        hasGenerated={Boolean(currentUser?.onboarding_completed_at)}
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
    return <Navigate to="/products" replace />;
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
