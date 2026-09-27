import {
  Building2,
  CalendarDays,
  ChevronRight,
  CircleArrowRight,
  Clock,
  CloudUpload,
  FileCheck,
  FileText,
  Folder,
  History,
  IdCard,
  Receipt,
  ShieldAlert,
  ShieldCheck,
  Wallet,
} from 'lucide-react'
import { Badge } from '../../ui/Badge'
import { percorsoSezione, type AzioneRichiesta, type DatiHome, type Fascicolo } from '../../portaleTokenData'
import { LinkSezione, type Naviga } from './PortaleTokenComuni'

type Props = {
  token: string
  dati: DatiHome
  occupato: boolean
  onNaviga: Naviga
  onAzione: (azione: AzioneRichiesta) => void
}

export function AzioniRichieste({ azioni, occupato, onAzione }: { azioni: AzioneRichiesta[]; occupato: boolean; onAzione: Props['onAzione'] }) {
  return (
    <ul className="iu-ptk-azioni">
      {azioni.map((azione) => (
        <li key={`${azione.kind}-${azione.id}`} className="iu-ptk-card is-avviso">
          <strong>{azione.title}</strong>
          {azione.subtitle ? <span className="iu-ptk-muted">{azione.subtitle}</span> : null}
          <button type="button" className="iu-ptk-btn iu-ptk-btn--successo" disabled={occupato} onClick={() => onAzione(azione)}>
            {azione.buttonLabel}
          </button>
        </li>
      ))}
    </ul>
  )
}

function tonoFascicolo(stato: string) {
  if (stato === 'APERTO') return 'primary' as const
  return 'neutral' as const
}

function SchedaFascicolo({ fascicolo }: { fascicolo: Fascicolo }) {
  const tracker = fascicolo.tracker
  return (
    <li className="iu-ptk-card">
      <div className="iu-ptk-riga">
        <Badge tone={tonoFascicolo(fascicolo.stato)}>{fascicolo.stato}</Badge>
        <div className="iu-ptk-flessibile">
          <strong>{fascicolo.titolo}</strong>
          <span className="iu-ptk-muted">
            {fascicolo.tipo}{fascicolo.numeroRg ? ` - RG ${fascicolo.numeroRg}` : ''}
          </span>
          {fascicolo.tribunale ? (
            <span className="iu-ptk-meta"><Building2 size={14} aria-hidden="true" />{fascicolo.tribunale}</span>
          ) : null}
          {tracker ? (
            <div className="iu-ptk-tracker">
              <div className="iu-ptk-tracker__testa">
                <span>Stato pratica</span>
                <strong>{tracker.currentLabel}</strong>
              </div>
              <progress className="iu-ptk-progresso" value={tracker.percent} max={100} aria-label={`Avanzamento pratica: ${tracker.percent}%`}>
                {tracker.percent}%
              </progress>
              <ol className="iu-ptk-passi">
                {tracker.steps.map((step, index) => (
                  <li key={`${step.label}-${index}`} className={step.complete ? 'is-fatto' : ''}>{step.label}</li>
                ))}
              </ol>
              {tracker.lastEvent ? (
                <span className="iu-ptk-meta"><History size={14} aria-hidden="true" />Ultimo evento: {tracker.lastEvent}</span>
              ) : null}
              {tracker.nextEvent ? (
                <span className="iu-ptk-meta"><CircleArrowRight size={14} aria-hidden="true" />Prossimo passaggio: {tracker.nextEvent}</span>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </li>
  )
}

function iconaDocumento(kind: string) {
  if (kind === 'preventivo') return <FileText size={18} aria-hidden="true" />
  if (kind === 'conferimento') return <FileCheck size={18} aria-hidden="true" />
  return <Receipt size={18} aria-hidden="true" />
}

function tonoPriorita(priorita: string): string {
  if (priorita === 'CRITICA') return 'is-critica'
  if (priorita === 'ALTA') return 'is-alta'
  return ''
}

export function PortaleTokenHome({ token, dati, occupato, onNaviga, onAzione }: Props) {
  const { intestazione } = dati
  const permessi = intestazione.permessi
  const privacyDaFirmare = permessi.firmaPrivacy && !intestazione.privacyFirmata
  return (
    <div className="iu-ptk-pagina">
      <header className="iu-ptk-intro">
        <h1>Benvenuto, {intestazione.clienteNome}</h1>
        <p>Benvenuto nel tuo spazio riservato - {dati.oggi}</p>
      </header>

      {privacyDaFirmare ? (
        <LinkSezione href={percorsoSezione(token, 'privacy')} sezione="privacy" onNaviga={onNaviga} className="iu-ptk-banner">
          <ShieldAlert size={22} aria-hidden="true" />
          <span className="iu-ptk-flessibile">
            <strong>Privacy da firmare</strong>
            <span>Firma il consenso al trattamento dei dati personali per completare il profilo del portale.</span>
          </span>
          <ChevronRight size={20} aria-hidden="true" />
        </LinkSezione>
      ) : null}

      {dati.azioni.length ? (
        <section aria-labelledby="iu-ptk-azioni-titolo">
          <h2 id="iu-ptk-azioni-titolo" className="iu-ptk-sezione-titolo">Azioni richieste</h2>
          <AzioniRichieste azioni={dati.azioni.slice(0, 2)} occupato={occupato} onAzione={onAzione} />
        </section>
      ) : null}

      {permessi.vediFascicoli ? (
        dati.fascicoli.length ? (
          <section aria-labelledby="fascicoli">
            <h2 id="fascicoli" className="iu-ptk-sezione-titolo">Le tue pratiche</h2>
            <ul className="iu-ptk-elenco">
              {dati.fascicoli.map((fascicolo) => <SchedaFascicolo key={fascicolo.id} fascicolo={fascicolo} />)}
            </ul>
          </section>
        ) : (
          <section id="fascicoli" className="iu-ptk-card iu-ptk-vuoto">
            <Folder size={36} aria-hidden="true" />
            <span>Nessuna pratica disponibile.</span>
          </section>
        )
      ) : null}

      {permessi.vediAppuntamenti && dati.appuntamenti.length ? (
        <section aria-labelledby="iu-ptk-appuntamenti-titolo">
          <h2 id="iu-ptk-appuntamenti-titolo" className="iu-ptk-sezione-titolo">Prossimi appuntamenti</h2>
          <ul className="iu-ptk-elenco">
            {dati.appuntamenti.map((appuntamento, index) => (
              <li key={`${appuntamento.titolo}-${index}`} className="iu-ptk-card iu-ptk-riga">
                <span className="iu-ptk-data">
                  <strong>{appuntamento.giorno}</strong>
                  <span>{appuntamento.mese}</span>
                </span>
                <span className="iu-ptk-flessibile">
                  <strong>{appuntamento.titolo}</strong>
                  <span className="iu-ptk-meta">
                    <Clock size={14} aria-hidden="true" />{appuntamento.ora}{appuntamento.luogo ? ` - ${appuntamento.luogo}` : ''}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {permessi.vediScadenze && dati.scadenze.length ? (
        <section aria-labelledby="iu-ptk-scadenze-titolo">
          <h2 id="iu-ptk-scadenze-titolo" className="iu-ptk-sezione-titolo">Scadenze nei prossimi 30 giorni</h2>
          <ul className="iu-ptk-elenco">
            {dati.scadenze.map((scadenza, index) => (
              <li key={`${scadenza.titolo}-${index}`} className="iu-ptk-card iu-ptk-riga">
                <CalendarDays size={22} className={`iu-ptk-priorita ${tonoPriorita(scadenza.priorita)}`} aria-hidden="true" />
                <span className="iu-ptk-flessibile">
                  <strong>{scadenza.titolo}</strong>
                  <span className="iu-ptk-meta">{scadenza.data}</span>
                </span>
                {scadenza.perentorio ? <Badge tone="danger">PERENTORIO</Badge> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {permessi.vediEconomici ? (
        <section aria-labelledby="iu-ptk-economia-titolo">
          <h2 id="iu-ptk-economia-titolo" className="iu-ptk-sezione-titolo">Preventivi, incarichi e parcelle</h2>
          <div className="iu-ptk-card">
            <div className="iu-ptk-riga iu-ptk-riga--spazio">
              <div>
                <strong>Area economica del tuo rapporto con lo studio</strong>
                <p className="iu-ptk-muted">Qui trovi i documenti economici disponibili in PDF, pronti da aprire, scaricare o stampare.</p>
              </div>
              <LinkSezione href={percorsoSezione(token, 'economici')} sezione="economici" onNaviga={onNaviga} className="iu-ptk-btn iu-ptk-btn--contorno">
                <Wallet size={16} aria-hidden="true" />Apri area
              </LinkSezione>
            </div>
            <dl className="iu-ptk-contatori">
              <div><dt>Preventivi</dt><dd>{dati.stats.preventivi}</dd></div>
              <div><dt>Incarichi</dt><dd>{dati.stats.conferimenti}</dd></div>
              <div><dt>Parcelle</dt><dd>{dati.stats.parcelle}</dd></div>
            </dl>
            {dati.cronologia.length ? (
              <ul className="iu-ptk-cronologia">
                {dati.cronologia.map((voce, index) => (
                  <li key={`${voce.kind}-${voce.numero}-${index}`}>
                    {iconaDocumento(voce.kind)}
                    <span className="iu-ptk-flessibile">
                      <strong>{voce.numero} - {voce.titolo}</strong>
                      <span className="iu-ptk-meta">{voce.data}{voce.fascicoloLabel ? ` - ${voce.fascicoloLabel}` : ''}</span>
                    </span>
                    <span className="iu-ptk-importo">{voce.totale}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="iu-ptk-muted">Nessun documento economico ancora disponibile.</p>
            )}
          </div>
        </section>
      ) : null}

      <section aria-labelledby="iu-ptk-rapide-titolo">
        <h2 id="iu-ptk-rapide-titolo" className="iu-ptk-sezione-titolo">Azioni rapide</h2>
        <div className="iu-ptk-rapide">
          {permessi.caricaDocumenti ? (
            <LinkSezione href={percorsoSezione(token, 'documenti')} sezione="documenti" onNaviga={onNaviga} className="iu-ptk-rapida">
              <CloudUpload size={30} aria-hidden="true" /><span>Carica documenti</span>
            </LinkSezione>
          ) : null}
          {permessi.vediAnagrafica ? (
            <LinkSezione href={percorsoSezione(token, 'anagrafica')} sezione="anagrafica" onNaviga={onNaviga} className="iu-ptk-rapida">
              <IdCard size={30} aria-hidden="true" /><span>I miei dati</span>
            </LinkSezione>
          ) : null}
          {permessi.vediEconomici ? (
            <LinkSezione href={percorsoSezione(token, 'economici')} sezione="economici" onNaviga={onNaviga} className="iu-ptk-rapida">
              <Wallet size={30} aria-hidden="true" /><span>Documenti economici</span>
            </LinkSezione>
          ) : null}
          {privacyDaFirmare ? (
            <LinkSezione href={percorsoSezione(token, 'privacy')} sezione="privacy" onNaviga={onNaviga} className="iu-ptk-rapida is-avviso">
              <ShieldCheck size={30} aria-hidden="true" /><span>Firma privacy</span>
            </LinkSezione>
          ) : null}
        </div>
      </section>

      <footer className="iu-ptk-piede">
        Portale riservato - accesso protetto tramite link sicuro.<br />
        {intestazione.studioNome}
      </footer>
    </div>
  )
}
