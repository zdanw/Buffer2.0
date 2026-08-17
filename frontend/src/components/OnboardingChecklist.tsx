import { useState } from 'react';
import { CheckCircle2, Circle, ChevronDown, ChevronUp } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

const OPEN_STORAGE_KEY = 'pulseforge_getting_started_open';

interface OnboardingChecklistProps {
  hasBrand: boolean;
  hasProduct: boolean;
  hasGenerated: boolean;
  onNavigate: (tab: string) => void;
}

export default function OnboardingChecklist({
  hasBrand,
  hasProduct,
  hasGenerated,
  onNavigate,
}: OnboardingChecklistProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(() => {
    const stored = localStorage.getItem(OPEN_STORAGE_KEY);
    if (stored === null) return true;
    return stored === '1';
  });

  const toggleOpen = () => {
    setOpen((prev) => {
      const next = !prev;
      localStorage.setItem(OPEN_STORAGE_KEY, next ? '1' : '0');
      return next;
    });
  };
  const coreSteps = [
    { done: hasBrand, label: t('onboarding.checklistBrand'), tab: 'brand' },
    { done: hasProduct, label: t('onboarding.checklistProduct'), tab: 'products' },
    { done: hasGenerated, label: t('onboarding.checklistGenerate'), tab: 'studio' },
  ];

  const allDone = coreSteps.every((s) => s.done);
  if (allDone) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40 w-72 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      <button
        type="button"
        onClick={toggleOpen}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-900 hover:bg-gray-50"
      >
        {t('onboarding.checklistTitle')}
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-2">
          {coreSteps.map((step) => (
            <button
              key={step.tab}
              type="button"
              onClick={() => onNavigate(step.tab)}
              className="w-full flex items-center gap-2 text-left text-sm text-gray-700 hover:text-forge-600"
            >
              {step.done ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
              ) : (
                <Circle className="w-4 h-4 text-gray-300 shrink-0" />
              )}
              {step.label}
            </button>
          ))}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">{t('onboarding.optionalSetup')}</p>
          <button type="button" onClick={() => onNavigate('automations')} className="text-xs text-forge-600 hover:underline block">
            {t('onboarding.linkAutomations')}
          </button>
        </div>
      )}
    </div>
  );
}
