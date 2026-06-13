import { Layout, Calendar, Image, Settings, Sparkles } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const menuItems = [
  { id: 'assets', label: '素材管理', icon: Image },
  { id: 'tasks', label: '任务配置', icon: Settings },
  { id: 'preview', label: '内容预览', icon: Sparkles },
  { id: 'calendar', label: '发布日历', icon: Calendar },
];

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-64 bg-gradient-to-b from-indigo-900 to-purple-900 min-h-screen p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Layout className="w-8 h-8 text-indigo-400" />
          Bebcare AI
        </h1>
        <p className="text-indigo-300 text-sm mt-1">全自动社媒内容生成系统</p>
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
              <span className="font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>
      
      <div className="mt-auto pt-8 border-t border-white/10">
        <p className="text-indigo-400 text-xs text-center">Version 2.0</p>
      </div>
    </aside>
  );
}