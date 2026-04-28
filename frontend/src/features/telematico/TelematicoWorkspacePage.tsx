import { Landmark, ShieldCheck, UploadCloud } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

const channels = [
  ["PST / PolisWeb", "Consultazione e import autorizzati", "/polisWeb"],
  ["PDP Penale", "Deposito e monitoraggio secondo policy canale", "/servizi-telematici?tab=pdp"],
  ["PAT / SIGA", "Acquisizione guidata e profilo separato", "/servizi-telematici"],
  ["PTT / SIGIT", "Canale autonomo, senza regole PCT improprie", "/servizi-telematici"],
  ["Upload guidato", "Pacchetto pronto per portali senza automazione completa", "/servizi-telematici"],
];

export function TelematicoWorkspacePage() {
  return (
    <div className="space-y-5">
      <section className="rounded-3xl bg-ius-navy p-6 text-white shadow-legal lg:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Badge tone="gold">Centro Servizi Telematici</Badge>
            <h1 className="mt-4 text-3xl font-black lg:text-4xl">Canali distinti, migrazione prudente.</h1>
            <p className="mt-3 max-w-3xl text-slate-300">
              PST, PDP, PAT, PTT e PEC restano governati dalla UI attuale finché React non copre policy,
              controlli, Local Signer, audit e rollback.
            </p>
          </div>
          <a href="/servizi-telematici" className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-ius-gold px-4 py-2 text-sm font-bold text-ius-navy transition hover:brightness-95">
            <UploadCloud className="h-4 w-4" />
            Apri UI attuale
          </a>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-5">
        {channels.map(([name, desc, href]) => (
          <Card key={name}>
            <CardBody>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-100 text-ius-blue">
                <Landmark className="h-5 w-5" />
              </div>
              <div className="mt-4 font-black">{name}</div>
              <div className="mt-1 text-sm text-slate-500">{desc}</div>
              <a href={href} className="mt-4 inline-flex text-sm font-black text-ius-blue hover:text-ius-sky">
                Apri percorso storico
              </a>
            </CardBody>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-black">Pre-deposito e conformità</h2>
        </CardHeader>
        <CardBody>
          <div className="grid gap-3 md:grid-cols-3">
            {["Metadati canale", "Allegati e limiti", "Firma secondo policy"].map((item) => (
              <div key={item} className="rounded-2xl border border-slate-200 p-4">
                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                <div className="mt-3 font-black">{item}</div>
                <div className="mt-1 text-sm text-slate-500">
                  Da portare in React solo dopo test su canale, tenant, audit e conferma dell’avvocato.
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
