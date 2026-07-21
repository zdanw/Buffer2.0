import { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, X, Clock, Zap, ChevronDown, ChevronRight } from 'lucide-react';
import type { ScheduledTask, TaskCreate, PaginatedResponse } from '@/api/tasks';
import { getTasks, createTask, updateTask, deleteTask } from '@/api/tasks';
import { getCategories, getProducts, type Product } from '@/api/products';
import { cachedFetch, invalidateCache } from '@/lib/staticCache';
import {
  LIMITS,
  alertValidationErrors,
  cronFormat,
  intInRange,
  maxLen,
  required,
} from '@/lib/formValidation';
import Pagination from '@/components/Pagination';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'];

export default function TaskConfiguration() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [selectedTask, setSelectedTask] = useState<ScheduledTask | null>(null);
  const [expandedCategories, setExpandedCategories] = useState<string[]>([]);
  const [currentPage, setCurrentPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [listBusy, setListBusy] = useState(false);
  const [formData, setFormData] = useState<TaskCreate>({
    name: '',
    cron: '0 10 * * *',
    mode: 'auto',
    target_categories: [],
    target_products: [],
    platforms: ['instagram'],
    reference_image_count: 3,
    run_count_per_execution: 1,
    generate_image_count: 3,
    generate_copy_count: 3,
    enabled: true,
    use_scene_reference: false,
  });

  useEffect(() => {
    void Promise.all([loadTasks(1), loadCategories(), loadProducts()]);
  }, []);

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
    }
  };

  const handlePageSizeChange = (newPageSize: number) => {
    void loadTasks(1, newPageSize, { keepRows: true });
  };

  const loadCategories = async () => {
    try {
      const data = await cachedFetch('categories', async () => {
        const cats = await getCategories();
        return cats;
      });
      setCategories(data);
    } catch (error) {
      console.error('Failed to load categories:', error);
    }
  };

  const loadProducts = async () => {
    try {
      const data = await cachedFetch('products:list:100', async () => {
        const response = await getProducts(1, 100);
        return response.data;
      });
      setProducts(data);
    } catch (error) {
      console.error('Failed to load products:', error);
    }
  };

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev =>
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  const getProductsByCategory = (category: string) => {
    return products.filter(p => p.category === category);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      cron: '0 10 * * *',
      mode: 'auto',
      target_categories: [],
      target_products: [],
      platforms: ['instagram'],
      reference_image_count: 3,
      run_count_per_execution: 1,
      generate_image_count: 3,
      generate_copy_count: 3,
      enabled: true,
      use_scene_reference: false,
    });
    setSelectedTask(null);
    setIsEdit(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors: Array<string | null> = [
      required('任务名称', formData.name),
      maxLen('任务名称', formData.name, LIMITS.taskName),
      cronFormat(formData.cron),
      formData.target_products.length === 0 ? '请至少选择一个目标产品' : null,
      intInRange(
        '参考图数量',
        formData.reference_image_count,
        LIMITS.referenceImageCount.min,
        LIMITS.referenceImageCount.max
      ),
    ];
    if (formData.mode === 'auto') {
      if (formData.platforms.length === 0) errors.push('自动模式请至少选择一个发布平台');
      errors.push(
        intInRange(
          '运行次数',
          formData.run_count_per_execution,
          LIMITS.runCount.min,
          LIMITS.runCount.max
        )
      );
    } else {
      errors.push(
        intInRange(
          '生成图片数量',
          formData.generate_image_count,
          LIMITS.generateImageCount.min,
          LIMITS.generateImageCount.max
        ),
        intInRange(
          '生成文案数量',
          formData.generate_copy_count,
          LIMITS.generateCopyCount.min,
          LIMITS.generateCopyCount.max
        )
      );
    }
    if (alertValidationErrors(errors)) return;

    try {
      if (isEdit && selectedTask) {
        const updated = await updateTask(selectedTask.task_id, formData);
        setTasks((prev) => prev.map((t) => (t.task_id === updated.task_id ? updated : t)));
        invalidateCache('tasks');
      } else {
        const created = await createTask(formData);
        invalidateCache('tasks');
        if (currentPage === 1) {
          setTasks((prev) => [created, ...prev].slice(0, pageSize));
          setTotal((t) => t + 1);
        } else {
          setTotal((t) => t + 1);
          void loadTasks(currentPage);
        }
      }
      setShowModal(false);
      resetForm();
    } catch (error) {
      console.error('Failed to save task:', error);
      alert('保存失败，请检查输入后重试');
    }
  };

  const handleDelete = async (taskId: string) => {
    if (confirm('确定删除该任务吗？')) {
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
      }
    }
  };

  const openModal = (task?: ScheduledTask) => {
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
        reference_image_count: 3,
        run_count_per_execution: 1,
        generate_image_count: 3,
        generate_copy_count: 3,
        enabled: true,
        use_scene_reference: false,
      });
    }
    setShowModal(true);
  };

  const formatCron = (cron: string) => {
    const parts = cron.split(' ');
    if (parts.length >= 5) {
      return `${parts[2]}日 ${parts[1]}:${parts[0].padStart(2, '0')}`;
    }
    return cron;
  };

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">任务配置</h2>
          <p className="text-gray-500 mt-1">管理定时发布任务</p>
        </div>
        <button
          onClick={() => openModal()}
          className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition-colors"
        >
          <Plus className="w-5 h-5" />
          添加任务
        </button>
      </div>

      <div className={`grid grid-cols-1 gap-4 ${listBusy ? 'opacity-70 pointer-events-none' : ''}`}>
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
                    {task.enabled ? '运行中' : '已禁用'}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    task.mode === 'auto'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}>
                    {task.mode === 'auto' ? '自动发布' : '手动发布'}
                  </span>
                </div>
                <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                  <span className="flex items-center gap-1">
                    <Clock className="w-4 h-4" />
                    {formatCron(task.cron)}
                  </span>
                  {((task.target_products || []).length > 0) ? (
                    <span>产品: {(task.target_products || []).length} 个</span>
                  ) : (
                    <span>分类: {(task.target_categories || []).join(', ')}</span>
                  )}
                  {task.mode === 'auto' && (
                    <span>平台: {(task.platforms || []).join(', ')}</span>
                  )}
                </div>
                <div className="flex flex-wrap gap-3 mt-3">
                  <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                    参考图: {task.reference_image_count}
                  </span>
                  {task.mode === 'auto' && (
                    <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs">
                      每次运行: {task.run_count_per_execution} 次
                    </span>
                  )}
                  {task.mode === 'manual' && (
                    <>
                      <span className="px-2 py-1 bg-amber-50 text-amber-600 rounded text-xs">
                        生成图片: {task.generate_image_count} 张
                      </span>
                      <span className="px-2 py-1 bg-amber-50 text-amber-600 rounded text-xs">
                        生成文案: {task.generate_copy_count} 条
                      </span>
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button
                  onClick={() => openModal(task)}
                  className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg"
                >
                  <Edit2 className="w-5 h-5" />
                </button>
                <button
                  onClick={() => handleDelete(task.task_id)}
                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-lg"
                >
                  <Trash2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        ))}

        {tasks.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-12 text-center">
            <Zap className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">暂无定时任务，点击上方按钮创建</p>
          </div>
        )}
        
        {total > 0 && (
          <div className="mt-4">
            <Pagination
              current={currentPage}
              total={total}
              pageSize={pageSize}
              onChange={(page) => void loadTasks(page, undefined, { keepRows: true })}
              onPageSizeChange={handlePageSizeChange}
            />
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">
                {isEdit ? '编辑任务' : '添加任务'}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">任务名称</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  required
                  maxLength={LIMITS.taskName}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">任务模式</label>
                <div className="flex gap-4">
                  <label
                    className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-all ${
                      formData.mode === 'auto'
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-700'
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
                    自动发布
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
                    手动发布
                  </label>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  {formData.mode === 'auto' 
                    ? '系统按CRON定时生成内容并自动发布到平台'
                    : '系统按CRON定时生成候选内容，保存到待发布列表等待审核'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  CRON 表达式
                  <span className="text-gray-400 font-normal ml-2">格式: 分 时 日 月 周</span>
                </label>
                <input
                  type="text"
                  value={formData.cron}
                  onChange={(e) => setFormData({ ...formData, cron: e.target.value })}
                  className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent ${
                    formData.cron.split(' ').filter(Boolean).length !== 5 ? 'border-red-500' : 'border-gray-300'
                  }`}
                  placeholder="0 10 * * *"
                  required
                  maxLength={LIMITS.cron}
                />
                {formData.cron.split(' ').filter(Boolean).length !== 5 && formData.cron && (
                  <p className="text-red-500 text-xs mt-1">CRON 表达式格式错误，需要5个字段: 分 时 日 月 周</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">选择产品</label>
                <p className="text-xs text-gray-500 mb-2">选择具体产品（优先）或选择分类</p>
                {products.length > 0 ? (
                  <div className="space-y-2">
                    {categories.map((category) => {
                      const categoryProducts = getProductsByCategory(category);
                      const isExpanded = expandedCategories.includes(category);
                      
                      return (
                        <div key={category} className="border border-gray-200 rounded-lg overflow-hidden">
                          <button
                            type="button"
                            onClick={() => toggleCategory(category)}
                            className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4 text-gray-500" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-gray-500" />
                              )}
                              <span className="font-medium text-gray-700">{category}</span>
                              <span className="text-sm text-gray-500">({categoryProducts.length} 个产品)</span>
                            </div>
                          </button>
                          {isExpanded && (
                            <div className="p-2 bg-white">
                              <div className="flex flex-wrap gap-2">
                                {categoryProducts.map((product) => (
                                  <label
                                    key={product.product_id}
                                    className={`px-3 py-1 rounded-full text-sm cursor-pointer transition-all ${
                                      formData.target_products.includes(product.product_id)
                                        ? 'bg-indigo-600 text-white'
                                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                    }`}
                                  >
                                    <input
                                      type="checkbox"
                                      checked={formData.target_products.includes(product.product_id)}
                                      onChange={() => {
                                        const newProducts = formData.target_products.includes(product.product_id)
                                          ? formData.target_products.filter(id => id !== product.product_id)
                                          : [...formData.target_products, product.product_id];
                                        setFormData({ ...formData, target_products: newProducts });
                                      }}
                                      className="sr-only"
                                    />
                                    {product.product_name}
                                  </label>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-gray-400 text-sm py-2">
                    暂无可用产品，请先在素材管理中添加产品
                  </div>
                )}
                {(formData.target_products.length === 0) && products.length > 0 && (
                  <p className="text-red-500 text-xs mt-1">请至少选择一个产品</p>
                )}
              </div>

              {formData.mode === 'auto' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">发布平台</label>
                  <div className="flex flex-wrap gap-2">
                    {PLATFORMS.map((platform) => (
                      <label
                        key={platform}
                        className={`px-3 py-1 rounded-full text-sm cursor-pointer transition-all ${
                          formData.platforms.includes(platform)
                            ? 'bg-indigo-600 text-white'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={formData.platforms.includes(platform)}
                          onChange={(e) => {
                            const platforms = formData.platforms.filter(p => p !== platform);
                            if (e.target.checked) platforms.push(platform);
                            setFormData({ ...formData, platforms });
                          }}
                          className="sr-only"
                        />
                        {platform}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">参考图数量</label>
                  <input
                    type="number"
                    value={formData.reference_image_count}
                    onChange={(e) => setFormData({ ...formData, reference_image_count: parseInt(e.target.value) || 1 })}
                    min="1"
                    max="10"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                {formData.mode === 'auto' ? (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">运行次数</label>
                    <input
                      type="number"
                      value={formData.run_count_per_execution}
                      onChange={(e) => setFormData({ ...formData, run_count_per_execution: parseInt(e.target.value) || 1 })}
                      min="1"
                      max="5"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>
                ) : (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">生成图片数量</label>
                    <input
                      type="number"
                      value={formData.generate_image_count}
                      onChange={(e) => setFormData({ ...formData, generate_image_count: parseInt(e.target.value) || 1 })}
                      min="1"
                      max="10"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                    />
                  </div>
                )}
              </div>

              {formData.mode === 'manual' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">生成文案数量</label>
                  <input
                    type="number"
                    value={formData.generate_copy_count}
                    onChange={(e) => setFormData({ ...formData, generate_copy_count: parseInt(e.target.value) || 1 })}
                    min="1"
                    max="10"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 focus:border-transparent"
                  />
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.enabled}
                  onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                  className="w-4 h-4 text-indigo-600 rounded"
                />
                <label className="text-sm font-medium text-gray-700">启用任务</label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={formData.use_scene_reference || false}
                  onChange={(e) => setFormData({ ...formData, use_scene_reference: e.target.checked })}
                  className="w-4 h-4 text-indigo-600 rounded"
                />
                <label className="text-sm font-medium text-gray-700">启用场景参考图</label>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  {isEdit ? '保存修改' : '创建任务'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
