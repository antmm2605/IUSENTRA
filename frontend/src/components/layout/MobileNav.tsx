import { NavLink } from "react-router-dom";
import { Bot, FolderOpen, Home, Landmark, ReceiptText } from "lucide-react";
import { cn } from "@/lib/utils/cn";

const items = [
  { label: "Home", href: "/dashboard", icon: Home },
  { label: "Fascicoli", href: "/fascicoli", icon: FolderOpen },
  { label: "Lex", href: "/dashboard?lex=open", icon: Bot },
  { label: "Telematico", href: "/telematico", icon: Landmark },
  { label: "Economia", href: "/economia", icon: ReceiptText },
];

export function MobileNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-2 pb-[env(safe-area-inset-bottom)] shadow-[0_-12px_40px_rgba(15,23,42,.08)] backdrop-blur lg:hidden">
      <div className="grid grid-cols-5 gap-1 py-2">
        {items.map((item) => (
          <NavLink
            to={item.href}
            key={item.label}
            className={({ isActive }) =>
              cn(
                "flex min-h-11 flex-col items-center justify-center rounded-xl px-1 py-2 text-[0.68rem] font-bold text-slate-500",
                isActive && "bg-slate-100 text-ius-blue"
              )
            }
          >
            <item.icon className="mb-1 h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
