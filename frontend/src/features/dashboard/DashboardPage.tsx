import { useEffect, useState } from "react";
import { AlertTriangle, CalendarDays, FileCheck2, FolderOpen, ReceiptText } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { apiGet } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { DashboardPayload, DashboardStats, FascicoloSummary, NextAction } from "@/types/domain";

const emptyStats: DashboardStats = {
  todayAppointments: 0,
  urgentDeadlines: 0,
  openMatters: 0,
  unpaidAmount: "€ 0,00",
  documentsToReview: 0,
};

const emptyPayload: DashboardPayload = {
  source: "inizializzazione",
  generated_at: "",
  stats: emptyStats,
  actions: [],
  fascicoli: [],
};

export function DashboardPage() {
  const [payload, setPayload] = useState<DashboardPayload>(emptyPayload);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void apiGet<DashboardPayload>(endpoints.dashboard, emptyPayload).then((data) => {
      setPayload(data);
      setLoading(false);
    });
  }, []);

  const stats = payload.stats || emptyStats;
  const actions = payload.actions || [];
  const fascicoli = payload.fascicoli || [];

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-3xl bg-ius-navy shadow-legal">
        <div className="grid gap-6 p-6 text-white lg:grid-cols-[1.35fr_.95fr] lg:p-8">
          <div>
            <div className="inline-flex rounded-full border border-white/10 bg-white/8 px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] text-slate-300">
              React shell controllata
            </div>
            <h1 className="mt-4 max-w-3xl text-3xl font-black tracking-tight lg:text-5xl">
              Nuova interfaccia, stesso backend verificato.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-slate-300">
              Questa anteprima usa dati reali serviti da Flask. Le pagine storiche restano attive finché ogni
              flusso React non supera test, accessibilità, responsive e parità funzionale.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href="/workspace-intelligente" className="inline-flex min-h-11 items-center justify-center rounded-xl bg-ius-gold px-4 py-2 text-sm font-bold text-ius-navy transition hover:brightness-95">
                Apri Regia Operativa attuale
              </a>
              <a href="/global-search" className="inline-flex min-h-11 items-center justify-center rounded-xl border border-white/15 bg-white px-4 py-2 text-sm font-bold text-slate-900 transition hover:bg-slate-50">
                Apri Ricerca Studio
              </a>
            </div>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/8 p-5">
            <div className="text-sm font-bold uppercase tracking-[0.16em] text-slate-300">Stato migrazione</div>
            <div className="mt-4 space-y-3">
              {loading ? (
                <StatusCard title="Caricamento dati reali" description="Recupero del contesto operativo da Flask." tone="info" />
              ) : actions.length ? (
                actions.slice(0, 3).map((action) => (
                  <StatusCard key={action.id || action.title} title={action.title} description={action.description} tone={action.tone} />
                ))
              ) : (
                <StatusCard
                  title="Nessuna azione urgente"
                  description="Il runtime non segnala priorità operative nel periodo monitorato."
                  tone="success"
                />
              )}
              {payload.warning ? <StatusCard title="Avviso" description={payload.warning} tone="warning" /> : null}
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Agenda oggi" value={stats.todayAppointments} icon={<CalendarDays className="h-5 w-5" />} hint="Appuntamenti del giorno" />
        <StatCard label="Scadenze urgenti" value={stats.urgentDeadlines} icon={<AlertTriangle className="h-5 w-5" />} hint="Da presidiare entro 3 giorni" />
        <StatCard label="Fascicoli aperti" value={stats.openMatters} icon={<FolderOpen className="h-5 w-5" />} hint="Attivi nello studio" />
        <StatCard label="Da incassare" value={stats.unpaidAmount} icon={<ReceiptText className="h-5 w-5" />} hint="Parcelle non saldate" />
        <StatCard label="Notifiche termini" value={stats.documentsToReview} icon={<FileCheck2 className="h-5 w-5" />} hint="Avvisi da presidiare" />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-black text-slate-950">Fascicoli dal runtime reale</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Anteprima read-only: l’apertura operativa rimane nella UI storica finché non chiudiamo la parità funzionale.
                </p>
              </div>
              <a href="/fascicoli" className="inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-800 transition hover:bg-slate-50">
                Apri UI attuale
              </a>
            </div>
          </CardHeader>
          <CardBody className="space-y-3">
            {fascicoli.length ? (
              fascicoli.map((fascicolo) => <FascicoloRow key={fascicolo.id || fascicolo.title} fascicolo={fascicolo} />)
            ) : (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
                Nessun fascicolo disponibile per l’anteprima React oppure dati non ancora migrati su questo endpoint.
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-black text-slate-950">Regola di migrazione</h2>
            <p className="mt-1 text-sm text-slate-500">Ogni schermata React entra in produzione solo dopo questi controlli.</p>
          </CardHeader>
          <CardBody>
            <div className="space-y-4">
              {["API reale", "Parità funzionale", "Test desktop/tablet/mobile", "Accessibilità", "Rollback immediato"].map((step, index) => (
                <div key={step} className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full bg-ius-navy text-sm font-black text-white">
                    {index + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-bold text-slate-900">{step}</div>
                    <div className="mt-1 text-xs text-slate-500">Blocco obbligatorio prima dello switch dalla UI Jinja.</div>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </section>
    </div>
  );
}

function StatusCard({ title, description, tone }: Pick<NextAction, "title" | "description" | "tone">) {
  return (
    <div className="rounded-2xl bg-white/10 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-bold">{title}</div>
          <div className="mt-1 text-sm text-slate-300">{description}</div>
        </div>
        <Badge tone={tone}>{tone}</Badge>
      </div>
    </div>
  );
}

function FascicoloRow({ fascicolo }: { fascicolo: FascicoloSummary }) {
  const href = fascicolo.id ? `/fascicoli/${encodeURIComponent(fascicolo.id)}` : "/fascicoli";
  return (
    <article className="rounded-2xl border border-slate-200 p-4 transition hover:border-ius-sky/40 hover:bg-slate-50">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-black text-slate-950">{fascicolo.title}</div>
          <div className="mt-1 text-sm text-slate-500">{fascicolo.rg} · {fascicolo.office}</div>
        </div>
        <a href={href} className="text-sm font-black text-ius-blue hover:text-ius-sky">
          Apri
        </a>
      </div>
    </article>
  );
}
