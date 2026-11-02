import { Mail } from 'lucide-react'

/** Provenienza di un documento entrato nel fascicolo da una PEC collegata: «da PEC del gg/mm/aaaa», con il link alla PEC. */
export type DocumentoOriginePecDati = { label: string; href: string }

export function DocumentoOriginePec({ origine, nome }: { origine?: DocumentoOriginePecDati | null; nome: string }) {
  if (!origine?.href) return null
  return (
    <a className="iu-fas-doc-origin" href={origine.href} title="Apri la PEC da cui proviene il documento" aria-label={`Apri la PEC da cui proviene ${nome}`}>
      <Mail size={13} aria-hidden="true"/>
      <span>{origine.label}</span>
    </a>
  )
}
