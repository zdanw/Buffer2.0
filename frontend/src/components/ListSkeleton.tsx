type ListSkeletonProps = {
  rows?: number;
  className?: string;
};

/** Placeholder rows while a filtered list is loading. */
export default function ListSkeleton({ rows = 4, className = '' }: ListSkeletonProps) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rounded-lg border border-canvas-border bg-gray-50 p-3 space-y-2 animate-pulse">
          <div className="h-4 w-[82%] rounded bg-gray-200" />
          <div className="h-3 w-[38%] rounded bg-gray-200" />
          <div className="h-5 w-16 rounded-full bg-gray-200" />
        </div>
      ))}
    </div>
  );
}
