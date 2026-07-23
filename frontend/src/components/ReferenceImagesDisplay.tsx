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
          <span className="text-gray-400 font-normal ml-1">({urls.length})</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {urls.map((url, idx) => {
            const img = (
              <img
                src={url}
                alt={`${label} ${idx + 1}`}
                className="w-full h-20 object-cover rounded-lg border border-gray-200"
              />
            );
            if (!onPreview) {
              return <div key={`${label}-${idx}`}>{img}</div>;
            }
            return (
              <button
                key={`${label}-${idx}`}
                type="button"
                onClick={() => onPreview(url)}
                className="relative group focus:outline-none focus:ring-2 focus:ring-indigo-400 rounded-lg overflow-hidden"
              >
                {img}
                <span className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
              </button>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className={`border border-gray-200 rounded-lg p-4 bg-gray-50/50 space-y-3 ${className}`}>
      <h4 className="text-sm font-semibold text-gray-700">参考图</h4>
      {renderGroup('产品图', products)}
      {renderGroup('场景图', scenes)}
    </div>
  );
}
