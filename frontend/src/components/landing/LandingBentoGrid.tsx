import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Calendar,
  Check,
  ClipboardCheck,
  Layers,
  PenLine,
  Pencil,
  Radio,
  Send,
  Zap,
} from 'lucide-react';
import PlatformIcon, { InstagramAppIcon } from '@/components/icons/PlatformIcon';
import { useI18n } from '@/i18n/useI18n';
import LandingPicture from '@/components/landing/LandingPicture';

const REVIEW_STEPS = [
  { icon: Check, labelKey: 'landing.reviewStepApprove' },
  { icon: Pencil, labelKey: 'landing.reviewStepEdit' },
  { icon: Send, labelKey: 'landing.reviewStepQueue' },
] as const;

export default function LandingBentoGrid() {
  const { t } = useI18n();

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 auto-rows-[minmax(140px,auto)]">
      <Link
        to="/signup"
        className="col-span-2 lg:col-span-2 lg:row-span-2 group relative overflow-hidden rounded-2xl border border-midnight-elevated bg-gradient-to-br from-midnight via-[#141a28] to-[#1e2638] p-6 sm:p-8 flex flex-col justify-between min-h-[200px] lg:min-h-[280px] transition-transform hover:scale-[1.01] hover:shadow-card-hover"
      >
        <div
          className="absolute inset-0 opacity-40 pointer-events-none"
          aria-hidden="true"
          style={{
            background:
              'radial-gradient(ellipse 70% 60% at 85% 20%, rgba(255, 77, 61, 0.35) 0%, transparent 55%), radial-gradient(ellipse 50% 50% at 10% 90%, rgba(64, 107, 255, 0.2) 0%, transparent 50%)',
          }}
        />
        <div className="absolute -right-8 -bottom-8 w-48 h-48 rounded-full bg-forge-500/10 blur-2xl group-hover:scale-110 transition-transform duration-700" />
        <div className="relative z-10">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/10 text-white/90 text-xs font-bold uppercase tracking-wide mb-4 border border-white/10">
            <Radio className="w-3 h-3" />
            {t('landing.bentoPromoBadge')}
          </span>
          <h3 className="text-2xl sm:text-3xl font-bold text-white leading-tight max-w-sm">
            {t('landing.bentoPromoTitle')}
          </h3>
          <p className="mt-2 text-white/75 text-sm max-w-md">{t('landing.bentoPromoDesc')}</p>
        </div>
        <span className="relative z-10 inline-flex items-center gap-2 mt-6 text-white font-semibold text-sm group-hover:gap-3 transition-all">
          {t('landing.getStarted')}
          <ArrowRight className="w-4 h-4" />
        </span>
      </Link>

      <div className="col-span-1 relative overflow-hidden rounded-2xl border border-canvas-border bg-white p-5 shadow-card group hover:border-signal-200 transition-colors">
        <div className="absolute inset-0 bg-gradient-to-br from-signal-50 to-transparent opacity-80" />
        <PenLine className="relative z-10 w-6 h-6 text-signal-600 mb-3" strokeWidth={1.75} />
        <h3 className="relative z-10 font-bold text-ink-900 text-sm">{t('landing.step2Title')}</h3>
        <p className="relative z-10 text-ink-500 text-xs mt-1 leading-relaxed">{t('landing.step2Desc')}</p>
      </div>

      <div className="col-span-1 relative overflow-hidden rounded-2xl border border-canvas-border bg-white p-5 shadow-card">
        <div className="flex gap-2.5 mb-3">
          <InstagramAppIcon size={28} />
          <PlatformIcon platform="tiktok" size={28} />
          <PlatformIcon platform="facebook" size={28} />
        </div>
        <h3 className="font-bold text-ink-900 text-sm">{t('landing.feature2Title')}</h3>
        <p className="text-ink-500 text-xs mt-1">{t('landing.feature2Desc')}</p>
      </div>

      <div className="col-span-2 relative overflow-hidden rounded-2xl border border-canvas-border aspect-[16/9] min-h-[180px] bg-ink-100 shadow-card">
        <LandingPicture
          asset="hero"
          className="absolute inset-0 w-full h-full object-cover object-center"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-ink-900/50 via-transparent to-transparent" />
        <p className="absolute bottom-3 left-4 text-xs font-medium text-white">
          {t('landing.previewFeed')}
        </p>
      </div>

      <div className="col-span-1 rounded-2xl border border-canvas-border bg-white p-5 shadow-card hover:border-forge-200 transition-colors">
        <Layers className="w-5 h-5 text-forge-600 mb-2" strokeWidth={1.75} />
        <h3 className="font-bold text-ink-900 text-sm">{t('landing.step1Title')}</h3>
        <p className="text-ink-500 text-xs mt-1 line-clamp-2">{t('landing.step1Desc')}</p>
      </div>

      <div className="col-span-1 rounded-2xl border border-canvas-border bg-white p-5 shadow-card">
        <ClipboardCheck className="w-5 h-5 text-moss-600 mb-2" strokeWidth={1.75} />
        <h3 className="font-bold text-ink-900 text-sm">{t('landing.step3Title')}</h3>
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {REVIEW_STEPS.map(({ icon: Icon, labelKey }, index) => (
            <span
              key={labelKey}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium ${
                index === 0
                  ? 'bg-moss-50 text-moss-600 border border-moss-50'
                  : 'bg-paper text-ink-500 border border-canvas-border'
              }`}
            >
              <Icon className="w-2.5 h-2.5" strokeWidth={2} />
              {t(labelKey)}
            </span>
          ))}
        </div>
      </div>

      <div className="col-span-2 rounded-2xl border border-canvas-border bg-white p-5 flex items-center gap-4 shadow-card">
        <div className="w-12 h-12 rounded-xl bg-forge-50 border border-forge-100 flex items-center justify-center shrink-0">
          <Calendar className="w-6 h-6 text-forge-600" />
        </div>
        <div>
          <h3 className="font-bold text-ink-900 text-sm">{t('landing.step4Title')}</h3>
          <p className="text-ink-500 text-xs mt-0.5">{t('landing.step4Desc')}</p>
        </div>
      </div>

      <div className="col-span-2 rounded-2xl border border-canvas-border bg-paper p-4 sm:p-5 grid sm:grid-cols-2 gap-3">
        <div className="rounded-xl bg-white border border-canvas-border p-3 shadow-sm">
          <div className="flex items-center gap-1.5 text-ink-400 text-xs font-medium mb-1">
            <Zap className="w-3 h-3" />
            {t('landing.compareBeforeLabel')}
          </div>
          <p className="text-ink-600 text-xs leading-relaxed">{t('landing.compareBefore')}</p>
        </div>
        <div className="rounded-xl bg-forge-50 border border-forge-100 p-3">
          <div className="flex items-center gap-1.5 text-forge-700 text-xs font-medium mb-1">
            <Radio className="w-3 h-3" />
            {t('landing.compareAfterLabel')}
          </div>
          <p className="text-ink-800 text-xs leading-relaxed font-medium">{t('landing.compareAfter')}</p>
        </div>
      </div>
    </div>
  );
}
