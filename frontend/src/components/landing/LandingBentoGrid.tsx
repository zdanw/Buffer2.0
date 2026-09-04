import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Calendar,
  Clock,
  Layers,
  PenLine,
  Radio,
  Settings,
  Zap,
} from 'lucide-react';
import PlatformIcon, { InstagramAppIcon } from '@/components/icons/PlatformIcon';
import { useI18n } from '@/i18n/useI18n';
import LandingPicture from '@/components/landing/LandingPicture';

export default function LandingBentoGrid() {
  const { t } = useI18n();

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 auto-rows-[minmax(140px,auto)]">
      <Link
        to="/signup"
        className="col-span-2 lg:col-span-2 lg:row-span-2 group relative overflow-hidden rounded-2xl border border-forge-200 bg-gradient-to-br from-forge-500 via-forge-600 to-forge-800 p-6 sm:p-8 flex flex-col justify-between min-h-[200px] lg:min-h-[280px] transition-transform hover:scale-[1.01] hover:shadow-card-hover"
      >
        <div className="absolute inset-0 landing-gradient-shift opacity-30 pointer-events-none" />
        <div className="absolute -right-8 -bottom-8 w-48 h-48 rounded-full bg-white/15 blur-2xl group-hover:scale-110 transition-transform duration-700" />
        <div className="relative z-10">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/20 text-white text-xs font-bold uppercase tracking-wide mb-4">
            <Radio className="w-3 h-3" />
            {t('landing.bentoPromoBadge')}
          </span>
          <h3 className="text-2xl sm:text-3xl font-bold text-white leading-tight max-w-sm">
            {t('landing.bentoPromoTitle')}
          </h3>
          <p className="mt-2 text-white/85 text-sm max-w-md">{t('landing.bentoPromoDesc')}</p>
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
        <Settings className="w-5 h-5 text-emerald-600 mb-2" strokeWidth={1.75} />
        <h3 className="font-bold text-ink-900 text-sm">{t('landing.step3Title')}</h3>
        <div className="mt-2 flex items-center gap-1.5 text-[10px] text-ink-400 font-mono">
          <Clock className="w-3 h-3" />
          0 9 * * 1-5
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

      <div className="col-span-2 rounded-2xl border border-canvas-border bg-canvas p-4 sm:p-5 grid sm:grid-cols-2 gap-3">
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
