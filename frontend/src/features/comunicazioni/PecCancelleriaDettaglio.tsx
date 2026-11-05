import { Eye, FileText, ShieldCheck } from 'lucide-react'
import type { EmailAttachment } from '../../emailData'
import { etichettaTecnica, formattaTestoPec, fraseDelRegistro, nomeProprio, sezioneLeggibile } from './testoPec'
import './pecCancelleriaDettaglio.css'

/**
 * La PEC di cancelleria come la legge l'avvocato: i dati della comunicazione (Comunicazione.xml, D.M. 44/2011 e
 * specifiche DGSIA), il provvedimento da leggere per primo, le prove di consegna conservate a parte (ricevuta del
 * gestore, firma, indice della busta) e il testo del messaggio solo se serve.
 */

type Props = {
  profilo: Record<string, unknown>
  allegati: EmailAttachment[]
  testo: string
  onLeggi: (allegato: EmailAttachment) => void
}

const testo = (valore: unknown) => (typeof valore === 'string' ? valore.trim() : '')

function Dato({ etichetta, valore }: { etichetta: string; valore: string }) {
  if (!valore) return null
  return <><dt>{etichetta}</dt><dd>{valore}</dd></>
}

function TestoMessaggio({ corpo }: { corpo: string }) {
  const { consegna, campi, avvertenze } = formattaTestoPec(corpo)
  return (
    <details className="iu-pec-canc__testo">
      <summary>Testo del messaggio PEC</summary>
      {consegna ? <p className="iu-pec-canc__consegna">{consegna}</p> : null}
      {campi.length ? (
        <dl className="iu-pec-canc__registro" aria-label="Testo della comunicazione di cancelleria">
          {campi.map(([etichetta, valore]) => <Dato key={etichetta} etichetta={etichetta} valore={valore}/>)}
        </dl>
      ) : null}
      {avvertenze.length ? <ul className="iu-pec-canc__avvertenze">{avvertenze.map((a) => <li key={a}>{a}</li>)}</ul> : null}
      <details className="iu-pec-canc__integrale">
        <summary>Testo integrale, come ricevuto</summary>
        <pre>{corpo}</pre>
      </details>
    </details>
  )
}

export function PecCancelleriaDettaglio({ profilo, allegati, testo: corpo, onLeggi }: Props) {
  const ufficio = nomeProprio(testo(profilo.ufficio))
  const rg = testo(profilo.numero_rg)
  const evento = fraseDelRegistro(testo(profilo.tipo_evento) || testo(profilo.oggetto_evento))
  const descrizione = fraseDelRegistro(testo(profilo.descrizione_evento))
  const documenti = allegati.filter((a) => !etichettaTecnica(a.name))
  const tecnici = allegati.filter((a) => etichettaTecnica(a.name))
  return (
    <div className="iu-pec-canc" aria-label="Comunicazione di cancelleria">
      <section className="iu-pec-canc__dati" aria-label="Dati della comunicazione">
        <h3>Dati della comunicazione</h3>
        <dl>
          <Dato etichetta="Ufficio" valore={[ufficio, sezioneLeggibile(testo(profilo.sezione))].filter(Boolean).join(', ')}/>
          <Dato etichetta="Numero di ruolo" valore={rg ? `RG ${rg}` : ''}/>
          <Dato etichetta="Giudice" valore={nomeProprio(testo(profilo.giudice))}/>
          <Dato etichetta="Ricorrente / attore" valore={nomeProprio(testo(profilo.attore_principale) || testo(profilo.cliente))}/>
          <Dato etichetta="Resistente / convenuto" valore={nomeProprio(testo(profilo.convenuto_principale))}/>
          <Dato etichetta="Evento" valore={evento}/>
          <Dato etichetta="Descrizione" valore={descrizione && descrizione !== evento ? descrizione : ''}/>
          <Dato etichetta="Udienza" valore={testo(profilo.udienza_data_ora)}/>
        </dl>
      </section>

      <section className="iu-pec-canc__documenti" aria-label="Documenti della comunicazione">
        <h3>{documenti.length === 1 ? 'Provvedimento' : 'Documenti'}</h3>
        {documenti.length ? documenti.map((allegato) => (
          <article key={allegato.index}>
            <FileText size={18} aria-hidden="true"/>
            <span><strong>{allegato.name.replace(/\.zip$/i, '')}</strong><small>{allegato.sizeLabel || 'documento del giudice o della cancelleria'}</small></span>
            {allegato.available && (allegato.viewHref || allegato.previewHref)
              ? <button type="button" className="is-principale" onClick={() => onLeggi(allegato)}><Eye size={14}/> Leggi</button> : null}
            {allegato.available && allegato.downloadHref ? <a href={allegato.downloadHref}>Scarica</a> : null}
            {!allegato.available ? <small>{allegato.statusLabel || 'Da recuperare con la sincronizzazione'}</small> : null}
          </article>
        )) : <p>La comunicazione non contiene documenti oltre ai dati di cancelleria.</p>}
      </section>

      {tecnici.length ? (
        <details className="iu-pec-canc__prove">
          <summary><ShieldCheck size={15} aria-hidden="true"/> Prove di consegna e file tecnici ({tecnici.length})</summary>
          <p>Conservati come prova della comunicazione: non serve leggerli per lavorare la pratica.</p>
          {tecnici.map((allegato) => (
            <article key={allegato.index}>
              <span><strong>{etichettaTecnica(allegato.name)}</strong><small>{allegato.name}</small></span>
              {allegato.available && (allegato.viewHref || allegato.previewHref) ? <button type="button" onClick={() => onLeggi(allegato)}>Visualizza</button> : null}
              {allegato.available && allegato.downloadHref ? <a href={allegato.downloadHref}>Scarica</a> : null}
            </article>
          ))}
        </details>
      ) : null}

      {corpo ? <TestoMessaggio corpo={corpo}/> : null}
    </div>
  )
}

export { haDatiDiCancelleria } from './testoPec'
