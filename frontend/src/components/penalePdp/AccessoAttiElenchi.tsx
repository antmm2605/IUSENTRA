import { useState, type FormEvent } from 'react'
import { CheckCircle2, Eye, EyeOff, Link2 } from 'lucide-react'
import { Badge } from '../dashboard'
import { dataOra, type AccessoAtti } from './types'

type Props = { dati: AccessoAtti; lavoro: boolean; invia: (azione: string) => (e: FormEvent<HTMLFormElement>) => void; completa: (id: string) => void }

/** Richieste, PEC con password, documenti collegati, attività e cronologia dell'accesso agli atti. */
export function AccessoAttiElenchi({ dati, lavoro, invia, completa }: Props) {
  const [visibili, setVisibili] = useState<Record<string, boolean>>({})
  const aperte = dati.attivita.filter((a) => a.aperta)
  return (
    <div className="iu-pdp-accesso__elenchi">
      <section><h6>Richieste di accesso ({dati.richieste.length})</h6>
        {dati.richieste.length ? <ul className="iu-pdp-lista">{dati.richieste.map((r) => (
          <li key={r.id}><strong>{r.tipo}</strong><Badge tone={r.stato === 'denied' || r.stato === 'expired' ? 'danger' : r.stato === 'authorized' || r.stato === 'downloaded' ? 'success' : 'info'}>{r.statoEtichetta}</Badge>
            {r.riferimento ? <em>{r.riferimento}</em> : null}{r.downloadFinoAl ? <span>link fino al {dataOra(r.downloadFinoAl)}</span> : null}</li>
        ))}</ul> : <p className="iu-pdp-nota">Nessuna richiesta ancora: genera la richiesta e depositala sul PDP.</p>}
      </section>
      <section><h6>PEC con link e password ({dati.pec.length})</h6>
        {dati.pec.length ? <ul className="iu-pdp-lista">{dati.pec.map((m) => (
          <li key={m.id}><strong>{m.oggetto}</strong><span>{dataOra(m.data)}</span>
            {m.password ? (<>
              <code>{visibili[m.id] ? m.password : '••••••••'}</code>
              <button type="button" aria-label={visibili[m.id] ? 'Nascondi password' : 'Mostra password'} onClick={() => setVisibili({ ...visibili, [m.id]: !visibili[m.id] })}>{visibili[m.id] ? <EyeOff size={14}/> : <Eye size={14}/>}</button>
            </>) : null}</li>
        ))}</ul> : <p className="iu-pdp-nota">Nessuna PEC collegata: usa «Cerca link e password nella PEC».</p>}
      </section>
      <section><h6>Attività aperte ({aperte.length})</h6>
        {aperte.length ? <ul className="iu-pdp-lista">{aperte.map((a) => (
          <li key={a.id}><strong>{a.titolo}</strong><Badge tone={a.priorita === 'urgent' || a.priorita === 'high' ? 'warning' : 'neutral'}>{a.prioritaEtichetta}</Badge>
            {a.scadenza ? <span>entro {dataOra(a.scadenza)}</span> : null}
            <button type="button" disabled={lavoro} onClick={() => completa(a.id)}><CheckCircle2 size={14}/> Fatta</button></li>
        ))}</ul> : <p className="iu-pdp-nota">Nessuna attività aperta.</p>}
      </section>
      <section><h6>Documenti del procedimento ({dati.documentiCollegati.length})</h6>
        {dati.documentiCollegati.length ? <ul className="iu-pdp-lista">{dati.documentiCollegati.map((d) => (
          <li key={d.id}><strong>{d.titolo}</strong><em>{d.ruolo}</em>{d.firmato ? <Badge tone="success">Firmato</Badge> : null}<span>{dataOra(d.quando)}</span></li>
        ))}</ul> : null}
        {dati.documentiFascicolo.length ? (
          <form className="iu-pdp-form" onSubmit={invia('collega-documento')}>
            <label>Documento del fascicolo<select name="local_doc_id" required>{dati.documentiFascicolo.map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}</select></label>
            <label>Ruolo<select name="document_role">{dati.opzioni.ruoliDocumento.map((o) => <option key={o.valore} value={o.valore}>{o.etichetta}</option>)}</select></label>
            <button type="submit" disabled={lavoro}><Link2 size={14}/> Collega</button>
          </form>
        ) : null}
      </section>
      {dati.cronologia.length ? (
        <details className="iu-pdp-cronologia"><summary>Cronologia ({dati.cronologia.length})</summary>
          <ul className="iu-pdp-lista">{dati.cronologia.map((e) => <li key={e.id}><span>{dataOra(e.quando)}</span><strong>{e.titolo}</strong>{e.descrizione ? <span>{e.descrizione}</span> : null}</li>)}</ul>
        </details>
      ) : null}
    </div>
  )
}
