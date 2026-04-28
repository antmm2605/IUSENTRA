import { FileText, ShieldCheck, WandSparkles } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

const checks = [
  ["Catalogo reale", "La UI attuale resta collegata ai modelli dello studio e al catalogo professionale.", FileText],
  ["Redazione guidata", "La migrazione porterà in React solo i flussi già coperti da API e test.", WandSparkles],
  ["Controlli deposito", "Nessun controllo deterministico viene sostituito da placeholder o testo generico.", ShieldCheck],
] as const;

export function RedazioneAttiPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-[.9fr_1.1fr]">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-black">Redazione Atti</h1>
          <p className="mt-1 text-sm text-slate-500">
            Area in migrazione controllata. Usa la UI attuale per redigere, validare e generare atti reali.
          </p>
        </CardHeader>
        <CardBody className="space-y-3">
          {checks.map(([title, text, Icon]) => (
            <div key={String(title)} className="rounded-2xl border border-slate-200 p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-2xl bg-slate-100 p-3 text-ius-blue">
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-black">{title}</div>
                  <div className="mt-1 text-sm text-slate-500">{text}</div>
                </div>
              </div>
            </div>
          ))}
          <a href="/template-atti" className="inline-flex min-h-11 items-center justify-center rounded-xl bg-ius-navy px-4 py-2 text-sm font-bold text-white transition hover:bg-ius-blue">
            Apri Redazione Atti attuale
          </a>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-black">Regola di attivazione</h2>
          <p className="mt-1 text-sm text-slate-500">
            Prima dello switch serviranno API reali per catalogo, compilazione, allegati, anteprima, audit e deposito.
          </p>
        </CardHeader>
        <CardBody>
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm leading-relaxed text-slate-600">
            Nessun atto viene generato da questa anteprima. Il contenuto redazionale rimane nel motore storico fino
            alla chiusura dei test di regressione su modelli, dati fascicolo, controlli telematici e PDF finale.
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
