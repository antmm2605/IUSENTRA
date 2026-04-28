import { Settings, ShieldCheck, Users } from "lucide-react";
import { Card, CardBody } from "@/components/ui/Card";

export function AdminPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-3xl font-black">Piattaforma</h1>
        <p className="mt-2 text-slate-500">Superadmin, tenant, storage, pack installazione e governance.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {([
          ["Tenant", "Gestione studi e storage", Users],
          ["Sicurezza", "Audit, ruoli e sessioni", ShieldCheck],
          ["Configurazione", "Pack, aggiornamenti e runtime", Settings],
        ] as const).map(([title, text, Icon]) => (
          <Card key={String(title)}>
            <CardBody>
              <Icon className="h-6 w-6 text-ius-blue" />
              <div className="mt-4 font-black">{title}</div>
              <div className="mt-1 text-sm text-slate-500">{text}</div>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
