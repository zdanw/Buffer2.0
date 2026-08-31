import { useEffect, useRef } from 'react';
import {
  Bookmark,
  Calendar,
  Heart,
  MessageCircle,
  Music2,
  Send,
} from 'lucide-react';
import PlatformIcon, { InstagramAppIcon } from '@/components/icons/PlatformIcon';
import StatusBarIcons from '@/components/icons/StatusBarIcons';
import { useI18n } from '@/i18n/useI18n';

const PLATFORMS = ['instagram', 'tiktok', 'facebook'] as const;
const REEL_VIDEO = '/landing/reel.mp4';
const REEL_POSTER = '/landing/reel-poster.jpg';

export default function LandingHeroVisual() {
  const { t } = useI18n();
  const brand = t('landing.heroMockBrand');
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.play().catch(() => {
      /* autoplay may be blocked until interaction */
    });
  }, []);

  return (
    <div className="relative w-full max-w-[440px] mx-auto flex flex-col items-center justify-center min-h-[300px] sm:min-h-[360px] lg:min-h-[400px]">
      <div className="absolute inset-0 rounded-3xl bg-forge-200/40 blur-[80px] animate-landing-glow pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-48 h-48 rounded-full bg-orange-100/80 blur-3xl animate-landing-float-slow pointer-events-none" />

      <div className="relative flex flex-col items-center">
        <div className="relative animate-landing-float-phone">
          <div className="relative w-[200px] sm:w-[220px]">
            <div className="rounded-[32px] bg-gradient-to-b from-zinc-500 to-zinc-800 p-[7px] shadow-xl shadow-ink-900/20 ring-1 ring-black/10">
              <div className="relative rounded-[26px] bg-black overflow-hidden aspect-[9/19]">
                <div className="absolute inset-0 overflow-hidden">
                  <video
                    ref={videoRef}
                    className="absolute inset-0 w-full h-full object-cover"
                    autoPlay
                    loop
                    muted
                    playsInline
                    preload="auto"
                    poster={REEL_POSTER}
                    aria-label={t('landing.heroReelAlt')}
                  >
                    <source src={REEL_VIDEO} type="video/mp4" />
                  </video>
                  <div className="absolute inset-0 landing-reel-rim-light pointer-events-none" />
                  <div className="absolute inset-0 landing-reel-sweep pointer-events-none" />
                  <div className="absolute inset-0 landing-reel-grain pointer-events-none" />
                  <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/10 to-black/45 pointer-events-none" />
                  <div className="absolute inset-0 bg-gradient-to-br from-forge-600/15 via-transparent to-violet-900/20 pointer-events-none landing-reel-color-grade" />
                </div>

                <div className="absolute top-0 inset-x-0 z-20 flex justify-between items-center px-5 pt-2 text-[8px] font-semibold text-white">
                  <span>9:41</span>
                  <StatusBarIcons tone="light" size="sm" />
                </div>
                <div className="absolute top-[6px] left-1/2 -translate-x-1/2 w-[72px] h-[20px] bg-black/80 rounded-full z-30 ring-1 ring-white/10" />

                <div className="absolute top-9 inset-x-0 z-20 flex justify-center">
                  <span className="text-[8px] font-bold text-white/90 tracking-wide">Reels</span>
                </div>

                <div className="absolute right-1.5 bottom-[22%] z-20 flex flex-col items-center gap-3 text-white">
                  <div className="flex flex-col items-center gap-0.5">
                    <Heart className="w-4 h-4 drop-shadow-md" fill="white" strokeWidth={0} />
                    <span className="text-[7px] font-semibold drop-shadow">24K</span>
                  </div>
                  <div className="flex flex-col items-center gap-0.5">
                    <MessageCircle className="w-4 h-4 drop-shadow-md" strokeWidth={2} />
                    <span className="text-[7px] font-semibold drop-shadow">892</span>
                  </div>
                  <Send className="w-3.5 h-3.5 drop-shadow-md" strokeWidth={2} />
                  <Bookmark className="w-3.5 h-3.5 drop-shadow-md" strokeWidth={2} />
                </div>

                <div className="absolute bottom-0 inset-x-0 z-20 px-2.5 pb-3 pt-8">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <div
                      className="w-6 h-6 rounded-full bg-black ring-2 ring-white/90 flex items-center justify-center shrink-0"
                      aria-hidden
                    >
                      <span className="text-[7px] font-black text-white tracking-tighter">GS</span>
                    </div>
                    <span className="text-[9px] font-bold text-white drop-shadow-md">{brand}</span>
                    <span className="text-[7px] font-semibold text-white/80 bg-white/20 px-1.5 py-0.5 rounded">
                      Follow
                    </span>
                  </div>
                  <p className="text-[8px] text-white/95 leading-snug line-clamp-2 drop-shadow-md">
                    <span className="font-semibold">{brand} </span>
                    {t('landing.heroMockCaption')}
                  </p>
                  <div className="mt-1.5 flex items-center gap-1 text-[7px] text-white/75">
                    <Music2 className="w-2.5 h-2.5 shrink-0" strokeWidth={2} />
                    <span className="truncate">{t('landing.heroReelAudio')}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="absolute -left-4 top-1/2 -translate-y-1/2 flex flex-col gap-2">
              {PLATFORMS.map((p, i) => (
                <span
                  key={p}
                  className="flex items-center justify-center w-8 h-8 rounded-full bg-white border border-canvas-border shadow-sm animate-landing-orbit"
                  style={{ animationDelay: `${i * 0.4}s` }}
                >
                  {p === 'instagram' ? (
                    <InstagramAppIcon size={18} />
                  ) : (
                    <PlatformIcon platform={p} size={18} />
                  )}
                </span>
              ))}
            </div>
          </div>
        </div>

        <p className="mt-5 inline-flex items-center gap-2 px-3 py-2 rounded-full border border-canvas-border bg-white/90 text-xs text-ink-600 font-medium shadow-sm">
          <Calendar className="w-3.5 h-3.5 text-forge-600 shrink-0" strokeWidth={2} />
          {t('landing.heroChipSchedule')}
        </p>
      </div>
    </div>
  );
}
