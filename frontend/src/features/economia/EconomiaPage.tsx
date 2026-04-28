import { ReceiptText, ShieldCheck, WalletCards } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

const domains = [
  ["Preventivi e Incarichi", "cliente -> preventivo -> conferimento", "/preventivi"],
  ["Parcelle e Fatture", "timesheet, parcelle, fatture e PDF", "/fatturazione"],
  ["Incassi e Pagamenti", "riconciliazione economica e stato incassi", "/pagamenti"],
];

export function EconomiaPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-black">Economia dello studio</h1>
        <p className="mt-2 text-slate-500">
          Superficie React in preparazione. I flussi economici reali restano nella UI attuale fino alla parità completa.
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        {domains.map(([title, text, href], index) => {
          const Icon = index === 0 ? ReceiptText : index === 1 ? ShieldCheck : WalletCards;
          return (
            <Card key={title}>
              <CardBody>
                <Icon className="h-6 w-6 text-ius-blue" />
                <div className="mt-4 font-black">{title}</div>
                <div className="mt-1 text-sm text-slate-500">{text}</div>
                <a href={href} className="mt-4 inline-flex text-sm font-black text-ius-blue hover:text-ius-sky">
                  Apri UI attuale
                </a>
              </CardBody>
            </Card>
          );
        })}
      </section>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-black">Gate economico</h2>
        </CardHeader>
        <CardBody>
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm leading-relaxed text-slate-600">
            Non vengono mostrati importi simulati. I valori economici in React saranno abilitati solo quando API,
            repository, arrotondamenti, log calcolo, permessi e test fiscali saranno allineati alla UI storica.
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
