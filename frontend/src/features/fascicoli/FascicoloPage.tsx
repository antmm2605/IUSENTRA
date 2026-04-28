import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { FolderOpen, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { apiGet } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";

type FascicoloPayload = Record<string, unknown>;

export function FascicoloPage() {
  const { id } = useParams();
  const [fascicolo, setFascicolo] = useState<FascicoloPayload | null>(null);
  const [loading, setLoading] = useState(Boolean(id));

  useEffect(() => {
    if (!id) return;
    void apiGet<FascicoloPayload | null>(endpoints.fascicolo(id), null).then((data) => {
      setFascicolo(data);
      setLoading(false);
    });
  }, [id]);

  const titolo = String(fascicolo?.titolo || fascicolo?.oggetto || "Fascicoli");
  const rg = String(fascicolo?.numero_rg || "RG non impostato");
  const ufficio = String(fascicolo?.tribunale || "Ufficio non impostato");
  const legacyHref = id ? `/fascicoli/${encodeURIComponent(id)}` : "/fascicoli";

  return (
    <div className="space-y-5">
      <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-panel lg:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="info">{id ? rg : "Elenco fascicoli"}</Badge>
              <Badge tone="gold">{ufficio}</Badge>
            </div>
            <h1 className="mt-3 text-2xl font-black tracking-tight text-slate-950 lg:text-4xl">
              {loading ? "Caricamento fascicolo..." : titolo}
            </h1>
            <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-500 lg:text-base">
              La scheda fascicolo React è in anteprima read-only. Le azioni su documenti, scadenze, deposito e
              attività restano nella UI attuale fino al completamento dei test di parità.
            </p>
          </div>
          <a href={legacyHref} className="inline-flex min-h-11 items-center justify-center rounded-xl bg-ius-navy px-4 py-2 text-sm font-bold text-white transition hover:bg-ius-blue">
            Apri nella UI attuale
          </a>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <FolderOpen className="h-5 w-5 text-ius-blue" />
              <h2 className="text-lg font-black text-slate-950">Dati collegati</h2>
            </div>
          </CardHeader>
          <CardBody>
            <p className="text-sm leading-relaxed text-slate-500">
              Questa superficie non mostra dati simulati. Quando le API fascicolo saranno complete verranno esposti
              documenti, parti, scadenze, attività, depositi e ricevute con la stessa profondità della UI Jinja.
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <ShieldCheck className="h-5 w-5 text-emerald-600" />
              <h2 className="text-lg font-black text-slate-950">Gate di sicurezza</h2>
            </div>
          </CardHeader>
          <CardBody>
            <p className="text-sm leading-relaxed text-slate-500">
              Nessuna azione sensibile sarà portata in React senza copertura su tenant, permessi, audit, upload,
              Local Signer e rollback verso il percorso storico.
            </p>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
