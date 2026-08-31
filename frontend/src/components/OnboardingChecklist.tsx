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
    { id: 'account', done: true, label: t('onboarding.checklistAccount'), tab: null },
    { id: 'brand', done: hasBrand, label: t('onboarding.checklistBrand'), tab: 'brand' },
    { id: 'product', done: hasProduct, label: t('onboarding.checklistProduct'), tab: 'products' },
    { id: 'generate', done: hasGenerated, label: t('onboarding.checklistGenerate'), tab: 'studio' },
  ];

  const completedCount = coreSteps.filter((s) => s.done).length;
  const totalCount = coreSteps.length;

  const allDone = coreSteps.every((s) => s.done);
  if (allDone) return null;

  return (
    <div data-help-overlay="onboarding-checklist" className="fixed bottom-4 right-4 z-40 w-72 bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      <button
        type="button"
        onClick={toggleOpen}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-semibold text-gray-900 hover:bg-gray-50"
      >
        <span className="flex items-center gap-2">
          {t('onboarding.checklistTitle')}
          <span className="text-xs font-medium text-gray-500 tabular-nums">
            {completedCount}/{totalCount}
          </span>
        </span>
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-2">
          {coreSteps.map((step) => {
            const rowClass =
              'w-full flex items-center gap-2 text-left text-sm text-gray-700';
            const content = (
              <>
                {step.done ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                ) : (
                  <Circle className="w-4 h-4 text-gray-300 shrink-0" />
                )}
                {step.label}
              </>
            );

            if (!step.tab) {
              return (
                <div key={step.id} className={rowClass}>
                  {content}
                </div>
              );
            }

            return (
              <button
                key={step.id}
                type="button"
                onClick={() => onNavigate(step.tab!)}
                className={`${rowClass} hover:text-forge-600`}
              >
                {content}
              </button>
            );
          })}
          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">{t('onboarding.optionalSetup')}</p>
          <button type="button" onClick={() => onNavigate('help')} className="text-xs text-forge-600 hover:underline block">
            {t('onboarding.linkHelp')}
          </button>
          <button type="button" onClick={() => onNavigate('automations')} className="text-xs text-forge-600 hover:underline block">
            {t('onboarding.linkAutomations')}
          </button>
        </div>
      )}
    </div>
  );
}
