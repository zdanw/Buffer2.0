import { useEffect, useMemo, useState } from 'react';
import {
  Bookmark,
  Heart,
  MessageCircle,
  MoreHorizontal,
  Send,
  Share2,
  ThumbsUp,
} from 'lucide-react';
import BrandAvatar from '@/components/BrandAvatar';
import PlatformIcon, { InstagramAppIcon } from '@/components/icons/PlatformIcon';
import StatusBarIcons from '@/components/icons/StatusBarIcons';
import { useI18n } from '@/i18n/useI18n';

type Platform = 'instagram' | 'tiktok' | 'facebook';

interface SocialFeedPreviewProps {
  platforms: string[];
  image?: string;
  caption?: string;
  brandName?: string;
  brandLogo?: string | null;
  imageAlt?: string;
}

function toUsername(name: string): string {
  const slug = name.toLowerCase().replace(/[^a-z0-9]/g, '');
  return slug.slice(0, 24) || 'yourbrand';
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, '')}K`;
  return String(n);
}

function StatusBar({ light }: { light?: boolean }) {
  const tone = light ? 'light' : 'dark';
  return (
    <div
      className={`absolute top-0 inset-x-0 z-20 flex items-center justify-between px-5 pt-2 pb-1 text-[8px] font-semibold ${
        light ? 'text-white' : 'text-black'
      }`}
    >
      <span>9:41</span>
      <StatusBarIcons tone={tone} size="sm" />
    </div>
  );
}

function HomeIndicator({ dark }: { dark?: boolean }) {
  return (
    <div
      className={`absolute bottom-[6px] left-1/2 -translate-x-1/2 z-30 w-[118px] h-[4px] rounded-full ${
        dark ? 'bg-black/25' : 'bg-white/35'
      }`}
    />
  );
}

function IPhoneFrame({
  children,
  screenClassName = 'bg-white',
  statusLight = false,
  homeDark = false,
}: {
  children: React.ReactNode;
  screenClassName?: string;
  statusLight?: boolean;
  homeDark?: boolean;
}) {
  return (
    <div className="relative mx-auto select-none" style={{ width: 300 }}>
      <div className="absolute -left-[2px] top-[92px] w-[3px] h-[24px] bg-[#48484a] rounded-l-[2px]" />
      <div className="absolute -left-[2px] top-[132px] w-[3px] h-[46px] bg-[#48484a] rounded-l-[2px]" />
      <div className="absolute -left-[2px] top-[188px] w-[3px] h-[46px] bg-[#48484a] rounded-l-[2px]" />
      <div className="absolute -right-[2px] top-[148px] w-[3px] h-[64px] bg-[#48484a] rounded-r-[2px]" />

      <div className="rounded-[44px] bg-gradient-to-b from-[#3a3a3c] to-[#1c1c1e] p-[9px] shadow-[0_25px_50px_-12px_rgba(0,0,0,0.45)] ring-1 ring-black/30">
        <div
          className={`relative rounded-[36px] overflow-hidden ${screenClassName}`}
          style={{ height: 620 }}
        >
          <div className="absolute top-[11px] left-1/2 -translate-x-1/2 z-30 w-[96px] h-[27px] bg-black rounded-full shadow-inner" />
          <StatusBar light={statusLight} />
          {children}
          <HomeIndicator dark={homeDark} />
        </div>
      </div>
    </div>
  );
}

function InstagramWordmark({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center gap-1.5 ${className}`}>
      <InstagramAppIcon size={18} />
      <img
        src="/icons/instagram-wordmark.png"
        alt="Instagram"
        className="h-[15px] w-auto object-contain"
        draggable={false}
      />
    </div>
  );
}

function FacebookLogo({ className = '' }: { className?: string }) {
  return <PlatformIcon platform="facebook" size={28} className={className} />;
}

function MessengerLogo({ className = '' }: { className?: string }) {
  return <PlatformIcon platform="messenger" size={28} className={className} />;
}

function InstagramFeed({
  image,
  caption,
  username,
  brandName,
  brandLogo,
  imageAlt,
}: {
  image?: string;
  caption?: string;
  username: string;
  brandName: string;
  brandLogo?: string | null;
  imageAlt: string;
}) {
  return (
    <div className="absolute inset-0 pt-[44px] flex flex-col bg-white text-black overflow-hidden">
      <div className="relative flex items-center justify-between px-3 py-2 border-b border-gray-100 shrink-0">
        <svg viewBox="0 0 24 24" className="w-[22px] h-[22px]" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
          <circle cx="12" cy="13" r="4" />
        </svg>
        <div className="absolute left-1/2 -translate-x-1/2">
          <InstagramWordmark />
        </div>
        <div className="flex items-center gap-3">
          <Heart className="w-[22px] h-[22px]" strokeWidth={1.8} />
          <Send className="w-[22px] h-[22px]" strokeWidth={1.8} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="flex items-center justify-between px-3 py-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="p-[1.5px] rounded-full bg-gradient-to-tr from-yellow-400 via-pink-500 to-purple-600 shrink-0">
              <BrandAvatar name={brandName} logoUrl={brandLogo} size="sm" className="!rounded-full !h-7 !w-7 border-2 border-white" />
            </div>
            <span className="text-[11px] font-semibold truncate">{username}</span>
          </div>
          <MoreHorizontal className="w-4 h-4 text-gray-700 shrink-0" />
        </div>

        {image ? (
          <img src={image} alt={imageAlt} className="w-full aspect-square object-cover bg-gray-100" />
        ) : (
          <div className="w-full aspect-square bg-gradient-to-br from-gray-100 to-gray-200" />
        )}

        <div className="px-3 pt-2.5 pb-1">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3.5">
              <Heart className="w-[22px] h-[22px]" strokeWidth={1.8} />
              <MessageCircle className="w-[22px] h-[22px]" strokeWidth={1.8} />
              <Send className="w-[20px] h-[20px]" strokeWidth={1.8} />
            </div>
            <Bookmark className="w-[20px] h-[20px]" strokeWidth={1.8} />
          </div>
          <p className="text-[11px] font-semibold mb-1">{formatCount(1284)} likes</p>
          {caption && (
            <p className="text-[10.5px] leading-[1.45] text-gray-900">
              <span className="font-semibold mr-1">{username}</span>
              <span className="whitespace-pre-wrap">{caption}</span>
            </p>
          )}
          <p className="text-[10px] text-gray-400 mt-1.5">View all 48 comments</p>
          <p className="text-[9px] text-gray-400 uppercase mt-0.5 tracking-wide">2 hours ago</p>
        </div>
      </div>

      <div className="border-t border-gray-100 px-3 py-2 flex items-center gap-2 shrink-0 pb-5">
        <BrandAvatar name={brandName} logoUrl={brandLogo} size="sm" className="!h-6 !w-6 !rounded-full" />
        <span className="text-[10px] text-gray-400">Add a comment...</span>
      </div>
    </div>
  );
}

function TikTokFeed({
  image,
  caption,
  username,
  brandName,
  brandLogo,
  imageAlt,
}: {
  image?: string;
  caption?: string;
  username: string;
  brandName: string;
  brandLogo?: string | null;
  imageAlt: string;
}) {
  return (
    <div className="absolute inset-0 bg-black text-white overflow-hidden">
      {image ? (
        <img src={image} alt={imageAlt} className="absolute inset-0 w-full h-full object-cover" />
      ) : (
        <div className="absolute inset-0 bg-gradient-to-b from-gray-800 to-black" />
      )}

      <div className="absolute inset-0 bg-gradient-to-b from-black/35 via-transparent to-black/75" />

      <div className="absolute inset-x-0 top-0 pt-[44px] px-3 flex items-center justify-between z-10">
        <PlatformIcon platform="tiktok" size={18} variant="mono" className="text-white" />
        <div className="flex items-center gap-5 text-[12px]">
          <span className="opacity-60">For You</span>
          <span className="font-bold border-b-2 border-white pb-0.5">Following</span>
        </div>
        <svg viewBox="0 0 24 24" className="w-5 h-5 opacity-90" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </div>

      <div className="absolute right-2 bottom-[88px] flex flex-col items-center gap-4 z-10">
        <div className="relative">
          <BrandAvatar name={brandName} logoUrl={brandLogo} size="sm" className="!h-10 !w-10 !rounded-full border-2 border-white" />
          <span className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-[#fe2c55] text-[10px] font-bold flex items-center justify-center border border-black">
            +
          </span>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <Heart className="w-7 h-7 drop-shadow-lg" fill="white" strokeWidth={0} />
          <span className="text-[10px] font-semibold drop-shadow">{formatCount(84200)}</span>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <MessageCircle className="w-7 h-7 drop-shadow-lg" strokeWidth={1.5} />
          <span className="text-[10px] font-semibold drop-shadow">{formatCount(1204)}</span>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <Bookmark className="w-6 h-6 drop-shadow-lg" strokeWidth={1.5} />
          <span className="text-[10px] font-semibold drop-shadow">{formatCount(3200)}</span>
        </div>
        <div className="flex flex-col items-center gap-0.5">
          <Share2 className="w-6 h-6 drop-shadow-lg" strokeWidth={1.5} />
          <span className="text-[10px] font-semibold drop-shadow">Share</span>
        </div>
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-gray-700 to-gray-900 border-2 border-white/30 animate-spin-slow mt-1" />
      </div>

      <div className="absolute left-3 right-14 bottom-[88px] z-10">
        <p className="text-[12px] font-bold mb-1 drop-shadow">@{username}</p>
        {caption && (
          <p className="text-[11px] leading-snug drop-shadow line-clamp-3 whitespace-pre-wrap">{caption}</p>
        )}
        <div className="flex items-center gap-1.5 mt-2 opacity-90">
          <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor" aria-hidden>
            <path d="M12 3v10.55A4 4 0 1 0 14 17V7h4V3h-6z" />
          </svg>
          <span className="text-[10px] truncate">Original sound — {brandName}</span>
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 z-10 flex items-center justify-around px-2 pt-2 pb-[18px] bg-black/40 backdrop-blur-sm border-t border-white/10 text-[9px]">
        <div className="flex flex-col items-center gap-0.5 opacity-90">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
          </svg>
          <span>Home</span>
        </div>
        <div className="flex flex-col items-center gap-0.5 opacity-50">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
          </svg>
          <span>Friends</span>
        </div>
        <div className="flex flex-col items-center -mt-3">
          <div className="w-10 h-7 rounded-md bg-white flex items-center justify-center">
            <span className="text-black text-lg font-light leading-none">+</span>
          </div>
        </div>
        <div className="flex flex-col items-center gap-0.5 opacity-50">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z" />
          </svg>
          <span>Inbox</span>
        </div>
        <div className="flex flex-col items-center gap-0.5 opacity-50">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
          </svg>
          <span>Profile</span>
        </div>
      </div>
    </div>
  );
}

function FacebookFeed({
  image,
  caption,
  brandName,
  brandLogo,
  imageAlt,
}: {
  image?: string;
  caption?: string;
  username: string;
  brandName: string;
  brandLogo?: string | null;
  imageAlt: string;
}) {
  return (
    <div className="absolute inset-0 pt-[44px] flex flex-col bg-[#f0f2f5] text-[#050505] overflow-hidden">
      <div className="bg-white px-3 py-2 flex items-center gap-2 border-b border-gray-200 shrink-0 shadow-sm">
        <FacebookLogo />
        <div className="flex-1 bg-[#f0f2f5] rounded-full px-3 py-1.5 text-[11px] text-gray-500">
          Search Facebook
        </div>
        <MessengerLogo />
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="flex items-start gap-2 p-3">
            <BrandAvatar name={brandName} logoUrl={brandLogo} size="sm" className="!h-9 !w-9 !rounded-full shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold leading-tight">{brandName}</p>
              <p className="text-[9px] text-gray-500 flex items-center gap-1 mt-0.5">
                2h
                <span>·</span>
                <svg viewBox="0 0 16 16" className="w-3 h-3" fill="currentColor" aria-hidden>
                  <path d="M8 0C3.6 0 0 3.6 0 8s3.6 8 8 8 8-3.6 8-8-3.6-8-8-8zm5.4 3.2L8.7 9.5 6.4 7.2l-1.4 1.4 3.7 3.7 6.3-7.6-1.6-1.5z" />
                </svg>
              </p>
            </div>
            <MoreHorizontal className="w-4 h-4 text-gray-500 shrink-0" />
          </div>

          {caption && (
            <p className="px-3 pb-2.5 text-[11px] leading-[1.45] whitespace-pre-wrap">{caption}</p>
          )}

          {image ? (
            <img src={image} alt={imageAlt} className="w-full aspect-[4/3] object-cover bg-gray-100" />
          ) : (
            <div className="w-full aspect-[4/3] bg-gradient-to-br from-gray-100 to-gray-200" />
          )}

          <div className="px-3 py-2 flex items-center justify-between border-b border-gray-100">
            <div className="flex items-center gap-1">
              <span className="flex -space-x-1">
                <span className="w-4 h-4 rounded-full bg-[#1877F2] flex items-center justify-center text-[8px] text-white border border-white">
                  <ThumbsUp className="w-2 h-2" fill="white" strokeWidth={0} />
                </span>
                <span className="w-4 h-4 rounded-full bg-[#f33e58] flex items-center justify-center text-[7px] border border-white">❤</span>
              </span>
              <span className="text-[10px] text-gray-500 ml-1">{formatCount(342)}</span>
            </div>
            <span className="text-[10px] text-gray-500">28 comments · 12 shares</span>
          </div>

          <div className="flex items-center justify-around py-1.5 text-[10px] text-gray-600 font-medium">
            <button type="button" className="flex items-center gap-1.5 px-2 py-1">
              <ThumbsUp className="w-4 h-4" strokeWidth={1.8} />
              Like
            </button>
            <button type="button" className="flex items-center gap-1.5 px-2 py-1">
              <MessageCircle className="w-4 h-4" strokeWidth={1.8} />
              Comment
            </button>
            <button type="button" className="flex items-center gap-1.5 px-2 py-1">
              <Share2 className="w-4 h-4" strokeWidth={1.8} />
              Share
            </button>
          </div>
        </div>

        <div className="mt-2 bg-white rounded-lg shadow-sm p-2.5 flex items-center gap-2">
          <BrandAvatar name={brandName} logoUrl={brandLogo} size="sm" className="!h-7 !w-7 !rounded-full shrink-0" />
          <div className="flex-1 bg-[#f0f2f5] rounded-full px-3 py-1.5 text-[10px] text-gray-500">
            Write a comment...
          </div>
        </div>
      </div>

      <div className="bg-white border-t border-gray-200 flex items-center justify-around px-2 pt-1.5 pb-[18px] shrink-0">
        <div className="flex flex-col items-center gap-0.5 text-[#1877F2]">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z" />
          </svg>
          <span className="text-[8px] font-medium">Home</span>
        </div>
        <div className="flex flex-col items-center gap-0.5 text-gray-500">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z" />
          </svg>
          <span className="text-[8px]">Friends</span>
        </div>
        <div className="flex flex-col items-center gap-0.5 text-gray-500">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z" />
          </svg>
          <span className="text-[8px]">Reels</span>
        </div>
        <div className="flex flex-col items-center gap-0.5 text-gray-500">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
          </svg>
          <span className="text-[8px]">Notif.</span>
        </div>
        <div className="flex flex-col items-center gap-0.5 text-gray-500">
          <svg viewBox="0 0 24 24" className="w-5 h-5" fill="currentColor" aria-hidden>
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z" />
          </svg>
          <span className="text-[8px]">Menu</span>
        </div>
      </div>
    </div>
  );
}

const PLATFORM_LABELS: Record<Platform, string> = {
  instagram: 'Instagram',
  tiktok: 'TikTok',
  facebook: 'Facebook',
};

function isPlatform(value: string): value is Platform {
  return value === 'instagram' || value === 'tiktok' || value === 'facebook';
}

export default function SocialFeedPreview({
  platforms,
  image,
  caption,
  brandName = 'Your Brand',
  brandLogo,
  imageAlt = 'Generated content',
}: SocialFeedPreviewProps) {
  const { t } = useI18n();

  const availablePlatforms = useMemo(
    () => platforms.filter(isPlatform),
    [platforms]
  );

  const [activePlatform, setActivePlatform] = useState<Platform>(
    availablePlatforms[0] ?? 'instagram'
  );

  useEffect(() => {
    if (!availablePlatforms.includes(activePlatform)) {
      setActivePlatform(availablePlatforms[0] ?? 'instagram');
    }
  }, [availablePlatforms, activePlatform]);

  const username = toUsername(brandName);
  const showTabs = availablePlatforms.length > 1;

  const feedProps = {
    image,
    caption,
    username,
    brandName,
    brandLogo,
    imageAlt,
  };

  const renderFeed = () => {
    switch (activePlatform) {
      case 'tiktok':
        return <TikTokFeed {...feedProps} />;
      case 'facebook':
        return <FacebookFeed {...feedProps} />;
      case 'instagram':
      default:
        return <InstagramFeed {...feedProps} />;
    }
  };

  const frameProps =
    activePlatform === 'tiktok'
      ? { screenClassName: 'bg-black', statusLight: true, homeDark: false }
      : { screenClassName: 'bg-white', statusLight: false, homeDark: true };

  return (
    <div className="w-full">
      <p className="text-xs text-center text-gray-500 mb-2">{t('studio.phonePreview')}</p>

      {showTabs && (
        <div className="flex justify-center gap-1.5 mb-3">
          {availablePlatforms.map((platform) => (
            <button
              key={platform}
              type="button"
              onClick={() => setActivePlatform(platform)}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors ${
                activePlatform === platform
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              <PlatformIcon
                platform={platform}
                size={12}
                variant={activePlatform === platform ? 'mono' : 'brand'}
                className={activePlatform === platform ? 'text-white' : ''}
              />
              {PLATFORM_LABELS[platform]}
            </button>
          ))}
        </div>
      )}

      <IPhoneFrame {...frameProps}>{renderFeed()}</IPhoneFrame>

      {!showTabs && availablePlatforms.length === 1 && (
        <p className="text-[10px] text-center text-gray-400 mt-2">
          {PLATFORM_LABELS[availablePlatforms[0]]}
        </p>
      )}
    </div>
  );
}
