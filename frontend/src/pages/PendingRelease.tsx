import { useState, useEffect } from 'react';
import { Calendar, Check, X, Trash2, Send, Eye, ZoomIn } from 'lucide-react';
import type { ManualTaskDraft, PaginatedResponse } from '@/api/tasks';
import { getDrafts, publishDraft, discardDraft } from '@/api/tasks';
import { getTasks } from '@/api/tasks';
import type { ScheduledTask } from '@/api/tasks';
import { cachedFetch } from '@/lib/staticCache';
import Pagination from '@/components/Pagination';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];

export default function PendingRelease() {
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

  useEffect(() => {
    void Promise.all([loadDrafts(1), loadTasks()]);
  }, []);

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
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    void loadDrafts(1, newPageSize, { keepRows: true });
  };

  const loadTasks = async () => {
    try {
      const data = await cachedFetch('tasks:list:100', async () => {
        const response = await getTasks(1, 100);
        return response.data;
      });
      setTasks(data);
    } catch (error) {
      console.error('Failed to load tasks:', error);
    }
  };

  const getTaskName = (taskId: string) => {
    const task = tasks.find(t => t.task_id === taskId);
    return task?.name || '未知任务';
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
      alert('请先选择一个草稿');
      return;
    }

    if (selectedPlatforms.length === 0) {
      alert('请至少选择一个发布平台');
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
      alert('发布成功！');
      const remaining = drafts.length - 1;
      removeDraftLocally(draftId);
      if (remaining <= 0 && currentPage > 1) {
        void loadDrafts(currentPage - 1);
      }
    } catch (error) {
      console.error('Failed to publish:', error);
      alert('发布失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDiscard = async (draftId: string) => {
    if (confirm('确定要丢弃这个草稿吗？此操作不可撤销。')) {
      try {
        await discardDraft(draftId);
        const remaining = drafts.length - 1;
        removeDraftLocally(draftId);
        if (remaining <= 0 && currentPage > 1) {
          void loadDrafts(currentPage - 1);
        }
      } catch (error) {
        console.error('Failed to discard:', error);
        alert('操作失败，请重试');
      }
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      return '未知时间';
    }
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const selectedDraft = drafts.find(d => d.draft_id === selectedDraftId);

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">待发布</h2>
          <p className="text-gray-500 mt-1">审核并发布手动任务生成的内容</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Calendar className="w-4 h-4" />
          <span>共 {total} 个待审核草稿</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">草稿列表</h3>
          
          {drafts.length === 0 ? (
            <div className="text-center py-12">
              <Eye className="w-16 h-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">暂无待发布草稿</p>
              <p className="text-gray-400 text-sm mt-2">手动发布模式的任务会在CRON时间自动生成草稿</p>
            </div>
          ) : (
            <>
              <div className={`space-y-3 max-h-[600px] overflow-y-auto ${listBusy ? 'opacity-70 pointer-events-none' : ''}`}>
                {drafts.map((draft) => (
                  <div
                    key={draft.draft_id}
                    className={`border rounded-lg p-4 cursor-pointer transition-all ${
                      selectedDraftId === draft.draft_id
                        ? 'border-indigo-600 bg-indigo-50'
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
                        className="p-1 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    
                    <div className="flex items-center gap-4 text-xs text-gray-500">
                      <span>{draft.images.length} 张图片</span>
                      <span>{draft.copywritings.length} 条文案</span>
                    </div>

                    <div className="mt-3 flex gap-2">
                      {draft.images.slice(0, 3).map((img, idx) => (
                        <img
                          key={idx}
                          src={img}
                          alt={`预览图 ${idx + 1}`}
                          className="w-16 h-16 object-cover rounded-md cursor-pointer hover:opacity-80 transition-opacity"
                          onClick={(e) => {
                            e.stopPropagation();
                            setPreviewImage(img);
                          }}
                        />
                      ))}
                      {draft.images.length > 3 && (
                        <div className="w-16 h-16 bg-gray-100 rounded-md flex items-center justify-center text-gray-500 text-xs">
                          +{draft.images.length - 3}
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
                    onChange={(page) => void loadDrafts(page, undefined, { keepRows: true })}
                    onPageSizeChange={handlePageSizeChange}
                  />
                </div>
              )}
            </>
          )}
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">内容审核</h3>
          
          {!selectedDraft ? (
            <div className="text-center py-12">
              <Eye className="w-16 h-16 mx-auto text-gray-300 mb-4" />
              <p className="text-gray-500">请从左侧选择一个草稿进行审核</p>
            </div>
          ) : (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">选择图片</label>
                <div className="grid grid-cols-2 gap-3">
                  {selectedDraft.images.map((img, idx) => (
                    <div
                      key={idx}
                      className={`relative cursor-pointer rounded-lg overflow-hidden border-2 transition-all group ${
                        selectedImageIndex === idx
                          ? 'border-indigo-600 ring-2 ring-indigo-200'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <img
                        src={img}
                        alt={`图片 ${idx + 1}`}
                        className="w-full h-32 object-cover"
                        onClick={() => setSelectedImageIndex(idx)}
                      />
                      {selectedImageIndex === idx && (
                        <div className="absolute top-2 right-2 bg-indigo-600 text-white p-1 rounded-full">
                          <Check className="w-4 h-4" />
                        </div>
                      )}
                      <div className="absolute bottom-0 left-0 right-0 bg-black/50 text-white text-xs p-2 flex justify-between items-center">
                        <span>图片 {idx + 1}</span>
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

              {(() => {
                const dims = selectedDraft.dimensions?.[selectedImageIndex] ?? null;
                const prompt = selectedDraft.image_prompts?.[selectedImageIndex] ?? null;
                if (!dims && !prompt) return null;
                return (
                  <div className="border border-gray-200 rounded-lg p-4 bg-gray-50/50">
                    {dims && (
                      <>
                        <h4 className="text-sm font-semibold text-gray-700 mb-3">维度信息</h4>
                        <div className="grid grid-cols-2 gap-2">
                          {dims.scene && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">场景</span>
                              <span className="text-xs text-gray-800">{dims.scene}</span>
                            </div>
                          )}
                          {dims.lighting && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">光线</span>
                              <span className="text-xs text-gray-800">{dims.lighting}</span>
                            </div>
                          )}
                          {dims.style && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">风格</span>
                              <span className="text-xs text-gray-800">{dims.style}</span>
                            </div>
                          )}
                          {dims.composition && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">构图</span>
                              <span className="text-xs text-gray-800">{dims.composition}</span>
                            </div>
                          )}
                          {dims.details && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">细节</span>
                              <span className="text-xs text-gray-800">{dims.details}</span>
                            </div>
                          )}
                          {dims.quality && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">画质</span>
                              <span className="text-xs text-gray-800">{dims.quality}</span>
                            </div>
                          )}
                          {dims.viewpoint && (
                            <div className="flex items-start gap-2">
                              <span className="text-xs text-gray-500 w-12 shrink-0">视角</span>
                              <span className="text-xs text-gray-800">{dims.viewpoint}</span>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                    {prompt && (
                      <div className={dims ? 'mt-3' : ''}>
                        <h4 className="text-xs font-medium text-gray-600 mb-2">图像提示词</h4>
                        <div className="text-xs text-gray-700 bg-white p-3 rounded-lg max-h-40 overflow-y-auto whitespace-pre-wrap border border-gray-100">
                          {prompt}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">选择文案</label>
                <div className="space-y-2">
                  {selectedDraft.copywritings.map((copy, idx) => (
                    <div
                      key={idx}
                      className={`p-3 rounded-lg border-2 cursor-pointer transition-all group ${
                        selectedCopyIndex === idx
                          ? 'border-indigo-600 bg-indigo-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div
                          onClick={() => setSelectedCopyIndex(idx)}
                          className="cursor-pointer"
                        >
                          {selectedCopyIndex === idx ? (
                            <Check className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
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
                              className="mt-2 text-xs text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
                            >
                              <Eye className="w-3 h-3" />
                              查看完整文案
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">发布平台</label>
                <div className="flex flex-wrap gap-2">
                  {PLATFORMS.map((platform) => (
                    <label
                      key={platform}
                      className={`px-4 py-2 rounded-lg border-2 cursor-pointer transition-all ${
                        selectedPlatforms.includes(platform)
                          ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
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
                  取消选择
                </button>
                <button
                  onClick={handlePublish}
                  disabled={loading || selectedPlatforms.length === 0}
                  className={`flex-1 px-4 py-2 rounded-lg flex items-center justify-center gap-2 transition-colors ${
                    loading || selectedPlatforms.length === 0
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : 'bg-indigo-600 text-white hover:bg-indigo-700'
                  }`}
                >
                  {loading ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      发布中...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" />
                      发布到 {selectedPlatforms.length > 0 ? selectedPlatforms.join(', ') : '平台'}
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
              alt="预览"
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
            <h3 className="text-lg font-semibold text-gray-900 mb-4">文案预览</h3>
            <div className="prose prose-sm max-w-none">
              <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">{previewCopy}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
