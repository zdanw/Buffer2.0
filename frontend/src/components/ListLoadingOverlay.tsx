import { Loader2 } from 'lucide-react';

type ListLoadingOverlayProps = {
  message: string;
  className?: string;
};

export default function ListLoadingOverlay({ message, className = '' }: ListLoadingOverlayProps) {
  return (
    <div
      className={`absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 rounded-lg bg-white/85 backdrop-blur-[1px] ${className}`}
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-7 w-7 animate-spin text-forge-600" />
      <span className="text-sm font-medium text-forge-800 text-center px-4">{message}</span>
    </div>
  );
}
