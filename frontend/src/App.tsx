import { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import AssetManagement from './pages/AssetManagement';
import TaskConfiguration from './pages/TaskConfiguration';
import PendingRelease from './pages/PendingRelease';
import ContentPreview from './pages/ContentPreview';
import PublishCalendar from './pages/PublishCalendar';
import UserManagement from './pages/UserManagement';
import Login from './pages/Login';
import { getCurrentUser, getToken } from './api/auth';
import type { UserResponse } from './api/auth';
import './App.css';

function AppContent() {
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

  const renderContent = () => {
    switch (activeTab) {
      case 'assets':
        return <AssetManagement />;
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
        onTabChange={setActiveTab}
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
