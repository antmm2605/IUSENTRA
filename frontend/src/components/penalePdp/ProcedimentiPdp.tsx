import { ArrowRight, CalendarClock, FolderOpen } from 'lucide-react'
import { Badge } from '../dashboard'
import type { ProcedimentoPdp } from './types'

export type Filtro = 'tutti' | 'da-fare' | 'attesa' | 'non-autorizzati'

const DA_FARE = new Set(['RIFARE', 'INVIARE', 'COMPLETARE', 'REGISTRO', 'NOMINA'])

function passa(p: ProcedimentoPdp, filtro: Filtro, cerca: string): boolean {
  if (filtro === 'da-fare' && !DA_FARE.has(p.azione.codice)) return false
  if (filtro === 'attesa' && p.azione.codice !== 'ESITO') return false
  if (filtro === 'non-autorizzati' && p.autorizzato) return false
  const testo = cerca.trim().toLowerCase()
  return !testo || [p.titolo, p.cliente, p.protocollo, p.tribunale, p.ultimo?.identificativo].some((v) => (v || '').toLowerCase().includes(testo))
}

function dataIt(valore: string): string {
  if (!valore) return ''
  const d = new Date(valore)
  return Number.isNaN(d.getTime()) ? valore : d.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

/** Elenco dei procedimenti penali con prossima azione; ogni riga apre la sezione «Deposito penale» del fascicolo. */
export function ProcedimentiPdp({ procedimenti, filtro, cerca }: { procedimenti: ProcedimentoPdp[]; filtro: Filtro; cerca: string }) {
  const visibili = procedimenti.filter((p) => passa(p, filtro, cerca))
  if (!procedimenti.length) {
    return <p className="iu-pdp-nota">Nessun fascicolo penale. Crea un fascicolo di tipo «Penale»: la sezione «Deposito penale (PDP)» comparirà nel fascicolo.</p>
  }
  if (!visibili.length) return <p className="iu-pdp-nota">Nessun procedimento per questo filtro.</p>
  return (
    <ul className="iu-pdp-procedimenti">
      {visibili.map((p) => (
        <li key={p.id}>
          <div className="iu-pdp-procedimenti__dati">
            <a href={p.href}><strong>{p.titolo}</strong></a>
            <span>{[p.cliente, p.protocollo || 'registro da indicare', p.ufficioEtichetta].filter(Boolean).join(' · ')}</span>
            <div className="iu-pdp-procedimenti__stati">
              <Badge tone={p.autorizzato ? 'success' : 'warning'}>{p.autorizzato ? 'Autorizzato' : 'Non autorizzato'}</Badge>
              {p.canale ? <Badge tone={p.canale.obbligatorio ? 'info' : 'neutral'}>{p.canale.etichetta}</Badge> : null}
              {p.ultimo ? <Badge tone={p.ultimo.statoTono}>{p.ultimo.statoEtichetta}</Badge> : null}
              {p.prossimaUdienza ? <span className="iu-pdp-procedimenti__udienza"><CalendarClock size={13}/> Udienza {dataIt(p.prossimaUdienza)}</span> : null}
            </div>
            {p.ultimo ? (
              <small>{p.ultimo.atto}{p.ultimo.identificativo ? ` · invio ${p.ultimo.identificativo}` : ''}{p.ultimo.dataInvio ? ` · ${dataIt(p.ultimo.dataInvio)}` : ''}
                {p.ultimo.motivazione ? ` · motivazione: ${p.ultimo.motivazione}` : ''}</small>
            ) : null}
          </div>
          <div className="iu-pdp-procedimenti__azione">
            <Badge tone={p.azione.tono}>{p.azione.testo}</Badge>
            <a className="iu-pdp-pagina__primario" href={p.href}>Deposito penale <ArrowRight size={14}/></a>
            <a href={p.accessoAttiHref}><FolderOpen size={14}/> Accesso agli atti</a>
          </div>
        </li>
      ))}
    </ul>
  )
}
