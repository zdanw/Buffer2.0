import { useState } from 'react';
import { Sparkles, Package, ArrowRight } from 'lucide-react';
import { createBrand } from '@/api/brands';
import { createProduct, uploadProductImages } from '@/api/products';
import { useBrandContext } from '@/context/BrandContext';
import { useI18n } from '@/i18n/useI18n';
import { LIMITS } from '@/lib/formValidation';

type Step = 'welcome' | 'brand' | 'product' | 'done';

interface OnboardingWizardProps {
  onComplete: () => void;
  onSkip: () => void;
  onGoStudio: () => void;
}

export default function OnboardingWizard({ onComplete, onSkip, onGoStudio }: OnboardingWizardProps) {
  const { t } = useI18n();
  const { refreshBrands, setActiveBrandId } = useBrandContext();
  const [step, setStep] = useState<Step>('welcome');
  const [useGeneric, setUseGeneric] = useState(false);
  const [brandName, setBrandName] = useState('');
  const [brandVoice, setBrandVoice] = useState('');
  const [productName, setProductName] = useState('');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const finish = async () => {
    setBusy(true);
    try {
      let brandId: string | undefined;
      if (!useGeneric && brandName.trim()) {
        const brand = await createBrand({ name: brandName.trim(), voice: brandVoice.trim() || undefined });
        brandId = brand.brand_id;
        setActiveBrandId(brandId);
        await refreshBrands();
      } else {
        setActiveBrandId(null);
      }

      if (productName.trim()) {
        const product = await createProduct({
          product_name: productName.trim(),
          category: 'General',
          ...(brandId ? { brand_id: brandId } : {}),
        });
        if (imageFile) {
          await uploadProductImages(product.product_id, [imageFile], 'product');
        }
      }
      setStep('done');
      await onComplete();
    } catch (err) {
      console.error(err);
      alert(t('common.saveFailed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] bg-black/60 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="flex justify-end p-3">
          <button
            type="button"
            onClick={onSkip}
            className="text-sm text-gray-500 hover:text-gray-700 px-2 py-1"
          >
            {t('onboarding.skip')}
          </button>
        </div>

        {step === 'welcome' && (
          <div className="px-8 pb-8 text-center">
            <div className="w-14 h-14 rounded-2xl bg-forge-100 text-forge-600 flex items-center justify-center mx-auto mb-4">
              <Sparkles className="w-7 h-7" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900">{t('onboarding.welcomeTitle')}</h2>
            <p className="text-gray-500 mt-2">{t('onboarding.welcomeSubtitle')}</p>
            <button
              type="button"
              onClick={() => setStep('brand')}
              className="mt-8 w-full py-3 bg-forge-600 text-white rounded-xl font-medium hover:bg-forge-700"
            >
              {t('onboarding.getStarted')}
            </button>
          </div>
        )}

        {step === 'brand' && (
          <div className="px-8 pb-8">
            <h2 className="text-xl font-bold text-gray-900">{t('onboarding.stepBrand')}</h2>
            <p className="text-sm text-gray-500 mt-1">{t('onboarding.stepBrandHint')}</p>
            <label className="flex items-center gap-2 mt-4 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={useGeneric}
                onChange={(e) => setUseGeneric(e.target.checked)}
                className="rounded border-gray-300 text-forge-600"
              />
              {t('onboarding.noSpecificBrand')}
            </label>
            {!useGeneric && (
              <div className="mt-4 space-y-3">
                <input
                  type="text"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  placeholder={t('placeholders.onboarding.brandName')}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
                <textarea
                  value={brandVoice}
                  onChange={(e) => setBrandVoice(e.target.value)}
                  placeholder={t('placeholders.onboarding.brandVoice')}
                  rows={2}
                  maxLength={LIMITS.brandVoice}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>
            )}
            <button
              type="button"
              onClick={() => setStep('product')}
              className="mt-6 w-full py-3 bg-forge-600 text-white rounded-xl font-medium hover:bg-forge-700 flex items-center justify-center gap-2"
            >
              {t('common.confirm')} <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {step === 'product' && (
          <div className="px-8 pb-8">
            <h2 className="text-xl font-bold text-gray-900">{t('onboarding.stepProduct')}</h2>
            <p className="text-sm text-gray-500 mt-1">{t('onboarding.stepProductHint')}</p>
            <div className="mt-4 space-y-3">
              <input
                type="text"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder={t('placeholders.onboarding.productName')}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              />
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                className="w-full text-sm"
              />
            </div>
            <button
              type="button"
              disabled={busy || !productName.trim()}
              onClick={() => void finish()}
              className="mt-6 w-full py-3 bg-forge-600 text-white rounded-xl font-medium hover:bg-forge-700 disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Package className="w-4 h-4" />
              {busy ? t('common.saving') : t('onboarding.goToStudio')}
            </button>
          </div>
        )}

        {step === 'done' && (
          <div className="px-8 pb-8 text-center">
            <h2 className="text-xl font-bold text-gray-900">{t('onboarding.checklistGenerate')}</h2>
            <p className="text-gray-500 mt-2">{t('onboarding.goToStudio')}</p>
            <button
              type="button"
              onClick={onGoStudio}
              className="mt-6 w-full py-3 bg-forge-600 text-white rounded-xl font-medium hover:bg-forge-700"
            >
              {t('onboarding.goToStudio')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
