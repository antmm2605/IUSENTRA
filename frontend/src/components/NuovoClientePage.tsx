import { useEffect, useMemo, useState, type ChangeEvent, type ReactNode } from 'react'
import {
  ArrowLeft,
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  CreditCard,
  FileText,
  Home,
  Landmark,
  Mail,
  Phone,
  ScanLine,
  ShieldCheck,
  Sparkles,
  UserCheck,
  UserPlus,
  UserRound,
  UsersRound,
} from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyClientiNuovoData,
  getClientiNuovoData,
  type ClientiNuovoData,
  type RegistryOption,
} from '../clientiNuovoData'
import './NuovoClientePage.css'

type Tab = 'cliente' | 'soggetto'
type ClientType = 'PERSONA_FISICA' | 'PERSONA_GIURIDICA'
type ClientFormState = Record<string, string | boolean>
type SubjectFormState = Record<string, string>

const subjectLegalTypes = new Set(['PERSONA_GIURIDICA', 'PUBBLICA_AMMINISTRAZIONE', 'ENTE', 'CONDOMINIO', 'ASSOCIAZIONE'])

const initialClient: ClientFormState = {
  tipo: 'PERSONA_FISICA',
  nome: '',
  cognome: '',
  ragione_sociale: '',
  codice_fiscale: '',
  partita_iva: '',
  forma_giuridica: '',
  data_nascita: '',
  luogo_nascita: '',
  provincia_nascita: '',
  sesso: '',
  nazionalita: 'Italiana',
  rappresentante_legale: '',
  cf_rappresentante: '',
  telefono: '',
  cellulare: '',
  email: '',
  pec: '',
  fax: '',
  sito_web: '',
  via: '',
  civico: '',
  cap: '',
  comune: '',
  provincia: '',
  nazione: 'Italia',
  dom_via: '',
  dom_civico: '',
  dom_cap: '',
  dom_comune: '',
  dom_provincia: '',
  dom_nazione: 'Italia',
  sl_via: '',
  sl_civico: '',
  sl_cap: '',
  sl_comune: '',
  sl_provincia: '',
  sl_nazione: 'Italia',
  doc_tipo: 'CARTA_IDENTITA',
  doc_numero: '',
  doc_rilasciato_da: '',
  doc_data_rilascio: '',
  doc_data_scadenza: '',
  avvocato_referente: '',
  provenienza: '',
  note: '',
  next_url: '',
  crea_preventivo_iniziale: true,
}

const initialSubject: SubjectFormState = {
  tipo: 'PERSONA_FISICA',
  nome: '',
  cognome: '',
  ragione_sociale: '',
  codice_fiscale: '',
  partita_iva: '',
  forma_giuridica: '',
  data_nascita: '',
  luogo_nascita: '',
  provincia_nascita: '',
  sesso: '',
  rappresentante_legale: '',
  qualifica: 'CONTROPARTE',
  ordine: '',
  numero_iscrizione: '',
  id_cliente: '',
  telefono: '',
  cellulare: '',
  email: '',
  pec: '',
  fax: '',
  sito_web: '',
  via: '',
  civico: '',
  cap: '',
  comune: '',
  provincia: '',
  nazione: 'Italia',
  note: '',
  tag: '',
}

function initialTab(): Tab {
  if (typeof window === 'undefined') return 'cliente'
  const path = window.location.pathname
  const params = new URLSearchParams(window.location.search)
  if (path.includes('/app-v2/soggetti/nuovo')) return 'soggetto'
  return (params.get('tab') || params.get('tipo')) === 'soggetto' ? 'soggetto' : 'cliente'
}

function text(value: unknown): string {
  return String(value ?? '').trim()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

async function safeJson(response: Response): Promise<Record<string, unknown>> {
  try {
    const payload = await response.json()
    return isRecord(payload) ? payload : {}
  } catch {
    return {}
  }
}

function asInputValue(value: string | boolean | undefined): string {
  return typeof value === 'boolean' ? (value ? '1' : '0') : text(value)
}

function Field({
  label,
  name,
  value,
  onChange,
  type = 'text',
  required = false,
  placeholder = '',
  wide = false,
  mono = false,
  children,
}:{
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  type?: string
  required?: boolean
  placeholder?: string
  wide?: boolean
  mono?: boolean
  children?: ReactNode
}) {
  return (
    <label className={`iu-cln-field ${wide ? 'is-wide' : ''} ${mono ? 'is-mono' : ''}`.trim()}>
      <span>{label}{required ? <b>*</b> : null}</span>
      <input name={name} type={type} value={value} required={required} placeholder={placeholder} onChange={(event) => onChange(name, event.currentTarget.value)}/>
      {children}
    </label>
  )
}

function TextAreaField({
  label,
  name,
  value,
  onChange,
  placeholder = '',
}:{
  label: string
  name: string
  value: string
  onChange: (name: string, value: string) => void
  placeholder?: string
}) {
  return (
    <label className="iu-cln-field is-wide">
      <span>{label}</span>
      <textarea name={name} value={value} placeholder={placeholder} onChange={(event) => onChange(name, event.currentTarget.value)}/>
    </label>
  )
}

function SelectField({
  label,
  name,
  value,
  options,
  onChange,
  required = false,
}:{
  label: string
  name: string
  value: string
  options: RegistryOption[]
  onChange: (name: string, value: string) => void
  required?: boolean
}) {
  return (
    <label className="iu-cln-field">
      <span>{label}{required ? <b>*</b> : null}</span>
      <select name={name} value={value} required={required} onChange={(event) => onChange(name, event.currentTarget.value)}>
        {options.map((option) => <option value={option.value} key={`${name}-${option.value}`}>{option.label}</option>)}
      </select>
    </label>
  )
}

function ChoiceGrid({
  name,
  value,
  options,
  onChange,
  columns = 'type',
}:{
  name: string
  value: string
  options: RegistryOption[]
  onChange: (name: string, value: string) => void
  columns?: 'type' | 'subject' | 'role'
}) {
  const className = columns === 'role' ? 'iu-cln-process-grid' : columns === 'subject' ? 'iu-cln-subject-type-grid' : 'iu-cln-type-grid'
  return (
    <div className={className}>
      {options.map((option) => (
        <label className={`iu-cln-choice iu-cln-choice--${option.tone || 'neutral'} ${value === option.value ? 'is-active' : ''}`} key={`${name}-${option.value}`}>
          <input type="radio" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(name, option.value)}/>
          <span>{columns === 'role' ? <BriefcaseBusiness size={18}/> : subjectLegalTypes.has(option.value) ? <Building2 size={18}/> : <UserRound size={18}/>}</span>
          <strong>{option.label}</strong>
          {option.subtitle ? <small>{option.subtitle}</small> : null}
        </label>
      ))}
    </div>
  )
}

function Card({ title, icon, note, children }:{title: string; icon: ReactNode; note?: string; children: ReactNode}) {
  return (
    <section className="iu-cln-card">
      <header className="iu-cln-card__head">
        <div>{icon}<strong>{title}</strong></div>
        {note ? <span>{note}</span> : null}
      </header>
      <div className="iu-cln-card__body">{children}</div>
    </section>
  )
}

async function decodeFiscalCode(value: string): Promise<Record<string, string>> {
  const code = value.replace(/\s/g, '').toUpperCase()
  if (code.length !== 16) return {}
  const response = await fetch(`/api/cf/decodifica?cf=${encodeURIComponent(code)}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
  const payload = await safeJson(response)
  if (payload.errore) return {}
  return {
    sesso: text(payload.sesso),
    data_nascita: text(payload.data_nascita),
    luogo_nascita: text(payload.luogo_nascita),
    provincia_nascita: text(payload.provincia_nascita),
  }
}

async function calculateFiscalCode(values: Record<string, string>): Promise<Record<string, string>> {
  const params = new URLSearchParams({
    cognome: text(values.cognome),
    nome: text(values.nome),
    sesso: text(values.sesso),
    data_nascita: text(values.data_nascita),
    luogo_nascita: text(values.luogo_nascita),
    provincia_nascita: text(values.provincia_nascita),
  })
  if ([params.get('cognome'), params.get('nome'), params.get('sesso'), params.get('data_nascita'), params.get('luogo_nascita')].some((item) => !item)) return {}
  const response = await fetch(`/api/cf/calcola?${params.toString()}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
  const payload = await safeJson(response)
  if (payload.errore) return {}
  return {
    codice_fiscale: text(payload.codice_fiscale),
    luogo_nascita: text(payload.luogo_nascita),
    provincia_nascita: text(payload.provincia_nascita),
  }
}

function StatsStrip({ data }:{data: ClientiNuovoData}) {
  return (
    <section className="iu-cln-stats" aria-label="Stato anagrafiche">
      <article><UsersRound size={20}/><span>Clienti</span><strong>{data.stats.totalClients}</strong><small>{data.stats.activeClients} attivi</small></article>
      <article><UserRound size={20}/><span>Persone fisiche</span><strong>{data.stats.physicalClients}</strong><small>PF in archivio</small></article>
      <article><Building2 size={20}/><span>Persone giuridiche</span><strong>{data.stats.legalClients}</strong><small>Societa ed enti</small></article>
      <article><ClipboardCheck size={20}/><span>Da completare</span><strong>{data.stats.missingRegistry}</strong><small>{data.stats.expiredDocuments} documenti scaduti</small></article>
    </section>
  )
}

function ClientForm({ data }:{data: ClientiNuovoData}) {
  const [values, setValues] = useState<ClientFormState>({...initialClient})
  const [cfStatus, setCfStatus] = useState('')
  const action = data.actions.legacyClientForm
  const isPhysical = values.tipo === 'PERSONA_FISICA'
  const nextUrl = data.query.nextUrl

  useEffect(() => {
    if (nextUrl) setValues((current) => ({...current, next_url: nextUrl}))
  }, [nextUrl])

  useEffect(() => {
    const code = text(values.codice_fiscale).replace(/\s/g, '').toUpperCase()
    if (!isPhysical || code.length !== 16) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      decodeFiscalCode(code).then((decoded) => {
        if (cancelled || !Object.keys(decoded).length) return
        setValues((current) => ({
          ...current,
          codice_fiscale: code,
          sesso: text(current.sesso) || decoded.sesso || '',
          data_nascita: text(current.data_nascita) || decoded.data_nascita || '',
          luogo_nascita: text(current.luogo_nascita) || decoded.luogo_nascita || '',
          provincia_nascita: text(current.provincia_nascita) || decoded.provincia_nascita || '',
        }))
        setCfStatus('Dati di nascita compilati dal codice fiscale.')
      })
    }, 240)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.codice_fiscale, isPhysical])

  useEffect(() => {
    if (!isPhysical || text(values.codice_fiscale)) return
    const fields = {
      cognome: text(values.cognome),
      nome: text(values.nome),
      sesso: text(values.sesso),
      data_nascita: text(values.data_nascita),
      luogo_nascita: text(values.luogo_nascita),
      provincia_nascita: text(values.provincia_nascita),
    }
    if (Object.values(fields).slice(0, 5).some((item) => !item)) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      calculateFiscalCode(fields).then((result) => {
        if (cancelled || !result.codice_fiscale) return
        setValues((current) => text(current.codice_fiscale) ? current : ({...current, ...result}))
        setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
      })
    }, 420)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.cognome, values.nome, values.sesso, values.data_nascita, values.luogo_nascita, values.provincia_nascita, values.codice_fiscale, isPhysical])

  const change = (name: string, value: string) => {
    setValues((current) => ({...current, [name]: name.includes('codice') || name.includes('partita') || name === 'provincia_nascita' ? value.toUpperCase() : value}))
  }
  const checkbox = (event: ChangeEvent<HTMLInputElement>) => {
    setValues((current) => ({...current, [event.currentTarget.name]: event.currentTarget.checked}))
  }
  const generateNow = () => {
    calculateFiscalCode({
      cognome: text(values.cognome),
      nome: text(values.nome),
      sesso: text(values.sesso),
      data_nascita: text(values.data_nascita),
      luogo_nascita: text(values.luogo_nascita),
      provincia_nascita: text(values.provincia_nascita),
    }).then((result) => {
      if (!result.codice_fiscale) {
        setCfStatus('Completa cognome, nome, sesso, data e luogo di nascita.')
        return
      }
      setValues((current) => ({...current, ...result}))
      setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
    })
  }

  return (
    <form className="iu-cln-form" method="post" action={action}>
      <input type="hidden" name="next_url" value={asInputValue(values.next_url)}/>
      <Card title="Tipo cliente" icon={<UserCheck size={18}/>} note="Scrittura su /clienti/nuovo">
        <ChoiceGrid name="tipo" value={asInputValue(values.tipo)} options={data.options.clientTypes} onChange={change}/>
      </Card>

      <Card title={isPhysical ? 'Dati persona fisica' : 'Dati persona giuridica'} icon={isPhysical ? <UserRound size={18}/> : <Building2 size={18}/>} note="Campi compatibili con il form storico">
        {isPhysical ? (
          <div className="iu-cln-grid">
            <Field label="Cognome" name="cognome" value={asInputValue(values.cognome)} required placeholder="Rossi" onChange={change}/>
            <Field label="Nome" name="nome" value={asInputValue(values.nome)} required placeholder="Mario" onChange={change}/>
            <SelectField label="Sesso" name="sesso" value={asInputValue(values.sesso)} required onChange={change} options={[{value: '', label: '-'}, {value: 'M', label: 'Maschile'}, {value: 'F', label: 'Femminile'}]}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={asInputValue(values.codice_fiscale)} placeholder="RSSMRA80A01H501Z" mono onChange={change}>
              <button className="iu-cln-mini-action" type="button" onClick={generateNow}>Genera CF</button>
            </Field>
            <Field label="Data di nascita" name="data_nascita" type="date" value={asInputValue(values.data_nascita)} onChange={change}/>
            <Field label="Luogo di nascita" name="luogo_nascita" value={asInputValue(values.luogo_nascita)} placeholder="Roma" onChange={change}/>
            <Field label="Provincia nascita" name="provincia_nascita" value={asInputValue(values.provincia_nascita)} placeholder="RM" mono onChange={change}/>
            <Field label="Nazionalita" name="nazionalita" value={asInputValue(values.nazionalita)} placeholder="Italiana" onChange={change}/>
            {cfStatus ? <p className="iu-cln-field-note"><Sparkles size={14}/>{cfStatus}</p> : null}
          </div>
        ) : (
          <div className="iu-cln-grid">
            <Field label="Ragione sociale" name="ragione_sociale" value={asInputValue(values.ragione_sociale)} required placeholder="Rossi Srl" onChange={change}/>
            <SelectField label="Forma giuridica" name="forma_giuridica" value={asInputValue(values.forma_giuridica)} options={data.options.legalForms} onChange={change}/>
            <Field label="Partita IVA" name="partita_iva" value={asInputValue(values.partita_iva)} placeholder="12345678901" mono onChange={change}/>
            <Field label="Codice fiscale ente" name="codice_fiscale" value={asInputValue(values.codice_fiscale)} mono onChange={change}/>
            <Field label="Rappresentante legale" name="rappresentante_legale" value={asInputValue(values.rappresentante_legale)} onChange={change}/>
            <Field label="CF rappresentante" name="cf_rappresentante" value={asInputValue(values.cf_rappresentante)} mono onChange={change}/>
          </div>
        )}
      </Card>

      <Card title="Recapiti" icon={<Phone size={18}/>} note="Usati da conferimenti, messaggi e PEC">
        <div className="iu-cln-grid">
          <Field label="Telefono" name="telefono" value={asInputValue(values.telefono)} onChange={change}/>
          <Field label="Cellulare" name="cellulare" value={asInputValue(values.cellulare)} onChange={change}/>
          <Field label="Email" name="email" type="email" value={asInputValue(values.email)} onChange={change}/>
          <Field label="PEC" name="pec" type="email" value={asInputValue(values.pec)} onChange={change}/>
          <Field label="Fax" name="fax" value={asInputValue(values.fax)} onChange={change}/>
          <Field label="Sito web" name="sito_web" value={asInputValue(values.sito_web)} onChange={change}/>
        </div>
      </Card>

      <Card title={isPhysical ? 'Residenza e domicilio' : 'Sede legale'} icon={<Home size={18}/>} note="Prefissi legacy rispettati">
        <div className="iu-cln-grid">
          <Field label={isPhysical ? 'Via residenza' : 'Via sede'} name={isPhysical ? 'via' : 'sl_via'} value={asInputValue(values[isPhysical ? 'via' : 'sl_via'])} onChange={change}/>
          <Field label="Civico" name={isPhysical ? 'civico' : 'sl_civico'} value={asInputValue(values[isPhysical ? 'civico' : 'sl_civico'])} onChange={change}/>
          <Field label="CAP" name={isPhysical ? 'cap' : 'sl_cap'} value={asInputValue(values[isPhysical ? 'cap' : 'sl_cap'])} onChange={change}/>
          <Field label="Comune" name={isPhysical ? 'comune' : 'sl_comune'} value={asInputValue(values[isPhysical ? 'comune' : 'sl_comune'])} onChange={change}/>
          <Field label="Provincia" name={isPhysical ? 'provincia' : 'sl_provincia'} value={asInputValue(values[isPhysical ? 'provincia' : 'sl_provincia'])} mono onChange={change}/>
          <Field label="Nazione" name={isPhysical ? 'nazione' : 'sl_nazione'} value={asInputValue(values[isPhysical ? 'nazione' : 'sl_nazione'])} onChange={change}/>
          {isPhysical ? (
            <>
              <Field label="Domicilio via" name="dom_via" value={asInputValue(values.dom_via)} onChange={change}/>
              <Field label="Domicilio comune" name="dom_comune" value={asInputValue(values.dom_comune)} onChange={change}/>
              <Field label="Domicilio provincia" name="dom_provincia" value={asInputValue(values.dom_provincia)} mono onChange={change}/>
            </>
          ) : null}
        </div>
      </Card>

      <Card title="Documento e studio" icon={<FileText size={18}/>} note="Documento salvato nella route storica estesa">
        <div className="iu-cln-grid">
          <SelectField label="Tipo documento" name="doc_tipo" value={asInputValue(values.doc_tipo)} options={data.options.documentTypes} onChange={change}/>
          <Field label="Numero documento" name="doc_numero" value={asInputValue(values.doc_numero)} mono onChange={change}/>
          <Field label="Rilasciato da" name="doc_rilasciato_da" value={asInputValue(values.doc_rilasciato_da)} onChange={change}/>
          <Field label="Data rilascio" name="doc_data_rilascio" type="date" value={asInputValue(values.doc_data_rilascio)} onChange={change}/>
          <Field label="Data scadenza" name="doc_data_scadenza" type="date" value={asInputValue(values.doc_data_scadenza)} onChange={change}/>
          <Field label="Avvocato referente" name="avvocato_referente" value={asInputValue(values.avvocato_referente)} onChange={change}/>
          <Field label="Provenienza" name="provenienza" value={asInputValue(values.provenienza)} placeholder="passaparola, web, cliente" onChange={change}/>
          <TextAreaField label="Note" name="note" value={asInputValue(values.note)} onChange={change}/>
        </div>
      </Card>

      <label className="iu-cln-switch">
        <input type="checkbox" name="crea_preventivo_iniziale" value="1" checked={Boolean(values.crea_preventivo_iniziale)} onChange={checkbox}/>
        <span><i/></span>
        <strong>Crea preventivo iniziale dopo il salvataggio</strong>
        <small>Segue il workflow storico preventivo - conferimento - fascicolo.</small>
      </label>

      <div className="iu-cln-actions">
        <button className="iu-cln-submit" type="submit"><CheckCircle2 size={17}/>Salva cliente</button>
        <a className="iu-cln-secondary" href="/app-v2/clienti">Annulla</a>
      </div>
    </form>
  )
}

function SubjectForm({ data }:{data: ClientiNuovoData}) {
  const [values, setValues] = useState<SubjectFormState>({...initialSubject})
  const [cfStatus, setCfStatus] = useState('')
  const action = data.actions.legacySubjectForm
  const isLegal = subjectLegalTypes.has(values.tipo)

  useEffect(() => {
    if (data.query.idCliente) setValues((current) => ({...current, id_cliente: data.query.idCliente}))
  }, [data.query.idCliente])

  useEffect(() => {
    const code = text(values.codice_fiscale).replace(/\s/g, '').toUpperCase()
    if (isLegal || code.length !== 16) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      decodeFiscalCode(code).then((decoded) => {
        if (cancelled || !Object.keys(decoded).length) return
        setValues((current) => ({
          ...current,
          codice_fiscale: code,
          sesso: text(current.sesso) || decoded.sesso || '',
          data_nascita: text(current.data_nascita) || decoded.data_nascita || '',
          luogo_nascita: text(current.luogo_nascita) || decoded.luogo_nascita || '',
          provincia_nascita: text(current.provincia_nascita) || decoded.provincia_nascita || '',
        }))
        setCfStatus('Dati di nascita compilati dal codice fiscale.')
      })
    }, 240)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.codice_fiscale, isLegal])

  useEffect(() => {
    if (isLegal || text(values.codice_fiscale)) return
    const fields = {
      cognome: text(values.cognome),
      nome: text(values.nome),
      sesso: text(values.sesso),
      data_nascita: text(values.data_nascita),
      luogo_nascita: text(values.luogo_nascita),
      provincia_nascita: text(values.provincia_nascita),
    }
    if (Object.values(fields).slice(0, 5).some((item) => !item)) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      calculateFiscalCode(fields).then((result) => {
        if (cancelled || !result.codice_fiscale) return
        setValues((current) => text(current.codice_fiscale) ? current : ({...current, ...result}))
        setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
      })
    }, 420)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [values.cognome, values.nome, values.sesso, values.data_nascita, values.luogo_nascita, values.provincia_nascita, values.codice_fiscale, isLegal])

  const change = (name: string, value: string) => {
    setValues((current) => ({...current, [name]: name.includes('codice') || name.includes('partita') || name.includes('provincia') ? value.toUpperCase() : value}))
  }
  const generateNow = () => {
    calculateFiscalCode(values).then((result) => {
      if (!result.codice_fiscale) {
        setCfStatus('Completa cognome, nome, sesso, data e luogo di nascita.')
        return
      }
      setValues((current) => ({...current, ...result}))
      setCfStatus('Codice fiscale generato: verifica prima del salvataggio.')
    })
  }

  return (
    <form className="iu-cln-form" method="post" action={action}>
      <Card title="Tipo soggetto" icon={<UsersRound size={18}/>} note="Anagrafica soggetto processuale">
        <ChoiceGrid name="tipo" value={values.tipo} options={data.options.subjectTypes} columns="subject" onChange={change}/>
      </Card>

      <Card title={isLegal ? 'Dati ente o parte giuridica' : 'Dati persona fisica'} icon={isLegal ? <Landmark size={18}/> : <UserRound size={18}/>} note="Scrittura su /soggetti/nuovo">
        {isLegal ? (
          <div className="iu-cln-grid">
            <Field label="Ragione sociale" name="ragione_sociale" value={values.ragione_sociale} required onChange={change}/>
            <SelectField label="Forma giuridica" name="forma_giuridica" value={values.forma_giuridica} options={data.options.legalForms} onChange={change}/>
            <Field label="Partita IVA" name="partita_iva" value={values.partita_iva} mono onChange={change}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={values.codice_fiscale} mono onChange={change}/>
            <Field label="Rappresentante legale" name="rappresentante_legale" value={values.rappresentante_legale} onChange={change}/>
          </div>
        ) : (
          <div className="iu-cln-grid">
            <Field label="Cognome" name="cognome" value={values.cognome} required onChange={change}/>
            <Field label="Nome" name="nome" value={values.nome} required onChange={change}/>
            <SelectField label="Sesso" name="sesso" value={values.sesso} onChange={change} options={[{value: '', label: '-'}, {value: 'M', label: 'Maschile'}, {value: 'F', label: 'Femminile'}]}/>
            <Field label="Codice fiscale" name="codice_fiscale" value={values.codice_fiscale} mono onChange={change}>
              <button className="iu-cln-mini-action" type="button" onClick={generateNow}>Genera CF</button>
            </Field>
            <Field label="Data di nascita" name="data_nascita" type="date" value={values.data_nascita} onChange={change}/>
            <Field label="Luogo di nascita" name="luogo_nascita" value={values.luogo_nascita} onChange={change}/>
            <Field label="Provincia nascita" name="provincia_nascita" value={values.provincia_nascita} mono onChange={change}/>
            {cfStatus ? <p className="iu-cln-field-note"><Sparkles size={14}/>{cfStatus}</p> : null}
          </div>
        )}
      </Card>

      <Card title="Tipo soggetto processuale" icon={<BriefcaseBusiness size={18}/>} note="Salvato nel campo qualifica">
        <ChoiceGrid name="qualifica" value={values.qualifica} options={data.options.subjectRoles} columns="role" onChange={change}/>
      </Card>

      <Card title="Collegamenti e qualifica" icon={<UserCheck size={18}/>} note="Cliente collegato e dati professionali">
        <div className="iu-cln-grid">
          <label className="iu-cln-field is-wide">
            <span>Cliente collegato</span>
            <select name="id_cliente" value={values.id_cliente} onChange={(event) => change('id_cliente', event.currentTarget.value)}>
              <option value="">Nessun cliente collegato</option>
              {data.clientOptions.map((cliente) => <option value={cliente.id} key={cliente.id}>{cliente.label}{cliente.taxCode ? ` - ${cliente.taxCode}` : ''}</option>)}
            </select>
          </label>
          <Field label="Ordine professionale" name="ordine" value={values.ordine} onChange={change}/>
          <Field label="Numero iscrizione" name="numero_iscrizione" value={values.numero_iscrizione} onChange={change}/>
          <Field label="Tag" name="tag" value={values.tag} placeholder="controparte, assicurazione" onChange={change}/>
        </div>
      </Card>

      <Card title="Recapiti e indirizzo" icon={<Mail size={18}/>} note="Compatibile con la vista storica soggetti">
        <div className="iu-cln-grid">
          <Field label="Telefono" name="telefono" value={values.telefono} onChange={change}/>
          <Field label="Cellulare" name="cellulare" value={values.cellulare} onChange={change}/>
          <Field label="Email" name="email" type="email" value={values.email} onChange={change}/>
          <Field label="PEC" name="pec" type="email" value={values.pec} onChange={change}/>
          <Field label="Via" name="via" value={values.via} onChange={change}/>
          <Field label="Civico" name="civico" value={values.civico} onChange={change}/>
          <Field label="CAP" name="cap" value={values.cap} onChange={change}/>
          <Field label="Comune" name="comune" value={values.comune} onChange={change}/>
          <Field label="Provincia" name="provincia" value={values.provincia} mono onChange={change}/>
          <Field label="Nazione" name="nazione" value={values.nazione} onChange={change}/>
          <TextAreaField label="Note" name="note" value={values.note} onChange={change}/>
        </div>
      </Card>

      <div className="iu-cln-actions">
        <button className="iu-cln-submit" type="submit"><CheckCircle2 size={17}/>Salva soggetto</button>
        <a className="iu-cln-secondary" href="/app-v2/soggetti">Annulla</a>
      </div>
    </form>
  )
}

function QualityRail({ data, activeTab }:{data: ClientiNuovoData; activeTab: Tab}) {
  const checkItems = activeTab === 'cliente'
    ? ['Dati fiscali verificati', 'Almeno un recapito presente', 'Indirizzo utile al conferimento', 'Documento identita controllato']
    : ['Ruolo processuale assegnato', 'Cliente collegato se pertinente', 'Recapiti della parte completi', 'Qualifica coerente con il fascicolo']
  return (
    <aside className="iu-cln-rail">
      <Panel title="Qualita anagrafica" icon={<BadgeCheck size={17}/>} count={checkItems.length}>
        <div className="iu-cln-checklist">
          {checkItems.map((item) => <span key={item}><CheckCircle2 size={15}/>{item}</span>)}
        </div>
      </Panel>
      <Panel title="Statistiche rapide" icon={<ClipboardCheck size={17}/>}>
        <div className="iu-cln-briefing">
          <article><span>Clienti da completare</span><strong>{data.stats.missingRegistry}</strong><small>prima del conferimento</small></article>
          <article><span>Soggetti non collegati</span><strong>{data.stats.subjectsWithoutClient}</strong><small>da associare se necessario</small></article>
          <article><span>Documenti scaduti</span><strong>{data.stats.expiredDocuments}</strong><small>da aggiornare</small></article>
        </div>
      </Panel>
      <Panel title="Azioni collegate" icon={<Sparkles size={17}/>}>
        <div className="iu-cln-shortcuts">
          <a href="/app-v2/clienti"><UsersRound size={15}/>Anagrafica clienti</a>
          <a href="/app-v2/soggetti"><UserCheck size={15}/>Soggetti e parti</a>
          <a href="/app-v2/ricerca-studio?tipo=clienti"><ScanLine size={15}/>Cerca duplicati</a>
          <a href="/preventivi/"><CreditCard size={15}/>Preventivi e incarichi</a>
        </div>
      </Panel>
    </aside>
  )
}

export function NuovoClientePage() {
  const [data, setData] = useState<ClientiNuovoData>(emptyClientiNuovoData)
  const [tab, setTab] = useState<Tab>(initialTab)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    getClientiNuovoData().then((payload) => {
      if (!alive) return
      setData(payload)
      if (payload.query.tab === 'soggetto') setTab('soggetto')
    }).finally(() => {
      if (alive) setLoading(false)
    })
    return () => {
      alive = false
    }
  }, [])

  const heroText = useMemo(() => tab === 'cliente'
    ? 'Nuova anagrafica cliente con dati fiscali, recapiti, documento, indirizzi e onboarding preventivo.'
    : 'Nuovo soggetto o parte processuale con ruolo, collegamento cliente e dati anagrafici completi.',
  [tab])

  return (
    <main className="iu-content iu-clienti-new-page">
      <section className="iu-cln-hero">
        <div>
          <a className="iu-cln-back" href={tab === 'cliente' ? '/app-v2/clienti' : '/app-v2/soggetti'}><ArrowLeft size={15}/>Torna all'anagrafica</a>
          <span className="iu-cln-eyebrow"><Sparkles size={14}/>Migrazione React progressiva</span>
          <h1>{tab === 'cliente' ? 'Nuovo Cliente' : 'Nuovo Soggetto'}</h1>
          <p>{heroText}</p>
        </div>
        <div className="iu-cln-hero__actions">
          <a href="/clienti/nuovo">Vista storica cliente</a>
          <a href="/soggetti/nuovo">Vista storica soggetto</a>
        </div>
      </section>

      <StatsStrip data={data}/>

      <div className="iu-cln-tabs" role="tablist" aria-label="Scelta anagrafica">
        <button type="button" className={tab === 'cliente' ? 'is-active' : ''} onClick={() => setTab('cliente')}><UserPlus size={17}/>Nuovo Cliente</button>
        <button type="button" className={tab === 'soggetto' ? 'is-active' : ''} onClick={() => setTab('soggetto')}><UsersRound size={17}/>Nuovo Soggetto</button>
        <span>{loading ? 'Caricamento dati...' : `${data.source} - scritture legacy`}</span>
      </div>

      {data.query.idCliente ? (
        <section className="iu-cln-flow-alert">
          <UserCheck size={18}/>
          <div><strong>Cliente precompilato dal contesto</strong><span>Il collegamento resta modificabile prima del salvataggio.</span></div>
        </section>
      ) : null}

      <section className="iu-cln-layout">
        <div className="iu-cln-main">
          {tab === 'cliente' ? <ClientForm data={data}/> : <SubjectForm data={data}/>}
        </div>
        <QualityRail data={data} activeTab={tab}/>
      </section>

      <div className="iu-cln-ocr-note"><Camera size={15}/>Hook OCR/MRZ pronto: quando collegheremo il parser documento potra popolare CF, documento e scadenze.</div>

      <FloatingLex
        context="clienti-nuovo"
        title="Lex AI anagrafiche"
        body="Posso controllare dati minimi, suggerire ruolo processuale, verificare recapiti mancanti e preparare il passaggio a preventivo, fascicolo o conferimento."
        primaryHref={`/lex?context=${tab === 'cliente' ? 'nuovo-cliente' : 'nuovo-soggetto'}`}
        primaryLabel="Apri Lex anagrafica"
        secondaryHref="/app-v2/ricerca-studio?tipo=clienti"
        secondaryLabel="Cerca duplicati"
      />
    </main>
  )
}
