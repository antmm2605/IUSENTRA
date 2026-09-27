import { useCallback, useEffect, useRef, useState } from 'react'
import { Briefcase, CloudUpload, FolderOpen, House, Moon, ShieldCheck, Sun, User, Wallet } from 'lucide-react'
import { messaggiDaAttributo, type MessaggioPagina } from '../pubblicoTokenApi'
import {
  anagrafica as normalizzaAnagrafica,
  caricaSezione,
  elencoStringhe,
  eseguiAzioneEconomica,
  firmaConsensoPrivacy,
  intestazione as normalizzaIntestazione,
  inviaDocumenti,
  percorsoSezione,
  salvaRecapiti,
  sezioneDaPercorso,
  sezioneValida,
  type AzioneRichiesta,
  type DatiAnagrafica,
  type Intestazione,
  type Sezione,
  type StatoSezione,
} from '../portaleTokenData'
import { Avvisi, Caricamento, LinkScaduto, LinkSezione, SezioneNegata, type Naviga } from './portaleToken/PortaleTokenComuni'
import { PortaleTokenAnagrafica } from './portaleToken/PortaleTokenAnagrafica'
import { PortaleTokenDocumenti, PortaleTokenDocumentiOk } from './portaleToken/PortaleTokenDocumenti'
import { PortaleTokenEconomici } from './portaleToken/PortaleTokenEconomici'
import { PortaleTokenHome } from './portaleToken/PortaleTokenHome'
import { PortaleTokenPrivacy, PortaleTokenPrivacyOk } from './portaleToken/PortaleTokenPrivacy'
import './PortaleTokenApp.css'

/**
 * Portale del cliente con link personale (`/portale/<token>`), senza la cornice
 * dello studio. Il token dell'indirizzo è l'unica credenziale: ogni dato arriva
 * da `/api/v1/pubblico/portale/<token>/...`, che risponde 410 se il link è
 * scaduto e 403 se la sezione non è consentita.
 */

type Radice = { token: string; sezione: Sezione; stato: string; studio: string; messaggi: MessaggioPagina[] }

type Esito =
  | { tipo: 'privacy_ok'; intestazione: Intestazione }
  | { tipo: 'documenti_ok'; caricati: string[]; errori: string[] }

const TITOLI: Record<Sezione, string> = {
  home: 'Benvenuto',
  privacy: 'Consenso Privacy',
  documenti: 'Carica documenti',
  economici: 'Documenti economici',
  anagrafica: 'I miei dati',
}

const CHIAVE_TEMA = 'pct-theme'

function leggiRadice(): Radice {
  const elemento = document.getElementById('portale-token-react-root')
  const dataset = elemento?.dataset ?? {}
  return {
    token: dataset.token || '',
    sezione: dataset.sezione ? sezioneValida(dataset.sezione) : sezioneDaPercorso(window.location.pathname),
    stato: dataset.stato || '',
    studio: dataset.studio || '',
    messaggi: messaggiDaAttributo(dataset.messaggi),
  }
}

function statoIniziale(radice: Radice): StatoSezione {
  if (radice.stato === 'scaduto') return { tipo: 'scaduto' }
  if (radice.stato === 'negato') return { tipo: 'negato', messaggio: 'Sezione non disponibile per questo accesso.' }
  return { tipo: 'caricamento' }
}

function temaSalvato(): 'light' | 'dark' {
  try {
    return window.localStorage.getItem(CHIAVE_TEMA) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function salvaTema(tema: 'light' | 'dark') {
  try {
    window.localStorage.setItem(CHIAVE_TEMA, tema)
  } catch {
    // Preferenza solo locale: se il browser non la conserva si resta sul tema chiaro.
  }
}

function intestazioneCorrente(stato: StatoSezione): Intestazione | null {
  if (stato.tipo !== 'pronto') return null
  const contenuto = stato.contenuto
  return contenuto.sezione === 'privacy' ? contenuto.dati : contenuto.dati.intestazione
}

export default function PortaleTokenApp() {
  const [radice] = useState(leggiRadice)
  const token = radice.token
  const [sezione, setSezione] = useState<Sezione>(radice.sezione)
  const [stato, setStato] = useState<StatoSezione>(() => statoIniziale(radice))
  const [versione, setVersione] = useState(0)
  const [revisione, setRevisione] = useState(0)
  const [esito, setEsito] = useState<Esito | null>(null)
  const [messaggi, setMessaggi] = useState<MessaggioPagina[]>(radice.messaggi)
  const [errore, setErrore] = useState('')
  const [occupato, setOccupato] = useState(false)
  const [tema, setTema] = useState<'light' | 'dark'>(temaSalvato)
  const [ultimaIntestazione, setUltimaIntestazione] = useState<Intestazione | null>(null)
  const ancora = useRef('')
  const saltaCaricamento = useRef(radice.stato === 'scaduto')

  useEffect(() => {
    if (saltaCaricamento.current) {
      // La shell ha già stabilito che il link è scaduto: nessuna richiesta.
      saltaCaricamento.current = false
      return undefined
    }
    const controller = new AbortController()
    setStato({ tipo: 'caricamento' })
    caricaSezione(token, sezione, controller.signal)
      .then((nuovo) => {
        setStato(nuovo)
        const testa = intestazioneCorrente(nuovo)
        if (testa) setUltimaIntestazione(testa)
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [token, sezione, versione])

  useEffect(() => {
    if (stato.tipo !== 'pronto' || !ancora.current) return
    document.getElementById(ancora.current)?.scrollIntoView({ block: 'start' })
    ancora.current = ''
  }, [stato])

  useEffect(() => {
    const studio = ultimaIntestazione?.studioNome || radice.studio
    const titolo = stato.tipo === 'scaduto' ? 'Link non valido' : TITOLI[sezione]
    document.title = `${titolo} - ${studio}`
  }, [sezione, stato.tipo, ultimaIntestazione, radice.studio])

  useEffect(() => {
    function indietro() {
      setEsito(null)
      setErrore('')
      setMessaggi([])
      setSezione(sezioneDaPercorso(window.location.pathname))
    }
    window.addEventListener('popstate', indietro)
    return () => window.removeEventListener('popstate', indietro)
  }, [])

  const naviga = useCallback<Naviga>((destinazione, opzioni = {}) => {
    const indirizzo = percorsoSezione(token, destinazione)
    if (window.location.pathname !== indirizzo) window.history.pushState({ sezione: destinazione }, '', indirizzo)
    ancora.current = opzioni.ancora || ''
    setEsito(null)
    setErrore('')
    setMessaggi(opzioni.messaggi ?? [])
    if (destinazione === sezione) setVersione((v) => v + 1)
    else setSezione(destinazione)
  }, [token, sezione])

  const scaduto = useCallback(() => setStato({ tipo: 'scaduto' }), [])

  const eseguiAzione = useCallback(async (azione: AzioneRichiesta) => {
    setOccupato(true)
    const risposta = await eseguiAzioneEconomica(token, azione)
    setOccupato(false)
    if (risposta.status === 410) return scaduto()
    const avvisi = risposta.messaggi.length
      ? risposta.messaggi
      : [{ categoria: 'danger' as const, testo: risposta.messaggio || 'Operazione non completata. Riprova o contatta lo studio.' }]
    // Come la vista classica: accettazione -> documenti economici; firma -> home
    // (o economici se l'anagrafica va completata); errori -> sezione corrente.
    const destinazione: Sezione = risposta.sezione === 'home' || risposta.sezione === 'economici' ? risposta.sezione : sezione
    naviga(destinazione, { messaggi: avvisi })
    return undefined
  }, [token, sezione, naviga, scaduto])

  const firmaPrivacy = useCallback(async () => {
    setOccupato(true)
    const risposta = await firmaConsensoPrivacy(token)
    setOccupato(false)
    if (risposta.status === 410) return scaduto()
    if (!risposta.ok) return setErrore(risposta.messaggio || 'Consenso non registrato. Riprova.')
    const testa = normalizzaIntestazione(risposta.dati)
    setUltimaIntestazione(testa)
    setErrore('')
    setEsito({ tipo: 'privacy_ok', intestazione: testa })
    return undefined
  }, [token, scaduto])

  const invia = useCallback(async (files: File[], idFascicolo: string, note: string) => {
    setOccupato(true)
    const risposta = await inviaDocumenti(token, files, idFascicolo, note)
    setOccupato(false)
    if (risposta.status === 410) return scaduto()
    if (!risposta.ok) return setErrore(risposta.messaggio || 'Invio non riuscito. Riprova o contatta lo studio.')
    setErrore('')
    setEsito({ tipo: 'documenti_ok', caricati: elencoStringhe(risposta.dati.caricati), errori: elencoStringhe(risposta.dati.errori) })
    return undefined
  }, [token, scaduto])

  const salva = useCallback(async (recapiti: DatiAnagrafica['recapiti']) => {
    setOccupato(true)
    const risposta = await salvaRecapiti(token, recapiti)
    setOccupato(false)
    if (risposta.status === 410) return scaduto()
    if (!risposta.ok) {
      setMessaggi([{ categoria: 'danger', testo: risposta.messaggio || 'Dati non aggiornati. Riprova.' }])
      return undefined
    }
    setMessaggi([{ categoria: 'success', testo: 'Dati aggiornati con successo.' }])
    setStato({ tipo: 'pronto', contenuto: { sezione: 'anagrafica', dati: normalizzaAnagrafica(risposta.dati) } })
    setRevisione((v) => v + 1)
    return undefined
  }, [token, scaduto])

  const cambiaTema = useCallback(() => {
    setTema((corrente) => {
      const prossimo = corrente === 'dark' ? 'light' : 'dark'
      salvaTema(prossimo)
      return prossimo
    })
  }, [])

  const studioNome = ultimaIntestazione?.studioNome || radice.studio
  const classeApp = `iu-ptk-app${tema === 'dark' ? ' is-scuro' : ''}`

  if (stato.tipo === 'scaduto') {
    return (
      <div className={classeApp}>
        <LinkScaduto studioNome={studioNome} />
      </div>
    )
  }

  const permessi = ultimaIntestazione?.permessi
  const privacyDaFirmare = Boolean(permessi?.firmaPrivacy && !ultimaIntestazione?.privacyFirmata)
  const attiva = esito ? '' : sezione

  return (
    <div className={classeApp}>
      <header className="iu-ptk-barra">
        <Briefcase size={20} aria-hidden="true" />
        <span className="iu-ptk-barra__studio">{studioNome}</span>
        <span className="iu-ptk-barra__etichetta">Portale</span>
        <button type="button" className="iu-ptk-barra__tema" onClick={cambiaTema} aria-label={tema === 'dark' ? 'Passa al tema chiaro' : 'Passa al tema scuro'}>
          {tema === 'dark' ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
        </button>
      </header>

      <main className="iu-ptk-contenuto" id="iu-ptk-contenuto">
        <Avvisi messaggi={messaggi} />
        <ContenutoSezione
          token={token}
          stato={stato}
          esito={esito}
          revisione={revisione}
          errore={errore}
          occupato={occupato}
          onNaviga={naviga}
          onAzione={eseguiAzione}
          onFirmaPrivacy={firmaPrivacy}
          onErrore={setErrore}
          onInvia={invia}
          onAltriDocumenti={() => { setEsito(null); setErrore('') }}
          onSalva={salva}
        />
      </main>

      {permessi ? (
        <nav className="iu-ptk-nav" aria-label="Sezioni del portale">
          <LinkSezione href={percorsoSezione(token, 'home')} sezione="home" onNaviga={naviga} className="iu-ptk-nav__voce" ariaCurrent={attiva === 'home'}>
            <House size={20} aria-hidden="true" /><span>Inizio</span>
          </LinkSezione>
          {permessi.vediFascicoli ? (
            <LinkSezione href={percorsoSezione(token, 'home')} sezione="home" ancora="fascicoli" onNaviga={naviga} className="iu-ptk-nav__voce" ariaCurrent={false}>
              <FolderOpen size={20} aria-hidden="true" /><span>Pratiche</span>
            </LinkSezione>
          ) : null}
          {permessi.caricaDocumenti ? (
            <LinkSezione href={percorsoSezione(token, 'documenti')} sezione="documenti" onNaviga={naviga} className="iu-ptk-nav__voce" ariaCurrent={attiva === 'documenti'}>
              <CloudUpload size={20} aria-hidden="true" /><span>Documenti</span>
            </LinkSezione>
          ) : null}
          {permessi.vediEconomici ? (
            <LinkSezione href={percorsoSezione(token, 'economici')} sezione="economici" onNaviga={naviga} className="iu-ptk-nav__voce" ariaCurrent={attiva === 'economici'}>
              <Wallet size={20} aria-hidden="true" /><span>Economici</span>
            </LinkSezione>
          ) : null}
          {permessi.vediAnagrafica ? (
            <LinkSezione href={percorsoSezione(token, 'anagrafica')} sezione="anagrafica" onNaviga={naviga} className="iu-ptk-nav__voce" ariaCurrent={attiva === 'anagrafica'}>
              <User size={20} aria-hidden="true" /><span>Profilo</span>
            </LinkSezione>
          ) : null}
          {privacyDaFirmare ? (
            <LinkSezione href={percorsoSezione(token, 'privacy')} sezione="privacy" onNaviga={naviga} className="iu-ptk-nav__voce is-accento" ariaCurrent={attiva === 'privacy'}>
              <ShieldCheck size={20} aria-hidden="true" /><span>Privacy</span>
            </LinkSezione>
          ) : null}
        </nav>
      ) : null}
    </div>
  )
}

type PropsContenuto = {
  token: string
  stato: StatoSezione
  esito: Esito | null
  revisione: number
  errore: string
  occupato: boolean
  onNaviga: Naviga
  onAzione: (azione: AzioneRichiesta) => void
  onFirmaPrivacy: () => void
  onErrore: (messaggio: string) => void
  onInvia: (files: File[], idFascicolo: string, note: string) => void
  onAltriDocumenti: () => void
  onSalva: (recapiti: DatiAnagrafica['recapiti']) => void
}

function ContenutoSezione(props: PropsContenuto) {
  const { token, stato, esito, onNaviga } = props
  if (esito?.tipo === 'privacy_ok') return <PortaleTokenPrivacyOk token={token} intestazione={esito.intestazione} onNaviga={onNaviga} />
  if (esito?.tipo === 'documenti_ok') {
    return <PortaleTokenDocumentiOk token={token} caricati={esito.caricati} errori={esito.errori} onNaviga={onNaviga} onAltri={props.onAltriDocumenti} />
  }
  if (stato.tipo === 'caricamento' || stato.tipo === 'scaduto') return <Caricamento />
  if (stato.tipo === 'negato') return <SezioneNegata messaggio={stato.messaggio} hrefHome={percorsoSezione(token, 'home')} onNaviga={onNaviga} />
  if (stato.tipo === 'errore') {
    return (
      <section className="iu-ptk-centro" role="alert">
        <h1>Portale non disponibile</h1>
        <p className="iu-ptk-muted">{stato.messaggio}</p>
      </section>
    )
  }
  const contenuto = stato.contenuto
  switch (contenuto.sezione) {
    case 'home':
      return <PortaleTokenHome token={token} dati={contenuto.dati} occupato={props.occupato} onNaviga={onNaviga} onAzione={props.onAzione} />
    case 'privacy':
      return <PortaleTokenPrivacy intestazione={contenuto.dati} occupato={props.occupato} errore={props.errore} onFirma={props.onFirmaPrivacy} onErrore={props.onErrore} />
    case 'documenti':
      return <PortaleTokenDocumenti dati={contenuto.dati} occupato={props.occupato} errore={props.errore} onInvia={props.onInvia} />
    case 'economici':
      return <PortaleTokenEconomici dati={contenuto.dati} occupato={props.occupato} onAzione={props.onAzione} />
    default:
      return <PortaleTokenAnagrafica key={props.revisione} token={token} dati={contenuto.dati} occupato={props.occupato} onNaviga={onNaviga} onSalva={props.onSalva} />
  }
}
