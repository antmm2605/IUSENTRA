import { ExternalLink, Search } from "lucide-react";

export function Topbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/78 px-4 py-3 backdrop-blur-xl lg:px-6">
      <div className="flex items-center justify-between gap-3">
        <div className="hidden min-w-0 flex-1 items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 lg:flex">
          <Search className="h-4 w-4 text-slate-400" />
          <a href="/global-search" className="w-full text-sm font-semibold text-slate-500 hover:text-ius-blue">
            Apri Ricerca Studio nella UI attuale
          </a>
        </div>

        <div className="flex items-center gap-2">
          <a
            href="/"
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
          >
            UI attuale
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>
    </header>
  );
}
