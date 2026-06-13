import { useState } from 'react';
import Sidebar from './components/Sidebar';
import AssetManagement from './pages/AssetManagement';
import TaskConfiguration from './pages/TaskConfiguration';
import ContentPreview from './pages/ContentPreview';
import PublishCalendar from './pages/PublishCalendar';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('assets');

  const renderContent = () => {
    switch (activeTab) {
      case 'assets':
        return <AssetManagement />;
      case 'tasks':
        return <TaskConfiguration />;
      case 'preview':
        return <ContentPreview />;
      case 'calendar':
        return <PublishCalendar />;
      default:
        return <AssetManagement />;
    }
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="flex-1 overflow-auto">
        {renderContent()}
      </main>
    </div>
  );
}

export default App;
