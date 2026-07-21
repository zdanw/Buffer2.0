import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import AssetManagement from './pages/AssetManagement';
import DimensionManagement from './pages/DimensionManagement';
import TaskConfiguration from './pages/TaskConfiguration';
import PendingRelease from './pages/PendingRelease';
import ContentPreview from './pages/ContentPreview';
import PublishCalendar from './pages/PublishCalendar';
import UserManagement from './pages/UserManagement';
import Login from './pages/Login';
import { getCurrentUser, getToken } from './api/auth';
import type { UserResponse } from './api/auth';

const TAB_ROUTES: Record<string, string> = {
  'assets': '/assets',
  'dimensions': '/dimensions',
  'tasks': '/tasks',
  'pending': '/pending',
  'preview': '/preview',
  'calendar': '/calendar',
  'users': '/users',
};

const ROUTE_TABS: Record<string, string> = {
  '/assets': 'assets',
  '/dimensions': 'dimensions',
  '/tasks': 'tasks',
  '/pending': 'pending',
  '/preview': 'preview',
  '/calendar': 'calendar',
  '/users': 'users',
};

function AppContent() {
  const location = useLocation();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('assets');
  const [currentUser, setCurrentUser] = useState<UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

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
    const path = location.pathname;
    const tab = ROUTE_TABS[path] || 'assets';
    setActiveTab(tab);
  }, [location.pathname]);

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    const route = TAB_ROUTES[tab];
    if (route) {
      navigate(route);
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'assets':
        return <AssetManagement />;
      case 'dimensions':
        return <DimensionManagement />;
      case 'tasks':
        return <TaskConfiguration />;
      case 'pending':
        return <PendingRelease />;
      case 'preview':
        return <ContentPreview />;
      case 'calendar':
        return <PublishCalendar />;
      case 'users':
        return <UserManagement />;
      default:
        return <AssetManagement />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        isAdmin={currentUser?.is_admin || false}
      />
      <main className="flex-1 overflow-auto">
        {renderContent()}
      </main>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
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
        <Route path="/login" element={<Login />} />
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
