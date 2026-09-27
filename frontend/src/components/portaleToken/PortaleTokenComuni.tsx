import type { MouseEvent, ReactNode } from 'react'
import { CircleAlert, CircleCheck, Link2, ShieldAlert, TriangleAlert } from 'lucide-react'
import type { BadgeTone } from '../../ui/Badge'
import type { MessaggioPagina } from '../../pubblicoTokenApi'
import type { Sezione } from '../../portaleTokenData'

/** Parti comuni delle schermate del portale con link personale. */

export type Naviga = (sezione: Sezione, opzioni?: { messaggi?: MessaggioPagina[]; ancora?: string }) => void

/** Link reale (funziona anche con apertura in nuova scheda) gestito senza ricaricare la pagina. */
export function LinkSezione({
  href,
  sezione,
  ancora,
  onNaviga,
  className,
  children,
  ariaCurrent,
}: {
  href: string
  sezione: Sezione
  ancora?: string
  onNaviga: Naviga
  className?: string
  children: ReactNode
  ariaCurrent?: boolean
}) {
  function apri(event: MouseEvent<HTMLAnchorElement>) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    onNaviga(sezione, { ancora })
  }
  return (
    <a href={ancora ? `${href}#${ancora}` : href} className={className} onClick={apri} aria-current={ariaCurrent ? 'page' : undefined}>
      {children}
    </a>
  )
}

const TITOLI_AVVISO: Record<MessaggioPagina['categoria'], string> = {
  success: 'Operazione completata',
  info: 'Informazione',
  warning: 'Attenzione',
  danger: 'Operazione non completata',
}

export function Avvisi({ messaggi }: { messaggi: MessaggioPagina[] }) {
  if (!messaggi.length) return null
  return (
    <div className="iu-ptk-avvisi" role="status" aria-live="polite">
      {messaggi.map((messaggio, index) => (
        <div key={`${messaggio.categoria}-${index}`} className={`iu-ptk-avviso is-${messaggio.categoria}`}>
          <span className="iu-ptk-avviso__icona" aria-hidden="true">
            {messaggio.categoria === 'success' ? <CircleCheck size={20} /> : messaggio.categoria === 'danger' ? <CircleAlert size={20} /> : <TriangleAlert size={20} />}
          </span>
          <div>
            <strong>{TITOLI_AVVISO[messaggio.categoria]}</strong>
            <p>{messaggio.testo}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

export function ErroreModulo({ children }: { children: ReactNode }) {
  return (
    <div className="iu-ptk-errore" role="alert">
      <TriangleAlert size={18} aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export function LinkScaduto({ studioNome }: { studioNome: string }) {
  return (
    <main className="iu-ptk-scaduto" aria-labelledby="iu-ptk-scaduto-titolo">
      <Link2 size={64} className="iu-ptk-scaduto__icona" aria-hidden="true" />
      <h1 id="iu-ptk-scaduto-titolo">Link non più valido</h1>
      <p>
        Questo link di accesso al portale è scaduto o è stato revocato.
        Contatta il tuo avvocato per ricevere un nuovo link di accesso.
      </p>
      <section className="iu-ptk-card iu-ptk-scaduto__studio">
        <strong>{studioNome}</strong>
        <span>Richiedi un nuovo link di accesso direttamente allo studio.</span>
      </section>
      <p className="iu-ptk-nota">
        Codice errore: 410 Gone<br />
        Il portale cliente è accessibile solo tramite link personale.
      </p>
    </main>
  )
}

export function SezioneNegata({ messaggio, hrefHome, onNaviga }: { messaggio: string; hrefHome: string; onNaviga: Naviga }) {
  return (
    <section className="iu-ptk-centro">
      <ShieldAlert size={48} className="iu-ptk-icona-avviso" aria-hidden="true" />
      <h1>Sezione non disponibile</h1>
      <p className="iu-ptk-muted">{messaggio}</p>
      <LinkSezione href={hrefHome} sezione="home" onNaviga={onNaviga} className="iu-ptk-btn iu-ptk-btn--primario">
        Torna alla home
      </LinkSezione>
    </section>
  )
}

const TONI_STATO: Record<string, BadgeTone> = {
  GENERATO: 'primary',
  VERIFICATO: 'info',
  INVIATO: 'primary',
  APERTO: 'warning',
  ACCETTATO: 'success',
  CONVERTITO: 'success',
  RIFIUTATO: 'danger',
  SCADUTO: 'warning',
  ATTIVO: 'success',
  REVOCATO: 'danger',
  EMESSA: 'primary',
  PAGATA: 'success',
}

export function tonoStato(stato: string): BadgeTone {
  return TONI_STATO[stato] ?? 'neutral'
}

/** Colori Bootstrap del riepilogo tariffario -> toni del design system. */
export function tonoBootstrap(valore: string): BadgeTone {
  if (valore === 'success' || valore === 'danger' || valore === 'warning' || valore === 'info' || valore === 'primary') return valore
  return 'neutral'
}

export function Caricamento() {
  return (
    <section className="iu-ptk-centro" aria-live="polite" aria-busy="true">
      <span className="iu-ptk-spinner" aria-hidden="true" />
      <p className="iu-ptk-muted">Caricamento del portale in corso…</p>
    </section>
  )
}
