import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { MobileNav } from "@/components/layout/MobileNav";
import { LexPanel } from "@/features/lex/LexPanel";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh lg:flex">
      <Sidebar />
      <div className="min-w-0 flex-1 pb-20 lg:pb-0">
        <Topbar />
        <main className="mx-auto w-full max-w-[1520px] px-4 py-5 lg:px-6 lg:py-6">
          {children}
        </main>
      </div>
      <LexPanel />
      <MobileNav />
    </div>
  );
}
