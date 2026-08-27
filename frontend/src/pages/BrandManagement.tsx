import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Plus, Edit2, Trash2, X, RefreshCw, Lock, Upload } from 'lucide-react';
import {
  createBrand,
  deleteBrand,
  getBrand,
  getBrands,
  uploadBrandLogo,
  BEBCARE_BRAND_ID,
  type BrandKit,
  type BrandSummary,
  type BrandCreate,
} from '@/api/brands';
import { listBufferAccounts, type BufferAccount } from '@/api/bufferAccounts';
import BrandBadge from '@/components/BrandBadge';
import BrandAvatar from '@/components/BrandAvatar';
import LabelWithTooltip from '@/components/LabelWithTooltip';
import SetupFlowCallout from '@/components/SetupFlowCallout';
import {
  clearBrandFormDraft,
  loadBrandFormDraft,
  saveBrandFormDraft,
  type BrandFormDraft,
} from '@/lib/formDraft';
import { LIMITS, alertValidationErrors, createValidators } from '@/lib/formValidation';
import { toast, confirmDialog } from '@/lib/feedback';
import { useI18n } from '@/i18n/useI18n';
import { useBrandContext } from '@/context/BrandContext';

type TabId = 'voice' | 'content' | 'advanced';

const EMPTY_FORM: BrandCreate = {
  name: '',
  voice: '',
  audience: '',
  tone_keywords: '',
  emoji_style: 'moderate',
  words_to_avoid: '',
  logo_in_images: 'preserve',
  buffer_account_id: '',
};

const RETURN_TO_PRODUCT_KEY = 'pulseforge:return-to-product';
const BUFFER_API_HELP_URL = 'https://support.buffer.com/article/984-how-to-create-your-buffer-api-key';

export default function BrandManagement() {
  const { t } = useI18n();
  const v = createValidators(t);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { refreshBrands } = useBrandContext();
  const [brands, setBrands] = useState<BrandSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('voice');
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<BrandCreate & { copy_system_prompt?: string; image_system_prompt?: string }>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [bufferAccounts, setBufferAccounts] = useState<BufferAccount[]>([]);
  const editRequestIdRef = useRef(0);

  const isProtectedBrand = (brand: BrandSummary) =>
    brand.is_generic || brand.brand_id === BEBCARE_BRAND_ID;

  const loadBrands = useCallback(async () => {
    setLoading(true);
    try {
      setBrands(await getBrands());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBrands();
    void listBufferAccounts()
      .then(setBufferAccounts)
      .catch(() => setBufferAccounts([]));
  }, [loadBrands]);

  const refreshBufferAccounts = useCallback(async () => {
    try {
      setBufferAccounts(await listBufferAccounts());
    } catch {
      setBufferAccounts([]);
    }
  }, []);

  const applyBrandDraft = useCallback((draft: BrandFormDraft, bufferAccountId?: string | null) => {
    setIsEdit(draft.isEdit);
    setEditingId(draft.editingId);
    setActiveTab(draft.activeTab as TabId);
    setLogoPreview(draft.logoPreview);
    setLogoFile(null);
    setForm({
      ...EMPTY_FORM,
      ...draft.form,
      buffer_account_id: bufferAccountId || (draft.form.buffer_account_id as string) || '',
    } as typeof form);
    setModalLoading(false);
    setShowModal(true);
  }, []);

  useEffect(() => {
    const resume = searchParams.get('resumeForm');
    const openAdd = searchParams.get('openAdd');
    const bufferAccountId = searchParams.get('bufferAccountId');

    if (resume === '1') {
      const draft = loadBrandFormDraft();
      if (draft) {
        applyBrandDraft(draft, bufferAccountId);
      }
      void refreshBufferAccounts();
      navigate('/brand', { replace: true });
      return;
    }

    if (openAdd === '1') {
      setIsEdit(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
      setLogoPreview(null);
      setLogoFile(null);
      setActiveTab('voice');
      setShowModal(true);
      navigate('/brand', { replace: true });
    }
  }, [searchParams, navigate, applyBrandDraft, refreshBufferAccounts]);

  useEffect(() => {
    if (!showModal || modalLoading) return;
    saveBrandFormDraft({
      form: { ...form },
      activeTab,
      isEdit,
      editingId,
      logoPreview,
    });
  }, [showModal, modalLoading, form, activeTab, isEdit, editingId, logoPreview]);

  const goToBufferSetup = () => {
    saveBrandFormDraft({
      form: { ...form },
      activeTab,
      isEdit,
      editingId,
      logoPreview,
    });
    const url = `${window.location.origin}/buffer-accounts?from=brand&openAdd=1`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  useEffect(() => {
    if (!showModal) return;
    const onFocus = () => void refreshBufferAccounts();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [showModal, refreshBufferAccounts]);

  const goToProductAfterBrandCreate = (brandId: string) => {
    try {
      sessionStorage.removeItem(RETURN_TO_PRODUCT_KEY);
    } catch {
      /* ignore */
    }
    navigate(`/products?resumeForm=1&brandId=${encodeURIComponent(brandId)}`);
  };

  const openCreate = () => {
    setIsEdit(false);
    setEditingId(null);
    setForm(EMPTY_FORM);
    setLogoPreview(null);
    setLogoFile(null);
    setActiveTab('voice');
    setModalLoading(false);
    setShowModal(true);
  };

  const closeModal = () => {
    editRequestIdRef.current += 1;
    setShowModal(false);
    setModalLoading(false);
  };

  const openEdit = async (summary: BrandSummary) => {
    const requestId = ++editRequestIdRef.current;
    setIsEdit(true);
    setEditingId(summary.brand_id);
    setActiveTab('voice');
    setLogoFile(null);
    setModalLoading(true);
    setShowModal(true);
    try {
      const kit: BrandKit = await getBrand(summary.brand_id);
      if (requestId !== editRequestIdRef.current) return;
      setLogoPreview(kit.logo_url || null);
      setForm({
        name: kit.name,
        voice: kit.voice || '',
        audience: kit.audience || '',
        tone_keywords: kit.tone_keywords || '',
        emoji_style: kit.emoji_style || 'moderate',
        words_to_avoid: kit.words_to_avoid || '',
        default_selling_points: kit.default_selling_points,
        default_hashtags: kit.default_hashtags,
        logo_font_rule: kit.logo_font_rule || '',
        logo_in_images: kit.logo_in_images || 'preserve',
        copy_system_prompt: kit.copy_system_prompt || '',
        image_system_prompt: kit.image_system_prompt || '',
        buffer_account_id: kit.buffer_account_id || '',
      });
    } catch (err) {
      if (requestId !== editRequestIdRef.current) return;
      console.error(err);
      toast.error(t('common.loadFailed'));
      setShowModal(false);
    } finally {
      if (requestId === editRequestIdRef.current) {
        setModalLoading(false);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      alertValidationErrors([
        v.required(t('brands.name'), form.name),
        v.maxLen(t('brands.name'), form.name, LIMITS.productName),
        v.maxLen(t('brands.voice'), form.voice, LIMITS.brandVoice),
      ])
    ) {
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        buffer_account_id: form.buffer_account_id || null,
      };
      if (isEdit && editingId) {
        const { updateBrand } = await import('@/api/brands');
        await updateBrand(editingId, payload);
      } else {
        const created = await createBrand(payload);
        if (logoFile) {
          await uploadBrandLogo(created.brand_id, logoFile);
        }
        try {
          if (sessionStorage.getItem(RETURN_TO_PRODUCT_KEY) === '1') {
            await loadBrands();
            await refreshBrands();
            clearBrandFormDraft();
            setShowModal(false);
            goToProductAfterBrandCreate(created.brand_id);
            return;
          }
        } catch {
          /* ignore */
        }
      }
      await loadBrands();
      await refreshBrands();
      try {
        setBufferAccounts(await listBufferAccounts());
      } catch {
        /* keep current list */
      }
      clearBrandFormDraft();
      setShowModal(false);
    } catch (err) {
      console.error(err);
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
            ? String(detail[0].msg)
            : t('common.saveFailed');
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (brand: BrandSummary) => {
    if (isProtectedBrand(brand)) return;
    const ok = await confirmDialog({
      message: t('brands.confirmDelete', { name: brand.name }),
      danger: true,
    });
    if (!ok) return;
    try {
      await deleteBrand(brand.brand_id);
      await loadBrands();
      await refreshBrands();
    } catch (err) {
      console.error(err);
      toast.error(t('common.deleteFailed'));
    }
  };

  const handleLogoChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoFile(file);
    setLogoPreview(URL.createObjectURL(file));
    if (isEdit && editingId) {
      setUploadingLogo(true);
      try {
        const result = await uploadBrandLogo(editingId, file);
        setLogoPreview(result.logo_url);
        setLogoFile(null);
        await loadBrands();
        await refreshBrands();
      } catch (err) {
        console.error(err);
        toast.error(t('brands.logoUploadFailed'));
      } finally {
        setUploadingLogo(false);
      }
    }
  };

  const tabs: { id: TabId; label: string }[] = [
    { id: 'voice', label: t('brands.tabs.voice') },
    { id: 'content', label: t('brands.tabs.content') },
    { id: 'advanced', label: t('brands.tabs.advanced') },
  ];

  const selectableBufferAccounts = bufferAccounts.filter((account) => {
    if (!account.is_active && account.id !== form.buffer_account_id) return false;
    const boundElsewhere = (account.brand_ids || []).some((id) => id !== editingId);
    return !boundElsewhere || account.id === form.buffer_account_id;
  });
  const hasUnboundBufferAccount = bufferAccounts.some(
    (account) =>
      account.is_active &&
      ((account.brand_ids || []).length === 0 ||
        (account.brand_ids || []).every((id) => id === editingId)),
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{t('brands.title')}</h1>
          <p className="text-gray-500 mt-1">{t('brands.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void loadBrands()}
            className="inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            {t('common.refresh')}
          </button>
          <button
            type="button"
            onClick={openCreate}
            className="inline-flex items-center gap-2 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 text-sm"
          >
            <Plus className="w-4 h-4" />
            {t('brands.addBrand')}
          </button>
        </div>
      </div>

      {loading && brands.length === 0 ? (
        <div className="flex justify-center py-16">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-forge-600" />
        </div>
      ) : brands.length === 0 ? (
        <div className="rounded-xl border border-canvas-border bg-white p-8 text-center max-w-lg mx-auto">
          <p className="font-semibold text-ink-900">{t('api.emptyBrandsTitle')}</p>
          <p className="text-sm text-ink-500 mt-2 leading-relaxed">{t('api.emptyBrandsBody')}</p>
          <button
            type="button"
            onClick={openCreate}
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-forge-600 text-white rounded-lg text-sm hover:bg-forge-700"
          >
            <Plus className="w-4 h-4" />
            {t('brands.addBrand')}
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {brands.map((brand) => (
            <div
              key={brand.brand_id}
              className="bg-white rounded-xl border border-canvas-border p-5 shadow-card hover:shadow-card-hover transition-shadow duration-200"
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="flex items-start gap-3 min-w-0">
                  <BrandAvatar
                    name={brand.is_generic ? t('brands.generic') : brand.name}
                    logoUrl={brand.logo_url}
                    size="lg"
                  />
                  <div className="min-w-0">
                    <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                      {brand.is_generic ? t('brands.generic') : brand.name}
                      {brand.is_generic && <Lock className="w-3.5 h-3.5 text-gray-400 shrink-0" aria-label={t('brands.system')} />}
                    </h3>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {brand.is_generic && <BrandBadge variant="generic" />}
                      {brand.is_generic && <BrandBadge variant="system" />}
                      {!brand.buffer_account_id && (
                        <span className="px-2 py-0.5 text-xs rounded-full bg-amber-50 text-amber-700">
                          {t('brands.bufferAccountNone')}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={() => void openEdit(brand)}
                    className="p-2 text-gray-500 hover:text-forge-600 rounded-lg hover:bg-forge-50"
                    aria-label={t('common.edit')}
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  {!isProtectedBrand(brand) && (
                    <button
                      type="button"
                      onClick={() => void handleDelete(brand)}
                      className="p-2 text-gray-500 hover:text-red-600 rounded-lg hover:bg-red-50"
                      aria-label={t('common.delete')}
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
              {brand.voice && (
                <p className="text-sm text-gray-600 line-clamp-2 mb-3">{brand.voice}</p>
              )}
              <p className="text-xs text-gray-400">
                {t('brands.productCount', { count: brand.product_count })}
              </p>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold">
                {isEdit ? t('brands.editBrand') : t('brands.addBrand')}
              </h3>
              <button type="button" onClick={closeModal} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex border-b border-gray-100 px-4 overflow-x-auto">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  disabled={modalLoading}
                  className={`px-3 py-2 text-sm font-medium whitespace-nowrap border-b-2 transition-colors disabled:opacity-50 ${
                    activeTab === tab.id
                      ? 'border-forge-600 text-forge-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {modalLoading ? (
              <div className="flex flex-col items-center justify-center gap-3 py-16 px-6">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-forge-600" />
                <p className="text-sm text-gray-500">{t('common.loading')}</p>
                <button
                  type="button"
                  onClick={closeModal}
                  className="mt-2 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
                >
                  {t('common.cancel')}
                </button>
              </div>
            ) : (
            <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
              {activeTab === 'voice' && (
                <>
                  <div className="flex items-center gap-4">
                    <BrandAvatar name={form.name || t('brands.addBrand')} logoUrl={logoPreview} size="lg" />
                    <div>
                      <LabelWithTooltip label={t('brands.logo')} tooltip={t('brands.tooltips.logo')} />
                      <label className="mt-1 inline-flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 cursor-pointer">
                        <Upload className="w-4 h-4" />
                        {uploadingLogo ? t('brands.logoUploading') : t('brands.uploadLogo')}
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp,image/svg+xml"
                          className="sr-only"
                          onChange={(e) => void handleLogoChange(e)}
                          disabled={uploadingLogo}
                        />
                      </label>
                      {!isEdit && (
                        <p className="mt-1 text-xs text-gray-400">{t('brands.logoCreateHint')}</p>
                      )}
                    </div>
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.name')} tooltip={t('brands.tooltips.name')} />
                    <input
                      type="text"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      required
                      disabled={isEdit && brands.find((b) => b.brand_id === editingId)?.is_generic}
                      placeholder={t('placeholders.brands.name')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.voice')} tooltip={t('brands.tooltips.voice')} />
                    <textarea
                      value={form.voice || ''}
                      onChange={(e) => setForm({ ...form, voice: e.target.value })}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      maxLength={LIMITS.brandVoice}
                      placeholder={t('placeholders.brands.voice')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.audience')} tooltip={t('brands.tooltips.audience')} />
                    <input
                      type="text"
                      value={form.audience || ''}
                      onChange={(e) => setForm({ ...form, audience: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.audience')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.toneKeywords')} tooltip={t('brands.tooltips.toneKeywords')} />
                    <input
                      type="text"
                      value={form.tone_keywords || ''}
                      onChange={(e) => setForm({ ...form, tone_keywords: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.toneKeywords')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip
                      label={t('brands.bufferAccount')}
                      tooltip={t('brands.tooltips.bufferAccount')}
                    />
                    <select
                      value={form.buffer_account_id || ''}
                      onChange={(e) => setForm({ ...form, buffer_account_id: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                    >
                      <option value="">{t('brands.bufferAccountNone')}</option>
                      {selectableBufferAccounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.name}
                            {account.buffer_email ? ` (${account.buffer_email})` : ''}
                          </option>
                        ))}
                    </select>
                    <p className="mt-1 text-xs text-gray-400">{t('brands.bufferAccountHint')}</p>
                    {!hasUnboundBufferAccount && (
                      <div className="mt-3">
                        <SetupFlowCallout
                          variant="warning"
                          title={t('brands.bufferSetup.title')}
                          description={t('brands.bufferSetup.description')}
                          actionLabel={t('brands.bufferSetup.action')}
                          onAction={goToBufferSetup}
                          openActionInNewTab
                          learnMoreUrl={BUFFER_API_HELP_URL}
                          learnMoreLabel={t('brands.bufferSetup.learnMore')}
                        />
                      </div>
                    )}
                  </div>
                </>
              )}

              {activeTab === 'content' && (
                <>
                  <div>
                    <LabelWithTooltip label={t('brands.defaultHashtags')} tooltip={t('brands.tooltips.hashtags')} />
                    <input
                      type="text"
                      value={(form.default_hashtags || []).join(', ')}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          default_hashtags: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.hashtags')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.emojiStyle')} tooltip={t('brands.tooltips.emojiStyle')} />
                    <select
                      value={form.emoji_style || 'moderate'}
                      onChange={(e) => setForm({ ...form, emoji_style: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                    >
                      <option value="none">{t('brands.emojiNone')}</option>
                      <option value="minimal">{t('brands.emojiMinimal')}</option>
                      <option value="moderate">{t('brands.emojiModerate')}</option>
                      <option value="heavy">{t('brands.emojiHeavy')}</option>
                    </select>
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.wordsToAvoid')} tooltip={t('brands.tooltips.wordsToAvoid')} />
                    <input
                      type="text"
                      value={form.words_to_avoid || ''}
                      onChange={(e) => setForm({ ...form, words_to_avoid: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.wordsToAvoid')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.logoInImages')} tooltip={t('brands.tooltips.logoInImages')} />
                    <select
                      value={form.logo_in_images || 'preserve'}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          logo_in_images: e.target.value as 'preserve' | 'omit' | 'composite',
                        })
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                    >
                      <option value="preserve">{t('brands.logoInImagesPreserve')}</option>
                      <option value="omit">{t('brands.logoInImagesOmit')}</option>
                      <option value="composite">{t('brands.logoInImagesComposite')}</option>
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      {form.logo_in_images === 'omit'
                        ? t('brands.logoInImagesOmitHint')
                        : form.logo_in_images === 'composite'
                          ? t('brands.logoInImagesCompositeHint')
                          : t('brands.logoInImagesPreserveHint')}
                    </p>
                    {form.logo_in_images === 'composite' && !logoPreview && (
                      <p className="mt-1 text-xs text-amber-600">{t('brands.logoCompositeNeedsUpload')}</p>
                    )}
                  </div>
                  {(form.logo_in_images || 'preserve') === 'preserve' && (
                  <div>
                    <LabelWithTooltip label={t('brands.logoFontRule')} tooltip={t('brands.tooltips.logoFontRule')} />
                    <input
                      type="text"
                      value={form.logo_font_rule || ''}
                      onChange={(e) => setForm({ ...form, logo_font_rule: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.logoFontRule')}
                    />
                  </div>
                  )}
                </>
              )}

              {activeTab === 'advanced' && (
                <>
                  <p className="text-sm text-amber-700 bg-amber-50 rounded-lg p-3">{t('brands.advancedWarning')}</p>
                  <div>
                    <LabelWithTooltip label={t('brands.copySystemPrompt')} tooltip={t('brands.tooltips.copySystemPrompt')} />
                    <textarea
                      value={form.copy_system_prompt || ''}
                      onChange={(e) => setForm({ ...form, copy_system_prompt: e.target.value })}
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-xs focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.copySystemPrompt')}
                    />
                  </div>
                  <div>
                    <LabelWithTooltip label={t('brands.imageSystemPrompt')} tooltip={t('brands.tooltips.imageSystemPrompt')} />
                    <textarea
                      value={form.image_system_prompt || ''}
                      onChange={(e) => setForm({ ...form, image_system_prompt: e.target.value })}
                      rows={4}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-xs focus:ring-2 focus:ring-forge-500"
                      placeholder={t('placeholders.brands.imageSystemPrompt')}
                    />
                  </div>
                </>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  disabled={saving}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 px-4 py-2 bg-forge-600 text-white rounded-lg hover:bg-forge-700 disabled:opacity-50"
                >
                  {saving ? t('common.saving') : t('common.save')}
                </button>
              </div>
            </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
