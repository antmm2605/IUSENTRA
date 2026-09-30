/** Finestra «Calcola contributo unificato» del fascicolo (D.P.R. 115/2002 art. 13), caricata solo quando si apre. */
import { useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, Calculator, Copy, Euro } from 'lucide-react'
import type { FascicoloFull } from '../../fascicoliData'
import { csrfToken } from '../../formSubmit'
import { formatEuroIt } from '../../formatting'
import {
  contributoAmountNumber,
  copyTextForUser,
  fascicoloOggettoRicorso,
  saveContributionMemory,
  type ContributoUnificatoMemory,
  type ContributoUnificatoResult,
} from './contributoUnificato'

type ContributoUnificatoFormState = {
  cu_categoria: string
  cu_grado: string
  cu_valore_tipo: string
  cu_valore: string
  cu_anticipazione_forfettaria: string
  cu_numero_parti_ricorrenti: string
  cu_sezione_specializzata_impresa: string
  cu_dati_obbligatori_mancanti: string
}

const CONTRIBUTION_CATEGORIES = [
  { value: 'civile_ordinario', label: 'Civile ordinario' },
  { value: 'decreto_ingiuntivo', label: 'Ricorso per decreto ingiuntivo' },
  { value: 'lavoro', label: 'Lavoro / pubblico impiego' },
  { value: 'processo_speciale_libro_iv', label: 'Procedimento speciale civile' },
  { value: 'volontaria_giurisdizione', label: 'Volontaria giurisdizione' },
  { value: 'separazione_consensuale', label: 'Separazione / divorzio congiunto' },
  { value: 'ricerca_beni_492bis', label: 'Ricerca beni ex art. 492-bis c.p.c.' },
  { value: 'cittadinanza_italiana', label: 'Accertamento cittadinanza italiana' },
  { value: 'esecuzione_immobiliare', label: 'Esecuzione immobiliare' },
  { value: 'altri_processi_esecutivi', label: 'Altra esecuzione' },
  { value: 'esecuzione_mobiliare_sotto_2500', label: 'Esecuzione mobiliare sotto € 2.500,00' },
  { value: 'opposizione_atti_esecutivi', label: 'Opposizione agli atti esecutivi' },
  { value: 'procedura_fallimentare', label: 'Procedura fallimentare' },
  { value: 'tributario', label: 'Ricorso tributario' },
  { value: 'amministrativo_accesso_soggiorno_cittadinanza', label: 'Accesso, soggiorno, cittadinanza e ottemperanza' },
  { value: 'amministrativo_ordinario', label: 'Ricorso amministrativo ordinario' },
  { value: 'amministrativo_rito_abbreviato', label: 'Rito abbreviato amministrativo' },
  { value: 'amministrativo_appalti', label: 'Appalti pubblici (art. 119 c.p.a.)' },
  { value: 'amministrativo_ottemperanza', label: 'Ottemperanza con contestuale risarcitoria' },
]
const CONTRIBUTION_DEGREES = [
  { value: 'primo_grado', label: 'Primo grado' },
  { value: 'appello', label: 'Appello' },
  { value: 'cassazione', label: 'Cassazione' },
]
const CONTRIBUTION_VALUE_MODES = [
  { value: 'determinato', label: 'Valore determinato' },
  { value: 'indeterminabile', label: 'Valore indeterminabile' },
  { value: 'non_indicato', label: 'Valore non indicato' },
]

function defaultContributoUnificatoForm(fascicolo: FascicoloFull, prefill?: Record<string, unknown>): ContributoUnificatoFormState {
  const value = String(prefill?.valore_causa ?? fascicolo.valueRaw ?? fascicolo.value ?? '').trim()
  return {
    cu_categoria: 'civile_ordinario',
    cu_grado: 'primo_grado',
    cu_valore_tipo: value ? 'determinato' : 'indeterminabile',
    cu_valore: value,
    cu_anticipazione_forfettaria: '1',
    cu_numero_parti_ricorrenti: '1',
    cu_sezione_specializzata_impresa: '0',
    cu_dati_obbligatori_mancanti: '0',
  }
}

function buildContributoUnificatoCopyText({
  fascicolo,
  clientName,
  result,
}:{
  fascicolo: FascicoloFull
  clientName: string
  result: ContributoUnificatoResult
}): string {
  const notes = Array.isArray(result.notes) ? result.notes.filter(Boolean) : []
  const warnings = Array.isArray(result.warnings) ? result.warnings.filter(Boolean) : []
  const objectLabel = fascicoloOggettoRicorso(fascicolo)
  const lines = [
    'Calcolo contributo unificato',
    `Fascicolo: ${fascicolo.title || fascicolo.ref || fascicolo.id}`,
    fascicolo.ref ? `Riferimento: ${fascicolo.ref}` : '',
    clientName ? `Cliente: ${clientName}` : '',
    objectLabel ? `Oggetto del ricorso: ${objectLabel}` : '',
    `Tipologia: ${result.categoria_label || result.categoria || 'Non indicata'}`,
    `Grado: ${result.grado_label || result.grado || 'Primo grado'}`,
    `Tipo valore: ${result.valore_tipo_label || result.valore_tipo || 'Non indicato'}`,
    result.valore ? `Valore causa: ${formatEuroIt(result.valore)}` : '',
    `Contributo base: ${formatEuroIt(result.base)}`,
    `Anticipazione forfettaria: ${formatEuroIt(result.anticipazione_forfettaria)}`,
    `Totale da usare per PagoPA: ${formatEuroIt(result.totale)}`,
    notes.length ? `Note: ${notes.join(' ')}` : '',
    warnings.length ? `Avvisi: ${warnings.join(' ')}` : '',
  ].filter(Boolean)
  return lines.join('\n')
}

function buildContributoUnificatoMemory({
  fascicolo,
  clientName,
  result,
}:{
  fascicolo: FascicoloFull
  clientName: string
  result: ContributoUnificatoResult
}): ContributoUnificatoMemory {
  const copyText = buildContributoUnificatoCopyText({ fascicolo, clientName, result })
  const totalValue = contributoAmountNumber(result.totale)
  return {
    fascicoloId: fascicolo.id,
    title: fascicolo.title,
    reference: fascicolo.ref,
    objectLabel: fascicoloOggettoRicorso(fascicolo),
    clientName,
    totalLabel: formatEuroIt(result.totale),
    totalValue,
    createdAt: new Date().toISOString(),
    copyText,
    result,
  }
}

export default function ContributoUnificatoModal({
  open,
  fascicolo,
  clientName,
  onClose,
  onMemory,
  onOpenPagoPa,
}:{
  open: boolean
  fascicolo: FascicoloFull
  clientName: string
  onClose: () => void
  onMemory: (memory: ContributoUnificatoMemory, message?: string) => void
  onOpenPagoPa: () => void
}) {
  const [form, setForm] = useState<ContributoUnificatoFormState>(() => defaultContributoUnificatoForm(fascicolo))
  const [result, setResult] = useState<ContributoUnificatoResult | null>(null)
  const [loadingPrefill, setLoadingPrefill] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return undefined
    let active = true
    setResult(null)
    setError('')
    setCopyState('idle')
    setForm(defaultContributoUnificatoForm(fascicolo))
    setLoadingPrefill(true)
    fetch(`/strumenti-legali/api/prefill/${encodeURIComponent(fascicolo.id)}`, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
    })
      .then((response) => response.json())
      .then((payload) => {
        if (!active) return
        if (payload?.ok && payload.prefill && typeof payload.prefill === 'object') {
          setForm(defaultContributoUnificatoForm(fascicolo, payload.prefill as Record<string, unknown>))
        }
      })
      .catch(() => {
        if (active) setError('Precompilazione non disponibile: puoi completare i campi manualmente.')
      })
      .finally(() => {
        if (active) setLoadingPrefill(false)
      })
    return () => { active = false }
  }, [open, fascicolo.id])

  useEffect(() => {
    if (!open) return undefined
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  if (!open) return null

  const updateField = (field: keyof ContributoUnificatoFormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setCopyState('idle')
  }
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setCopyState('idle')
    try {
      const response = await fetch('/strumenti-legali/api/contributo-unificato', {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken(),
        },
        credentials: 'same-origin',
        body: JSON.stringify(form),
      })
      const payload = await response.json()
      if (!payload?.ok) throw new Error(String(payload?.errore || 'Calcolo non riuscito.'))
      const nextResult = payload.result as ContributoUnificatoResult
      setResult(nextResult)
      const memory = buildContributoUnificatoMemory({ fascicolo, clientName, result: nextResult })
      saveContributionMemory(memory)
      onMemory(memory, 'Calcolo contributo unificato salvato in memoria per PagoPA.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calcolo non riuscito.')
    } finally {
      setSubmitting(false)
    }
  }
  const copyCurrentResult = async (openPagoPa = false) => {
    if (!result) return
    const memory = buildContributoUnificatoMemory({ fascicolo, clientName, result })
    try {
      await copyTextForUser(memory.copyText)
      saveContributionMemory(memory)
      onMemory(memory, 'Calcolo copiato e pronto per PagoPA.')
      setCopyState('copied')
      if (openPagoPa) {
        onClose()
        onOpenPagoPa()
      }
    } catch {
      saveContributionMemory(memory)
      onMemory(memory, 'Calcolo salvato in memoria per PagoPA, ma la copia negli appunti è stata bloccata dal browser.')
      setCopyState('error')
      if (openPagoPa) {
        onClose()
        onOpenPagoPa()
      }
    }
  }
  const notes = Array.isArray(result?.notes) ? result?.notes || [] : []
  const warnings = Array.isArray(result?.warnings) ? result?.warnings || [] : []
  const rules = Array.isArray(result?.regole_applicate) ? result?.regole_applicate || [] : []
  return (
    <div className="iu-fas-contributo-modal" role="dialog" aria-modal="true" aria-label="Calcola contributo unificato">
      <div className="iu-fas-contributo-modal__box">
        <header>
          <div>
            <span><Calculator size={15}/> Calcolo contributo unificato</span>
            <strong>{fascicolo.title || fascicolo.ref}</strong>
          </div>
          <nav>
            <button type="button" onClick={onClose} aria-label="Chiudi calcolo contributo unificato">Chiudi</button>
          </nav>
        </header>
        <form onSubmit={submit} className="iu-fas-contributo-form">
          <label>
            <span>Tipologia</span>
            <select value={form.cu_categoria} onChange={(event) => updateField('cu_categoria', event.target.value)}>
              {CONTRIBUTION_CATEGORIES.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Grado</span>
            <select value={form.cu_grado} onChange={(event) => updateField('cu_grado', event.target.value)}>
              {CONTRIBUTION_DEGREES.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Tipo valore</span>
            <select value={form.cu_valore_tipo} onChange={(event) => updateField('cu_valore_tipo', event.target.value)}>
              {CONTRIBUTION_VALUE_MODES.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
            </select>
          </label>
          <label>
            <span>Valore causa</span>
            <input type="number" min="0" step="0.01" value={form.cu_valore} onChange={(event) => updateField('cu_valore', event.target.value)} placeholder="0,00"/>
          </label>
          <label>
            <span>Anticipazione forfettaria</span>
            <select value={form.cu_anticipazione_forfettaria} onChange={(event) => updateField('cu_anticipazione_forfettaria', event.target.value)}>
              <option value="1">Sì</option>
              <option value="0">No</option>
            </select>
          </label>
          <label>
            <span>Parti ricorrenti</span>
            <input type="number" min="1" step="1" value={form.cu_numero_parti_ricorrenti} onChange={(event) => updateField('cu_numero_parti_ricorrenti', event.target.value)}/>
          </label>
          <label>
            <span>Sezione impresa</span>
            <select value={form.cu_sezione_specializzata_impresa} onChange={(event) => updateField('cu_sezione_specializzata_impresa', event.target.value)}>
              <option value="0">No</option>
              <option value="1">Sì</option>
            </select>
          </label>
          <label>
            <span>Dati obbligatori mancanti</span>
            <select value={form.cu_dati_obbligatori_mancanti} onChange={(event) => updateField('cu_dati_obbligatori_mancanti', event.target.value)}>
              <option value="0">No</option>
              <option value="1">Sì</option>
            </select>
          </label>
          <footer>
            {loadingPrefill ? <span>Precompilazione dal fascicolo in corso...</span> : <span>Il calcolo usa il servizio interno già presente negli strumenti forensi.</span>}
            <button type="submit" disabled={submitting}>{submitting ? 'Calcolo...' : 'Calcola contributo'}</button>
          </footer>
        </form>
        {error ? <p className="iu-fas-contributo-alert is-danger"><AlertTriangle size={15}/> {error}</p> : null}
        {result ? (
          <section className="iu-fas-contributo-result" aria-label="Risultato contributo unificato">
            <div className="iu-fas-contributo-result__metrics">
              <span><small>Contributo base</small><strong>{formatEuroIt(result.base)}</strong></span>
              <span><small>Anticipazione</small><strong>{formatEuroIt(result.anticipazione_forfettaria)}</strong></span>
              <span className="is-total"><small>Totale PagoPA</small><strong>{formatEuroIt(result.totale)}</strong></span>
            </div>
            {rules.length ? (
              <div className="iu-fas-contributo-result__rules">
                {rules.map((rule, index) => <span key={`${String(rule.code || rule.label || 'regola')}-${index}`}>{String(rule.label || rule.code || 'Regola applicata')}</span>)}
              </div>
            ) : null}
            {[...notes, ...warnings].length ? (
              <ul>
                {notes.map((note, index) => <li key={`note-${index}`}>{note}</li>)}
                {warnings.map((warning, index) => <li className="is-warning" key={`warning-${index}`}>{warning}</li>)}
              </ul>
            ) : null}
            <div className="iu-fas-contributo-result__actions">
              <button type="button" onClick={() => copyCurrentResult(false)}><Copy size={15}/> Copia calcolo</button>
              <button type="button" className="is-primary" onClick={() => copyCurrentResult(true)}><Euro size={15}/> Copia e apri PagoPA</button>
              {copyState === 'copied' ? <span>Calcolo copiato negli appunti e salvato in memoria.</span> : null}
              {copyState === 'error' ? <span>Memoria salvata; gli appunti sono stati bloccati dal browser.</span> : null}
            </div>
          </section>
        ) : (
          <section className="iu-fas-contributo-empty">
            <strong>Calcolo non ancora eseguito</strong>
            <p>Inserisci valore e categoria, poi salva il risultato in memoria per usarlo durante la compilazione PagoPA.</p>
          </section>
        )}
      </div>
    </div>
  )
}
