type HelpScreenshotProps = {
  src: string;
  alt: string;
  caption?: string;
};

export default function HelpScreenshot({ src, alt, caption }: HelpScreenshotProps) {
  return (
    <figure className="my-6 overflow-hidden rounded-xl border border-canvas-border bg-ink-50 shadow-card">
      <img
        src={src}
        alt={alt}
        className="w-full h-auto block"
        loading="lazy"
        decoding="async"
      />
      {caption ? (
        <figcaption className="px-4 py-2.5 text-xs text-ink-500 border-t border-canvas-border bg-white">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  );
}
