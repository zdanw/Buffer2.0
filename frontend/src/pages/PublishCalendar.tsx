import { useState, useEffect } from 'react';
import { Calendar, ChevronLeft, ChevronRight, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import type { ScheduledTask } from '@/api/tasks';
import { getTasks } from '@/api/tasks';

interface CalendarEvent {
  id: string;
  title: string;
  time: string;
  status: 'pending' | 'completed' | 'failed';
  platforms: string[];
}

export default function PublishCalendar() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);

  useEffect(() => {
    loadTasks();
  }, []);

  useEffect(() => {
    generateEvents();
  }, [tasks]);

  const loadTasks = async () => {
    try {
      const data = await getTasks();
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    }
  };

  const generateEvents = () => {
    const events: CalendarEvent[] = [];
    
    tasks.forEach((task) => {
      if (task.enabled) {
        const cronParts = task.cron.split(' ');
        const hour = cronParts[1];
        const minute = cronParts[0];
        
        events.push({
          id: task.task_id,
          title: task.name,
          time: `${hour}:${minute.padStart(2, '0')}`,
          status: 'pending',
          platforms: task.platforms,
        });
      }
    });
    
    setCalendarEvents(events);
  };

  const getDaysInMonth = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const lastDay = new Date(year, month + 1, 0);
    const days = [];
    
    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push(i);
    }
    
    return days;
  };

  const getFirstDayOffset = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDay = new Date(year, month, 1);
    return firstDay.getDay();
  };

  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1));
  };

  const formatMonth = () => {
    return currentDate.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">发布日历</h2>
          <p className="text-gray-500 mt-1">查看和管理发布计划</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="col-span-2">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <button
                onClick={prevMonth}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ChevronLeft className="w-6 h-6 text-gray-600" />
              </button>
              <h3 className="text-xl font-semibold text-gray-800">
                {formatMonth()}
              </h3>
              <button
                onClick={nextMonth}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ChevronRight className="w-6 h-6 text-gray-600" />
              </button>
            </div>

            <div className="grid grid-cols-7 gap-1 mb-2">
              {['日', '一', '二', '三', '四', '五', '六'].map((day) => (
                <div key={day} className="text-center text-sm font-medium text-gray-500 py-2">
                  {day}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-1">
              {Array.from({ length: getFirstDayOffset() }).map((_, i) => (
                <div key={`empty-${i}`} className="aspect-square bg-gray-50 rounded-lg" />
              ))}
              {getDaysInMonth().map((day) => (
                <div
                  key={day}
                  className="aspect-square bg-gray-50 rounded-lg p-2 hover:bg-gray-100 transition-colors cursor-pointer"
                >
                  <span className="text-sm font-medium text-gray-800">{day}</span>
                  <div className="mt-1 space-y-1">
                    {calendarEvents.slice(0, 2).map((event) => (
                      <div
                        key={event.id}
                        className="flex items-center gap-1 text-xs bg-white rounded px-1 py-0.5 border border-gray-200"
                      >
                        {getStatusIcon(event.status)}
                        <span className="truncate max-w-[80px]">{event.title}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="col-span-1">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h3 className="font-semibold text-gray-800 mb-4">即将发布</h3>
            <div className="space-y-3">
              {calendarEvents.length > 0 ? (
                calendarEvents.map((event) => (
                  <div
                    key={event.id}
                    className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {getStatusIcon(event.status)}
                      <span className="font-medium text-gray-800 text-sm">{event.title}</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <Calendar className="w-3 h-3" />
                      <span>每日 {event.time}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {event.platforms.map((platform) => (
                        <span
                          key={platform}
                          className="px-2 py-0.5 bg-indigo-100 text-indigo-700 rounded text-xs"
                        >
                          {platform}
                        </span>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-400">
                  <Calendar className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p className="text-sm">暂无发布计划</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}