import { ZoomIn } from 'lucide-react';
import { useI18n } from '@/i18n/useI18n';

interface ReferenceImagesDisplayProps {
  productImages?: string[] | null;
  sceneImages?: string[] | null;
  onPreview?: (url: string) => void;
  className?: string;
}

export default function ReferenceImagesDisplay({
  productImages,
  sceneImages,
  onPreview,
  className = '',
}: ReferenceImagesDisplayProps) {
  const { t } = useI18n();
  const products = (productImages || []).filter(Boolean);
  const scenes = (sceneImages || []).filter(Boolean);

  if (products.length === 0 && scenes.length === 0) {
    return null;
  }

  const renderGroup = (label: string, urls: string[]) => {
    if (urls.length === 0) return null;
    return (
      <div>
        <div className="text-xs font-medium text-gray-600 mb-2">
          {label}
          <span className="text-gray-400 font-normal ml-1">
            {t('referenceImages.count', { count: urls.length })}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {urls.map((url, idx) => {
            if (!onPreview) {
              return (
                <div key={`${label}-${idx}`}>
                  <img
                    src={url}
                    alt={t('referenceImages.alt', { label, n: idx + 1 })}
                    className="w-full h-20 object-cover rounded-lg border border-gray-200"
                  />
                </div>
              );
            }
            return (
              <button
                key={`${label}-${idx}`}
                type="button"
                onClick={() => onPreview(url)}
                className="relative group w-full rounded-lg overflow-hidden border border-gray-200 focus:outline-none focus:ring-2 focus:ring-forge-400"
              >
                <img
                  src={url}
                  alt={t('referenceImages.alt', { label, n: idx + 1 })}
                  className="w-full h-20 object-cover"
                />
                <span className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                  <ZoomIn className="w-5 h-5 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className={`border border-gray-200 rounded-lg p-4 bg-gray-50/50 space-y-3 ${className}`}>
      <h4 className="text-sm font-semibold text-gray-700">{t('referenceImages.title')}</h4>
      {renderGroup(t('referenceImages.product'), products)}
      {renderGroup(t('referenceImages.scene'), scenes)}
    </div>
  );
}
