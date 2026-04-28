import { NavLink } from "react-router-dom";
import { navigation } from "@/config/navigation";
import { IusentraLogo } from "@/components/brand/IusentraLogo";
import { cn } from "@/lib/utils/cn";

export function Sidebar() {
  return (
    <aside className="hidden h-dvh w-[286px] shrink-0 overflow-hidden bg-ius-navy text-white lg:flex lg:flex-col">
      <div className="border-b border-white/10 px-5 py-5">
        <IusentraLogo />
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <div className="mb-3 px-3 text-[0.68rem] font-black uppercase tracking-[0.18em] text-slate-400">
          Studio
        </div>
        <div className="space-y-1">
          {navigation.map((item) => (
            <NavLink
              key={item.label}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-slate-300 transition hover:bg-white/8 hover:text-white",
                  isActive && "bg-white/12 text-white shadow-sm"
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0 text-slate-400 group-hover:text-ius-gold" />
              <span className="truncate">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="border-t border-white/10 p-4">
        <div className="rounded-2xl bg-white/8 p-3">
          <div className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">Modalità</div>
          <div className="mt-1 text-sm font-bold">React Shell /app-v2</div>
          <div className="mt-1 text-xs leading-relaxed text-slate-400">
            Migrazione progressiva: backend Flask invariato.
          </div>
        </div>
      </div>
    </aside>
  );
}
