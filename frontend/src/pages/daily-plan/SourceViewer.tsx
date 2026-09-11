import { ExternalLink, FileSearch, FolderOpen, Info, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { SourceDocumentReader } from '@/components/SourceDocumentModal'
import { formatDateTimeIt } from '@/formatting'
import { dailyPlanSourceKindLabel, type FonteAttivita } from './types'

type Props = {
  fonti: FonteAttivita[]
  attiva: number
  onSelect: (index: number) => void
  stato: 'loading' | 'ready' | 'error'
  messaggio: string
  fascicoloHref: string
  onRetry: () => void
}

function SourceCard({ fonte }: { fonte: FonteAttivita }) {
  return (
    <div className="grid h-full content-start gap-3 overflow-y-auto p-4 sm:p-6">
      <div className="grid gap-1">
        <span className="text-xs font-medium text-muted-foreground">
          {dailyPlanSourceKindLabel[fonte.tipo] || 'Fonte'}
        </span>
        <strong className="text-base">{fonte.etichetta}</strong>
      </div>
      {fonte.dettagli.length ? (
        <dl className="grid gap-x-6 gap-y-2 rounded-md border bg-background p-3 text-sm sm:grid-cols-[max-content_1fr]">
          {fonte.dettagli.map((dettaglio) => (
            <div key={dettaglio.etichetta} className="contents">
              <dt className="font-medium text-muted-foreground">{dettaglio.etichetta}</dt>
              <dd className="leading-6">{dettaglio.valore}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {fonte.nota ? (
        <p className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <Info size={15} className="mt-0.5" aria-hidden="true" /> {fonte.nota}
        </p>
      ) : null}
      {fonte.apri_href ? (
        <Button asChild variant="outline" size="sm" className="justify-self-start">
          <a href={fonte.apri_href}>
            <ExternalLink aria-hidden="true" /> Apri la scheda completa
          </a>
        </Button>
      ) : null}
    </div>
  )
}

export function SourceViewer({ fonti, attiva, onSelect, stato, messaggio, fascicoloHref, onRetry }: Props) {
  if (stato === 'loading') {
    return (
      <div className="iu-source-document-reader__state" role="status">
        <strong>Cerco la fonte dell’attività...</strong>
        <span>Documento, PEC o scadenza che la prova si aprono qui, senza lasciare il piano.</span>
      </div>
    )
  }
  if (stato === 'error') {
    return (
      <div className="iu-source-document-reader__state iu-source-document-reader__state--error" role="alert">
        <strong>Fonte non disponibile in questo momento.</strong>
        <span>Riprova tra poco: il piano resta consultabile.</span>
        <Button type="button" size="sm" variant="outline" className="justify-self-center" onClick={onRetry}>
          Riprova
        </Button>
      </div>
    )
  }
  const fonte = fonti[attiva]
  if (!fonte) {
    return (
      <div className="iu-source-document-reader__state" role="status">
        <strong>Nessuna fonte consultabile collegata.</strong>
        <span>{messaggio || 'Per questa attività non risulta un documento o una PEC di origine.'}</span>
        {fascicoloHref ? (
          <Button asChild size="sm" variant="outline" className="justify-self-center">
            <a href={fascicoloHref}>
              <FolderOpen aria-hidden="true" /> Apri il fascicolo
            </a>
          </Button>
        ) : null}
      </div>
    )
  }
  const rilevata = formatDateTimeIt(fonte.rilevata_il, '')
  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)]">
      <div className="flex flex-wrap items-center gap-1.5 border-b bg-background px-3 py-2" role="tablist" aria-label="Fonti dell’attività">
        {fonti.map((item, index) => (
          <button
            key={`${item.tipo}-${item.href || item.apri_href}-${index}`}
            type="button"
            role="tab"
            aria-selected={index === attiva}
            onClick={() => onSelect(index)}
            className={`flex max-w-72 items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              index === attiva ? 'border-primary bg-primary/10 text-primary' : 'bg-background hover:bg-muted'
            }`}
          >
            {item.verificata ? <ShieldCheck size={13} aria-hidden="true" /> : <FileSearch size={13} aria-hidden="true" />}
            <span className="truncate">
              {dailyPlanSourceKindLabel[item.tipo] || 'Fonte'} · {item.etichetta}
            </span>
          </button>
        ))}
        {rilevata ? <span className="ml-auto text-xs text-muted-foreground">Ricevuta il {rilevata}</span> : null}
      </div>
      <div className="relative min-h-0" role="tabpanel">
        {fonte.href ? (
          <SourceDocumentReader key={fonte.href} href={fonte.href} label={fonte.etichetta} />
        ) : (
          <SourceCard fonte={fonte} />
        )}
      </div>
    </div>
  )
}
