import { useState, useEffect, useMemo, useCallback } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  Clock,
  AlertCircle,
  RefreshCw,
  X,
  Image,
  FileText,
  Zap,
  ZoomIn,
  ExternalLink,
} from 'lucide-react';
import type {
  ScheduledTask,
  TaskExecution,
  CalendarExecutionSummary,
  CalendarDraftSummary,
  PlatformPost,
} from '@/api/tasks';
import { getTasks, getCalendarMonth, getExecutionDetail } from '@/api/tasks';
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
  executionSummaries: CalendarExecutionSummary[];
  draftSummaries: CalendarDraftSummary[];
  tasks: ScheduledTask[];
}

interface GroupedEvents {
  date: Date;
  dateLabel: string;
  weekday: string;
  events: CalendarEvent[];
}

function isSameLocalDay(isoOrDate: string, year: number, month: number, day: number): boolean {
  const d = parseServerDate(isoOrDate);
  if (!d) return false;
  return d.getFullYear() === year && d.getMonth() === month && d.getDate() === day;
}

function PlatformPostLinks({ posts, t }: { posts: PlatformPost[]; t: (key: string, vars?: Record<string, string>) => string }) {
  const withLinks = (posts || []).filter((p) => p.post_link);
  if (withLinks.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {withLinks.map((post) => (
        <a
          key={`${post.platform}-${post.post_id || post.post_link}`}
          href={post.post_link}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-forge-50 text-forge-700 rounded-lg text-sm font-medium hover:bg-forge-100 transition-colors"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          {t('calendar.viewPost', { platform: post.platform })}
        </a>
      ))}
    </div>
  );
}

export default function PublishCalendar() {
  const location = useLocation();
  const { t, locale } = useI18n();
  const { activeBrandId } = useBrandContext();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [executionSummaries, setExecutionSummaries] = useState<CalendarExecutionSummary[]>([]);
  const [draftSummaries, setDraftSummaries] = useState<CalendarDraftSummary[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const [selectedDay, setSelectedDay] = useState<DayDetail | null>(null);
  const [executionDetails, setExecutionDetails] = useState<Map<string, TaskExecution>>(new Map());
  const [loadingDetails, setLoadingDetails] = useState(false);
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

  const summaryMatchesBrand = useCallback(
    (productId?: string | null) => {
      if (!activeBrandId) return true;
      if (!productId) return true;
      return brandProductIds.has(productId);
    },
    [activeBrandId, brandProductIds]
  );

  const loadCalendarData = useCallback(
    async (force = false) => {
      if (force) setRefreshing(true);
      else setLoading(true);
      try {
        if (force) invalidateCache('tasks');

        const year = currentDate.getFullYear();
        const month = currentDate.getMonth() + 1;

        const taskPromise = force
          ? getTasks(1, 100).then((r) => r.data)
          : cachedFetch('tasks:list:100', async () => {
              const response = await getTasks(1, 100);
              return response.data;
            });

        const calendarPromise = getCalendarMonth(year, month);

        const [taskResult, calendarResult] = await Promise.allSettled([taskPromise, calendarPromise]);

        if (taskResult.status === 'fulfilled') {
          setTasks(taskResult.value);
        } else {
          console.error('Failed to load tasks:', taskResult.reason);
        }

        if (calendarResult.status === 'fulfilled') {
          setExecutionSummaries(calendarResult.value.executions);
          setDraftSummaries(calendarResult.value.drafts);
        } else {
          console.error('Failed to load calendar month:', calendarResult.reason);
        }
      } catch (error) {
        console.error('Failed to load calendar data:', error);
      } finally {
        if (force) setRefreshing(false);
        else setLoading(false);
      }
    },
    [currentDate]
  );

  useEffect(() => {
    if (location.pathname === '/calendar') {
      loadCalendarData();
    }
  }, [location.pathname, loadCalendarData]);

  const filteredExecutions = useMemo(
    () => executionSummaries.filter((ex) => summaryMatchesBrand(ex.product_id)),
    [executionSummaries, summaryMatchesBrand]
  );

  const filteredDrafts = useMemo(
    () => draftSummaries.filter((d) => summaryMatchesBrand(d.product_id)),
    [draftSummaries, summaryMatchesBrand]
  );

  const getDayExecutions = useCallback(
    (day: number, month: number, year: number): CalendarExecutionSummary[] => {
      return filteredExecutions.filter((ex) => isSameLocalDay(ex.created_at, year, month, day));
    },
    [filteredExecutions]
  );

  const getDayDrafts = useCallback(
    (day: number, month: number, year: number): CalendarDraftSummary[] => {
      return filteredDrafts.filter((d) => isSameLocalDay(d.created_at, year, month, day));
    },
    [filteredDrafts]
  );

  const getEventStatus = (
    taskId: string,
    day: number,
    month: number,
    year: number
  ): 'pending' | 'completed' | 'failed' | 'running' => {
    const dayExecutions = getDayExecutions(day, month, year).filter((ex) => ex.task_id === taskId);
    if (dayExecutions.length === 0) return 'pending';

    const latest = dayExecutions[0];
    switch (latest.status) {
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

  const loadExecutionDetails = useCallback(async (summaries: CalendarExecutionSummary[]) => {
    if (summaries.length === 0) return;
    setLoadingDetails(true);
    try {
      const results = await Promise.allSettled(
        summaries.map((s) => getExecutionDetail(s.execution_id))
      );
      setExecutionDetails((prev) => {
        const next = new Map(prev);
        results.forEach((result, index) => {
          if (result.status === 'fulfilled') {
            next.set(summaries[index].execution_id, result.value);
          }
        });
        return next;
      });
    } finally {
      setLoadingDetails(false);
    }
  }, []);

  const handleDayClick = (day: number) => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const dayExecutionSummaries = getDayExecutions(day, month, year);
    const dayDraftSummaries = getDayDrafts(day, month, year);

    const dayTasks = calendarEvents
      .filter((e) => e.day === day)
      .map((e) => tasks.find((tk) => tk.task_id === e.taskId))
      .filter(Boolean) as ScheduledTask[];

    setSelectedDay({
      date: new Date(year, month, day),
      executionSummaries: dayExecutionSummaries,
      draftSummaries: dayDraftSummaries,
      tasks: dayTasks,
    });

    void loadExecutionDetails(dayExecutionSummaries);
  };

  useEffect(() => {
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

          const eventTime = new Date(year, month, d, hour, minute, 0, 0);
          if (eventTime.getTime() < now.getTime()) continue;

          const status = getEventStatus(task.task_id, d, month, year);

          events.push({
            id: `${task.task_id}-${d}`,
            taskId: task.task_id,
            title: task.name,
            time: `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`,
            status,
            platforms: task.platforms || [],
            mode: task.mode || 'auto',
            day: d,
            month,
            year,
          });
        }
      }
    });

    setCalendarEvents(events);
  }, [tasks, filteredExecutions, currentDate, taskMatchesBrand, getDayExecutions]);

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
    return new Date(year, month, 1).getDay();
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
    const upcoming = calendarEvents
      .filter((e) => isEventUpcoming(e, now))
      .sort((a, b) => {
        const dateA = new Date(a.year, a.month, a.day);
        const dateB = new Date(b.year, b.month, b.day);
        if (dateA.getTime() !== dateB.getTime()) return dateA.getTime() - dateB.getTime();
        return a.time.localeCompare(b.time);
      });

    const grouped: Record<string, GroupedEvents> = {};

    upcoming.forEach((event) => {
      const dateKey = `${event.year}-${event.month}-${event.day}`;
      if (!grouped[dateKey]) {
        const date = new Date(event.year, event.month, event.day);
        grouped[dateKey] = {
          date,
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
        return <span className="w-2 h-2 bg-forge-500 rounded-full animate-pulse" />;
      default:
        return <span className="w-2 h-2 bg-gray-400 rounded-full" />;
    }
  };

  const findDraftForTask = (taskId: string, day: number, month: number, year: number) => {
    return getDayDrafts(day, month, year).find(
      (d) => d.task_id === taskId && d.status === 'pending'
    );
  };

  const groupedEvents = getGroupedEvents();

  const renderPublishedCellItem = (label: string, thumbnail?: string | null, key?: string) => (
    <div
      key={key || label}
      className="flex items-center gap-1 text-xs bg-green-50 rounded px-1 py-0.5 border border-green-200"
    >
      {thumbnail ? (
        <img src={thumbnail} alt="" className="w-4 h-4 rounded object-cover shrink-0" loading="lazy" />
      ) : (
        <CheckCircle className="w-3 h-3 text-green-500 shrink-0" />
      )}
      <span className="truncate max-w-[72px]">{label}</span>
    </div>
  );

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t('calendar.title')}</h2>
          <p className="text-gray-500 mt-1">{t('calendar.subtitle')}</p>
        </div>
        <button
          onClick={() => loadCalendarData(true)}
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
                <RefreshCw className="w-6 h-6 animate-spin text-forge-600" />
              </div>
            )}
            <div className="flex items-center justify-between mb-6">
              <button onClick={prevMonth} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                <ChevronLeft className="w-6 h-6 text-gray-600" />
              </button>
              <h3 className="text-xl font-semibold text-gray-800">{formatMonth()}</h3>
              <button onClick={nextMonth} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
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
                const month = currentDate.getMonth();
                const year = currentDate.getFullYear();
                const dayEvents = calendarEvents.filter((e) => e.day === day && isEventUpcoming(e));
                const dayExecutions = getDayExecutions(day, month, year);
                const dayPublishedDrafts = getDayDrafts(day, month, year).filter((d) => d.status === 'published');
                const publishedItems = [
                  ...dayExecutions.map((ex) => ({
                    key: ex.execution_id,
                    label: ex.task_name,
                    thumbnail: ex.thumbnail_url,
                  })),
                  ...dayPublishedDrafts.map((d) => ({
                    key: d.draft_id,
                    label: d.task_name,
                    thumbnail: d.thumbnail_url,
                  })),
                ];
                const hasPublished = publishedItems.length > 0;

                return (
                  <div
                    key={day}
                    onClick={() => handleDayClick(day)}
                    className={`aspect-square bg-gray-50 rounded-lg p-2 hover:bg-gray-100 transition-colors cursor-pointer ${hasPublished ? 'ring-2 ring-forge-400' : ''}`}
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
                      {publishedItems.slice(0, dayEvents.length > 0 ? 1 : 2).map((item) =>
                        renderPublishedCellItem(item.label, item.thumbnail, item.key)
                      )}
                      {publishedItems.length > (dayEvents.length > 0 ? 1 : 2) && (
                        <div className="text-[10px] text-gray-500 px-1">
                          {t('calendar.moreItems', {
                            count: String(publishedItems.length - (dayEvents.length > 0 ? 1 : 2)),
                          })}
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
                    <div className="bg-gradient-to-r from-forge-50 to-blue-50 px-3 py-2">
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="font-medium text-forge-800 text-sm">{group.dateLabel}</span>
                          <span className="text-xs text-forge-600 ml-2">{group.weekday}</span>
                        </div>
                        <span className="text-xs text-forge-500 bg-white px-2 py-0.5 rounded-full">
                          {t('calendar.tasksCount', { count: group.events.length })}
                        </span>
                      </div>
                    </div>

                    <div className="divide-y divide-gray-50">
                      {group.events.map((event) => {
                        const pendingDraft = findDraftForTask(
                          event.taskId,
                          event.day,
                          event.month,
                          event.year
                        );
                        return (
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

                            <div className="flex flex-wrap gap-1 mb-2">
                              {event.platforms.map((platform) => (
                                <span
                                  key={platform}
                                  className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-medium"
                                >
                                  {platform}
                                </span>
                              ))}
                            </div>

                            {pendingDraft && (
                              <Link
                                to={`/review?draft=${pendingDraft.draft_id}`}
                                onClick={(e) => e.stopPropagation()}
                                className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-700 hover:text-amber-900"
                              >
                                <Zap className="w-3 h-3" />
                                {t('calendar.reviewDraft')}
                              </Link>
                            )}
                          </div>
                        );
                      })}
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
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6"
            onClick={(e) => e.stopPropagation()}
          >
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

            {selectedDay.executionSummaries.length > 0 ? (
              <div className="space-y-6">
                {loadingDetails && (
                  <p className="text-sm text-gray-500 flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    {t('calendar.loadingDetails')}
                  </p>
                )}
                {selectedDay.executionSummaries.map((summary) => {
                  const execution = executionDetails.get(summary.execution_id);
                  const task = tasks.find((tk) => tk.task_id === summary.task_id);
                  return (
                    <div key={summary.execution_id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-center gap-3 mb-4">
                        {getExecutionStatusIcon(summary.status)}
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-gray-800">
                            {task?.name || summary.task_name || t('calendar.unknownTask')}
                          </div>
                          <div className="text-sm text-gray-500">
                            {formatServerDateTime(summary.created_at, locale, t('datetime.unknown'), {
                              year: 'numeric',
                              month: 'numeric',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                            })}
                          </div>
                        </div>
                        {summary.thumbnail_url && (
                          <button
                            type="button"
                            onClick={() => setPreviewImage(summary.thumbnail_url!)}
                            className="shrink-0 rounded-lg overflow-hidden focus:outline-none focus:ring-2 focus:ring-forge-400"
                          >
                            <img
                              src={summary.thumbnail_url}
                              alt=""
                              className="w-14 h-14 object-cover"
                              loading="lazy"
                            />
                          </button>
                        )}
                      </div>

                      <PlatformPostLinks posts={summary.platform_posts} t={t} />

                      {execution?.copywriting && (
                        <div className="mb-4 mt-4">
                          <div className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
                            <FileText className="w-4 h-4" />
                            {t('fields.copyContent')}
                          </div>
                          <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 whitespace-pre-wrap">
                            {execution.copywriting}
                          </div>
                        </div>
                      )}

                      {execution && (execution.generated_images || []).length > 0 && (
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
                                className="relative group w-full rounded-lg overflow-hidden focus:outline-none focus:ring-2 focus:ring-forge-400"
                              >
                                <img
                                  src={img}
                                  alt={t('calendar.generatedAlt', { n: String(index + 1) })}
                                  className="w-full h-40 object-cover"
                                  loading="lazy"
                                />
                                <span className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                                  <ZoomIn className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {execution && (
                        <ReferenceImagesDisplay
                          className="mt-4"
                          productImages={execution.reference_product_images}
                          sceneImages={execution.reference_scene_images}
                          onPreview={setPreviewImage}
                        />
                      )}

                      {((summary.published_platforms || []).length > 0) && (
                        <div className="mt-4">
                          <div className="text-sm text-gray-500 mb-2">{t('fields.publishPlatformsLabel')}</div>
                          <div className="flex flex-wrap gap-2">
                            {(summary.published_platforms || []).map((platform) => (
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

                      {execution && (execution.dimensions || execution.image_prompt) && (
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

                      {execution?.error_message && (
                        <div className="mt-4 p-3 bg-red-50 rounded-lg text-sm text-red-600">
                          {t('calendar.errorInfo', { message: execution.error_message })}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : null}

            {selectedDay.draftSummaries.length > 0 && (
              <div className={`space-y-4 ${selectedDay.executionSummaries.length > 0 ? 'mt-6 pt-6 border-t border-gray-100' : ''}`}>
                {selectedDay.draftSummaries.map((draft) => (
                  <div key={draft.draft_id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      {draft.thumbnail_url && (
                        <img
                          src={draft.thumbnail_url}
                          alt=""
                          className="w-14 h-14 rounded-lg object-cover shrink-0"
                          loading="lazy"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-gray-800">{draft.task_name}</div>
                        <div className="text-sm text-gray-500 mt-0.5">
                          {draft.status === 'pending'
                            ? t('calendar.manualDraftReady')
                            : t('calendar.publishedDraft')}
                        </div>
                        {draft.copy_preview && (
                          <p className="text-sm text-gray-600 mt-2 line-clamp-3">{draft.copy_preview}</p>
                        )}
                        {draft.status === 'pending' && (
                          <Link
                            to={`/review?draft=${draft.draft_id}`}
                            className="inline-flex items-center gap-1.5 mt-3 text-sm font-medium text-forge-700 hover:text-forge-900"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            {t('calendar.openInReview')}
                          </Link>
                        )}
                        <PlatformPostLinks posts={draft.platform_posts} t={t} />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {selectedDay.executionSummaries.length === 0 &&
              selectedDay.draftSummaries.length === 0 &&
              selectedDay.tasks.length > 0 && (
                <div className="space-y-3">
                  <p className="text-sm text-gray-500 mb-2">{t('calendar.scheduledNoExecution')}</p>
                  {selectedDay.tasks.map((task) => {
                    const day = selectedDay.date.getDate();
                    const month = selectedDay.date.getMonth();
                    const year = selectedDay.date.getFullYear();
                    const pendingDraft = findDraftForTask(task.task_id, day, month, year);
                    return (
                      <div key={task.task_id} className="border border-gray-200 rounded-lg p-4">
                        <div className="font-medium text-gray-800">{task.name}</div>
                        <div className="text-sm text-gray-500 mt-1">
                          {task.mode === 'manual' ? t('calendar.manualDesc') : t('calendar.autoDesc')}
                        </div>
                        {pendingDraft && (
                          <Link
                            to={`/review?draft=${pendingDraft.draft_id}`}
                            className="inline-flex items-center gap-1.5 mt-3 text-sm font-medium text-amber-700 hover:text-amber-900"
                          >
                            <Zap className="w-3 h-3" />
                            {t('calendar.reviewDraft')}
                          </Link>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

            {selectedDay.executionSummaries.length === 0 &&
              selectedDay.draftSummaries.length === 0 &&
              selectedDay.tasks.length === 0 && (
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
