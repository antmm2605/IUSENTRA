import { cn } from "@/lib/utils/cn";

type IusentraLogoProps = {
  compact?: boolean;
  className?: string;
};

export function IusentraLogo({ compact = false, className }: IusentraLogoProps) {
  return (
    <div className={cn("flex items-center gap-3", className)} aria-label="IUSENTRA">
      <svg
        viewBox="0 0 64 64"
        className="h-10 w-10 shrink-0 drop-shadow-sm"
        role="img"
        aria-label="Logo IUSENTRA"
      >
        <title>IUSENTRA</title>
        <circle cx="32" cy="32" r="25" fill="none" stroke="#071B33" strokeWidth="6" strokeDasharray="132 28" strokeLinecap="round" transform="rotate(-32 32 32)" />
        <circle cx="48" cy="15" r="4" fill="#2F80ED" />
        <path d="M25 17h16v6h-6v24h6v6H23v-6h6V25h-4z" fill="#071B33" />
        <path d="M41 17l6 6h-6z" fill="#C8A24A" />
        <path d="M18 52c8 4 20 4 28 0" fill="none" stroke="#C8A24A" strokeWidth="2" strokeLinecap="round" opacity=".9" />
      </svg>
      {!compact && (
        <div className="min-w-0">
          <div className="text-[0.98rem] font-black tracking-[0.22em] text-white">IUSENTRA</div>
          <div className="mt-0.5 text-[0.66rem] font-semibold tracking-[0.06em] text-slate-300">
            Legal Tech Platform
          </div>
        </div>
      )}
    </div>
  );
}
