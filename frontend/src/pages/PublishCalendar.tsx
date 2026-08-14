import { useState, useEffect, useMemo, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { Calendar, ChevronLeft, ChevronRight, CheckCircle, Clock, AlertCircle, RefreshCw, X, Image, FileText, Zap, ZoomIn } from 'lucide-react';
import type { ScheduledTask, TaskExecution } from '@/api/tasks';
import { getTasks, getAllExecutions } from '@/api/tasks';
import { getProducts } from '@/api/products';
import { useBrandContext } from '@/context/BrandContext';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import { formatServerDateTime, parseServerDate } from '@/lib/datetime';
import ReferenceImagesDisplay from '@/components/ReferenceImagesDisplay';
import { useI18n } from '@/i18n/useI18n';
import { localeToIntl } from '@/i18n/localeUtils';

const DIMENSION_FIELD_KEYS: Record<string, string> = {
  scene: 'scenes',
  lighting: 'lighting',
  style: 'styles',
  composition: 'compositions',
  details: 'details',
  quality: 'quality',
  viewpoint: 'viewpoints',
};
const DIMENSION_FIELDS = ['scene', 'lighting', 'style', 'composition', 'details', 'quality', 'viewpoint'] as const;
const CALENDAR_WEEKDAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const;

interface CalendarEvent {
  id: string;
  taskId: string;
  title: string;
  time: string;
  status: 'pending' | 'completed' | 'failed' | 'running';
  platforms: string[];
  mode: string;
  day: number;
  month: number;
  year: number;
}

interface DayDetail {
  date: Date;
  executions: TaskExecution[];
  tasks: ScheduledTask[];
}

interface GroupedEvents {
  date: Date;
  dateLabel: string;
  weekday: string;
  events: CalendarEvent[];
}

export default function PublishCalendar() {
  const location = useLocation();
  const { t, locale } = useI18n();
  const { activeBrandId } = useBrandContext();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [executions, setExecutions] = useState<Map<string, TaskExecution[]>>(new Map());
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [selectedDay, setSelectedDay] = useState<DayDetail | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [brandProductIds, setBrandProductIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    void (async () => {
      if (!activeBrandId) {
        setBrandProductIds(new Set());
        return;
      }
      try {
        const res = await getProducts(1, 200, activeBrandId);
        setBrandProductIds(new Set(res.data.map((p) => p.product_id)));
      } catch (error) {
        console.error('Failed to load brand products for calendar:', error);
      }
    })();
  }, [activeBrandId]);

  const taskMatchesBrand = useCallback(
    (task: ScheduledTask) => {
      if (!activeBrandId) return true;
      const targets = task.target_products || [];
      if (targets.length === 0) return true;
      return targets.some((id) => brandProductIds.has(id));
    },
    [activeBrandId, brandProductIds]
  );

  const loadTasks = useCallback(async (force = false) => {
    if (force) setRefreshing(true);
    else setLoading(true);
    try {
      if (force) invalidateCache('tasks');

      const taskPromise = force
        ? getTasks(1, 100).then((r) => r.data)
        : cachedFetch('tasks:list:100', async () => {
            const response = await getTasks(1, 100);
            return response.data;
          });

      const [taskResult, exeResult] = await Promise.allSettled([
        taskPromise,
        getAllExecutions(),
      ]);

      if (taskResult.status === 'fulfilled') {
        setTasks(taskResult.value);
      } else {
        console.error('Failed to load tasks:', taskResult.reason);
      }

      if (exeResult.status === 'fulfilled') {
        const newExecutions = new Map<string, TaskExecution[]>();
        for (const ex of exeResult.value) {
          if (!newExecutions.has(ex.task_id)) {
            newExecutions.set(ex.task_id, []);
          }
          newExecutions.get(ex.task_id)!.push(ex);
        }
        setExecutions(newExecutions);
      } else {
        console.error('Failed to load executions:', exeResult.reason);
      }
    } catch (error) {
      console.error('Failed to load calendar data:', error);
    } finally {
      if (force) setRefreshing(false);
      else setLoading(false);
    }
  }, []);

  // 页面保活：切回日历时重新拉取，避免任务配置后仍显示空日历
  useEffect(() => {
    if (location.pathname === '/calendar') {
      loadTasks();
    }
  }, [location.pathname, loadTasks]);

  useEffect(() => {
    generateEvents();
  }, [tasks, executions, currentDate, activeBrandId, brandProductIds]);

  /** 按「年月日」预索引当日执行记录，避免每个格子重复扫描 */
  const executionsByDay = useMemo(() => {
    const map = new Map<string, TaskExecution[]>();
    executions.forEach((taskExes) => {
      for (const ex of taskExes) {
        const d = parseServerDate(ex.created_at);
        if (!d) continue;
        const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
        if (!map.has(key)) map.set(key, []);
        map.get(key)!.push(ex);
      }
    });
    for (const list of map.values()) {
      list.sort((a, b) => {
        const ta = parseServerDate(a.created_at)?.getTime() ?? 0;
        const tb = parseServerDate(b.created_at)?.getTime() ?? 0;
        return tb - ta;
      });
    }
    return map;
  }, [executions]);

  const getEventStatus = (taskId: string, day: number, month: number, year: number): 'pending' | 'completed' | 'failed' | 'running' => {
    const dayExes = executionsByDay.get(`${year}-${month}-${day}`) || [];
    const dayExecutions = dayExes.filter((ex) => ex.task_id === taskId);
    
    if (dayExecutions.length === 0) {
      return 'pending';
    }
    
    const latestExecution = dayExecutions[0];
    switch (latestExecution.status) {
      case 'SUCCESS':
        return 'completed';
      case 'FAILED':
        return 'failed';
      case 'RUNNING':
        return 'running';
      default:
        return 'pending';
    }
  };

  const getDayExecutions = (day: number, month: number, year: number): TaskExecution[] => {
    return executionsByDay.get(`${year}-${month}-${day}`) || [];
  };

  const handleDayClick = (day: number) => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const dayExecutions = getDayExecutions(day, month, year);
    
    const dayTasks = calendarEvents.filter(e => e.day === day).map(e => {
      return tasks.find(t => t.task_id === e.taskId);
    }).filter(Boolean) as ScheduledTask[];
    
    setSelectedDay({
      date: new Date(year, month, day),
      executions: dayExecutions,
      tasks: dayTasks,
    });
  };

  const generateEvents = () => {
    const events: CalendarEvent[] = [];
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const now = new Date();
    
    tasks.forEach((task) => {
      if (task.enabled && taskMatchesBrand(task)) {
        const cronParts = task.cron.trim().split(/\s+/);
        if (cronParts.length < 5) return;
        const minute = parseInt(cronParts[0], 10);
        const hour = parseInt(cronParts[1], 10);
        const day = cronParts[2];
        const monthField = cronParts[3];
        const weekday = cronParts[4];
        if (Number.isNaN(minute) || Number.isNaN(hour)) return;
        
        for (let d = 1; d <= daysInMonth; d++) {
          const date = new Date(year, month, d);
          const isDayMatch = day === '*' || parseInt(day, 10) === d;
          const isMonthMatch = monthField === '*' || parseInt(monthField, 10) === month + 1;
          const isWeekdayMatch = weekday === '*' || parseInt(weekday, 10) === date.getDay();
          if (!isDayMatch || !isMonthMatch || !isWeekdayMatch) continue;

          // 日历与「即将发布」均只展示未到点的排期；已过点只保留执行记录标记
          const eventTime = new Date(year, month, d, hour, minute, 0, 0);
          if (eventTime.getTime() < now.getTime()) continue;
            
          const status = getEventStatus(task.task_id, d, month, year);
          
          events.push({
            id: `${task.task_id}-${d}`,
            taskId: task.task_id,
            title: task.name,
            time: `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`,
            status: status,
            platforms: task.platforms || [],
            mode: task.mode || 'auto',
            day: d,
            month: month,
            year: year,
          });
        }
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
    return currentDate.toLocaleDateString(localeToIntl(locale), { year: 'numeric', month: 'long' });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'running':
        return <Clock className="w-4 h-4 text-blue-500 animate-pulse" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getExecutionStatusIcon = (status: string) => {
    switch (status) {
      case 'SUCCESS':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'FAILED':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'RUNNING':
        return <Clock className="w-5 h-5 text-blue-500 animate-pulse" />;
      default:
        return <Clock className="w-5 h-5 text-gray-400" />;
    }
  };

  const isEventUpcoming = (event: CalendarEvent, now = new Date()) => {
    const [h, m] = event.time.split(':').map(Number);
    const eventTime = new Date(event.year, event.month, event.day, h || 0, m || 0, 0, 0);
    return eventTime.getTime() >= now.getTime();
  };

  const getGroupedEvents = (): GroupedEvents[] => {
    const now = new Date();
    // 二次过滤：页面长时间打开时 generateEvents 不会自动重跑
    const upcoming = calendarEvents
      .filter((e) => isEventUpcoming(e, now))
      .sort((a, b) => {
        const dateA = new Date(a.year, a.month, a.day);
        const dateB = new Date(b.year, b.month, b.day);
        if (dateA.getTime() !== dateB.getTime()) return dateA.getTime() - dateB.getTime();
        return a.time.localeCompare(b.time);
      });

    const grouped: Record<string, GroupedEvents> = {};
    
    upcoming.forEach(event => {
      const dateKey = `${event.year}-${event.month}-${event.day}`;
      if (!grouped[dateKey]) {
        const date = new Date(event.year, event.month, event.day);
        grouped[dateKey] = {
          date: date,
          dateLabel: t('calendar.monthDay', { month: event.month + 1, day: event.day }),
          weekday: t(`calendar.weekdayLong.${CALENDAR_WEEKDAYS[date.getDay()]}`),
          events: [],
        };
      }
      grouped[dateKey].events.push(event);
    });
    
    return Object.values(grouped);
  };

  const getModeBadge = (mode: string) => {
    if (mode === 'manual') {
      return (
        <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs font-medium">
          <Zap className="w-3 h-3" />
          {t('calendar.manual')}
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
        <Clock className="w-3 h-3" />
        {t('calendar.auto')}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <span className="w-2 h-2 bg-green-500 rounded-full" />;
      case 'failed':
        return <span className="w-2 h-2 bg-red-500 rounded-full" />;
      case 'running':
        return <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />;
      default:
        return <span className="w-2 h-2 bg-gray-400 rounded-full" />;
    }
  };

  const groupedEvents = getGroupedEvents();

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t('calendar.title')}</h2>
          <p className="text-gray-500 mt-1">{t('calendar.subtitle')}</p>
        </div>
        <button
          onClick={() => loadTasks(true)}
          disabled={refreshing || loading}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing || loading ? 'animate-spin' : ''}`} />
          {t('common.refresh')}
        </button>
      </div>

      <div className={`grid grid-cols-3 gap-6 ${loading || refreshing ? 'opacity-70 pointer-events-none' : ''}`}>
        <div className="col-span-2">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 relative">
            {(loading || refreshing) && (
              <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-10 rounded-xl">
                <RefreshCw className="w-6 h-6 animate-spin text-indigo-600" />
              </div>
            )}
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
              {CALENDAR_WEEKDAYS.map((day) => (
                <div key={day} className="text-center text-sm font-medium text-gray-500 py-2">
                  {t(`calendar.weekdays.${day}`)}
                </div>
              ))}
            </div>

            <div className="grid grid-cols-7 gap-1">
              {Array.from({ length: getFirstDayOffset() }).map((_, i) => (
                <div key={`empty-${i}`} className="aspect-square bg-gray-50 rounded-lg" />
              ))}
              {getDaysInMonth().map((day) => {
                const dayEvents = calendarEvents.filter(e => e.day === day && isEventUpcoming(e));
                const dayExecutions = getDayExecutions(day, currentDate.getMonth(), currentDate.getFullYear());
                const hasExecutions = dayExecutions.length > 0;
                
                return (
                  <div
                    key={day}
                    onClick={() => handleDayClick(day)}
                    className={`aspect-square bg-gray-50 rounded-lg p-2 hover:bg-gray-100 transition-colors cursor-pointer ${hasExecutions ? 'ring-2 ring-indigo-400' : ''}`}
                  >
                    <span className="text-sm font-medium text-gray-800">{day}</span>
                    <div className="mt-1 space-y-1">
                      {dayEvents.slice(0, 2).map((event) => (
                        <div
                          key={event.id}
                          className="flex items-center gap-1 text-xs bg-white rounded px-1 py-0.5 border border-gray-200"
                        >
                          {getStatusIcon(event.status)}
                          <span className="truncate max-w-[80px]">{event.title}</span>
                        </div>
                      ))}
                      {hasExecutions && dayEvents.length === 0 && (
                        <div className="flex items-center gap-1 text-xs bg-green-50 rounded px-1 py-0.5 border border-green-200">
                          <CheckCircle className="w-3 h-3 text-green-500" />
                          <span className="truncate max-w-[80px]">{t('calendar.published')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="col-span-1">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">{t('calendar.upcoming')}</h3>
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
                {t('calendar.tasksCount', { count: groupedEvents.reduce((n, g) => n + g.events.length, 0) })}
              </span>
            </div>
            
            {groupedEvents.length > 0 ? (
              <div className="space-y-4 max-h-[600px] overflow-y-auto">
                {groupedEvents.map((group) => (
                  <div key={group.dateLabel} className="border border-gray-100 rounded-lg overflow-hidden">
                    <div className="bg-gradient-to-r from-indigo-50 to-blue-50 px-3 py-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-indigo-800 text-sm">{group.dateLabel}</span>
                          <span className="text-xs text-indigo-600 ml-2">{group.weekday}</span>
                        </div>
                        <span className="text-xs text-indigo-500 bg-white px-2 py-0.5 rounded-full">
                          {t('calendar.tasksCount', { count: group.events.length })}
                        </span>
                      </div>
                    </div>
                    
                    <div className="divide-y divide-gray-50">
                      {group.events.map((event) => (
                        <div
                          key={event.id}
                          className="p-3 hover:bg-gray-50 transition-colors cursor-pointer"
                          onClick={() => handleDayClick(event.day)}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              {getStatusBadge(event.status)}
                              <span className="font-medium text-gray-800 text-sm">{event.title}</span>
                            </div>
                            {getModeBadge(event.mode)}
                          </div>
                          
                          <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {event.time}
                            </span>
                          </div>
                          
                          <div className="flex flex-wrap gap-1">
                            {event.platforms.map((platform) => (
                              <span
                                key={platform}
                                className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium"
                              >
                                {platform}
                              </span>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <Calendar className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p className="text-gray-500 text-sm">{t('calendar.noSchedule')}</p>
                <p className="text-gray-400 text-xs mt-1">{t('calendar.createTaskHint')}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedDay && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setSelectedDay(null)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-semibold text-gray-800">
                {selectedDay.date.toLocaleDateString(localeToIntl(locale), {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  weekday: 'long',
                })}
              </h3>
              <button onClick={() => setSelectedDay(null)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {selectedDay.executions.length > 0 ? (
              <div className="space-y-6">
                {selectedDay.executions.map((execution) => {
                  const task = tasks.find(t => t.task_id === execution.task_id);
                  return (
                    <div key={execution.execution_id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center gap-3 mb-4">
                        {getExecutionStatusIcon(execution.status)}
                        <div>
                          <div className="font-medium text-gray-800">
                            {task?.name || t('calendar.unknownTask')}
                          </div>
                          <div className="text-sm text-gray-500">
                            {formatServerDateTime(execution.created_at, locale, t('datetime.unknown'), {
                              year: 'numeric',
                              month: 'numeric',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </div>
                        </div>
                      </div>

                      {execution.copywriting && (
                        <div className="mb-4">
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                            <FileText className="w-4 h-4" />
                            {t('fields.copyContent')}
                          </div>
                          <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 whitespace-pre-wrap">
                            {execution.copywriting}
                          </div>
                        </div>
                      )}

                      {((execution.generated_images || []).length > 0) && (
                        <div>
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                            <Image className="w-4 h-4" />
                            {t('calendar.publishImages')}
                          </div>
                          <div className="grid grid-cols-2 gap-3">
                            {(execution.generated_images || []).map((img, index) => (
                              <button
                                key={index}
                                type="button"
                                onClick={() => setPreviewImage(img)}
                                className="relative group w-full rounded-lg overflow-hidden focus:outline-none focus:ring-2 focus:ring-indigo-400"
                              >
                                <img
                                  src={img}
                                  alt={t('calendar.generatedAlt', { n: index + 1 })}
                                  className="w-full h-40 object-cover"
                                />
                                <span className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                                  <ZoomIn className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      <ReferenceImagesDisplay
                        className="mt-4"
                        productImages={execution.reference_product_images}
                        sceneImages={execution.reference_scene_images}
                        onPreview={setPreviewImage}
                      />

                      {((execution.published_platforms || []).length > 0) && (
                        <div className="mt-4">
                          <div className="text-sm text-gray-500 mb-2">{t('fields.publishPlatformsLabel')}</div>
                          <div className="flex flex-wrap gap-2">
                            {(execution.published_platforms || []).map((platform) => (
                              <span
                                key={platform}
                                className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm"
                              >
                                {platform}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {(execution.dimensions || execution.image_prompt) && (
                        <div className="mt-4 border border-gray-200 rounded-lg p-4 bg-gray-50/50">
                          {execution.dimensions && (
                            <>
                              <h4 className="text-sm font-semibold text-gray-700 mb-3">{t('fields.dimensionInfo')}</h4>
                              <div className="grid grid-cols-2 gap-2">
                                {DIMENSION_FIELDS.map((field) => {
                                  const value = execution.dimensions![field];
                                  if (!value) return null;
                                  return (
                                    <div key={field} className="flex items-start gap-2">
                                      <span className="text-xs text-gray-500 w-12 shrink-0">
                                        {t(`dimensionTypes.${DIMENSION_FIELD_KEYS[field]}`)}
                                      </span>
                                      <span className="text-xs text-gray-800">{value}</span>
                                    </div>
                                  );
                                })}
                              </div>
                            </>
                          )}
                          {execution.image_prompt && (
                            <div className={execution.dimensions ? 'mt-3' : ''}>
                              <h4 className="text-xs font-medium text-gray-600 mb-2">{t('fields.imagePrompt')}</h4>
                              <div className="text-xs text-gray-700 bg-white p-3 rounded-lg max-h-40 overflow-y-auto whitespace-pre-wrap border border-gray-100">
                                {execution.image_prompt}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {execution.error_message && (
                        <div className="mt-4 p-3 bg-red-50 rounded-lg text-sm text-red-600">
                          {t('calendar.errorInfo', { message: execution.error_message })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : selectedDay.tasks.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm text-gray-500 mb-2">{t('calendar.scheduledNoExecution')}</p>
                {selectedDay.tasks.map((task) => (
                  <div key={task.task_id} className="border border-gray-200 rounded-lg p-4">
                    <div className="font-medium text-gray-800">{task.name}</div>
                    <div className="text-sm text-gray-500 mt-1">
                      {task.mode === 'manual' ? t('calendar.manualDesc') : t('calendar.autoDesc')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12">
                <Calendar className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <p className="text-gray-500">{t('calendar.noRecordsToday')}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {previewImage && (
        <div
          className="fixed inset-0 bg-black/80 flex items-center justify-center z-[60]"
          onClick={() => setPreviewImage(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] p-4">
            <button
              type="button"
              onClick={() => setPreviewImage(null)}
              className="absolute top-2 right-2 text-white hover:text-gray-300 z-10"
            >
              <X className="w-8 h-8" />
            </button>
            <img
              src={previewImage}
              alt={t('calendar.previewAlt')}
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
}
