import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Landmark, Loader2, Plus, Scale, Search, ShieldCheck, Trash2, UserPlus, UsersRound } from 'lucide-react'
import { Badge } from '../../components/dashboard'
import { searchPublicSubjectRegisters, type PublicRegistrySubjectLookup, type PublicRegistrySubjectResult } from '../../clientiNuovoData'
import type { FascicoloFormSubject, FascicoloParty } from '../../fascicoliData'
import type { Tone } from '../../data'

/**
 * Altre controparti del fascicolo (Nuovo/Modifica).
 *
 * L'avvocato aggiunge piu controparti (o il difensore della controparte) cercando fra i Soggetti
 * dello studio, ReGIndE, Registro PP.AA. e INI-PEC consultati in cache locale, oppure a mano.
 * Le righe viaggiano nel campo nascosto `controparti_aggiuntive_json`: al salvataggio il server
 * valida, riusa le schede con lo stesso C.F./P.IVA e collega le parti al fascicolo.
 */

export type ControparteFonte = 'soggetti' | 'reginde' | 'registro_ppaa' | 'inipec' | 'manuale'
export type ControparteRuolo = 'CONTROPARTE' | 'DIFENSORE_CONTROPARTE'
type SearchSource = Exclude<ControparteFonte, 'manuale'>

export type ControparteCandidata = {
  id: string
  idSoggetto: string
  nome: string
  identificativo: string
  tipo: string
  ruolo: ControparteRuolo
  fonte: ControparteFonte
  pec: string
  email: string
  telefono: string
  personaNome: string
  personaCognome: string
}

type ControparteRiga = ControparteCandidata & { key: string }

export const CONTROPARTI_MAX = 20

export const CONTROPARTI_FONTI: Array<{ id: SearchSource; label: string; note: string; placeholder: string }> = [
  { id: 'soggetti', label: 'Soggetti dello studio', note: 'Schede già censite', placeholder: 'Nome, C.F., P. IVA o PEC' },
  { id: 'registro_ppaa', label: 'Registro PP.AA.', note: 'Pubbliche amministrazioni', placeholder: 'Ente, C.F., P. IVA o PEC' },
  { id: 'reginde', label: 'ReGIndE', note: 'Avvocati e difensori', placeholder: 'Nome, C.F. o PEC del difensore' },
  { id: 'inipec', label: 'INI-PEC', note: 'Imprese e professionisti', placeholder: 'Ragione sociale, P. IVA o PEC' },
]

const FONTE_LABEL: Record<ControparteFonte, string> = {
  soggetti: 'Soggetti',
  reginde: 'ReGIndE',
  registro_ppaa: 'Registro PP.AA.',
  inipec: 'INI-PEC',
  manuale: 'Manuale',
}

const FONTE_TONE: Record<ControparteFonte, Tone> = {
  soggetti: 'success',
  reginde: 'primary',
  registro_ppaa: 'info',
  inipec: 'purple',
  manuale: 'neutral',
}

const TIPI_SOGGETTO = [
  { value: 'PERSONA_GIURIDICA', label: 'Persona giuridica' },
  { value: 'PERSONA_FISICA', label: 'Persona fisica' },
  { value: 'PUBBLICA_AMMINISTRAZIONE', label: 'Pubblica amministrazione' },
  { value: 'ENTE', label: 'Ente' },
  { value: 'CONDOMINIO', label: 'Condominio' },
  { value: 'ASSOCIAZIONE', label: 'Associazione' },
  { value: 'PROFESSIONISTA', label: 'Professionista' },
]

const CF_RE = /^[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$/
const PIVA_RE = /^[0-9]{11}$/

export function normalizzaIdentificativo(value: string): string {
  return String(value || '').replace(/[^A-Za-z0-9]/g, '').toUpperCase()
}

export function identificativoValido(value: string): boolean {
  const normalized = normalizzaIdentificativo(value)
  return CF_RE.test(normalized) || PIVA_RE.test(normalized)
}

function normalizeText(value: string): string {
  return String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim()
}

export function candidataDaSoggetto(subject: FascicoloFormSubject): ControparteCandidata {
  const qualification = String(subject.qualification || '').toUpperCase()
  return {
    id: `soggetti-${subject.id}`,
    idSoggetto: subject.id,
    nome: subject.label,
    identificativo: normalizzaIdentificativo(subject.vat || subject.taxCode),
    tipo: subject.type || 'PERSONA_GIURIDICA',
    ruolo: qualification.includes('DIFENSORE') ? 'DIFENSORE_CONTROPARTE' : 'CONTROPARTE',
    fonte: 'soggetti',
    pec: subject.pec,
    email: subject.email,
    telefono: subject.phone,
    personaNome: '',
    personaCognome: '',
  }
}

export function candidataDaRegistro(item: PublicRegistrySubjectResult): ControparteCandidata {
  const patch = item.subjectPatch || {}
  const registry = (['reginde', 'registro_ppaa', 'inipec'].includes(item.registry) ? item.registry : 'reginde') as SearchSource
  const persona = patch.nome || patch.cognome
  return {
    id: item.id,
    idSoggetto: '',
    nome: persona ? [patch.nome, patch.cognome].filter(Boolean).join(' ') : (patch.ragione_sociale || item.label),
    identificativo: normalizzaIdentificativo(patch.partita_iva || patch.codice_fiscale || item.taxCode),
    tipo: patch.tipo || (registry === 'registro_ppaa' ? 'PUBBLICA_AMMINISTRAZIONE' : 'PERSONA_GIURIDICA'),
    ruolo: patch.qualifica === 'DIFENSORE_CONTROPARTE' ? 'DIFENSORE_CONTROPARTE' : 'CONTROPARTE',
    fonte: registry,
    pec: patch.pec || item.pec,
    email: patch.email || '',
    telefono: patch.telefono || '',
    personaNome: patch.nome || '',
    personaCognome: patch.cognome || '',
  }
}

export function filtraSoggettiStudio(subjects: FascicoloFormSubject[], query: string, limit = 12): FascicoloFormSubject[] {
  const tokens = normalizeText(query).split(/\s+/).filter(Boolean)
  if (!tokens.length) return []
  return subjects
    .filter((subject) => {
      const haystack = normalizeText([subject.label, subject.taxCode, subject.vat, subject.pec, subject.email].join(' '))
      return tokens.every((token) => haystack.includes(token))
    })
    .slice(0, limit)
}

function chiaveRiga(item: Pick<ControparteCandidata, 'ruolo' | 'idSoggetto' | 'identificativo' | 'nome'>): string {
  return `${item.ruolo}|${item.idSoggetto || normalizzaIdentificativo(item.identificativo) || normalizeText(item.nome)}`
}

export function payloadControparti(rows: ControparteCandidata[]): string {
  const items = rows
    .filter((row) => row.idSoggetto || row.nome.trim() || row.identificativo.trim())
    .map((row) => ({
      id_soggetto: row.idSoggetto,
      nome: row.nome.trim(),
      identificativo: normalizzaIdentificativo(row.identificativo),
      tipo: row.tipo,
      ruolo: row.ruolo,
      fonte: row.fonte,
      pec: row.pec.trim(),
      email: row.email.trim(),
      telefono: row.telefono.trim(),
      persona_nome: row.personaNome,
      persona_cognome: row.personaCognome,
    }))
  return items.length ? JSON.stringify(items) : ''
}

let rowSequence = 0
function nuovaRiga(candidate: ControparteCandidata): ControparteRiga {
  rowSequence += 1
  return { ...candidate, key: `controparte-${Date.now()}-${rowSequence}` }
}

function rigaManuale(): ControparteRiga {
  return nuovaRiga({
    id: '',
    idSoggetto: '',
    nome: '',
    identificativo: '',
    tipo: 'PERSONA_GIURIDICA',
    ruolo: 'CONTROPARTE',
    fonte: 'manuale',
    pec: '',
    email: '',
    telefono: '',
    personaNome: '',
    personaCognome: '',
  })
}

function metaCandidata(candidate: ControparteCandidata): string {
  return [
    candidate.identificativo || 'C.F./P. IVA non presente',
    candidate.pec || candidate.email || 'PEC non presente',
    candidate.ruolo === 'DIFENSORE_CONTROPARTE' ? 'Difensore' : '',
  ].filter(Boolean).join(' · ')
}

export function ContropartiRegistriField({
  subjects,
  linkedSubjects,
  principalName,
  principalCode,
  onUsePrincipal,
  onCounterpartyRowsChange,
}: {
  subjects: FascicoloFormSubject[]
  linkedSubjects: FascicoloParty[]
  principalName: string
  principalCode: string
  onUsePrincipal: (candidate: ControparteCandidata) => void
  onCounterpartyRowsChange?: (count: number) => void
}) {
  const [rows, setRows] = useState<ControparteRiga[]>([])
  const [source, setSource] = useState<SearchSource>('soggetti')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ControparteCandidata[]>([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [registries, setRegistries] = useState<PublicRegistrySubjectLookup['registries']>([])
  const lastManualRef = useRef<string>('')
  const selectedSource = CONTROPARTI_FONTI.find((item) => item.id === source) || CONTROPARTI_FONTI[0]
  const counterpartyRows = rows.filter((row) => row.ruolo === 'CONTROPARTE').length

  useEffect(() => {
    onCounterpartyRowsChange?.(counterpartyRows)
  }, [counterpartyRows, onCounterpartyRowsChange])

  useEffect(() => {
    if (!lastManualRef.current) return
    const input = document.querySelector<HTMLInputElement>(`[data-controparte-row="${lastManualRef.current}"]`)
    input?.focus()
    lastManualRef.current = ''
  }, [rows])

  const rowKeys = useMemo(() => new Set(rows.map(chiaveRiga)), [rows])
  const linkedIds = useMemo(() => new Set(linkedSubjects.map((subject) => subject.id)), [linkedSubjects])
  const principalKey = normalizzaIdentificativo(principalCode) || normalizeText(principalName)
  const registryState = registries.find((item) => item.id === source)

  const runSearch = async () => {
    const text = query.trim()
    setError('')
    if (text.length < (source === 'soggetti' ? 2 : 3)) {
      setResults([])
      setMessage(`Digita almeno ${source === 'soggetti' ? 2 : 3} caratteri per cercare in ${selectedSource.label}.`)
      return
    }
    if (source === 'soggetti') {
      const found = filtraSoggettiStudio(subjects, text).map(candidataDaSoggetto)
      setResults(found)
      setMessage(found.length ? `${found.length} soggetti trovati in anagrafica.` : 'Nessun soggetto dello studio corrisponde: prova nei registri pubblici o inserisci a mano.')
      return
    }
    setLoading(true)
    try {
      const payload = await searchPublicSubjectRegisters(text, 12, source)
      setRegistries(payload.registries)
      const found = payload.results.map(candidataDaRegistro)
      setResults(found)
      const state = payload.registries.find((item) => item.id === source)
      if (state && !state.available) {
        setMessage(`${selectedSource.label} non ancora sincronizzato su questo server: inserisci la controparte a mano.`)
      } else {
        setMessage(payload.message || `${found.length} risultati in ${selectedSource.label}: verifica i dati prima di salvare.`)
      }
    } catch (searchError) {
      setResults([])
      setError(searchError instanceof Error ? searchError.message : 'Ricerca nei registri pubblici non riuscita.')
    } finally {
      setLoading(false)
    }
  }

  const handleSearchKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key !== 'Enter') return
    event.preventDefault()
    void runSearch()
  }

  const addCandidate = (candidate: ControparteCandidata, ruolo: ControparteRuolo = candidate.ruolo) => {
    const next = { ...candidate, ruolo }
    if (rows.length >= CONTROPARTI_MAX) {
      setError(`Puoi aggiungere al massimo ${CONTROPARTI_MAX} controparti per volta.`)
      return
    }
    if (rowKeys.has(chiaveRiga(next))) {
      setMessage(`${next.nome} è già nell'elenco delle altre controparti.`)
      return
    }
    setRows((current) => [...current, nuovaRiga(next)])
    setError('')
    setMessage(next.identificativo
      ? `${next.nome} aggiunta: sarà collegata al fascicolo al salvataggio.`
      : `${next.nome} aggiunta: completa codice fiscale o partita IVA prima di salvare.`)
  }

  const addManualRow = () => {
    if (rows.length >= CONTROPARTI_MAX) {
      setError(`Puoi aggiungere al massimo ${CONTROPARTI_MAX} controparti per volta.`)
      return
    }
    const row = rigaManuale()
    lastManualRef.current = row.key
    setRows((current) => [...current, row])
    setError('')
  }

  const updateRow = (key: string, patch: Partial<ControparteRiga>) => {
    setRows((current) => current.map((row) => (row.key === key ? { ...row, ...patch } : row)))
  }

  const removeRow = (key: string) => {
    setRows((current) => current.filter((row) => row.key !== key))
  }

  return (
    <section className="iu-fas-controparti iu-fas-field--wide" aria-label="Altre controparti">
      <header className="iu-fas-controparti__header">
        <div>
          <strong><UsersRound size={16}/> Altre controparti</strong>
          <span>Più controparti o il loro difensore: cerca nei Soggetti dello studio, nel Registro PP.AA., in ReGIndE e INI-PEC, oppure inserisci a mano.</span>
        </div>
        <button type="button" className="iu-fas-controparti__add" onClick={addManualRow}>
          <Plus size={15}/> Aggiungi controparte
        </button>
      </header>

      <div className="iu-fas-controparti__sources" role="tablist" aria-label="Dove cercare la controparte">
        {CONTROPARTI_FONTI.map((choice) => {
          const state = registries.find((item) => item.id === choice.id)
          return (
            <button
              type="button"
              role="tab"
              aria-selected={source === choice.id}
              className={source === choice.id ? 'is-active' : ''}
              key={choice.id}
              onClick={() => {
                setSource(choice.id)
                setResults([])
                setError('')
                setMessage(`Ricerca impostata su ${choice.label}.`)
              }}
            >
              <strong>{choice.id === 'registro_ppaa' ? <Landmark size={13}/> : choice.id === 'reginde' ? <Scale size={13}/> : choice.id === 'inipec' ? <ShieldCheck size={13}/> : <UsersRound size={13}/>} {choice.label}</strong>
              <span>{state && !state.available ? 'Non sincronizzato' : choice.note}</span>
            </button>
          )
        })}
      </div>

      <div className="iu-fas-controparti__search">
        <Search size={15}/>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          onKeyDown={handleSearchKey}
          placeholder={selectedSource.placeholder}
          aria-label={`Cerca in ${selectedSource.label}`}
        />
        <button type="button" onClick={() => void runSearch()} disabled={loading}>
          {loading ? <Loader2 className="iu-spin" size={14}/> : <Search size={14}/>}
          {loading ? 'Ricerca...' : 'Cerca'}
        </button>
      </div>
      <div className="iu-fas-controparti__status" aria-live="polite">
        {error ? <span className="is-error">{error}</span> : <span>{message || (registryState && !registryState.available ? `${selectedSource.label} non ancora sincronizzato su questo server.` : 'I dati dei registri sono suggerimenti: verificali prima di salvare il fascicolo.')}</span>}
      </div>

      {results.length ? (
        <div className="iu-fas-controparti__results">
          {results.map((candidate) => {
            const alreadyLinked = Boolean(candidate.idSoggetto && linkedIds.has(candidate.idSoggetto))
            const alreadyAdded = rowKeys.has(chiaveRiga(candidate))
            const isPrincipal = Boolean(principalKey) && principalKey === (candidate.identificativo || normalizeText(candidate.nome))
            return (
              <article className="iu-fas-controparti__result" key={candidate.id}>
                <div>
                  <strong>{candidate.nome}</strong>
                  <small>{metaCandidata(candidate)}</small>
                </div>
                <Badge tone={FONTE_TONE[candidate.fonte]}>{FONTE_LABEL[candidate.fonte]}</Badge>
                <div className="iu-fas-controparti__result-actions">
                  <button type="button" onClick={() => onUsePrincipal(candidate)} disabled={isPrincipal}>
                    {isPrincipal ? 'Controparte principale' : 'Usa come principale'}
                  </button>
                  <button type="button" className="is-primary" onClick={() => addCandidate(candidate, 'CONTROPARTE')} disabled={alreadyLinked || alreadyAdded}>
                    <UserPlus size={13}/>{alreadyLinked ? 'Già collegata' : alreadyAdded ? 'Aggiunta' : 'Aggiungi controparte'}
                  </button>
                  {candidate.fonte === 'reginde' || candidate.ruolo === 'DIFENSORE_CONTROPARTE' ? (
                    <button type="button" onClick={() => addCandidate(candidate, 'DIFENSORE_CONTROPARTE')} disabled={rowKeys.has(chiaveRiga({ ...candidate, ruolo: 'DIFENSORE_CONTROPARTE' }))}>
                      <Scale size={13}/> Difensore controparte
                    </button>
                  ) : null}
                </div>
              </article>
            )
          })}
        </div>
      ) : null}

      {rows.length ? (
        <div className="iu-fas-controparti__rows">
          {rows.map((row, index) => {
            const identityInvalid = Boolean(row.identificativo) && !identificativoValido(row.identificativo)
            const fromRegistry = row.fonte !== 'manuale'
            return (
              <div className="iu-fas-controparti__row" key={row.key}>
                <div className="iu-fas-controparti__row-head">
                  <span>{index + 1}</span>
                  <Badge tone={FONTE_TONE[row.fonte]}>{FONTE_LABEL[row.fonte]}</Badge>
                  <select
                    value={row.ruolo}
                    onChange={(event) => updateRow(row.key, { ruolo: event.currentTarget.value as ControparteRuolo })}
                    aria-label="Ruolo nel fascicolo"
                  >
                    <option value="CONTROPARTE">Controparte</option>
                    <option value="DIFENSORE_CONTROPARTE">Difensore della controparte</option>
                  </select>
                  <button type="button" className="iu-fas-controparti__remove" onClick={() => removeRow(row.key)} aria-label={`Rimuovi ${row.nome || 'controparte'}`}>
                    <Trash2 size={14}/>
                  </button>
                </div>
                {row.idSoggetto ? (
                  <p className="iu-fas-controparti__linked">
                    <strong>{row.nome}</strong>
                    <small>{metaCandidata(row)} · scheda già in anagrafica, nessun duplicato</small>
                  </p>
                ) : (
                  <div className="iu-fas-controparti__row-grid">
                    <label>
                      <span>Nome / ragione sociale<b>*</b></span>
                      <input
                        data-controparte-row={row.key}
                        value={row.nome}
                        required
                        onChange={(event) => updateRow(row.key, { nome: event.currentTarget.value, personaNome: '', personaCognome: '' })}
                        placeholder="Dato obbligatorio"
                      />
                    </label>
                    <label>
                      <span>C.F. / P. IVA<b>*</b></span>
                      <input
                        value={row.identificativo}
                        required
                        aria-invalid={identityInvalid || undefined}
                        onChange={(event) => updateRow(row.key, { identificativo: normalizzaIdentificativo(event.currentTarget.value) })}
                        placeholder={fromRegistry ? 'Non presente nel registro: completalo' : 'Dato obbligatorio'}
                      />
                    </label>
                    <label>
                      <span>Tipo soggetto</span>
                      <select value={row.tipo} onChange={(event) => updateRow(row.key, { tipo: event.currentTarget.value })}>
                        {TIPI_SOGGETTO.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
                      </select>
                    </label>
                    <label>
                      <span>PEC</span>
                      <input type="email" value={row.pec} onChange={(event) => updateRow(row.key, { pec: event.currentTarget.value })}/>
                    </label>
                    {identityInvalid ? <small className="is-warning">Codice fiscale (16 caratteri) o partita IVA (11 cifre) non valido.</small> : null}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <small className="iu-fas-field-help">Nessuna altra controparte: usa «Aggiungi controparte» o la ricerca per inserirne una o più.</small>
      )}
      <input type="hidden" name="controparti_aggiuntive_json" value={payloadControparti(rows)}/>
    </section>
  )
}
