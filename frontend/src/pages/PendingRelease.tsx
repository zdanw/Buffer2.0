import { useState, useEffect, useMemo } from 'react';
import { Calendar, Check, X, Trash2, Send, Eye, ZoomIn, RefreshCw } from 'lucide-react';
import type { ManualTaskDraft, PaginatedResponse } from '@/api/tasks';
import { getDrafts, publishDraft, discardDraft, reuploadDraftCdn } from '@/api/tasks';
import { getTasks } from '@/api/tasks';
import type { ScheduledTask } from '@/api/tasks';
import { getProducts } from '@/api/products';
import { useBrandContext } from '@/context/BrandContext';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import { formatServerDateTime } from '@/lib/datetime';
import Pagination from '@/components/Pagination';
import ReferenceImagesDisplay from '@/components/ReferenceImagesDisplay';
import { useI18n } from '@/i18n/useI18n';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];
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
const CDN_MARKER = 'cdn.jsdelivr.net';

function isCdnUrl(url: string) {
  return Boolean(url && url.includes(CDN_MARKER));
}

export default function PendingRelease() {
  const { t, locale } = useI18n();
  const { activeBrandId } = useBrandContext();
  const [drafts, setDrafts] = useState<ManualTaskDraft[]>([]);
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null);
  const [selectedImageIndex, setSelectedImageIndex] = useState<number>(0);
  const [selectedCopyIndex, setSelectedCopyIndex] = useState<number>(0);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [previewCopy, setPreviewCopy] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [listBusy, setListBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [discardingId, setDiscardingId] = useState<string | null>(null);
  const [reuploading, setReuploading] = useState(false);
  const [productBrandMap, setProductBrandMap] = useState<Record<string, { brand_id?: string; name?: string; slug?: string }>>({});

  useEffect(() => {
    void Promise.all([loadDrafts(1), loadTasks(), loadProductBrands()]);
  }, [activeBrandId]);

  const loadProductBrands = async () => {
    try {
      const res = await getProducts(1, 200, activeBrandId || undefined);
      const map: Record<string, { brand_id?: string; name?: string; slug?: string }> = {};
      for (const p of res.data) {
        map[p.product_id] = p.brand
          ? { brand_id: p.brand.brand_id, name: p.brand.name, slug: p.brand.slug }
          : { brand_id: p.brand_id };
      }
      setProductBrandMap(map);
    } catch (error) {
      console.error('Failed to load product brands:', error);
    }
  };

  const visibleDrafts = useMemo(() => {
    if (!activeBrandId) return drafts;
    return drafts.filter((d) => {
      if (!d.product_id) return true;
      const brand = productBrandMap[d.product_id];
      return brand?.brand_id === activeBrandId;
    });
  }, [drafts, activeBrandId, productBrandMap]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      invalidateCache('tasks');
      await Promise.all([loadDrafts(currentPage, undefined, { keepRows: true }), loadTasks(true)]);
    } finally {
      setRefreshing(false);
    }
  };

  const loadDrafts = async (
    page: number = currentPage,
    newPageSize?: number,
    opts?: { keepRows?: boolean }
  ) => {
    const keepRows = Boolean(opts?.keepRows);
    if (keepRows) setListBusy(true);
    const size = newPageSize ?? pageSize;
    try {
      const response: PaginatedResponse<ManualTaskDraft> = await getDrafts('pending', page, size);
      setDrafts(response.data);
      setTotal(response.pagination.total);
      setCurrentPage(response.pagination.current);
      if (newPageSize) {
        setPageSize(newPageSize);
      }
    } catch (error) {
      console.error('Failed to load drafts:', error);
    } finally {
      if (keepRows) setListBusy(false);
      setInitialLoading(false);
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    void loadDrafts(1, newPageSize, { keepRows: true });
  };

  const loadTasks = async (force = false) => {
    try {
      if (force) invalidateCache('tasks');
      const data = force
        ? (await getTasks(1, 100)).data
        : await cachedFetch('tasks:list:100', async () => {
            const response = await getTasks(1, 100);
            return response.data;
          });
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    }
  };

  const getTaskName = (taskId?: string | null) => {
    if (!taskId) return t('pending.contentPreview');
    const task = tasks.find(tk => tk.task_id === taskId);
    return task?.name || t('pending.unknownTask');
  };

  const removeDraftLocally = (draftId: string) => {
    setDrafts((prev) => prev.filter((d) => d.draft_id !== draftId));
    setTotal((t) => Math.max(0, t - 1));
    if (selectedDraftId === draftId) {
      setSelectedDraftId(null);
      setSelectedPlatforms([]);
    }
  };

  const handleSelectDraft = (draft: ManualTaskDraft) => {
    setSelectedDraftId(draft.draft_id);
    setSelectedImageIndex(0);
    setSelectedCopyIndex(0);
    setSelectedPlatforms([]);
  };

  const handlePlatformToggle = (platform: string) => {
    setSelectedPlatforms(prev =>
      prev.includes(platform)
        ? prev.filter(p => p !== platform)
        : [...prev, platform]
    );
  };

  const handlePublish = async () => {
    if (!selectedDraftId) {
      alert(t('pending.selectDraftFirst'));
      return;
    }

    if (selectedPlatforms.length === 0) {
      alert(t('pending.selectPlatform'));
      return;
    }

    const draftId = selectedDraftId;
    setLoading(true);
    try {
      await publishDraft(draftId, {
        selected_image_index: selectedImageIndex,
        selected_copy_index: selectedCopyIndex,
        platforms: selectedPlatforms
      });
      alert(t('pending.publishSuccess'));
      const remaining = drafts.length - 1;
      removeDraftLocally(draftId);
      if (remaining <= 0 && currentPage > 1) {
        void loadDrafts(currentPage - 1);
      }
    } catch (error: any) {
      console.error('Failed to publish:', error);
      const detail = error?.response?.data?.detail;
      alert(typeof detail === 'string' && detail.trim() ? detail : t('pending.publishFailed'));
    } finally {
      setLoading(false);
    }
  };

  const handleDiscard = async (draftId: string) => {
    if (confirm(t('pending.confirmDiscard'))) {
      setDiscardingId(draftId);
      try {
        await discardDraft(draftId);
        const remaining = drafts.length - 1;
        removeDraftLocally(draftId);
        if (remaining <= 0 && currentPage > 1) {
          void loadDrafts(currentPage - 1);
        }
      } catch (error) {
        console.error('Failed to discard:', error);
        alert(t('pending.actionFailed'));
      } finally {
        setDiscardingId(null);
      }
    }
  };

  const handleReuploadCdn = async () => {
    if (!selectedDraftId) return;
    setReuploading(true);
    try {
      const result = await reuploadDraftCdn(selectedDraftId);
      setDrafts((prev) =>
        prev.map((d) =>
          d.draft_id === selectedDraftId
            ? {
                ...d,
                images: result.images,
                cdn_upload_failed: result.cdn_upload_failed,
              }
            : d
        )
      );
      if (result.success) {
        alert(t('pending.reuploadSuccess'));
      } else {
        alert(t('pending.reuploadPartialFail'));
      }
    } catch (error) {
      console.error('Failed to reupload CDN:', error);
      alert(t('pending.reuploadFailed'));
    } finally {
      setReuploading(false);
    }
  };

  const formatDate = (dateStr: string) => formatServerDateTime(dateStr, locale, t('datetime.unknown'));

  const selectedDraft = drafts.find(d => d.draft_id === selectedDraftId);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t('pending.title')}</h2>
          <p className="text-gray-500 mt-1">{t('pending.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Calendar className="w-4 h-4" />
            <span>{t('pending.totalDrafts', { total })}</span>
          </div>
          <button
            type="button"
            onClick={() => void handleRefresh()}
            disabled={refreshing || listBusy}
            className="flex items-center gap-2 bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('pending.draftList')}</h3>
          
          {initialLoading && drafts.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-6 h-6 border-2 border-forge-600 border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
              <p className="text-gray-500 text-sm">{t('common.loading')}</p>
            </div>
          ) : visibleDrafts.length === 0 ? (
            <div className="text-center py-12">
              <Eye className="w-16 h-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">{t('pending.noDrafts')}</p>
              <p className="text-gray-400 text-sm mt-2">{t('pending.draftHint')}</p>
            </div>
          ) : (
            <>
              <div className={`space-y-3 max-h-[600px] overflow-y-auto ${listBusy ? 'opacity-70 pointer-events-none' : ''}`}>
                {visibleDrafts.map((draft) => (
                  <div
                    key={draft.draft_id}
                    className={`border rounded-lg p-4 cursor-pointer transition-all ${
                      selectedDraftId === draft.draft_id
                        ? 'border-forge-600 bg-forge-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                    onClick={() => handleSelectDraft(draft)}
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <span className="text-xs font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded">
                          {getTaskName(draft.task_id)}
                        </span>
                        <p className="text-sm text-gray-500 mt-1">
                          {formatDate(draft.created_at)}
                        </p>
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDiscard(draft.draft_id);
                        }}
                        disabled={discardingId === draft.draft_id}
                        className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded disabled:opacity-50"
                      >
                        {discardingId === draft.draft_id ? (
                          <RefreshCw className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                    
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>{t('pending.imagesCount', { count: draft.images.length })}</span>
                      <span>{t('pending.copiesCount', { count: draft.copywritings.length })}</span>
                      {(draft.cdn_upload_failed ?? draft.images.some((img) => !isCdnUrl(img))) && (
                        <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">{t('pending.cdnFailed')}</span>
                      )}
                    </div>

                    <div className="mt-3 flex gap-2">
                      {draft.images.slice(0, 3).map((img, idx) => (
                        <img
                          key={idx}
                          src={img}
                          alt={t('pending.previewAlt', { n: idx + 1 })}
                          className="w-16 h-16 object-cover rounded-md cursor-pointer hover:opacity-80 transition-opacity"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPreviewImage(img);
                          }}
                        />
                      ))}
                      {draft.images.length > 3 && (
                        <div className="w-16 h-16 bg-gray-100 rounded-md flex items-center justify-center text-gray-500 text-xs">
                          +{t('pending.moreImages', { count: draft.images.length - 3 })}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {total > 0 && (
                <div className="mt-4">
                  <Pagination
                    current={currentPage}
                    total={total}
                    pageSize={pageSize}
                    disabled={listBusy}
                    onChange={(page) => void loadDrafts(page, undefined, { keepRows: true })}
                    onPageSizeChange={handlePageSizeChange}
                  />
                </div>
              )}
            </>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('pending.contentReview')}</h3>
          
          {!selectedDraft ? (
            <div className="text-center py-12">
              <Eye className="w-16 h-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">{t('pending.selectDraftHint')}</p>
            </div>
          ) : (
            <div className="space-y-6">
              {(selectedDraft.cdn_upload_failed ??
                selectedDraft.images.some((img) => !isCdnUrl(img))) && (
                <div className="p-4 rounded-lg bg-amber-50 border border-amber-200">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                    <div>
                      <p className="font-medium text-amber-800">{t('pending.cdnFailed')}</p>
                      <p className="text-sm text-amber-700 mt-1">
                        {t('pending.cdnBanner')}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleReuploadCdn()}
                      disabled={reuploading}
                      className="shrink-0 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <RefreshCw className={`w-4 h-4 ${reuploading ? 'animate-spin' : ''}`} />
                      {reuploading ? t('pending.uploadingCdn') : t('pending.uploadToCdn')}
                    </button>
                  </div>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">{t('pending.selectImage')}</label>
                <div className="grid grid-cols-2 gap-3">
                  {selectedDraft.images.map((img, idx) => (
                    <div
                      key={idx}
                      className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all group ${
                        selectedImageIndex === idx
                          ? 'border-forge-600 ring-2 ring-forge-200'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <img
                        src={img}
                        alt={t('pending.imageN', { n: idx + 1 })}
                        className="w-full h-32 object-cover"
                        onClick={() => setSelectedImageIndex(idx)}
                      />
                      {selectedImageIndex === idx && (
                        <div className="absolute top-2 right-2 bg-forge-600 text-white p-1 rounded-full">
                          <Check className="w-4 h-4" />
                        </div>
                      )}
                      {!isCdnUrl(img) && (
                        <div className="absolute top-2 left-2 bg-amber-500 text-white text-[10px] px-1.5 py-0.5 rounded">
                          {t('pending.notOnCdn')}
                        </div>
                      )}
                      <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-2 flex justify-between items-center">
                        <span>{t('pending.imageN', { n: idx + 1 })}</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setPreviewImage(img);
                          }}
                          className="p-1 bg-white/20 rounded-full hover:bg-white/30 transition-colors"
                        >
                          <ZoomIn className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <ReferenceImagesDisplay
                productImages={selectedDraft.reference_product_images}
                sceneImages={selectedDraft.reference_scene_images}
                onPreview={setPreviewImage}
              />

              {(() => {
                const dims = selectedDraft.dimensions?.[selectedImageIndex] ?? null;
                const prompt = selectedDraft.image_prompts?.[selectedImageIndex] ?? null;
                if (!dims && !prompt) return null;
                return (
                  <div className="border border-gray-200 rounded-lg p-4 bg-gray-50/50">
                    {dims && (
                      <>
                        <h4 className="text-sm font-semibold text-gray-700 mb-3">{t('fields.dimensionInfo')}</h4>
                        <div className="grid grid-cols-2 gap-2">
                          {DIMENSION_FIELDS.map((field) => {
                            const value = dims[field];
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
                    {prompt && (
                      <div className={dims ? 'mt-3' : ''}>
                        <h4 className="text-xs font-medium text-gray-600 mb-2">{t('fields.imagePrompt')}</h4>
                        <div className="text-xs text-gray-700 bg-white p-3 rounded-lg max-h-40 overflow-y-auto whitespace-pre-wrap border border-gray-100">
                          {prompt}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">{t('pending.selectCopy')}</label>
                <div className="space-y-2">
                  {selectedDraft.copywritings.map((copy, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border-2 cursor-pointer transition-all group ${
                        selectedCopyIndex === idx
                          ? 'border-forge-600 bg-forge-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div
                          onClick={() => setSelectedCopyIndex(idx)}
                          className="cursor-pointer"
                        >
                          {selectedCopyIndex === idx ? (
                            <Check className="w-4 h-4 text-forge-600 flex-shrink-0 mt-0.5" />
                          ) : (
                            <div className="w-4 h-4 border border-gray-300 rounded flex-shrink-0 mt-0.5" />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm text-gray-700 leading-relaxed">
                            {copy.length > 150 ? copy.substring(0, 150) + '...' : copy}
                          </p>
                          {copy.length > 150 && (
                            <button
                              onClick={() => setPreviewCopy(copy)}
                              className="mt-2 text-xs text-forge-600 hover:text-forge-700 flex items-center gap-1"
                            >
                              <Eye className="w-3 h-3" />
                              {t('pending.viewFullCopy')}
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">{t('fields.publishPlatformsLabel')}</label>
                <div className="flex flex-wrap gap-2">
                  {PLATFORMS.map((platform) => (
                    <label
                      key={platform}
                      className={`px-4 py-2 rounded-lg border-2 cursor-pointer transition-all ${
                        selectedPlatforms.includes(platform)
                          ? 'border-forge-600 bg-forge-50 text-forge-700'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedPlatforms.includes(platform)}
                        onChange={() => handlePlatformToggle(platform)}
                        className="sr-only"
                      />
                      {platform}
                    </label>
                  ))}
                </div>
              </div>

              <div className="flex gap-3 pt-4 border-t border-gray-100">
                <button
                  onClick={() => {
                    setSelectedDraftId(null);
                    setSelectedPlatforms([]);
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 flex items-center justify-center gap-2"
                >
                  <X className="w-4 h-4" />
                  {t('pending.deselect')}
                </button>
                <button
                  onClick={handlePublish}
                  disabled={loading || selectedPlatforms.length === 0}
                  className={`flex-1 px-4 py-2 rounded-lg flex items-center justify-center gap-2 transition-colors ${
                    loading || selectedPlatforms.length === 0
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : 'bg-forge-600 text-white hover:bg-forge-700'
                  }`}
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      {t('pending.publishing')}
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      {selectedPlatforms.length > 0
                        ? t('pending.publishTo', { platforms: selectedPlatforms.join(', ') })
                        : t('pending.publishToPlatform')}
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {previewImage && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50" onClick={() => setPreviewImage(null)}>
          <div className="relative max-w-4xl max-h-[90vh] p-4">
            <button
              onClick={() => setPreviewImage(null)}
              className="absolute top-2 right-2 text-white hover:text-gray-300 z-10"
            >
              <X className="w-8 h-8" />
            </button>
            <img
              src={previewImage}
              alt={t('common.preview')}
              className="max-w-full max-h-[90vh] object-contain rounded-lg"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}

      {previewCopy && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setPreviewCopy(null)}>
          <div className="relative bg-white rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={() => setPreviewCopy(null)}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="w-6 h-6" />
            </button>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('fields.copyContent')}</h3>
            <div className="prose prose-sm max-w-none">
              <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{previewCopy}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
