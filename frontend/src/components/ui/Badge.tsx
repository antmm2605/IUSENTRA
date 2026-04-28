import type { ReactNode } from "react";
import type { Tone } from "@/types/domain";
import { cn } from "@/lib/utils/cn";

const toneClass: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 border-slate-200",
  primary: "bg-blue-50 text-blue-700 border-blue-200",
  secondary: "bg-slate-100 text-slate-700 border-slate-200",
  success: "bg-emerald-50 text-emerald-700 border-emerald-200",
  warning: "bg-amber-50 text-amber-800 border-amber-200",
  danger: "bg-rose-50 text-rose-700 border-rose-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
  gold: "bg-yellow-50 text-yellow-800 border-yellow-200",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-bold", toneClass[tone], className)}>
      {children}
    </span>
  );
}
