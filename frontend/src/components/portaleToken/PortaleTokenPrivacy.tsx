import { useState, type FormEvent } from 'react'
import { CalendarCheck, House, Lock, PenLine, ShieldCheck, User } from 'lucide-react'
import { percorsoSezione, type Intestazione } from '../../portaleTokenData'
import { ErroreModulo, LinkSezione, type Naviga } from './PortaleTokenComuni'

const ERRORE_CONSENSO = 'Devi spuntare la casella per procedere.'

type Props = {
  intestazione: Intestazione
  occupato: boolean
  errore: string
  onFirma: () => void
  onErrore: (messaggio: string) => void
}

/** Consenso al trattamento dei dati (art. 7 Reg. UE 2016/679). */
export function PortaleTokenPrivacy({ intestazione, occupato, errore, onFirma, onErrore }: Props) {
  const [consenso, setConsenso] = useState(false)

  function invia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!consenso) {
      onErrore(ERRORE_CONSENSO)
      return
    }
    onFirma()
  }

  return (
    <div className="iu-ptk-pagina">
      <header className="iu-ptk-intestazione-centrata">
        <Lock size={40} className="iu-ptk-icona-avviso" aria-hidden="true" />
        <h1>Consenso al trattamento dei dati</h1>
        <p className="iu-ptk-muted">Ai sensi del Reg. UE 2016/679 (GDPR) — Art. 7</p>
      </header>

      {errore ? <ErroreModulo>{errore}</ErroreModulo> : null}

      <section className="iu-ptk-card" aria-labelledby="iu-ptk-informativa-titolo">
        <h2 id="iu-ptk-informativa-titolo" className="iu-ptk-card-titolo">Informativa sul trattamento dei dati personali</h2>
        <div className="iu-ptk-informativa" role="region" aria-labelledby="iu-ptk-informativa-titolo" tabIndex={0}>
          <p><strong>Titolare del trattamento:</strong> {intestazione.studioNome}</p>
          <p><strong>Finalità:</strong> I suoi dati personali (nome, cognome, indirizzo, recapiti, dati processuali) sono trattati esclusivamente per finalità connesse alla prestazione dell'assistenza legale richiesta, inclusa la gestione del mandato professionale, la comunicazione con le autorità giudiziarie e amministrative e il rispetto degli obblighi di legge.</p>
          <p><strong>Base giuridica:</strong> Il trattamento si fonda sull'esecuzione del contratto di prestazione professionale (art. 6, par. 1, lett. b) GDPR) e sull'adempimento di obblighi legali (lett. c).</p>
          <p><strong>Conservazione:</strong> I dati sono conservati per il periodo necessario all'esecuzione dell'incarico e per i successivi obblighi di conservazione previsti dalla legge (ordinariamente 10 anni).</p>
          <p><strong>Comunicazione:</strong> I dati potranno essere comunicati a soggetti terzi (consulenti, periti, autorità giudiziarie) nei limiti strettamente necessari alla tutela dei suoi interessi.</p>
          <p><strong>Diritti:</strong> Ha il diritto di accesso, rettifica, cancellazione, portabilità e opposizione al trattamento, da esercitare contattando direttamente lo studio.</p>
          <p><strong>Reclamo:</strong> Ha il diritto di proporre reclamo al Garante per la Protezione dei Dati Personali (www.garanteprivacy.it).</p>
        </div>
      </section>

      <form className="iu-ptk-modulo" onSubmit={invia} noValidate>
        <div className="iu-ptk-card">
          <label className="iu-ptk-spunta" htmlFor="iu-ptk-consenso">
            <input
              id="iu-ptk-consenso"
              type="checkbox"
              checked={consenso}
              onChange={(event) => setConsenso(event.target.checked)}
              aria-required="true"
              aria-invalid={Boolean(errore) && !consenso}
            />
            <span>
              Dichiaro di aver letto l'informativa e <strong>acconsento</strong> al trattamento dei miei dati personali
              da parte di <strong>{intestazione.studioNome}</strong> per le finalità indicate.
            </span>
          </label>
        </div>
        <button type="submit" className="iu-ptk-btn iu-ptk-btn--primario iu-ptk-btn--grande" disabled={occupato}>
          <PenLine size={18} aria-hidden="true" />{occupato ? 'Registrazione in corso…' : 'Firma il consenso'}
        </button>
        <p className="iu-ptk-nota">La firma digitale verrà registrata con data, ora e indirizzo IP per documentazione legale.</p>
      </form>
    </div>
  )
}

export function PortaleTokenPrivacyOk({ token, intestazione, onNaviga }: { token: string; intestazione: Intestazione; onNaviga: Naviga }) {
  return (
    <div className="iu-ptk-pagina iu-ptk-esito">
      <ShieldCheck size={48} className="iu-ptk-icona-ok" aria-hidden="true" />
      <h1>Consenso registrato</h1>
      <p className="iu-ptk-muted">
        Grazie {intestazione.clienteNome}. Il tuo consenso al trattamento dei dati
        è stato firmato digitalmente e registrato in modo sicuro.
      </p>
      <section className="iu-ptk-card iu-ptk-testo-sinistra" aria-labelledby="iu-ptk-riepilogo-firma">
        <h2 id="iu-ptk-riepilogo-firma" className="iu-ptk-card-titolo">Riepilogo firma</h2>
        <dl className="iu-ptk-dettagli">
          <div><dt><User size={16} aria-hidden="true" />Cliente:</dt><dd>{intestazione.clienteNome}</dd></div>
          <div><dt><CalendarCheck size={16} aria-hidden="true" />Data firma:</dt><dd>{intestazione.dataFirmaPrivacy || '—'}</dd></div>
          <div><dt><Lock size={16} aria-hidden="true" />Modalità:</dt><dd>Firma digitale GDPR</dd></div>
        </dl>
      </section>
      <LinkSezione href={percorsoSezione(token, 'home')} sezione="home" onNaviga={onNaviga} className="iu-ptk-btn iu-ptk-btn--primario">
        <House size={18} aria-hidden="true" />Torna alla home
      </LinkSezione>
    </div>
  )
}
