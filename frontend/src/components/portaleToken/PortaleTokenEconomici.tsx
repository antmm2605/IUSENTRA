import { CircleCheck, Download, FileText, PenLine, Wallet } from 'lucide-react'
import { Badge } from '../../ui/Badge'
import type { AzioneRichiesta, DatiEconomici, DocumentoEconomico } from '../../portaleTokenData'
import { tonoBootstrap, tonoStato } from './PortaleTokenComuni'
import { AzioniRichieste } from './PortaleTokenHome'

const TITOLI: Record<DocumentoEconomico['kind'], string> = {
  preventivo: 'Preventivo',
  conferimento: 'Conferimento',
  parcella: 'Parcella',
}

type Props = {
  dati: DatiEconomici
  occupato: boolean
  onAzione: (azione: AzioneRichiesta) => void
}

function SchedaDocumento({ doc, occupato, onAzione }: { doc: DocumentoEconomico; occupato: boolean; onAzione: Props['onAzione'] }) {
  const titolo = `${TITOLI[doc.kind]} ${doc.numero}`
  return (
    <li className="iu-ptk-card">
      <div className="iu-ptk-riga iu-ptk-riga--spazio">
        <div>
          <div className="iu-ptk-riga">
            <strong>{titolo}</strong>
            <Badge tone={tonoStato(doc.stato)}>{doc.stato}</Badge>
          </div>
          <span className="iu-ptk-meta">
            {doc.data}{doc.scadenza ? ` · Scadenza ${doc.scadenza}` : ''}
          </span>
        </div>
        <strong className="iu-ptk-importo">{doc.totale}</strong>
      </div>
      <p className="iu-ptk-descrizione">{doc.descrizione}</p>

      {doc.calcolo ? (
        <dl className="iu-ptk-riquadro">
          {doc.calcolo.praticaLabel ? <div><dt>Tipologia:</dt><dd>{doc.calcolo.praticaLabel}</dd></div> : null}
          {doc.calcolo.regola ? <div><dt>Regola:</dt><dd>{doc.calcolo.regola}</dd></div> : null}
          {doc.calcolo.gradoSede ? <div><dt>Grado / sede:</dt><dd>{doc.calcolo.gradoSede}</dd></div> : null}
          {doc.calcolo.complianceLabel ? (
            <div className="iu-ptk-riga">
              <Badge tone={tonoBootstrap(doc.calcolo.complianceTone)}>{doc.calcolo.complianceLabel}</Badge>
              {doc.calcolo.tableCode ? <span className="iu-ptk-muted">Tabella {doc.calcolo.tableCode}</span> : null}
            </div>
          ) : null}
        </dl>
      ) : null}

      {doc.workflow ? (
        <div className="iu-ptk-riquadro is-bordo">
          <strong>Riepilogo intelligente</strong>
          {doc.workflow.channelLabel ? <p><span className="iu-ptk-muted">Canale:</span> <strong>{doc.workflow.channelLabel}</strong></p> : null}
          {doc.workflow.nextStepLabel ? <p><span className="iu-ptk-muted">Prossimo passo:</span> {doc.workflow.nextStepLabel}</p> : null}
          {doc.workflow.riferimenti.length ? <p className="iu-ptk-muted">{doc.workflow.riferimenti.join(' · ')}</p> : null}
        </div>
      ) : null}

      <div className="iu-ptk-pulsanti">
        {doc.kind === 'preventivo' && doc.canAccept ? (
          <button type="button" className="iu-ptk-btn iu-ptk-btn--successo" disabled={occupato} onClick={() => onAzione({ kind: 'preventivo', id: doc.id, title: titolo, subtitle: '', buttonLabel: '' })}>
            <CircleCheck size={16} aria-hidden="true" />Accetta preventivo
          </button>
        ) : null}
        {doc.kind === 'conferimento' && doc.canSign ? (
          <button type="button" className="iu-ptk-btn iu-ptk-btn--successo" disabled={occupato} onClick={() => onAzione({ kind: 'conferimento', id: doc.id, title: titolo, subtitle: '', buttonLabel: '' })}>
            <PenLine size={16} aria-hidden="true" />Firma conferimento
          </button>
        ) : null}
        {doc.pdfUrl ? (
          <>
            <a href={doc.pdfUrl} target="_blank" rel="noopener" className="iu-ptk-btn iu-ptk-btn--primario">
              <FileText size={16} aria-hidden="true" />PDF / Stampa<span className="iu-ptk-sr"> (si apre in una nuova scheda)</span>
            </a>
            <a href={`${doc.pdfUrl}?download=1`} className="iu-ptk-btn iu-ptk-btn--contorno">
              <Download size={16} aria-hidden="true" />Scarica
            </a>
          </>
        ) : null}
      </div>
    </li>
  )
}

function Gruppo({ titolo, documenti, occupato, onAzione }: { titolo: string; documenti: DocumentoEconomico[]; occupato: boolean; onAzione: Props['onAzione'] }) {
  if (!documenti.length) return null
  return (
    <section aria-label={titolo}>
      <h2 className="iu-ptk-sezione-titolo">{titolo}</h2>
      <ul className="iu-ptk-elenco">
        {documenti.map((doc) => <SchedaDocumento key={`${doc.kind}-${doc.id}`} doc={doc} occupato={occupato} onAzione={onAzione} />)}
      </ul>
    </section>
  )
}

export function PortaleTokenEconomici({ dati, occupato, onAzione }: Props) {
  return (
    <div className="iu-ptk-pagina">
      <header className="iu-ptk-intro">
        <h1>Documenti economici</h1>
        <p>Consultazione semplice e ordinata di preventivi, conferimenti d'incarico e parcelle dello studio.</p>
      </header>

      <dl className="iu-ptk-contatori iu-ptk-contatori--schede">
        <div className="iu-ptk-card"><dt>Preventivi</dt><dd>{dati.stats.preventivi}</dd></div>
        <div className="iu-ptk-card"><dt>Incarichi</dt><dd>{dati.stats.conferimenti}</dd></div>
        <div className="iu-ptk-card"><dt>Parcelle</dt><dd>{dati.stats.parcelle}</dd></div>
      </dl>

      {!dati.stats.totale ? (
        <section className="iu-ptk-card iu-ptk-vuoto">
          <Wallet size={36} aria-hidden="true" />
          <span>Nessun documento economico disponibile al momento.</span>
        </section>
      ) : (
        <>
          {dati.azioni.length ? (
            <section className="iu-ptk-card is-avviso" aria-labelledby="iu-ptk-azioni-economiche">
              <h2 id="iu-ptk-azioni-economiche" className="iu-ptk-card-titolo">Azioni richieste</h2>
              <AzioniRichieste azioni={dati.azioni.slice(0, 3)} occupato={occupato} onAzione={onAzione} />
            </section>
          ) : null}
          <Gruppo titolo="Preventivi" documenti={dati.preventivi} occupato={occupato} onAzione={onAzione} />
          <Gruppo titolo="Conferimenti di incarico" documenti={dati.conferimenti} occupato={occupato} onAzione={onAzione} />
          <Gruppo titolo="Parcelle" documenti={dati.parcelle} occupato={occupato} onAzione={onAzione} />
        </>
      )}
    </div>
  )
}
