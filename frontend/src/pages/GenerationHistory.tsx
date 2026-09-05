import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { X } from 'lucide-react';
import {
  getGenerationRun,
  listGenerationRuns,
  type GenerationHistoryDetail,
  type GenerationHistoryListItem,
} from '@/api/generationHistory';
import GenerationRunDetail from '@/components/GenerationRunDetail';
import Pagination from '@/components/Pagination';
import { toUserFacingMessage } from '@/lib/apiErrors';
import { useI18n } from '@/i18n/useI18n';
import { formatServerDateTime } from '@/lib/datetime';
import { listRunSummary } from '@/lib/generationHistoryUtils';

function statusClass(status: string): string {
  switch (status) {
    case 'succeeded':
      return 'bg-green-100 text-green-800';
    case 'failed':
      return 'bg-red-100 text-red-800';
    case 'pending':
    case 'running':
      return 'bg-yellow-100 text-yellow-800';
    default:
      return 'bg-gray-100 text-gray-800';
  }
}

type AppliedFilters = {
  username: string;
  email: string;
  status: string;
  source: string;
  hasQaFailures: string;
  dateFrom: string;
  dateTo: string;
};

const EMPTY_FILTERS: AppliedFilters = {
  username: '',
  email: '',
  status: '',
  source: '',
  hasQaFailures: '',
  dateFrom: '',
  dateTo: '',
};

export default function GenerationHistory() {
  const { t, locale } = useI18n();
  const [searchParams, setSearchParams] = useSearchParams();
  const [items, setItems] = useState<GenerationHistoryListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<GenerationHistoryDetail | null>(null);

  const [draftFilters, setDraftFilters] = useState<AppliedFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<AppliedFilters>(EMPTY_FILTERS);

  const userIdFromUrl = searchParams.get('user_id') || '';

  const creditsShort = useCallback(
    (n: number) => t('generationHistory.creditsShort', { n }),
    [t],
  );

  const fetchList = useCallback(
    async (opts?: { silent?: boolean; nextPage?: number; filters?: AppliedFilters }) => {
      const filters = opts?.filters ?? appliedFilters;
      try {
        setLoading(true);
        setError('');
        const currentPage = opts?.nextPage ?? page;
        const response = await listGenerationRuns({
          page: currentPage,
          page_size: pageSize,
          user_id: userIdFromUrl || undefined,
          username: filters.username.trim() || undefined,
          email: filters.email.trim() || undefined,
          status: filters.status || undefined,
          source: filters.source || undefined,
          date_from: filters.dateFrom ? `${filters.dateFrom}T00:00:00` : undefined,
          date_to: filters.dateTo ? `${filters.dateTo}T23:59:59` : undefined,
          has_qa_failures:
            filters.hasQaFailures === 'yes'
              ? true
              : filters.hasQaFailures === 'no'
                ? false
                : undefined,
        });
        setItems(response.items);
        setTotal(response.total);
        setPage(response.page);
      } catch (err: unknown) {
        setError(toUserFacingMessage(err, t('generationHistory.loadFailed')));
      } finally {
        setLoading(false);
      }
    },
    [page, pageSize, userIdFromUrl, appliedFilters, t],
  );

  const fetchDetail = useCallback(
    async (runId: string) => {
      try {
        setDetailLoading(true);
        const data = await getGenerationRun(runId);
        setDetail(data);
      } catch (err: unknown) {
        setError(toUserFacingMessage(err, t('generationHistory.detailFailed')));
        setDetail(null);
      } finally {
        setDetailLoading(false);
      }
    },
    [t],
  );

  useEffect(() => {
    void fetchList();
  }, [fetchList]);

  useEffect(() => {
    if (items.length === 0) {
      setSelectedRunId(null);
      return;
    }
    if (!selectedRunId || !items.some((item) => item.run_id === selectedRunId)) {
      setSelectedRunId(items[0].run_id);
    }
  }, [items, selectedRunId]);

  useEffect(() => {
    if (selectedRunId) {
      void fetchDetail(selectedRunId);
    } else {
      setDetail(null);
    }
  }, [selectedRunId, fetchDetail]);

  const activeFilterChips = useMemo(() => {
    const chips: { key: keyof AppliedFilters | 'user_id'; label: string }[] = [];
    if (userIdFromUrl) {
      chips.push({ key: 'user_id', label: t('generationHistory.activeUserFilter') });
    }
    if (appliedFilters.username) {
      chips.push({
        key: 'username',
        label: t('generationHistory.chipUsername', { value: appliedFilters.username }),
      });
    }
    if (appliedFilters.email) {
      chips.push({
        key: 'email',
        label: t('generationHistory.chipEmail', { value: appliedFilters.email }),
      });
    }
    if (appliedFilters.status) {
      chips.push({
        key: 'status',
        label: t('generationHistory.chipStatus', { value: appliedFilters.status }),
      });
    }
    if (appliedFilters.source) {
      chips.push({
        key: 'source',
        label: t('generationHistory.chipSource', { value: appliedFilters.source }),
      });
    }
    if (appliedFilters.hasQaFailures) {
      chips.push({
        key: 'hasQaFailures',
        label:
          appliedFilters.hasQaFailures === 'yes'
            ? t('generationHistory.filterQaYes')
            : t('generationHistory.filterQaNo'),
      });
    }
    if (appliedFilters.dateFrom || appliedFilters.dateTo) {
      chips.push({
        key: 'dateFrom',
        label: t('generationHistory.chipDateRange', {
          from: appliedFilters.dateFrom || '…',
          to: appliedFilters.dateTo || '…',
        }),
      });
    }
    return chips;
  }, [appliedFilters, userIdFromUrl, t]);

  const handleApplyFilters = () => {
    setAppliedFilters(draftFilters);
    setPage(1);
  };

  const handleClearFilters = () => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setPage(1);
  };

  const handleRemoveChip = (key: keyof AppliedFilters | 'user_id') => {
    if (key === 'user_id') {
      const next = new URLSearchParams(searchParams);
      next.delete('user_id');
      setSearchParams(next);
      return;
    }
    const nextDraft = { ...draftFilters, [key]: '' };
    const nextApplied = { ...appliedFilters, [key]: '' };
    if (key === 'dateFrom') {
      nextDraft.dateTo = '';
      nextApplied.dateTo = '';
    }
    setDraftFilters(nextDraft);
    setAppliedFilters(nextApplied);
    setPage(1);
  };

  if (loading && items.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-forge-600" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 h-full flex flex-col">
      <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('generationHistory.title')}</h1>
          <p className="text-sm text-gray-600 mt-1">{t('generationHistory.subtitle')}</p>
        </div>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      <div className="mb-3 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7 gap-3">
        <input
          type="text"
          value={draftFilters.username}
          onChange={(e) => setDraftFilters((f) => ({ ...f, username: e.target.value }))}
          placeholder={t('generationHistory.filterUsername')}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg"
        />
        <input
          type="text"
          value={draftFilters.email}
          onChange={(e) => setDraftFilters((f) => ({ ...f, email: e.target.value }))}
          placeholder={t('generationHistory.filterEmail')}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg"
        />
        <select
          value={draftFilters.status}
          onChange={(e) => setDraftFilters((f) => ({ ...f, status: e.target.value }))}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
        >
          <option value="">{t('generationHistory.filterStatusAll')}</option>
          <option value="succeeded">{t('generationHistory.statusSucceeded')}</option>
          <option value="failed">{t('generationHistory.statusFailed')}</option>
          <option value="pending">{t('generationHistory.statusPending')}</option>
          <option value="cancelled">{t('generationHistory.statusCancelled')}</option>
        </select>
        <select
          value={draftFilters.source}
          onChange={(e) => setDraftFilters((f) => ({ ...f, source: e.target.value }))}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
        >
          <option value="">{t('generationHistory.filterSourceAll')}</option>
          <option value="studio">{t('generationHistory.sourceStudio')}</option>
          <option value="automation">{t('generationHistory.sourceAutomation')}</option>
        </select>
        <select
          value={draftFilters.hasQaFailures}
          onChange={(e) => setDraftFilters((f) => ({ ...f, hasQaFailures: e.target.value }))}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
        >
          <option value="">{t('generationHistory.filterQaAll')}</option>
          <option value="yes">{t('generationHistory.filterQaYes')}</option>
          <option value="no">{t('generationHistory.filterQaNo')}</option>
        </select>
        <input
          type="date"
          value={draftFilters.dateFrom}
          onChange={(e) => setDraftFilters((f) => ({ ...f, dateFrom: e.target.value }))}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
          aria-label={t('generationHistory.filterDateFrom')}
        />
        <input
          type="date"
          value={draftFilters.dateTo}
          onChange={(e) => setDraftFilters((f) => ({ ...f, dateTo: e.target.value }))}
          className="px-3 py-2 text-sm border border-gray-300 rounded-lg bg-white"
          aria-label={t('generationHistory.filterDateTo')}
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={handleApplyFilters}
          className="px-4 py-2 text-sm font-medium text-white bg-forge-600 rounded-lg hover:bg-forge-700"
        >
          {t('generationHistory.applyFilters')}
        </button>
        {activeFilterChips.length > 0 ? (
          <button
            type="button"
            onClick={handleClearFilters}
            className="text-sm text-gray-600 hover:text-gray-900"
          >
            {t('generationHistory.clearAllFilters')}
          </button>
        ) : null}
      </div>

      {activeFilterChips.length > 0 ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {activeFilterChips.map((chip) => (
            <button
              key={chip.key}
              type="button"
              onClick={() => handleRemoveChip(chip.key)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-forge-50 text-forge-800 border border-forge-200 hover:bg-forge-100"
            >
              {chip.label}
              <X className="w-3 h-3" />
            </button>
          ))}
        </div>
      ) : null}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-6 min-h-0">
        <div className="flex flex-col min-h-0">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden flex-1 min-h-0 flex flex-col">
            <div className="px-4 py-3 border-b border-gray-100">
              <h2 className="text-sm font-semibold text-gray-900">{t('generationHistory.runList')}</h2>
            </div>
            <div className="overflow-auto flex-1 p-3 space-y-2">
              {items.map((item) => (
                <button
                  key={item.run_id}
                  type="button"
                  onClick={() => setSelectedRunId(item.run_id)}
                  className={`w-full text-left border rounded-lg p-3 transition-all ${
                    selectedRunId === item.run_id
                      ? 'border-forge-600 bg-forge-50 ring-1 ring-forge-200'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {item.thumbnail_url ? (
                      <img
                        src={item.thumbnail_url}
                        alt=""
                        className="w-12 h-12 rounded-lg object-cover border border-gray-200 shrink-0"
                      />
                    ) : (
                      <div className="w-12 h-12 rounded-lg bg-gray-100 border border-gray-200 shrink-0 flex items-center justify-center">
                        <span className="text-[9px] text-gray-400 text-center leading-tight px-1">
                          {t('generationHistory.noThumb')}
                        </span>
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {item.product?.name || item.source}
                        </p>
                        <span
                          className={`shrink-0 inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium ${statusClass(item.status)}`}
                        >
                          {item.status}
                        </span>
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {formatServerDateTime(item.created_at, locale, t('datetime.unknown'))}
                      </p>
                      <p className="text-xs text-gray-600 mt-1 truncate">
                        {item.user.username} · {item.user.email}
                      </p>
                      <p className="text-[11px] text-gray-400 mt-1">
                        {listRunSummary(item, creditsShort)}
                      </p>
                    </div>
                  </div>
                </button>
              ))}
              {items.length === 0 ? (
                <div className="text-center py-12 text-sm text-gray-500">{t('generationHistory.empty')}</div>
              ) : null}
            </div>
            <div className="border-t border-gray-100 p-3">
              <Pagination
                current={page}
                total={total}
                pageSize={pageSize}
                onChange={(nextPage) => {
                  setPage(nextPage);
                }}
                onPageSizeChange={(size) => {
                  setPageSize(size);
                  setPage(1);
                }}
              />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 overflow-auto min-h-[28rem] lg:min-h-0">
          <GenerationRunDetail detail={detail} loading={detailLoading} />
        </div>
      </div>
    </div>
  );
}
