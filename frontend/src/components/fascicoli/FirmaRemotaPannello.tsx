import { useEffect, useState } from 'react'
import { KeyRound, Send, ShieldCheck } from 'lucide-react'
import { csrfHeader } from '../../api/csrf'

type StatoRemota = {
  ok: boolean
  attiva: boolean
  messaggio?: string
  prestatore?: string
  protocollo?: string
  utente?: string
  tipo_otp?: string
  invia_codice?: boolean
  chiede_pin?: boolean
  etichetta_password?: string
}

type Esito = { ok: boolean; messaggio?: string; requires_confirm_resign?: boolean }

const ETICHETTE_OTP: Record<string, string> = {
  app: 'Codice dall’app del prestatore',
  sms: 'Codice ricevuto per SMS',
  chiamata: 'Codice ricevuto con la chiamata',
  notifica: 'Codice dalla notifica sul telefono',
}

async function postJson(url: string, corpo: Record<string, unknown>): Promise<Esito> {
  const risposta = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', ...csrfHeader() },
    body: JSON.stringify(corpo),
  })
  const esito = await risposta.json().catch(() => ({ ok: false, messaggio: 'Risposta non valida.' })) as Esito
  return risposta.ok ? esito : { ...esito, ok: false }
}

/**
 * Firma remota qualificata (Reg. eIDAS art. 29): la chiave è nell'HSM del prestatore scelto in
 * Impostazioni → Firma digitale. L'avvocato digita password (e PIN, se il servizio lo chiede) e
 * il codice OTP; nulla viene salvato. Funziona da qualsiasi dispositivo, telefono compreso.
 */
export default function FirmaRemotaPannello({ fascicoloId, documentoId, nomeDocumento, giaFirmato, confermaRifirma, visibile, onFirmato }: {
  fascicoloId: string
  documentoId: string
  nomeDocumento: string
  giaFirmato: boolean
  confermaRifirma: boolean
  visibile: { mode: string; place: string; datetimeMode: string }
  onFirmato: (messaggio: string) => void
}) {
  const [stato, setStato] = useState<StatoRemota | null>(null)
  const [password, setPassword] = useState('')
  const [pin, setPin] = useState('')
  const [otp, setOtp] = useState('')
  const isPdf = nomeDocumento.toLowerCase().endsWith('.pdf')
  const [formato, setFormato] = useState(isPdf ? 'pades' : 'cades')
  const [messaggio, setMessaggio] = useState('')
  const [errore, setErrore] = useState('')
  const [occupato, setOccupato] = useState(false)

  useEffect(() => {
    let attivo = true
    fetch('/api/firma/remota/stato', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((r) => r.json())
      .then((dati: StatoRemota) => { if (attivo) setStato(dati) })
      .catch(() => { if (attivo) setStato({ ok: false, attiva: false, messaggio: 'Stato della firma remota non disponibile.' }) })
    return () => { attivo = false }
  }, [])

  const inviaCodice = async () => {
    setOccupato(true); setErrore(''); setMessaggio('Richiedo il codice al prestatore…')
    const esito = await postJson('/api/firma/remota/otp', { password }).catch(() => ({ ok: false, messaggio: 'Richiesta non riuscita.' }))
    setOccupato(false)
    if (esito.ok) setMessaggio(esito.messaggio || 'Codice richiesto.')
    else { setMessaggio(''); setErrore(esito.messaggio || 'Invio del codice non riuscito.') }
  }

  const firma = async () => {
    setOccupato(true); setErrore(''); setMessaggio('Firma remota in corso…')
    const esito = await postJson('/api/firma/remota/firma-documento', {
      fascicolo_id: fascicoloId, documento_id: documentoId, password, pin, otp, formato,
      visible_signature_mode: visibile.mode, visible_signature_place: visibile.place, visible_signature_datetime_mode: visibile.datetimeMode,
      confirm_resign: giaFirmato && confermaRifirma ? '1' : '',
    }).catch(() => ({ ok: false, messaggio: 'Firma remota non completata.' }))
    setOccupato(false)
    setOtp('')
    if (esito.ok) { setPassword(''); setPin(''); setMessaggio(''); onFirmato(esito.messaggio || 'Documento firmato.') }
    else { setMessaggio(''); setErrore(esito.messaggio || 'Firma remota non completata.') }
  }

  if (!stato) return <p role="status">Carico la firma remota…</p>
  if (!stato.attiva) {
    return (
      <div className="iu-fas-signature-box">
        <div className="iu-fas-signer-status is-warn"><strong>Firma remota non pronta</strong><span>{stato.messaggio}</span></div>
      </div>
    )
  }
  const bloccato = occupato || (giaFirmato && !confermaRifirma)
  return (
    <div className="iu-fas-signature-box">
      <div className="iu-fas-signer-status is-ok">
        <strong>{stato.prestatore}</strong>
        <span>Firma remota qualificata: la chiave resta nel prestatore, IUSENTRA non salva password, PIN né codici.</span>
        {stato.utente ? <small>Utente {stato.utente}</small> : null}
      </div>
      <label className="iu-fas-field">
        <span>{stato.etichetta_password || 'Password di firma'} <b>*</b></span>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="off" placeholder="Non viene salvata"/>
      </label>
      {stato.chiede_pin ? (
        <label className="iu-fas-field">
          <span>PIN di firma <b>*</b></span>
          <input type="password" value={pin} onChange={(e) => setPin(e.target.value)} autoComplete="off" placeholder="Non viene salvato"/>
        </label>
      ) : null}
      {stato.invia_codice ? (
        <button className="iu-fas-mini-action" type="button" onClick={() => void inviaCodice()} disabled={occupato || !password}>
          <Send size={14}/> Invia il codice
        </button>
      ) : null}
      <label className="iu-fas-field">
        <span>{ETICHETTE_OTP[stato.tipo_otp || 'app'] || 'Codice OTP'} <b>*</b></span>
        <input inputMode="numeric" autoComplete="one-time-code" value={otp} onChange={(e) => setOtp(e.target.value.trim())} placeholder="Codice usa e getta"/>
      </label>
      <label className="iu-fas-field">
        <span>Formato</span>
        <select value={formato} onChange={(e) => setFormato(e.target.value)}>
          {isPdf ? <option value="pades">PAdES: il PDF resta PDF</option> : null}
          <option value="cades">CAdES: busta .p7m</option>
        </select>
      </label>
      {messaggio ? <p role="status" className="iu-fas-signature-help">{messaggio}</p> : null}
      {errore ? <p role="alert" className="iu-fas-signature-help">{errore}</p> : null}
      <button className="iu-fas-submit" type="button" disabled={bloccato || !password || !otp || (stato.chiede_pin && !pin)} onClick={() => void firma()}>
        {occupato ? <KeyRound size={16}/> : <ShieldCheck size={16}/>} {occupato ? 'Firma in corso…' : 'Firma con la firma remota'}
      </button>
    </div>
  )
}
