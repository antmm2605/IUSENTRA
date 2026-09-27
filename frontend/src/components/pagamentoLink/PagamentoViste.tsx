import { useState, type ReactNode } from 'react'
import {
  Building2,
  Check,
  ChevronRight,
  CircleCheck,
  Clipboard,
  Clock,
  CreditCard,
  History,
  Hourglass,
  Info,
  Landmark,
  Lock,
  Mail,
  Smartphone,
  TriangleAlert,
  User,
  Wallet,
} from 'lucide-react'
import type { MessaggioPagina } from '../../pubblicoTokenApi'
import type { DatiCheckout, DatiEsito, DatiGiaPagato, Provider } from '../../pagamentoLinkData'

/** Schermate del link di pagamento: stessi testi delle pagine classiche. */

const PROVIDER: Record<Provider, { etichetta: string; dettaglio: string; icona: ReactNode }> = {
  stripe: { etichetta: 'Carta di credito / debito', dettaglio: 'Visa, Mastercard, Amex — powered by Stripe', icona: <CreditCard size={28} aria-hidden="true" /> },
  paypal: { etichetta: 'PayPal', dettaglio: 'Paga con il tuo account PayPal', icona: <Wallet size={28} aria-hidden="true" /> },
  satispay: { etichetta: 'Satispay', dettaglio: "Paga con l'app Satispay", icona: <Smartphone size={28} aria-hidden="true" /> },
  sumup: { etichetta: 'SumUp', dettaglio: 'Carta o pagamento digitale via SumUp', icona: <Wallet size={28} aria-hidden="true" /> },
  bonifico: { etichetta: 'Bonifico bancario (SEPA)', dettaglio: 'Riceverai le coordinate bancarie', icona: <Landmark size={28} aria-hidden="true" /> },
}

function PiedeStudio({ studioNome }: { studioNome: string }) {
  return <p className="iu-pgl-piede"><Building2 size={14} aria-hidden="true" /><strong>{studioNome}</strong></p>
}

export function Messaggi({ messaggi }: { messaggi: MessaggioPagina[] }) {
  if (!messaggi.length) return null
  return (
    <div className="iu-pgl-messaggi" role="status" aria-live="polite">
      {messaggi.map((m, i) => (
        <div key={`${m.categoria}-${i}`} className={`iu-pgl-avviso is-${m.categoria}`}>
          {m.categoria === 'success' ? <CircleCheck size={18} aria-hidden="true" /> : <TriangleAlert size={18} aria-hidden="true" />}
          <span>{m.testo}</span>
        </div>
      ))}
    </div>
  )
}

export function VistaCheckout({
  studioNome,
  dati,
  messaggi,
  inCorso,
  onScegli,
}: {
  studioNome: string
  dati: DatiCheckout
  messaggi: MessaggioPagina[]
  inCorso: Provider | null
  onScegli: (provider: Provider) => void
}) {
  return (
    <main className="iu-pgl-scheda" aria-labelledby="iu-pgl-studio">
      <header className="iu-pgl-testata">
        <p className="iu-pgl-studio" id="iu-pgl-studio"><Building2 size={18} aria-hidden="true" />{studioNome}</p>
        {dati.descrizione ? <p className="iu-pgl-descrizione">{dati.descrizione}</p> : null}
        <p className="iu-pgl-importo"><span className="iu-pgl-sr">Importo da pagare: </span>{dati.importo}</p>
        {dati.cliente ? <p className="iu-pgl-cliente"><User size={16} aria-hidden="true" />{dati.cliente}</p> : null}
      </header>
      <div className="iu-pgl-corpo">
        {dati.scadenza ? (
          <dl className="iu-pgl-info">
            <div><dt>Scadenza link</dt><dd>{dati.scadenza}</dd></div>
          </dl>
        ) : null}

        {dati.providerAttivi.length ? (
          <section aria-labelledby="iu-pgl-metodi">
            <h1 id="iu-pgl-metodi" className="iu-pgl-titoletto">Scegli il metodo di pagamento</h1>
            <ul className="iu-pgl-metodi">
              {dati.providerAttivi.map((provider) => {
                const voce = PROVIDER[provider]
                return (
                  <li key={provider}>
                    <button
                      type="button"
                      className={`iu-pgl-metodo is-${provider}${inCorso === provider ? ' is-scelto' : ''}`}
                      disabled={inCorso !== null}
                      aria-busy={inCorso === provider}
                      onClick={() => onScegli(provider)}
                    >
                      <span className="iu-pgl-metodo__icona">{voce.icona}</span>
                      <span className="iu-pgl-metodo__testo">
                        <strong>{voce.etichetta}</strong>
                        <span>{inCorso === provider ? 'Apertura del pagamento in corso…' : voce.dettaglio}</span>
                      </span>
                      <ChevronRight size={18} aria-hidden="true" />
                    </button>
                  </li>
                )
              })}
            </ul>
          </section>
        ) : (
          <div className="iu-pgl-avviso is-warning" role="status">
            <TriangleAlert size={18} aria-hidden="true" />Nessun metodo di pagamento attivo. Contatta lo studio.
          </div>
        )}

        <Messaggi messaggi={messaggi} />
        <p className="iu-pgl-sicuro"><Lock size={14} aria-hidden="true" />Pagamento sicuro — connessione cifrata HTTPS</p>
      </div>
    </main>
  )
}

export function VistaGiaPagato({ studioNome, dati }: { studioNome: string; dati: DatiGiaPagato }) {
  return (
    <main className="iu-pgl-scheda is-stretta" aria-labelledby="iu-pgl-gia-pagato">
      <header className="iu-pgl-testata is-ok is-centrata">
        <span className="iu-pgl-cerchio" aria-hidden="true"><CircleCheck size={40} /></span>
        <h1 id="iu-pgl-gia-pagato">Già pagato</h1>
        <p>{dati.importo}</p>
      </header>
      <div className="iu-pgl-corpo is-centrata">
        <p className="iu-pgl-muted">
          Questa parcella risulta già saldata.
          {dati.dataPagamento ? <> Pagamento registrato il <strong>{dati.dataPagamento}</strong>.</> : null}
        </p>
        {dati.metodo ? <p className="iu-pgl-muted">Metodo: <strong>{dati.metodo}</strong></p> : null}
        <PiedeStudio studioNome={studioNome} />
      </div>
    </main>
  )
}

export function VistaScaduto({ studioNome }: { studioNome: string }) {
  return (
    <main className="iu-pgl-scheda is-stretta" aria-labelledby="iu-pgl-scaduto">
      <header className="iu-pgl-testata is-spento is-centrata">
        <span className="iu-pgl-cerchio" aria-hidden="true"><History size={40} /></span>
        <h1 id="iu-pgl-scaduto">Link scaduto</h1>
      </header>
      <div className="iu-pgl-corpo is-centrata">
        <p className="iu-pgl-muted">
          Questo link di pagamento non è più valido o è scaduto.<br />
          Contatta lo studio per richiederne uno nuovo.
        </p>
        <PiedeStudio studioNome={studioNome} />
      </div>
    </main>
  )
}

function CopiaIban({ iban }: { iban: string }) {
  const [copiato, setCopiato] = useState(false)
  async function copia() {
    try {
      await navigator.clipboard.writeText(iban)
      setCopiato(true)
    } catch {
      setCopiato(false)
    }
  }
  return (
    <>
      <button type="button" className="iu-pgl-btn iu-pgl-btn--piccolo" onClick={copia} aria-label="Copia IBAN">
        {copiato ? <Check size={14} aria-hidden="true" /> : <Clipboard size={14} aria-hidden="true" />}
      </button>
      <span className="iu-pgl-sr" role="status" aria-live="polite">{copiato ? 'IBAN copiato negli appunti' : ''}</span>
    </>
  )
}

export function VistaEsito({ studioNome, dati }: { studioNome: string; dati: DatiEsito }) {
  if (dati.vista === 'pagato') {
    return (
      <main className="iu-pgl-scheda" aria-labelledby="iu-pgl-esito">
        <header className="iu-pgl-testata is-ok is-centrata">
          <span className="iu-pgl-cerchio" aria-hidden="true"><Check size={40} /></span>
          <h1 id="iu-pgl-esito">Pagamento ricevuto!</h1>
          <p>{dati.importo}</p>
        </header>
        <div className="iu-pgl-corpo">
          <p className="iu-pgl-muted">Il tuo pagamento è stato elaborato con successo. Lo studio riceverà automaticamente la conferma.</p>
          <dl className="iu-pgl-info">
            <div><dt>Metodo</dt><dd>{dati.metodo}</dd></div>
            {dati.idTransazione ? <div><dt>ID transazione</dt><dd className="iu-pgl-spezza">{dati.idTransazione}</dd></div> : null}
            <div><dt>Data</dt><dd>{dati.dataPagamento}</dd></div>
          </dl>
          <div className="iu-pgl-avviso is-success"><Mail size={18} aria-hidden="true" />Conserva questa pagina come ricevuta.</div>
          <PiedeStudio studioNome={studioNome} />
        </div>
      </main>
    )
  }
  if (dati.vista === 'bonifico') {
    const coordinate = dati.bonifico
    return (
      <main className="iu-pgl-scheda" aria-labelledby="iu-pgl-esito">
        <header className="iu-pgl-testata is-info is-centrata">
          <span className="iu-pgl-cerchio" aria-hidden="true"><Landmark size={40} /></span>
          <h1 id="iu-pgl-esito">Effettua il bonifico</h1>
          <p>{dati.importo}</p>
        </header>
        <div className="iu-pgl-corpo">
          <p className="iu-pgl-muted">
            Per completare il pagamento esegui un bonifico SEPA con i seguenti dati.
            Il pagamento sarà confermato dallo studio alla ricezione.
          </p>
          {coordinate ? (
            <dl className="iu-pgl-iban">
              {coordinate.intestazione ? <div><dt>Intestatario</dt><dd><strong>{coordinate.intestazione}</strong></dd></div> : null}
              <div>
                <dt>IBAN</dt>
                <dd className="iu-pgl-riga"><strong className="iu-pgl-spezza">{coordinate.iban}</strong>{coordinate.iban ? <CopiaIban iban={coordinate.iban} /> : null}</dd>
              </div>
              {coordinate.banca ? <div><dt>Banca</dt><dd>{coordinate.banca}</dd></div> : null}
              <div><dt>Importo esatto</dt><dd><strong>{dati.importo}</strong></dd></div>
              <div><dt>Causale</dt><dd><strong>{dati.causale}</strong></dd></div>
              {coordinate.noteAggiuntive ? <div className="iu-pgl-note"><dt className="iu-pgl-sr">Note</dt><dd>{coordinate.noteAggiuntive}</dd></div> : null}
            </dl>
          ) : null}
          <div className="iu-pgl-avviso is-info"><Info size={18} aria-hidden="true" />Lo studio verificherà l'accredito e aggiornerà lo stato della parcella.</div>
          <PiedeStudio studioNome={studioNome} />
        </div>
      </main>
    )
  }
  return (
    <main className="iu-pgl-scheda" aria-labelledby="iu-pgl-esito">
      <header className="iu-pgl-testata is-attesa is-centrata">
        <span className="iu-pgl-cerchio" aria-hidden="true"><Hourglass size={40} /></span>
        <h1 id="iu-pgl-esito">Pagamento in attesa</h1>
        <p>{dati.importo}</p>
      </header>
      <div className="iu-pgl-corpo">
        <p className="iu-pgl-muted">Il tuo pagamento è in fase di elaborazione. Lo studio riceverà conferma a breve.</p>
        <div className="iu-pgl-avviso is-warning"><Clock size={18} aria-hidden="true" />Torna a controllare tra qualche minuto o contatta lo studio.</div>
        <PiedeStudio studioNome={studioNome} />
      </div>
    </main>
  )
}
