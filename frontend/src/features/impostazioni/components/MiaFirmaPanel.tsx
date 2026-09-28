import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckCircle2, CloudCog, KeyRound, Save, ShieldCheck, Usb, Users } from 'lucide-react'
import catalogoFirma from '@iusentra-data/cataloghi/firma_digitale.json'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { IusStatusBadge } from '@/components/iusentra'
import { apiJson, apiPostJson } from '@/lib/apiClient'
import './MiaFirmaPanel.css'

type Canale = 'studio' | 'pkcs11' | 'remota'
type Valori = {
  canale: Canale
  prestatore: string
  dispositivo_produttore: string
  remota_protocollo: string
  remota_endpoint: string
  remota_utente: string
  remota_dominio: string
  remota_credenziale: string
  remota_tipo_otp: string
}
type Profilo = {
  ok: boolean
  message?: string
  puo_modificare?: boolean
  utente?: string
  personale?: boolean
  aggiornato_il?: string
  studio?: { canale: string; canale_etichetta: string; prestatore: string }
  valori?: Valori
  librerie_dispositivo?: Record<string, string[]>
}
type Esito = { ok: boolean; message?: string; errors?: Record<string, string>; profilo?: Profilo; intestatario?: string; emittente?: string; scadenza?: string }

type Protocollo = keyof typeof catalogoFirma.protocolli_remoti
type VocePrestatore = (typeof catalogoFirma.prestatori)[number]

const VALORI_VUOTI: Valori = {
  canale: 'studio', prestatore: '', dispositivo_produttore: '', remota_protocollo: '', remota_endpoint: '',
  remota_utente: '', remota_dominio: '', remota_credenziale: '', remota_tipo_otp: 'app',
}
const NESSUNO = 'nessuno'
const AUTOMATICO = 'automatico'
const ETICHETTE_OTP: Record<string, string> = {
  app: 'Dall’app del prestatore (codice che cambia ogni 30 secondi)',
  sms: 'Per SMS',
  chiamata: 'Con una chiamata (ArubaCall)',
  notifica: 'Con una notifica sul telefono',
}
const ETICHETTE_UTENTE: Record<string, string> = {
  arss: 'Utente del servizio di firma remota',
  sws: 'Codice del dispositivo di firma remota (RHI…)',
  csc: 'Utente del servizio di firma',
}
const CANALI: Array<{ id: Canale; titolo: string; testo: string; icona: typeof Users }> = [
  { id: 'studio', titolo: 'Come lo studio', testo: 'Uso la firma impostata dall’amministratore.', icona: Users },
  { id: 'pkcs11', titolo: 'Il mio dispositivo', testo: 'Smart card o token USB sul mio PC, con il Local Signer.', icona: Usb },
  { id: 'remota', titolo: 'La mia firma remota', testo: 'Certificato nel server del prestatore: firmo anche dal telefono.', icona: CloudCog },
]

const prestatori = catalogoFirma.prestatori as VocePrestatore[]
const conServizio = prestatori.filter((p) => p.remota.protocolli.length > 0)
const senzaServizio = prestatori.filter((p) => p.remota.protocolli.length === 0)

function voce(id: string): VocePrestatore | undefined {
  return prestatori.find((p) => p.id === id)
}

function protocolli(id: string): Protocollo[] {
  return (voce(id)?.remota.protocolli || []) as Protocollo[]
}

function endpointPredefinito(id: string, protocollo: string): string {
  const endpoint = (voce(id)?.remota as { endpoint?: Record<string, string> } | undefined)?.endpoint || {}
  return endpoint[protocollo] || ''
}

function nota(id: string): string {
  return (voce(id)?.remota as { nota?: string } | undefined)?.nota || ''
}

export function MiaFirmaPanel() {
  const [profilo, setProfilo] = useState<Profilo | null>(null)
  const [valori, setValori] = useState<Valori>(VALORI_VUOTI)
  const [errori, setErrori] = useState<Record<string, string>>({})
  const [messaggio, setMessaggio] = useState('')
  const [salvataggio, setSalvataggio] = useState(false)
  const [password, setPassword] = useState('')
  const [prova, setProva] = useState<Esito | null>(null)
  const [provaInCorso, setProvaInCorso] = useState(false)

  const applica = useCallback((dati: Profilo) => {
    setProfilo(dati)
    setValori({ ...VALORI_VUOTI, ...(dati.valori || {}) })
  }, [])

  useEffect(() => {
    const controllo = new AbortController()
    apiJson<Profilo>('/api/v1/ui/impostazioni/firma-personale', { ok: false }, { signal: controllo.signal })
      .then(applica)
      .catch(() => undefined)
    return () => controllo.abort()
  }, [applica])

  const protocolliPrestatore = useMemo(() => protocolli(valori.prestatore), [valori.prestatore])
  const protocollo = (valori.remota_protocollo || protocolliPrestatore[0] || '') as Protocollo | ''
  const servizio = protocollo ? catalogoFirma.protocolli_remoti[protocollo] : null
  const campi: string[] = servizio?.campi || []
  const otpAmmessi: string[] = servizio?.otp || ['app']
  const predefinito = protocollo ? endpointPredefinito(valori.prestatore, protocollo) : ''
  const prestatoreSenzaServizio = valori.canale === 'remota' && Boolean(valori.prestatore) && protocolliPrestatore.length === 0
  const puoModificare = Boolean(profilo?.puo_modificare)

  const cambia = (campo: keyof Valori, valore: string) => {
    setErrori((attuali) => ({ ...attuali, [campo]: '' }))
    setMessaggio('')
    setValori((attuali) => {
      const nuovi = { ...attuali, [campo]: valore }
      if (campo === 'prestatore') {
        const disponibili = protocolli(valore)
        nuovi.remota_protocollo = disponibili.length > 1 ? disponibili[0] : ''
        const otp = (disponibili[0] ? catalogoFirma.protocolli_remoti[disponibili[0]].otp : ['app']) as string[]
        if (!otp.includes(nuovi.remota_tipo_otp)) nuovi.remota_tipo_otp = otp[0]
        const dispositivi = voce(valore)?.dispositivi || []
        if (attuali.canale === 'pkcs11' && !attuali.dispositivo_produttore && dispositivi[0]) nuovi.dispositivo_produttore = dispositivi[0]
      }
      if (campo === 'remota_protocollo') {
        const otp = catalogoFirma.protocolli_remoti[valore as Protocollo]?.otp as string[] | undefined
        if (otp && !otp.includes(nuovi.remota_tipo_otp)) nuovi.remota_tipo_otp = otp[0]
      }
      return nuovi
    })
  }

  const salva = async () => {
    setSalvataggio(true); setMessaggio(''); setErrori({}); setProva(null)
    const esito = await apiPostJson<Esito>('/api/v1/ui/impostazioni/firma-personale', valori, { ok: false, message: 'Salvataggio non riuscito.' })
    setSalvataggio(false)
    if (esito.ok && esito.profilo) {
      applica(esito.profilo)
      setMessaggio(esito.message || 'Firma salvata.')
    } else {
      setErrori(esito.errors || {})
      setMessaggio(esito.message || 'Controlla la tua firma.')
    }
  }

  const provaCollegamento = async () => {
    setProvaInCorso(true); setProva(null)
    const esito = await apiPostJson<Esito>('/api/v1/ui/impostazioni/firma-personale/prova', { password }, { ok: false, message: 'Prova non riuscita.' })
    setProvaInCorso(false)
    setPassword('')
    setProva(esito)
  }

  if (!profilo) return <p role="status" className="iu-mia-firma__stato">Carico la tua firma…</p>
  if (!profilo.ok) return <p role="alert" className="iu-mia-firma__stato">{profilo.message || 'La tua firma non è leggibile in questo momento.'}</p>

  const studio = profilo.studio
  const salvati = { ...VALORI_VUOTI, ...(profilo.valori || {}) }
  const modificata = (Object.keys(VALORI_VUOTI) as Array<keyof Valori>).some((campo) => salvati[campo] !== valori[campo])
  const salvataRemota = profilo.personale && profilo.valori?.canale === 'remota' && !modificata
  const librerie = profilo.librerie_dispositivo?.windows || []

  return (
    <div className="iu-mia-firma">
      <header className="iu-mia-firma__intro">
        <ShieldCheck aria-hidden="true" />
        <div>
          <strong>{profilo.utente ? `Firma di ${profilo.utente}` : 'La mia firma'}</strong>
          <span>
            Ogni avvocato firma con il proprio certificato: scegli qui il tuo gestore o il tuo dispositivo.
            {studio ? ` Firma dello studio: ${studio.canale_etichetta}${studio.prestatore ? ` · ${studio.prestatore}` : ''}.` : ''}
          </span>
        </div>
        <IusStatusBadge tone={profilo.personale ? 'success' : 'neutral'}>{profilo.personale ? 'Scelta personale' : 'Come lo studio'}</IusStatusBadge>
      </header>

      <fieldset className="iu-mia-firma__canali" disabled={!puoModificare}>
        <legend>Come firmi</legend>
        <div className="iu-mia-firma__canali-griglia">
        {CANALI.map(({ id, titolo, testo, icona: Icona }) => (
          <button
            key={id}
            type="button"
            className={`iu-mia-firma__canale${valori.canale === id ? ' is-active' : ''}`}
            aria-pressed={valori.canale === id}
            onClick={() => cambia('canale', id)}
          >
            <Icona aria-hidden="true" />
            <strong>{titolo}</strong>
            <span>{testo}</span>
          </button>
        ))}
        </div>
      </fieldset>

      {valori.canale === 'pkcs11' ? (
        <div className="iu-mia-firma__griglia">
          <label className="iu-mia-firma__campo">
            <span>Chi ti ha rilasciato il dispositivo</span>
            <Select value={valori.prestatore || NESSUNO} onValueChange={(v) => cambia('prestatore', v === NESSUNO ? '' : v)} disabled={!puoModificare}>
              <SelectTrigger aria-label="Chi ti ha rilasciato il dispositivo"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NESSUNO}>Non indicato</SelectItem>
                {prestatori.filter((p) => p.id !== 'altro_csc').map((p) => <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <label className="iu-mia-firma__campo">
            <span>Produttore della smart card o del token</span>
            <Select value={valori.dispositivo_produttore || AUTOMATICO} onValueChange={(v) => cambia('dispositivo_produttore', v === AUTOMATICO ? '' : v)} disabled={!puoModificare}>
              <SelectTrigger aria-label="Produttore della smart card o del token"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={AUTOMATICO}>Rilevamento automatico</SelectItem>
                {catalogoFirma.produttori_dispositivo.map((p) => <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>)}
              </SelectContent>
            </Select>
            {errori.dispositivo_produttore ? <small role="alert">{errori.dispositivo_produttore}</small> : null}
            <small>Il Local Signer cerca prima il driver di questo produttore; il PIN si digita a ogni firma e non si salva.</small>
          </label>
          {librerie.length && profilo.valori?.canale === 'pkcs11' ? (
            <p className="iu-mia-firma__nota">Driver cercati su Windows: {librerie.slice(0, 3).join(', ')}</p>
          ) : null}
        </div>
      ) : null}

      {valori.canale === 'remota' ? (
        <div className="iu-mia-firma__griglia">
          <label className="iu-mia-firma__campo is-full">
            <span>Gestore della firma remota</span>
            <Select value={valori.prestatore || NESSUNO} onValueChange={(v) => cambia('prestatore', v === NESSUNO ? '' : v)} disabled={!puoModificare}>
              <SelectTrigger aria-label="Gestore della firma remota"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value={NESSUNO}>Scegli il gestore</SelectItem>
                <SelectGroup>
                  <SelectLabel>Firma da IUSENTRA</SelectLabel>
                  {conServizio.map((p) => <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>)}
                </SelectGroup>
                <SelectGroup>
                  <SelectLabel>Solo dall’app del gestore</SelectLabel>
                  {senzaServizio.map((p) => <SelectItem key={p.id} value={p.id}>{p.nome}</SelectItem>)}
                </SelectGroup>
              </SelectContent>
            </Select>
            {errori.prestatore ? <small role="alert">{errori.prestatore}</small> : null}
          </label>

          {prestatoreSenzaServizio ? (
            <p className="iu-mia-firma__avviso" role="note">
              {voce(valori.prestatore)?.nome} non offre un servizio di firma per i gestionali. {nota(valori.prestatore)} Firma dall’app
              del gestore e carica il documento firmato nel fascicolo con «Firma esterna».
            </p>
          ) : null}

          {servizio ? (
            <>
              <p className="iu-mia-firma__nota is-full">{servizio.descrizione}</p>
              {protocolliPrestatore.length > 1 ? (
                <label className="iu-mia-firma__campo">
                  <span>Servizio</span>
                  <Select value={protocollo} onValueChange={(v) => cambia('remota_protocollo', v)} disabled={!puoModificare}>
                    <SelectTrigger aria-label="Servizio"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {protocolliPrestatore.map((p) => <SelectItem key={p} value={p}>{catalogoFirma.protocolli_remoti[p].etichetta}</SelectItem>)}
                    </SelectContent>
                  </Select>
                  {errori.remota_protocollo ? <small role="alert">{errori.remota_protocollo}</small> : null}
                </label>
              ) : null}
              <label className="iu-mia-firma__campo">
                <span>{ETICHETTE_UTENTE[protocollo] || 'Utente'}</span>
                <Input value={valori.remota_utente} onChange={(e) => cambia('remota_utente', e.target.value)} autoComplete="username" disabled={!puoModificare}/>
                <small>Lo trovi nella lettera di attivazione della firma remota.</small>
              </label>
              <label className="iu-mia-firma__campo">
                <span>Come ricevi il codice OTP</span>
                <Select value={otpAmmessi.includes(valori.remota_tipo_otp) ? valori.remota_tipo_otp : otpAmmessi[0]} onValueChange={(v) => cambia('remota_tipo_otp', v)} disabled={!puoModificare}>
                  <SelectTrigger aria-label="Come ricevi il codice OTP"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {otpAmmessi.map((o) => <SelectItem key={o} value={o}>{ETICHETTE_OTP[o] || o}</SelectItem>)}
                  </SelectContent>
                </Select>
                {errori.remota_tipo_otp ? <small role="alert">{errori.remota_tipo_otp}</small> : null}
              </label>
              {campi.includes('dominio') ? (
                <label className="iu-mia-firma__campo">
                  <span>Dominio del contratto</span>
                  <Input value={valori.remota_dominio} onChange={(e) => cambia('remota_dominio', e.target.value)} disabled={!puoModificare}/>
                  <small>Indicato dal gestore con le credenziali di firma remota.</small>
                </label>
              ) : null}
              {campi.includes('certificato') ? (
                <label className="iu-mia-firma__campo">
                  <span>Identificativo del certificato (facoltativo)</span>
                  <Input value={valori.remota_credenziale} onChange={(e) => cambia('remota_credenziale', e.target.value)} disabled={!puoModificare}/>
                  <small>Vuoto: si usa il primo certificato di firma del tuo account.</small>
                </label>
              ) : null}
              {campi.includes('endpoint') || !predefinito ? (
                <label className="iu-mia-firma__campo is-full">
                  <span>Indirizzo del servizio{predefinito ? ' (facoltativo)' : ''}</span>
                  <Input type="url" inputMode="url" value={valori.remota_endpoint} placeholder={predefinito || 'https://…/csc/v2'}
                    onChange={(e) => cambia('remota_endpoint', e.target.value)} disabled={!puoModificare}/>
                  {errori.remota_endpoint ? <small role="alert">{errori.remota_endpoint}</small> : null}
                  <small>{nota(valori.prestatore) || 'Lo rilascia il gestore con il contratto e termina con /csc/v1 o /csc/v2.'}</small>
                </label>
              ) : (
                <p className="iu-mia-firma__nota is-full">Indirizzo del servizio: {predefinito}</p>
              )}
            </>
          ) : null}
        </div>
      ) : null}

      <div className="iu-mia-firma__azioni">
        <Button type="button" onClick={() => void salva()} disabled={!puoModificare || salvataggio || prestatoreSenzaServizio}>
          <Save data-icon="inline-start" />
          {salvataggio ? 'Salvataggio…' : 'Salva la mia firma'}
        </Button>
        {messaggio ? <p role="status">{messaggio}</p> : null}
      </div>

      {salvataRemota ? (
        <section className="iu-mia-firma__prova" aria-label="Prova del collegamento">
          <strong>Prova il collegamento</strong>
          <span>IUSENTRA chiede al gestore il tuo certificato. La password serve solo per la prova e non si salva.</span>
          <div className="iu-mia-firma__prova-riga">
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off"
              placeholder="Password del servizio di firma" aria-label="Password del servizio di firma"/>
            <Button type="button" variant="outline" disabled={!password || provaInCorso} onClick={() => void provaCollegamento()}>
              <KeyRound data-icon="inline-start" />
              {provaInCorso ? 'Verifica…' : 'Prova'}
            </Button>
          </div>
          {prova ? (
            prova.ok ? (
              <p className="iu-mia-firma__esito is-ok" role="status">
                <CheckCircle2 aria-hidden="true" />
                {prova.message} Certificato di {prova.intestatario}, emesso da {prova.emittente}, valido fino al {prova.scadenza}.
              </p>
            ) : <p className="iu-mia-firma__esito" role="alert">{prova.message}</p>
          ) : null}
        </section>
      ) : null}

      {!puoModificare ? (
        <p className="iu-mia-firma__nota">Per scegliere la propria firma serve il permesso di lavorare sui fascicoli.</p>
      ) : null}
    </div>
  )
}

export default MiaFirmaPanel
