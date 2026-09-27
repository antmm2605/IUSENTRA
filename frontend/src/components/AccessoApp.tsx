import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode, type Ref } from 'react'
import {
  ArrowLeft,
  BookCheck,
  Building2,
  CircleAlert,
  CircleCheck,
  Clock,
  Eye,
  EyeOff,
  Info,
  KeyRound,
  LogIn,
  LogOut,
  ShieldCheck,
  Smartphone,
  TriangleAlert,
  UserCheck,
} from 'lucide-react'
import {
  cambiaPasswordObbligatoria,
  configurazionePagina,
  esciDallaSessione,
  inviaCodiceVerifica,
  inviaCredenziali,
  leggiStatoAccesso,
  percorsoInterno,
  type ConfigurazionePagina,
  type EsitoAccesso,
  type MessaggioAccesso,
  type StatoAccesso,
  type TonoMessaggio,
} from '../accessoData'
import './AccessoApp.css'

/*
 * Pagina pubblica di accesso: credenziali, verifica in due passaggi e cambio
 * obbligatorio della password. Ogni decisione (blocco dei tentativi, secondo
 * fattore, destinazione) è del server; qui si mostra l'esito.
 */

const ICONE_TONO: Record<TonoMessaggio, typeof Info> = {
  success: CircleCheck,
  info: Info,
  warning: TriangleAlert,
  danger: CircleAlert,
}

const LUNGHEZZA_MINIMA_PASSWORD = 8

function Avviso({ tono, children, id, focusRef }: { tono: TonoMessaggio; children: ReactNode; id?: string; focusRef?: Ref<HTMLDivElement> }) {
  const Icona = ICONE_TONO[tono]
  const urgente = tono === 'danger' || tono === 'warning'
  return (
    <div
      id={id}
      ref={focusRef}
      tabIndex={focusRef ? -1 : undefined}
      className={`iu-accesso-avviso is-${tono}`}
      role={urgente ? 'alert' : 'status'}
    >
      <Icona size={18} aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}

function formatoAttesa(secondi: number): string {
  const minuti = Math.floor(secondi / 60)
  const resto = String(secondi % 60).padStart(2, '0')
  return `${minuti}:${resto}`
}

/** Secondi di blocco residui, aggiornati ogni secondo a partire dal Retry-After. */
function useSecondiResidui(iniziali: number, versione: number): number {
  const [residui, setResidui] = useState(0)
  useEffect(() => {
    setResidui(iniziali)
    if (iniziali <= 0) return undefined
    const fine = Date.now() + iniziali * 1000
    const timer = window.setInterval(() => {
      const valore = Math.max(0, Math.ceil((fine - Date.now()) / 1000))
      setResidui(valore)
      if (valore === 0) window.clearInterval(timer)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [iniziali, versione])
  return residui
}

function CampoPassword({
  id,
  name,
  label,
  autoComplete,
  visibile,
  onToggle,
  minLength,
  describedBy,
  invalid,
  autoFocus,
}: {
  id: string
  name: string
  label: string
  autoComplete: string
  visibile: boolean
  onToggle?: () => void
  minLength?: number
  describedBy?: string
  invalid?: boolean
  autoFocus?: boolean
}) {
  return (
    <div className="iu-accesso-campo">
      <label htmlFor={id}>{label}</label>
      <div className="iu-accesso-password">
        <input
          id={id}
          name={name}
          type={visibile ? 'text' : 'password'}
          autoComplete={autoComplete}
          required
          minLength={minLength}
          aria-describedby={describedBy}
          aria-invalid={invalid ? true : undefined}
          autoFocus={autoFocus}
          spellCheck={false}
          autoCapitalize="none"
        />
        {onToggle ? (
          <button
            type="button"
            className="iu-accesso-mostra"
            onClick={onToggle}
            aria-controls={id}
            aria-pressed={visibile}
            aria-label={visibile ? 'Nascondi password' : 'Mostra password'}
            title={visibile ? 'Nascondi password' : 'Mostra password'}
          >
            {visibile ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
          </button>
        ) : null}
      </div>
    </div>
  )
}

function ModuloAccesso({ stato, config }: { stato: StatoAccesso; config: ConfigurazionePagina }) {
  const [invio, setInvio] = useState(false)
  const [esito, setEsito] = useState<EsitoAccesso | null>(null)
  const [versioneBlocco, setVersioneBlocco] = useState(0)
  const [passwordVisibile, setPasswordVisibile] = useState(false)
  const avvisoRef = useRef<HTMLDivElement>(null)
  const residui = useSecondiResidui(esito?.retryAfter ?? 0, versioneBlocco)
  const bloccato = residui > 0

  useEffect(() => {
    if (esito && !esito.ok) avvisoRef.current?.focus()
  }, [esito])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (invio || bloccato) return
    const form = event.currentTarget
    setInvio(true)
    const risultato = await inviaCredenziali(form, config.next)
    if (risultato.ok && risultato.redirect) {
      window.location.assign(risultato.redirect)
      return
    }
    const campoPassword = form.elements.namedItem('password')
    if (campoPassword instanceof HTMLInputElement) campoPassword.value = ''
    setEsito(risultato)
    setVersioneBlocco((valore) => valore + 1)
    setInvio(false)
  }

  const errore = esito && !esito.ok ? esito : null
  return (
    <form className="iu-accesso-form" onSubmit={onSubmit} aria-describedby={errore ? 'accesso-errore' : undefined}>
      {errore ? (
        <Avviso tono="danger" id="accesso-errore" focusRef={avvisoRef}>
          <p>{errore.message}</p>
          {bloccato ? (
            <p className="iu-accesso-timer" role="timer" aria-live="off">
              <Clock size={14} aria-hidden="true" /> Nuovo tentativo possibile tra {formatoAttesa(residui)}
            </p>
          ) : null}
        </Avviso>
      ) : null}
      {stato.multiStudio ? (
        <div className="iu-accesso-campo">
          <label htmlFor="accesso-studio">
            Studio <span className="iu-accesso-facoltativo">(lascia vuoto per l'accesso degli amministratori di piattaforma)</span>
          </label>
          {stato.studi.length ? (
            <select id="accesso-studio" name="studio_slug" defaultValue="" autoComplete="organization">
              <option value="">Amministrazione di piattaforma</option>
              {stato.studi.map((studio) => (
                <option key={studio.slug} value={studio.slug}>{studio.nome}</option>
              ))}
            </select>
          ) : (
            <input
              id="accesso-studio"
              name="studio_slug"
              type="text"
              autoComplete="organization"
              placeholder="es. studio-rossi"
              spellCheck={false}
              autoCapitalize="none"
            />
          )}
        </div>
      ) : null}
      <div className="iu-accesso-campo">
        <label htmlFor="accesso-utente">Nome utente</label>
        <input
          id="accesso-utente"
          name="username"
          type="text"
          autoComplete="username"
          placeholder="nome.utente"
          required
          autoFocus
          spellCheck={false}
          autoCapitalize="none"
        />
      </div>
      <CampoPassword
        id="accesso-password"
        name="password"
        label="Password"
        autoComplete="current-password"
        visibile={passwordVisibile}
        onToggle={() => setPasswordVisibile((valore) => !valore)}
        invalid={Boolean(errore)}
      />
      <button type="submit" className="iu-accesso-primario" disabled={invio || bloccato} aria-busy={invio}>
        <LogIn size={18} aria-hidden="true" />
        {invio ? 'Accesso in corso…' : 'Accedi'}
      </button>
      {config.next ? (
        <p className="iu-accesso-nota">
          <ArrowLeft size={14} aria-hidden="true" className="iu-accesso-ritorno" />
          Dopo l'accesso torni automaticamente alla pagina richiesta.
        </p>
      ) : null}
    </form>
  )
}

function ModuloVerifica({ stato }: { stato: StatoAccesso }) {
  const [invio, setInvio] = useState(false)
  const [esito, setEsito] = useState<EsitoAccesso | null>(null)
  const avvisoRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (esito && !esito.ok) avvisoRef.current?.focus()
  }, [esito])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (invio) return
    const form = event.currentTarget
    setInvio(true)
    const risultato = await inviaCodiceVerifica(form)
    if (risultato.redirect && (risultato.ok || risultato.code === 'verifica_annullata' || risultato.code === 'verifica_non_in_corso')) {
      window.location.assign(risultato.redirect)
      return
    }
    const campo = form.elements.namedItem('codice')
    if (campo instanceof HTMLInputElement) campo.value = ''
    setEsito(risultato)
    setInvio(false)
  }

  const errore = esito && !esito.ok ? esito : null
  return (
    <form className="iu-accesso-form" onSubmit={onSubmit} autoComplete="off">
      {stato.utenteVerifica ? <p className="iu-accesso-utente">{stato.utenteVerifica}</p> : null}
      {errore ? (
        <Avviso tono="danger" id="verifica-errore" focusRef={avvisoRef}>
          <p>{errore.message}</p>
        </Avviso>
      ) : null}
      <p className="iu-accesso-aiuto" id="verifica-aiuto">
        <Smartphone size={16} aria-hidden="true" />
        Inserisci il codice a 6 cifre generato dalla tua app di autenticazione (Google Authenticator, Aegis, ecc.).
      </p>
      <div className="iu-accesso-campo">
        <label htmlFor="verifica-codice">Codice di verifica</label>
        <input
          id="verifica-codice"
          name="codice"
          className="iu-accesso-codice"
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          pattern="[0-9]{6}"
          maxLength={6}
          placeholder="000000"
          required
          autoFocus
          aria-describedby={errore ? 'verifica-aiuto verifica-errore' : 'verifica-aiuto'}
          aria-invalid={errore ? true : undefined}
        />
      </div>
      <button type="submit" className="iu-accesso-primario" disabled={invio} aria-busy={invio}>
        <ShieldCheck size={18} aria-hidden="true" />
        {invio ? 'Verifica in corso…' : 'Verifica'}
      </button>
      <a className="iu-accesso-link" href="/login">
        <ArrowLeft size={14} aria-hidden="true" /> Torna all'accesso
      </a>
    </form>
  )
}

function ModuloPassword({ stato, avvisoGiaMostrato }: { stato: StatoAccesso; avvisoGiaMostrato: boolean }) {
  const [invio, setInvio] = useState(false)
  const [errore, setErrore] = useState('')
  const [completato, setCompletato] = useState('')
  const [sessioneScaduta, setSessioneScaduta] = useState(false)
  const [visibili, setVisibili] = useState(false)
  const avvisoRef = useRef<HTMLDivElement>(null)
  const destinazione = percorsoInterno(stato.destinazione)

  useEffect(() => {
    if (errore || completato) avvisoRef.current?.focus()
  }, [errore, completato])

  useEffect(() => {
    if (!completato) return undefined
    const timer = window.setTimeout(() => window.location.assign(destinazione), 1500)
    return () => window.clearTimeout(timer)
  }, [completato, destinazione])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (invio) return
    const form = event.currentTarget
    const dati = new FormData(form)
    const nuova = String(dati.get('password_new') || '')
    if (nuova.length < LUNGHEZZA_MINIMA_PASSWORD) {
      setErrore('La nuova password deve avere almeno 8 caratteri.')
      return
    }
    if (nuova !== String(dati.get('password_conferma') || '')) {
      setErrore('Le due nuove password non coincidono.')
      return
    }
    setInvio(true)
    setErrore('')
    const risultato = await cambiaPasswordObbligatoria(form)
    if (risultato.ok) {
      form.reset()
      setCompletato(risultato.message)
      return
    }
    setSessioneScaduta(risultato.sessioneScaduta)
    setErrore(risultato.message)
    setInvio(false)
  }

  if (!stato.ok) {
    return (
      <div className="iu-accesso-form">
        <Avviso tono="warning" focusRef={avvisoRef}>
          <p>La pagina non è stata caricata correttamente. Ricaricala per impostare la nuova password.</p>
        </Avviso>
        <button type="button" className="iu-accesso-primario" onClick={() => window.location.reload()}>
          <KeyRound size={18} aria-hidden="true" /> Ricarica la pagina
        </button>
      </div>
    )
  }

  if (!stato.autenticato || sessioneScaduta) {
    return (
      <div className="iu-accesso-form">
        <Avviso tono="warning" focusRef={avvisoRef}>
          <p>{errore || 'La sessione è scaduta: accedi di nuovo per impostare la nuova password.'}</p>
        </Avviso>
        <a className="iu-accesso-primario" href="/login">
          <LogIn size={18} aria-hidden="true" /> Vai all'accesso
        </a>
      </div>
    )
  }

  if (completato) {
    return (
      <div className="iu-accesso-form">
        <Avviso tono="success" focusRef={avvisoRef}>
          <p>{completato}</p>
          <p>Stai per essere indirizzato al gestionale.</p>
        </Avviso>
        <a className="iu-accesso-primario" href={destinazione}>
          <LogIn size={18} aria-hidden="true" /> Continua
        </a>
      </div>
    )
  }

  return (
    <form className="iu-accesso-form" onSubmit={onSubmit}>
      {avvisoGiaMostrato ? null : (
        <Avviso tono="warning">
          <p>
            <strong>Cambio password obbligatorio.</strong> Stai usando una password temporanea o iniziale:
            prima di continuare devi impostarne una nuova.
          </p>
        </Avviso>
      )}
      {errore ? (
        <Avviso tono="danger" id="password-errore" focusRef={avvisoRef}>
          <p>{errore}</p>
        </Avviso>
      ) : null}
      {stato.utente ? (
        <input type="text" name="username" autoComplete="username" value={stato.utente} readOnly hidden />
      ) : null}
      <CampoPassword
        id="password-attuale"
        name="password_old"
        label="Password attuale"
        autoComplete="current-password"
        visibile={visibili}
        autoFocus
      />
      <CampoPassword
        id="password-nuova"
        name="password_new"
        label="Nuova password"
        autoComplete="new-password"
        visibile={visibili}
        minLength={LUNGHEZZA_MINIMA_PASSWORD}
        describedBy="password-regole"
      />
      <p className="iu-accesso-aiuto" id="password-regole">Almeno 8 caratteri. Scegli una password personale, diversa da quella ricevuta.</p>
      <CampoPassword
        id="password-conferma"
        name="password_conferma"
        label="Ripeti la nuova password"
        autoComplete="new-password"
        visibile={visibili}
        minLength={LUNGHEZZA_MINIMA_PASSWORD}
      />
      <label className="iu-accesso-scelta">
        <input type="checkbox" checked={visibili} onChange={(event) => setVisibili(event.target.checked)} />
        Mostra le password
      </label>
      <button type="submit" className="iu-accesso-primario" disabled={invio} aria-busy={invio}>
        <KeyRound size={18} aria-hidden="true" />
        {invio ? 'Aggiornamento in corso…' : 'Imposta la nuova password'}
      </button>
      <button type="button" className="iu-accesso-secondario" onClick={() => void esciDallaSessione()} disabled={invio}>
        <LogOut size={18} aria-hidden="true" /> Esci
      </button>
    </form>
  )
}

const TITOLI: Record<ConfigurazionePagina['vista'], { titolo: string; sottotitolo: string }> = {
  login: { titolo: 'Accesso sicuro', sottotitolo: 'Accedi per continuare il lavoro dello studio' },
  '2fa': { titolo: 'Conferma la tua identità', sottotitolo: 'Verifica in due passaggi' },
  password: { titolo: 'Imposta una nuova password', sottotitolo: 'Un ultimo passaggio prima di entrare' },
}

export default function AccessoApp() {
  const config = useMemo(() => configurazionePagina(document.getElementById('accesso-react-root')), [])
  const [stato, setStato] = useState<StatoAccesso | null>(null)

  useEffect(() => {
    document.body.classList.add('accesso-react-page')
    const controller = new AbortController()
    leggiStatoAccesso(controller.signal)
      .then((letto) => {
        if (config.vista === 'login' && letto.autenticato) {
          window.location.replace(letto.destinazione)
          return
        }
        if (config.vista === '2fa' && letto.ok && !letto.verificaInAttesa) {
          window.location.replace('/login')
          return
        }
        setStato(letto)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [config.vista])

  const intestazione = TITOLI[config.vista]
  const messaggi: MessaggioAccesso[] = stato?.messaggi ?? []

  return (
    <main className={`iu-accesso is-${config.vista}`} aria-labelledby="accesso-titolo">
      {config.vista === 'login' ? (
        <section className="iu-accesso-intro" aria-label="Area riservata dello studio">
          <p className="iu-accesso-eyebrow"><ShieldCheck size={16} aria-hidden="true" /> Area riservata studio</p>
          <h2>Rientra nel lavoro dello studio.</h2>
          <p>Fascicoli, scadenze, comunicazioni e documenti restano in un ambiente ordinato, protetto e separato per ogni studio.</p>
          <ul className="iu-accesso-garanzie" aria-label="Garanzie di accesso">
            <li><UserCheck size={16} aria-hidden="true" /> Accesso personale</li>
            <li><Building2 size={16} aria-hidden="true" /> Dati separati per studio</li>
            <li><BookCheck size={16} aria-hidden="true" /> Attività registrate</li>
          </ul>
        </section>
      ) : null}
      <section className="iu-accesso-card">
        <header className="iu-accesso-testata">
          <div className="iu-accesso-marchio">
            {config.logo ? <img src={config.logo} alt="" aria-hidden="true" width={56} height={56} /> : null}
            <div>
              <span className="iu-accesso-nome">IUSENTRA</span>
              <span className="iu-accesso-motto">Lo studio legale, in un unico sistema</span>
            </div>
          </div>
          <h1 id="accesso-titolo">{intestazione.titolo}</h1>
          <p>{intestazione.sottotitolo}</p>
        </header>
        <div className="iu-accesso-corpo">
          {config.sessioneScaduta && config.vista === 'login' ? (
            <Avviso tono="warning"><p>Sessione scaduta per inattività. Accedi di nuovo.</p></Avviso>
          ) : null}
          {stato && !stato.ok && config.vista !== 'password' ? (
            <Avviso tono="info"><p>Alcune informazioni della pagina non sono state caricate: se qualcosa non funziona, ricarica la pagina.</p></Avviso>
          ) : null}
          {messaggi.map((messaggio, indice) => (
            <Avviso key={`${messaggio.tono}-${indice}`} tono={messaggio.tono}><p>{messaggio.testo}</p></Avviso>
          ))}
          {!stato ? (
            <p className="iu-accesso-caricamento" role="status">Preparazione della pagina di accesso…</p>
          ) : config.vista === '2fa' ? (
            <ModuloVerifica stato={stato} />
          ) : config.vista === 'password' ? (
            <ModuloPassword stato={stato} avvisoGiaMostrato={messaggi.some((messaggio) => messaggio.tono === 'warning')} />
          ) : (
            <ModuloAccesso stato={stato} config={config} />
          )}
          <p className="iu-accesso-piede">
            <ShieldCheck size={14} aria-hidden="true" /> Accesso riservato al personale autorizzato
            {config.vistaClassica ? (
              <>
                {' · '}
                <a href={config.vistaClassica}>Vista classica</a>
              </>
            ) : null}
          </p>
        </div>
      </section>
    </main>
  )
}
