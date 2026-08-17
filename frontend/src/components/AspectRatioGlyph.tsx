const GLYPH_BOX = 22;

function parseDimensions(
  width: number,
  height: number
): { w: number; h: number } | null {
  if (!width || !height || width <= 0 || height <= 0) return null;
  const ratio = width / height;
  if (ratio >= 1) {
    return { w: GLYPH_BOX, h: GLYPH_BOX / ratio };
  }
  return { w: GLYPH_BOX * ratio, h: GLYPH_BOX };
}

export function parseSizeString(size: string): { width: number; height: number } | null {
  const m = size.trim().match(/^(\d+)[xX](\d+)$/);
  if (!m) return null;
  return { width: Number(m[1]), height: Number(m[2]) };
}

export default function AspectRatioGlyph({
  width,
  height,
  variant = 'preset',
  className = '',
}: {
  width?: number;
  height?: number;
  variant?: 'preset' | 'custom';
  className?: string;
}) {
  if (variant === 'custom') {
    return (
      <span
        className={`inline-flex items-center justify-center shrink-0 ${className}`}
        style={{ width: GLYPH_BOX, height: GLYPH_BOX }}
        aria-hidden
      >
        <span
          className="rounded-sm border-2 border-dashed border-gray-400 bg-gray-50"
          style={{ width: 14, height: 14 }}
        />
      </span>
    );
  }

  const dims = width && height ? parseDimensions(width, height) : null;
  if (!dims) {
    return (
      <span
        className={`inline-flex items-center justify-center shrink-0 ${className}`}
        style={{ width: GLYPH_BOX, height: GLYPH_BOX }}
        aria-hidden
      >
        <span className="w-3 h-3 rounded-sm border border-gray-300 bg-gray-100" />
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center justify-center shrink-0 text-gray-600 ${className}`}
      style={{ width: GLYPH_BOX, height: GLYPH_BOX }}
      aria-hidden
    >
      <span
        className="rounded-sm border-2 border-current bg-current/10"
        style={{ width: dims.w, height: dims.h }}
      />
    </span>
  );
}
