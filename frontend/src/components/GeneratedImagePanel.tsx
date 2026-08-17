import { useState } from 'react';
import { ChevronDown, Download, Expand, ZoomIn } from 'lucide-react';
import { downloadImage } from '@/lib/download';
import { useI18n } from '@/i18n/useI18n';

interface GeneratedImagePanelProps {
  imageUrl: string;
  imageAlt: string;
  onViewFullSize?: (url: string) => void;
  filename?: string;
}

export default function GeneratedImagePanel({
  imageUrl,
  imageAlt,
  onViewFullSize,
  filename = 'generated-image.jpg',
}: GeneratedImagePanelProps) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadImage(imageUrl, filename);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="w-full max-w-sm mt-4 rounded-xl border border-gray-200 bg-gray-50/80 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-gray-100/80 transition-colors"
        aria-expanded={expanded}
      >
        <div className="relative w-11 h-11 rounded-lg overflow-hidden border border-gray-200 bg-white shrink-0">
          <img src={imageUrl} alt="" className="w-full h-full object-cover" />
          <span className="absolute inset-0 bg-black/0 hover:bg-black/10 transition-colors flex items-center justify-center">
            <ZoomIn className="w-4 h-4 text-white opacity-0" />
          </span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-900">{t('preview.generatedImage')}</p>
          <p className="text-xs text-gray-500 truncate">{t('preview.generatedImageHint')}</p>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {expanded && (
        <div className="px-3 pb-3 border-t border-gray-200/80 bg-white">
          <button
            type="button"
            onClick={() => onViewFullSize?.(imageUrl)}
            className="relative w-full mt-3 rounded-lg overflow-hidden border border-gray-200 group focus:outline-none focus:ring-2 focus:ring-forge-400"
          >
            <img
              src={imageUrl}
              alt={imageAlt}
              className="w-full max-h-72 object-contain bg-gray-50"
            />
            <span className="absolute inset-0 bg-black/0 group-hover:bg-black/25 transition-colors flex items-center justify-center">
              <Expand className="w-6 h-6 text-white opacity-0 group-hover:opacity-100 transition-opacity drop-shadow" />
            </span>
          </button>
          <div className="flex gap-2 mt-3">
            <button
              type="button"
              onClick={() => onViewFullSize?.(imageUrl)}
              className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-white border border-gray-300 text-gray-700 hover:bg-gray-50"
            >
              <Expand className="w-4 h-4" />
              {t('preview.viewFullSize')}
            </button>
            <button
              type="button"
              onClick={() => void handleDownload()}
              disabled={downloading}
              className="flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium bg-gray-900 text-white hover:bg-gray-800 disabled:opacity-60"
            >
              <Download className="w-4 h-4" />
              {downloading ? t('preview.downloading') : t('preview.downloadImage')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
