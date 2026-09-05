import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Plus, Edit2, Trash2, X, Clock, Zap, RefreshCw } from 'lucide-react';
import type { ScheduledTask, TaskCreate, PaginatedResponse } from '@/api/tasks';
import { getTasks, getTask, createTask, updateTask, deleteTask } from '@/api/tasks';
import { getProducts, type Product } from '@/api/products';
import { useBrandContext } from '@/context/BrandContext';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import { LIMITS, alertValidationErrors } from '@/lib/formValidation';
import { toast, confirmDialog } from '@/lib/feedback';
import { useValidators } from '@/i18n/helpers';
import { useI18n } from '@/i18n/useI18n';
import Pagination from '@/components/Pagination';
import ListSkeleton from '@/components/ListSkeleton';
import ListLoadingOverlay from '@/components/ListLoadingOverlay';
import ImageModelPicker from '@/components/ImageModelPicker';
import ImageGenerationControls from '@/components/ImageGenerationControls';
import { DEFAULT_IMAGE_GENERATION_CONTROLS } from '@/lib/imageGenerationControls';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import FieldRequirementBadge from '@/components/FieldRequirementBadge';
import HelpTooltip from '@/components/HelpTooltip';
import TaskProductPicker, { TaskProductPickerLabel } from '@/components/TaskProductPicker';
import PlatformIcon from '@/components/icons/PlatformIcon';
import type { PlatformId } from '@/components/icons/PlatformIcon';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];

export default function TaskConfiguration() {
  const { t } = useI18n();
  const { activeBrandId, brands, setBrandFilterLoading, brandFilterLoading } = useBrandContext();
  const { required, maxLen, cronFormat, intInRange } = useValidators();
  const [searchParams, setSearchParams] = useSearchParams();
  const openedTaskFromUrlRef = useRef<string | null>(null);
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [pickerProducts, setPickerProducts] = useState<Product[]>([]);
  const [loadingPickerProducts, setLoadingPickerProducts] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [selectedTask, setSelectedTask] = useState<ScheduledTask | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [listBusy, setListBusy] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<TaskCreate>({
    name: '',
    cron: '0 10 * * *',
    mode: 'auto',
    target_categories: [],
    target_products: [],
    platforms: ['instagram'],
    reference_image_count: 2,
    run_count_per_execution: 1,
    generate_image_count: 3,
    generate_copy_count: 3,
    enabled: true,
    use_scene_reference: DEFAULT_IMAGE_GENERATION_CONTROLS.use_scene_reference,
    use_vision_image_prompt: DEFAULT_IMAGE_GENERATION_CONTROLS.use_vision_image_prompt,
    realistic_placement: DEFAULT_IMAGE_GENERATION_CONTROLS.realistic_placement,
    image_provider_id: null,
    image_provider_mode: null as 'platform' | 'byok' | null,
    image_model: null,
    image_size: '2048x2048',
    notify_on_publish: true,
  });

  useEffect(() => {
    setInitialLoading(true);
    void loadTasks(1);
  }, [activeBrandId]);

  useEffect(() => {
    const taskId = searchParams.get('task');
    if (!taskId || initialLoading || openedTaskFromUrlRef.current === taskId) return;

    const openFromUrl = async () => {
      let task = tasks.find((tk) => tk.task_id === taskId);
      if (!task) {
        try {
          task = await getTask(taskId);
        } catch (error) {
          console.error('Failed to load task from URL:', error);
          return;
        }
      }
      openedTaskFromUrlRef.current = taskId;
      openModal(task);
    };

    void openFromUrl();
  }, [searchParams, tasks, initialLoading]);

  const closeModal = () => {
    setShowModal(false);
    resetForm();
    if (searchParams.get('task')) {
      const next = new URLSearchParams(searchParams);
      next.delete('task');
      setSearchParams(next, { replace: true });
      openedTaskFromUrlRef.current = null;
    }
  };

  const loadPickerProducts = async () => {
    setLoadingPickerProducts(true);
    try {
      const data = await cachedFetch('products:list:500:all', async () => {
        const response = await getProducts(1, 500);
        return response.data;
      });
      setPickerProducts(data);
    } catch (error) {
      console.error('Failed to load products for picker:', error);
    } finally {
      setLoadingPickerProducts(false);
    }
  };

  const loadTasks = async (
    page: number = currentPage,
    newPageSize?: number,
    opts?: { keepRows?: boolean }
  ) => {
    const keepRows = Boolean(opts?.keepRows);
    if (keepRows) setListBusy(true);
    const size = newPageSize ?? pageSize;
    try {
      const response: PaginatedResponse<ScheduledTask> = await getTasks(page, size);
      setTasks(response.data);
      setTotal(response.pagination.total);
      setCurrentPage(response.pagination.current);
      if (newPageSize) {
        setPageSize(newPageSize);
      }
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      if (keepRows) setListBusy(false);
      setInitialLoading(false);
      setBrandFilterLoading(false);
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    void loadTasks(1, newPageSize, { keepRows: true });
  };

  const resetForm = () => {
    setFormData({
      name: '',
      cron: '0 10 * * *',
      mode: 'auto',
      target_categories: [],
      target_products: [],
      platforms: ['instagram'],
      reference_image_count: 1,
      run_count_per_execution: 1,
      generate_image_count: 3,
      generate_copy_count: 3,
      enabled: true,
      use_scene_reference: DEFAULT_IMAGE_GENERATION_CONTROLS.use_scene_reference,
      use_vision_image_prompt: DEFAULT_IMAGE_GENERATION_CONTROLS.use_vision_image_prompt,
      realistic_placement: DEFAULT_IMAGE_GENERATION_CONTROLS.realistic_placement,
      image_provider_id: null,
      image_provider_mode: null,
      image_model: null,
      image_size: '2048x2048',
      notify_on_publish: true,
    });
    setSelectedTask(null);
    setIsEdit(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: Array<string | null> = [
      required(t('tasks.taskName'), formData.name),
      maxLen(t('tasks.taskName'), formData.name, LIMITS.taskName),
      cronFormat(formData.cron),
      formData.target_products.length === 0 ? t('tasks.selectProductsLabel') : null,
      intInRange(
        t('tasks.referenceImageCount'),
        formData.reference_image_count,
        LIMITS.referenceImageCount.min,
        LIMITS.referenceImageCount.max
      ),
    ];
    if (formData.mode === 'auto') {
      if (formData.platforms.length === 0) errors.push(t('tasks.selectPlatformRequired'));
      errors.push(
        intInRange(
          t('tasks.runCount'),
          formData.run_count_per_execution,
          LIMITS.runCount.min,
          LIMITS.runCount.max
        )
      );
    } else {
      errors.push(
        intInRange(
          t('tasks.generateImageCount'),
          formData.generate_image_count,
          LIMITS.generateImageCount.min,
          LIMITS.generateImageCount.max
        ),
        intInRange(
          t('tasks.generateCopyCount'),
          formData.generate_copy_count,
          LIMITS.generateCopyCount.min,
          LIMITS.generateCopyCount.max
        )
      );
    }
    if (alertValidationErrors(errors)) return;

    setSaving(true);
    try {
      const payload: TaskCreate = {
        ...formData,
        notify_on_publish: formData.mode === 'auto' ? Boolean(formData.notify_on_publish) : false,
      };
      if (isEdit && selectedTask) {
        const updated = await updateTask(selectedTask.task_id, payload);
        setTasks((prev) => prev.map((t) => (t.task_id === updated.task_id ? updated : t)));
        invalidateCache('tasks');
      } else {
        const created = await createTask(payload);
        invalidateCache('tasks');
        if (currentPage === 1) {
          setTasks((prev) => [created, ...prev].slice(0, pageSize));
          setTotal((t) => t + 1);
        } else {
          setTotal((t) => t + 1);
          void loadTasks(currentPage);
        }
      }
      closeModal();
    } catch (error) {
      console.error('Failed to save task:', error);
      toast.error(t('tasks.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (taskId: string) => {
    const ok = await confirmDialog({
      message: t('tasks.confirmDelete'),
      danger: true,
    });
    if (!ok) return;
    setDeletingId(taskId);
    try {
      await deleteTask(taskId);
      invalidateCache('tasks');
      const remaining = tasks.length - 1;
      setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
      setTotal((t) => Math.max(0, t - 1));
      if (remaining <= 0 && currentPage > 1) {
        void loadTasks(currentPage - 1);
      }
    } catch (error) {
      console.error('Failed to delete task:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const openModal = (task?: ScheduledTask) => {
    void loadPickerProducts();
    if (task) {
      setIsEdit(true);
      setSelectedTask(task);
      setFormData({
        name: task.name,
        cron: task.cron,
        mode: task.mode,
        target_categories: task.target_categories || [],
        target_products: task.target_products || [],
        platforms: task.platforms || ['instagram'],
        reference_image_count: task.reference_image_count,
        run_count_per_execution: task.run_count_per_execution,
        generate_image_count: task.generate_image_count || 3,
        generate_copy_count: task.generate_copy_count || 3,
        enabled: task.enabled,
        use_scene_reference: task.use_scene_reference || false,
        use_vision_image_prompt: task.use_vision_image_prompt || false,
        realistic_placement: task.realistic_placement ?? DEFAULT_IMAGE_GENERATION_CONTROLS.realistic_placement,
        image_provider_id: task.image_provider_id || null,
        image_provider_mode: (task.image_provider_mode as 'platform' | 'byok' | null) || null,
        image_model: task.image_model || null,
        image_size: task.image_size || '2048x2048',
        notify_on_publish: task.notify_on_publish ?? true,
      });
    } else {
      setIsEdit(false);
      setSelectedTask(null);
      setFormData({
        name: '',
        cron: '0 10 * * *',
        mode: 'auto',
        target_categories: [],
        target_products: [],
        platforms: ['instagram'],
        reference_image_count: 1,
        run_count_per_execution: 1,
        generate_image_count: 3,
        generate_copy_count: 3,
        enabled: true,
        use_scene_reference: DEFAULT_IMAGE_GENERATION_CONTROLS.use_scene_reference,
        use_vision_image_prompt: DEFAULT_IMAGE_GENERATION_CONTROLS.use_vision_image_prompt,
        realistic_placement: DEFAULT_IMAGE_GENERATION_CONTROLS.realistic_placement,
        image_provider_id: null,
        image_provider_mode: null,
        image_model: null,
        image_size: '2048x2048',
        notify_on_publish: true,
      });
    }
    setShowModal(true);
  };

  const formatCron = (cron: string) => {
    const parts = cron.split(' ');
    if (parts.length >= 5) {
      return t('tasks.cronDisplay', {
        day: parts[2],
        hour: parts[1],
        minute: parts[0].padStart(2, '0'),
      });
    }
    return cron;
  };

  const formatPlatformList = (platforms: string[] | undefined) =>
    (platforms || []).map((platform) => t(`platforms.${platform}`)).join(', ');

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{t('tasks.title')}</h2>
          <p className="text-gray-500 mt-1">{t('tasks.subtitle')}</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => openModal()}
            className="flex items-center gap-2 bg-forge-600 text-white px-4 py-2 rounded-lg hover:bg-forge-700 transition-colors"
          >
            <Plus className="w-5 h-5" />
            {t('tasks.addTask')}
          </button>
        </div>
      </div>

      <div className={`relative ${listBusy ? 'opacity-60 pointer-events-none' : ''}`}>
        {listBusy && <ListLoadingOverlay message={t('tasks.updatingList')} />}
      <div className="grid grid-cols-1 gap-4">
        {tasks.map((task) => (
          <div
            key={task.task_id}
            className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 hover:shadow-md transition-shadow"
          >
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="font-semibold text-gray-900">{task.name}</h3>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    task.enabled
                      ? 'bg-green-100 text-green-700'
                      : 'bg-gray-100 text-gray-500'
                  }`}>
                    {task.enabled ? t('tasks.running') : t('tasks.disabled')}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    task.mode === 'auto'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}>
                    {task.mode === 'auto' ? t('tasks.autoPublish') : t('tasks.manualPublish')}
                  </span>
                </div>
                <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    {formatCron(task.cron)}
                  </span>
                  {((task.target_products || []).length > 0) ? (
                    <span>{t('tasks.productsCount', { count: (task.target_products || []).length })}</span>
                  ) : (
                    <span>{t('tasks.categories', { list: (task.target_categories || []).join(', ') })}</span>
                  )}
                  {task.mode === 'auto' && (
                    <span>{t('tasks.platforms', { list: formatPlatformList(task.platforms) })}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-3 mt-3">
                  <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                    {t('tasks.referenceImages', { count: task.reference_image_count })}
                  </span>
                  {task.mode === 'auto' && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                      {t('tasks.runsPerRound', { count: task.run_count_per_execution })}
                    </span>
                  )}
                  {task.mode === 'manual' && (
                    <>
                      <span className="px-2 py-1 bg-amber-50 text-amber-600 rounded text-xs">
                        {t('tasks.imagesPerRun', { count: task.generate_image_count })}
                      </span>
                      <span className="px-2 py-1 bg-amber-50 text-amber-600 rounded text-xs">
                        {t('tasks.copiesPerRun', { count: task.generate_copy_count })}
                      </span>
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => openModal(task)}
                  className="p-2 text-gray-500 hover:text-forge-600 hover:bg-forge-50 rounded-lg"
                >
                  <Edit2 className="w-5 h-5" />
                </button>
                  <button
                  onClick={() => handleDelete(task.task_id)}
                  disabled={deletingId === task.task_id}
                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-50"
                >
                  {deletingId === task.task_id ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <Trash2 className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>
          </div>
        ))}

        {initialLoading && tasks.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-3" role="status" aria-live="polite">
            <div className="flex items-center gap-2 text-sm font-medium text-forge-800">
              <div className="w-5 h-5 border-2 border-forge-600 border-t-transparent rounded-full animate-spin shrink-0" />
              <span>{brandFilterLoading ? t('tasks.loadingTasks') : t('common.loading')}</span>
            </div>
            <ListSkeleton rows={3} />
          </div>
        ) : tasks.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <Zap className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">{t('tasks.noTasks')}</p>
          </div>
        ) : null}
        
        {total > 0 && (
          <div className="mt-4">
            <Pagination
              current={currentPage}
              total={total}
              pageSize={pageSize}
              disabled={listBusy}
              onChange={(page) => void loadTasks(page, undefined, { keepRows: true })}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        )}
      </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                {isEdit ? t('tasks.editTask') : t('tasks.addTask')}
              </h3>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <LabelWithTooltip
                  label={t('tasks.taskName')}
                  tooltip={t('tasks.tooltips.taskName')}
                  required
                />
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                  required
                  maxLength={LIMITS.taskName}
                  placeholder={t('placeholders.tasks.name')}
                />
              </div>

              <div>
                <LabelWithTooltip
                  label={t('tasks.taskMode')}
                  tooltip={t('tasks.tooltips.taskMode')}
                  required
                />
                <div className="flex gap-4">
                  <label
                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-all ${
                      formData.mode === 'auto'
                        ? 'border-forge-600 bg-forge-50 text-forge-700'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      checked={formData.mode === 'auto'}
                      onChange={() => setFormData({ ...formData, mode: 'auto' })}
                      className="sr-only"
                    />
                    <Clock className="w-4 h-4" />
                    {t('tasks.autoPublish')}
                  </label>
                  <label
                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-all ${
                      formData.mode === 'manual'
                        ? 'border-amber-600 bg-amber-50 text-amber-700'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      checked={formData.mode === 'manual'}
                      onChange={() => setFormData({ ...formData, mode: 'manual' })}
                      className="sr-only"
                    />
                    <Zap className="w-4 h-4" />
                    {t('tasks.manualPublish')}
                  </label>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  {formData.mode === 'auto' 
                    ? t('tasks.autoDesc')
                    : t('tasks.manualDesc')}
                </p>
              </div>

              <div>
                <LabelWithTooltip
                  label={t('tasks.cronExpression')}
                  tooltip={t('tasks.tooltips.cronExpression')}
                  required
                />
                <p className="mb-1 text-xs text-gray-400">{t('tasks.cronHint')}</p>
                <input
                  type="text"
                  value={formData.cron}
                  onChange={(e) => setFormData({ ...formData, cron: e.target.value })}
                  className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent ${
                    formData.cron.split(' ').filter(Boolean).length !== 5 ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder={t('placeholders.tasks.cron')}
                  required
                  maxLength={LIMITS.cron}
                />
                {formData.cron.split(' ').filter(Boolean).length !== 5 && formData.cron && (
                  <p className="text-red-500 text-xs mt-1">{t('tasks.cronInvalid')}</p>
                )}
              </div>

              <div>
                <TaskProductPickerLabel />
                <p className="mb-2 text-xs text-gray-500">{t('tasks.multiProductHint')}</p>
                {loadingPickerProducts ? (
                  <div className="flex items-center justify-center rounded-lg border border-gray-200 py-10">
                    <div className="h-6 w-6 animate-spin rounded-full border-2 border-forge-600 border-t-transparent" />
                  </div>
                ) : (
                  <TaskProductPicker
                    products={pickerProducts}
                    brands={brands}
                    selectedIds={formData.target_products}
                    onChange={(target_products) => setFormData({ ...formData, target_products })}
                    error={
                      formData.target_products.length === 0 && pickerProducts.length > 0
                        ? t('tasks.selectProductRequired')
                        : undefined
                    }
                  />
                )}
              </div>

              {formData.mode === 'auto' && (
                <div>
                  <LabelWithTooltip
                    label={t('fields.publishPlatformsLabel')}
                    tooltip={t('tasks.tooltips.publishPlatforms')}
                    required
                  />
                  <div className="flex flex-wrap gap-2">
                    {PLATFORMS.map((platform) => {
                      const selected = formData.platforms.includes(platform);
                      return (
                      <label
                        key={platform}
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm cursor-pointer transition-all ${
                          selected
                            ? 'bg-forge-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={(e) => {
                            const platforms = formData.platforms.filter(p => p !== platform);
                            if (e.target.checked) platforms.push(platform);
                            setFormData({ ...formData, platforms });
                          }}
                          className="sr-only"
                        />
                        <PlatformIcon
                          platform={platform as PlatformId}
                          size={14}
                          variant={selected ? 'mono' : 'brand'}
                          className={selected ? 'text-white' : ''}
                        />
                        {t(`platforms.${platform}`)}
                      </label>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <LabelWithTooltip
                    label={t('tasks.referenceImageCount')}
                    tooltip={t('tasks.tooltips.referenceImageCount')}
                    required
                  />
                  <input
                    type="number"
                    value={formData.reference_image_count}
                    onChange={(e) => setFormData({ ...formData, reference_image_count: parseInt(e.target.value) || 1 })}
                    min="1"
                    max="10"
                    placeholder={t('placeholders.tasks.referenceImageCount')}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                  />
                </div>
                {formData.mode === 'auto' ? (
                  <div>
                    <LabelWithTooltip
                      label={t('tasks.runCount')}
                      tooltip={t('tasks.tooltips.runCount')}
                      required
                    />
                    <input
                      type="number"
                      value={formData.run_count_per_execution}
                      onChange={(e) => setFormData({ ...formData, run_count_per_execution: parseInt(e.target.value) || 1 })}
                      min="1"
                      max="5"
                      placeholder={t('placeholders.tasks.runCount')}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500 focus:border-transparent"
                    />
                    <p className="text-xs text-gray-500 mt-1">{t('tasks.runCoversAll')}</p>
                  </div>
                ) : (
                  <div>
                    <LabelWithTooltip
                      label={t('tasks.generateImageCount')}
                      tooltip={t('tasks.tooltips.generateImageCount')}
                      required
                    />
                    <input
                      type="number"
                      value={formData.generate_image_count}
                      onChange={(e) => setFormData({ ...formData, generate_image_count: parseInt(e.target.value) || 1 })}
                      min="1"
                      max="10"
                      placeholder={t('placeholders.tasks.generateImageCount')}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    />
                  </div>
                )}
              </div>

              {formData.mode === 'manual' && (
                <div>
                  <LabelWithTooltip
                    label={t('tasks.generateCopyCount')}
                    tooltip={t('tasks.tooltips.generateCopyCount')}
                    required
                  />
                  <input
                    type="number"
                    value={formData.generate_copy_count}
                    onChange={(e) => setFormData({ ...formData, generate_copy_count: parseInt(e.target.value) || 1 })}
                    min="1"
                    max="10"
                    placeholder={t('placeholders.tasks.generateCopyCount')}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
              )}

              <ImageGenerationControls
                value={{
                  use_scene_reference: formData.use_scene_reference || false,
                  use_vision_image_prompt: formData.use_vision_image_prompt || false,
                  realistic_placement:
                    formData.realistic_placement ??
                    DEFAULT_IMAGE_GENERATION_CONTROLS.realistic_placement,
                  reference_count: formData.reference_image_count ?? DEFAULT_IMAGE_GENERATION_CONTROLS.reference_count,
                }}
                showCompareToggle={false}
                onChange={(next) =>
                  setFormData({
                    ...formData,
                    use_scene_reference: next.use_scene_reference,
                    use_vision_image_prompt: next.use_vision_image_prompt,
                    realistic_placement: next.realistic_placement,
                  })
                }
              />

              <div>
                <LabelWithTooltip
                  label={t('fields.imageModel')}
                  tooltip={t('tasks.tooltips.imageModel')}
                  required={false}
                />
                <ImageModelPicker
                  compact
                  value={{
                    image_provider_id: formData.image_provider_id,
                    image_model: formData.image_model,
                    image_size: formData.image_size,
                    image_provider_mode: formData.image_provider_mode,
                  }}
                  onChange={(next) =>
                    setFormData({
                      ...formData,
                      image_provider_id: next.image_provider_id ?? null,
                      image_model: next.image_model ?? null,
                      image_size: next.image_size ?? '2048x2048',
                      image_provider_mode: next.image_provider_mode ?? null,
                    })
                  }
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="w-4 h-4 text-forge-600 rounded"
                  id="task-enabled"
                />
                <label htmlFor="task-enabled" className="flex items-center gap-1.5 text-sm font-medium text-gray-700">
                  {t('tasks.enableTask')}
                  <FieldRequirementBadge required={false} />
                  <HelpTooltip content={t('tasks.tooltips.enableTask')} />
                </label>
              </div>

              {formData.mode === 'auto' && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.notify_on_publish ?? true}
                    onChange={(e) =>
                      setFormData({ ...formData, notify_on_publish: e.target.checked })
                    }
                    className="w-4 h-4 text-forge-600 rounded"
                    id="task-notify-email"
                  />
                  <label htmlFor="task-notify-email" className="flex items-center gap-1.5 text-sm font-medium text-gray-700">
                    {t('tasks.notifyOnPublish')}
                    <FieldRequirementBadge required={false} />
                    <HelpTooltip content={t('tasks.tooltips.notifyOnPublish')} />
                  </label>
                </div>
              )}

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={saving}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? t('common.saving') : isEdit ? t('common.save') : t('tasks.createTask')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
