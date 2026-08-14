import { lazy, Suspense, useState, useEffect, type ComponentType, type ReactNode } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import { useI18n } from './i18n/useI18n';
import { getCurrentUser, getToken } from './api/auth';
import type { UserResponse } from './api/auth';

const AssetManagement = lazy(() => import('./pages/AssetManagement'));
const DimensionManagement = lazy(() => import('./pages/DimensionManagement'));
const TaskConfiguration = lazy(() => import('./pages/TaskConfiguration'));
const PendingRelease = lazy(() => import('./pages/PendingRelease'));
const ContentPreview = lazy(() => import('./pages/ContentPreview'));
const PublishCalendar = lazy(() => import('./pages/PublishCalendar'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const ImageProviderSettings = lazy(() => import('./pages/ImageProviderSettings'));
const Login = lazy(() => import('./pages/Login'));

const TAB_ROUTES: Record<string, string> = {
  'assets': '/assets',
  'dimensions': '/dimensions',
  'tasks': '/tasks',
  'pending': '/pending',
  'preview': '/preview',
  'calendar': '/calendar',
  'image-models': '/image-models',
  'users': '/users',
};

const ROUTE_TABS: Record<string, string> = {
  '/assets': 'assets',
  '/dimensions': 'dimensions',
  '/tasks': 'tasks',
  '/pending': 'pending',
  '/preview': 'preview',
  '/calendar': 'calendar',
  '/image-models': 'image-models',
  '/users': 'users',
};

function PageFallback() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
    </div>
  );
}

function AppShellFallback() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600" />
    </div>
  );
}

function lazyPanel(id: string, activeTab: string, mountedTabs: Set<string>, Page: ComponentType) {
  if (!mountedTabs.has(id)) return null;
  return (
    <div
      key={id}
      className={activeTab === id ? 'h-full' : 'hidden'}
      aria-hidden={activeTab !== id}
    >
      <Suspense fallback={<PageFallback />}>
        <Page />
      </Suspense>
    </div>
  );
}

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useI18n();
  const initialTab = ROUTE_TABS[location.pathname] || 'assets';
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
    const tab = ROUTE_TABS[location.pathname] || 'assets';
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
      // 清空查询串，避免内容预览页保活时把 ?product_id=&platform= 写到其他页
      navigate({ pathname: route, search: '' });
    }
    setSidebarOpen(false);
  };

  if (loading) {
    return <AppShellFallback />;
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isAdmin={currentUser?.is_admin || false}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-gray-200 bg-gray-50 px-4 py-3 lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-2 text-gray-600 hover:bg-gray-200"
            aria-label={t('nav.openMenu')}
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-sm font-semibold text-gray-900">{t('brand.name')}</span>
        </div>
        {lazyPanel('assets', activeTab, mountedTabs, AssetManagement)}
        {lazyPanel('dimensions', activeTab, mountedTabs, DimensionManagement)}
        {lazyPanel('tasks', activeTab, mountedTabs, TaskConfiguration)}
        {lazyPanel('pending', activeTab, mountedTabs, PendingRelease)}
        {lazyPanel('preview', activeTab, mountedTabs, ContentPreview)}
        {lazyPanel('calendar', activeTab, mountedTabs, PublishCalendar)}
        {currentUser?.is_admin
          ? lazyPanel('image-models', activeTab, mountedTabs, ImageProviderSettings)
          : null}
        {currentUser?.is_admin
          ? lazyPanel('users', activeTab, mountedTabs, UserManagement)
          : null}
      </main>
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

function App() {
  return (
    <Router>
      <Routes>
        <Route
          path="/login"
          element={
            <Suspense fallback={<AppShellFallback />}>
              <Login />
            </Suspense>
          }
        />
        <Route path="/" element={<Navigate to="/assets" />} />
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AppContent />
            </ProtectedRoute>
          }
        />
      </Routes>
    </Router>
  );
}

export default App;
