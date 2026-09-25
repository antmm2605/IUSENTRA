import { useState, type FormEvent, type ReactNode } from 'react'
import { ClipboardPlus, FileUp, KeyRound, ListPlus } from 'lucide-react'
import type { AccessoAtti, Opzione } from './types'

type Props = { dati: AccessoAtti; lavoro: boolean; invia: (azione: string) => (e: FormEvent<HTMLFormElement>) => void }
type Pannello = '' | 'richiesta' | 'pec' | 'importa' | 'attivita'

const Scelta = ({ nome, etichetta, opzioni }: { nome: string; etichetta: string; opzioni: Opzione[] }) => (
  <label>{etichetta}<select name={nome}>{opzioni.map((o) => <option key={o.valore} value={o.valore}>{o.etichetta}</option>)}</select></label>
)

/** Registrazioni dell'accesso agli atti: richiesta depositata, PEC con password, pacchetto scaricato, attività. */
export function AccessoAttiAzioni({ dati, lavoro, invia }: Props) {
  const [aperto, setAperto] = useState<Pannello>('')
  const [nomiFile, setNomiFile] = useState('')
  const voci: Array<{ id: Pannello; etichetta: string; icona: ReactNode }> = [
    { id: 'richiesta', etichetta: 'Registra la richiesta', icona: <ClipboardPlus size={14}/> },
    { id: 'pec', etichetta: 'Registra PEC e password', icona: <KeyRound size={14}/> },
    { id: 'importa', etichetta: 'Importa il fascicolo scaricato', icona: <FileUp size={14}/> },
    { id: 'attivita', etichetta: 'Nuova attività', icona: <ListPlus size={14}/> },
  ]
  return (
    <section className="iu-pdp-accesso__azioni" aria-label="Registrazioni">
      <div className="iu-pdp-segmenti">
        {voci.map((v) => <button key={v.id} type="button" className={aperto === v.id ? 'is-attiva' : ''} aria-expanded={aperto === v.id} onClick={() => setAperto(aperto === v.id ? '' : v.id)}>{v.icona} {v.etichetta}</button>)}
      </div>
      {aperto === 'richiesta' ? (
        <form className="iu-pdp-form" onSubmit={invia('richiesta')}>
          <Scelta nome="request_type" etichetta="Tipo" opzioni={dati.opzioni.tipiRichiesta}/>
          <Scelta nome="request_status" etichetta="Stato" opzioni={dati.opzioni.statiRichiesta}/>
          <label>Identificativo PDP<input name="request_reference" placeholder="AAAA/NNNNNNN"/></label>
          <label>Depositata il<input name="submitted_at" type="datetime-local"/></label>
          <label>Link valido fino al<input name="download_available_until" type="datetime-local"/></label>
          <label>Importo diritti (€)<input name="payment_amount" type="number" min="0" step="0.01"/></label>
          <label className="iu-pdp-spunta"><input type="checkbox" name="payment_required" value="1"/> Diritti di copia da pagare</label>
          <label className="iu-pdp-spunta"><input type="checkbox" name="legal_aid_declared" value="1"/> Gratuito patrocinio</label>
          <label className="iu-pdp-form__largo">Note<textarea name="notes" rows={2}/></label>
          <button type="submit" className="iu-pdp-primario" disabled={lavoro}>Registra</button>
        </form>
      ) : null}
      {aperto === 'pec' ? (
        <form className="iu-pdp-form" onSubmit={invia('registra-pec')}>
          <label>Oggetto della PEC<input name="subject" required/></label>
          <label>Ricevuta il<input name="message_date" type="datetime-local"/></label>
          <label>Password<input name="extracted_password" autoComplete="off"/></label>
          <label>Link valido fino al<input name="download_available_until" type="datetime-local"/></label>
          <label className="iu-pdp-form__largo">Testo della PEC (IUSENTRA ricava password e scadenza)<textarea name="body_text" rows={3}/></label>
          <input type="hidden" name="contains_download_notice" value="1"/>
          <button type="submit" className="iu-pdp-primario" disabled={lavoro}>Registra</button>
        </form>
      ) : null}
      {aperto === 'importa' ? (
        <form className="iu-pdp-form" onSubmit={invia('importa-scaricato')}>
          <label className="iu-pdp-carica"><FileUp size={14}/> {nomiFile || 'Scegli lo ZIP o i file scaricati dal PDP'}
            <input type="file" name="files" multiple onChange={(e) => setNomiFile(Array.from(e.target.files || []).map((f) => f.name).join(', '))}/></label>
          <label>Nota<input name="note_importazione"/></label>
          <button type="submit" className="iu-pdp-primario" disabled={lavoro}>Importa nel fascicolo</button>
        </form>
      ) : null}
      {aperto === 'attivita' ? (
        <form className="iu-pdp-form" onSubmit={invia('nuova-attivita')}>
          <label>Titolo<input name="title" required/></label>
          <Scelta nome="task_type" etichetta="Tipo" opzioni={dati.opzioni.tipiAttivita}/>
          <Scelta nome="priority" etichetta="Priorità" opzioni={dati.opzioni.priorita}/>
          <label>Entro il<input name="due_at" type="datetime-local"/></label>
          <button type="submit" className="iu-pdp-primario" disabled={lavoro}>Aggiungi</button>
        </form>
      ) : null}
    </section>
  )
}
