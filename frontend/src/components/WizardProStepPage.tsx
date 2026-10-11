import { useBusyActivity } from '../ui/useBusyActivity'
import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowRight, CalendarDays, Check, FolderOpen, Gavel, MapPin, Printer, Video } from 'lucide-react'
import { FloatingLex } from './FloatingLex'
import { PassoDocumenti, PassoEsito, PassoPartenza, PassoQuadro, PassoStrategia, type Azioni } from './PreparazioneUdienzaPassi'
import { inviaPreparazione } from './preparazioneUdienzaApi'
import type { SchedaUdienza } from './preparazioneUdienzaTipi'
import './WizardProPage.css'
import { useOperationalRefresh } from '../hooks/useOperationalRefresh'
import { loadPreparationCommand, preparationCommand, type PreparationCommand } from '../preparazioneUdienzaCommand'
import { acknowledgedPreparationValues, applyPreparationDraft, mergePreparationRefresh, preparationSnapshot, preparationStepFields, preservePreparationDraft, restorePreparationDraft } from '../preparazioneUdienzaDraft'

function idDallIndirizzo(): { id: string; passo: number } {
  const trovato = window.location.pathname.match(/\/wizard-pro\/([^/]+)\/(?:step\/([1-5])|completo)/)
  return { id: decodeURIComponent(trovato?.[1] || ''), passo: trovato?.[2] ? Number(trovato[2]) : 5 }
}

/** Preparazione di una udienza: cinque passi in una sola pagina, con salvataggio immediato. */
export function WizardProStepPage({ sessionId, initialStep = 1, embedded = false }: { sessionId?: string; initialStep?: number; embedded?: boolean } = {}) {
  const [{ id, passo: passoIniziale }] = useState(() => sessionId ? { id: sessionId, passo: initialStep } : idDallIndirizzo())
  const [s, setS] = useState<SchedaUdienza | null>(null)
  const [passo, setPasso] = useState(passoIniziale)
  const [avviso, setAvviso] = useState<{ testo: string; ok: boolean } | null>(null)
  const [occupato, setOccupato] = useState(false)
  useBusyActivity(occupato, 'Salvataggio della preparazione udienza…')
  const [pending, setPending] = useState<PreparationCommand | null>(null)
  const [storageError, setStorageError] = useState('')
  const [conflicts, setConflicts] = useState<string[]>([])
  const [liveError, setLiveError] = useState('')
  const [draftEpoch, setDraftEpoch] = useState(0)
  const source = useRef<SchedaUdienza | null>(null)
  const view = useRef<SchedaUdienza | null>(null)
  const busy = useRef(false)
  const refreshLater = useRef(false)
  const outcomeDirty = useRef(false)
  const [outcomeDraft, setOutcomeDraft] = useState(false)
  const show = useCallback((data: SchedaUdienza) => { view.current = data; setS(data) }, [])
  const readPending = useCallback((data: SchedaUdienza, restore = false) => {
    if (!data.writeProtocol?.scope) return
    try {
      const command = loadPreparationCommand(sessionStorage, data.writeProtocol.scope, id)
      setPending(command); setStorageError('')
      if (restore && command && view.current && !outcomeDirty.current && JSON.stringify(preparationSnapshot(view.current)) === JSON.stringify(preparationSnapshot(data))) {
        const action = command.href.split('/').pop()!
        show(applyPreparationDraft(view.current, action, command.body))
        if (action === 'esito') { outcomeDirty.current = true; setOutcomeDraft(true) }
      }
    }
    catch { setStorageError('Comando conservato non recuperabile: bozza disponibile, salvataggio sospeso.') }
  }, [id, show])
  const refresh = useCallback(async () => {
    if (busy.current) { refreshLater.current = true; return true }
    try {
      const response = await fetch(`/api/v1/ui/preparazione-udienza/${encodeURIComponent(id)}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      const incoming = await response.json() as SchedaUdienza
      if (!response.ok || !incoming.ok) throw new Error(incoming.message || 'Preparazione non disponibile.')
      if (busy.current) { refreshLater.current = true; return true }
      if (source.current && incoming.writeProtocol?.scope !== source.current.writeProtocol?.scope) throw new Error('Contesto dello studio cambiato: riapri la preparazione.')
      if (source.current?.revision !== undefined && incoming.revision !== undefined && incoming.revision < source.current.revision) return true
      const initial = !source.current
      if (source.current && view.current) {
        const merged = mergePreparationRefresh(view.current, preparationSnapshot(source.current), incoming)
        if (outcomeDirty.current && JSON.stringify(incoming.esito) !== JSON.stringify(source.current.esito)) merged.conflicts.push('esito')
        const currentValues = preparationSnapshot(view.current), incomingValues = preparationSnapshot(incoming)
        setConflicts(previous => Array.from(new Set([...previous.filter(key => key === 'esito'
          ? outcomeDirty.current : currentValues[key] !== incomingValues[key]), ...merged.conflicts])))
        if (outcomeDirty.current) { merged.values.completata = view.current.completata; merged.values.esito = view.current.esito }
        show(merged.values)
      } else {
        try {
          const restored = incoming.writeProtocol?.scope ? restorePreparationDraft(sessionStorage, incoming.writeProtocol.scope, incoming) : null
          show(restored?.values || incoming); setConflicts(restored?.conflicts || [])
          outcomeDirty.current = Boolean(restored?.outcomeDirty); setOutcomeDraft(outcomeDirty.current)
        } catch { show(incoming); setStorageError('Bozza conservata non recuperabile: contenuto preservato, salvataggio sospeso.'); return false }
      }
      source.current = incoming; readPending(incoming, initial); setLiveError(''); return true
    } catch (error) { setLiveError(error instanceof Error ? error.message : 'Aggiornamento non riuscito: bozza conservata.'); return false }
  }, [id, readPending, show])

  useEffect(() => {
    void refresh()
  }, [refresh])
  useOperationalRefresh(['agenda', 'fascicoli', 'scadenze', 'clienti'], refresh)

  useEffect(() => {
    const baseline = source.current
    if (!s || !baseline?.writeProtocol?.scope || storageError) return
    try { preservePreparationDraft(sessionStorage, baseline.writeProtocol.scope, baseline, s, outcomeDraft) }
    catch { setStorageError('La bozza resta visibile, ma non è conservabile nella finestra. Salvataggio sospeso.') }
  }, [s, outcomeDraft, storageError])
  useEffect(() => {
    const leaving = (event: BeforeUnloadEvent) => {
      if (outcomeDirty.current || pending || (view.current && source.current && JSON.stringify(preparationSnapshot(view.current)) !== JSON.stringify(preparationSnapshot(source.current)))) {
        event.preventDefault(); event.returnValue = ''
      }
    }
    window.addEventListener('beforeunload', leaving)
    return () => window.removeEventListener('beforeunload', leaving)
  }, [pending])

  const vaiA = useCallback((n: number) => {
    setPasso(n)
    if (!embedded) {
      window.history.replaceState(window.history.state, '', `/wizard-pro/${encodeURIComponent(id)}/step/${n}`)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }, [id, embedded])

  const execute = useCallback(async (nome: string, corpo: Record<string, unknown>, recover = false) => {
    const saved = source.current
    if (busy.current) return { ok: false, code: 'in_progress', message: 'Salvataggio già in corso.' }
    if (!saved || (!recover && (conflicts.length || pending || storageError || liveError))) return { ok: false, message: 'Salvataggio sospeso: risolvi il conflitto o recupera il comando pendente.' }
    const protocol = saved.writeProtocol
    busy.current = true; setOccupato(true)
    const action = recover && pending ? pending.href.split('/').pop()! : nome
    const body = recover && pending ? pending.body : corpo
    if (view.current && !recover) show(applyPreparationDraft(view.current, action, body))
    const baseline = acknowledgedPreparationValues(preparationSnapshot(saved), action, body)
    const url = `/api/v1/ui/preparazione-udienza/${encodeURIComponent(id)}/${nome}`
    const r = protocol?.persistentCommands && protocol.scope
      ? await preparationCommand(sessionStorage, inviaPreparazione, { scope: protocol.scope, target: id, sessionId: id }, saved.revision!, url, corpo, recover)
      : await inviaPreparazione(url, corpo)
    if (r.ok && r.dati && view.current) {
      const incoming = { ...(r.dati as SchedaUdienza), puoModificare: saved.puoModificare }
      if (saved.revision !== undefined && incoming.revision !== undefined && incoming.revision < saved.revision) refreshLater.current = true
      else {
        const merged = mergePreparationRefresh(view.current, baseline, incoming)
        source.current = incoming; setConflicts(merged.conflicts); show(merged.values)
      }
      if (action === 'esito') { outcomeDirty.current = false; setOutcomeDraft(false) }
    }
    readPending(saved); busy.current = false; setOccupato(false)
    setAvviso({ testo: String(r.message || (r.ok ? 'Salvataggio confermato.' : 'Salvataggio non confermato: bozza conservata.')), ok: Boolean(r.ok) })
    if (r.terminalRejected || refreshLater.current) { refreshLater.current = false; await refresh() }
    return r
  }, [id, conflicts, pending, storageError, liveError, readPending, refresh, show])
  const azione: Azioni['azione'] = (nome, corpo) => execute(nome, corpo)

  const salvaCampi: Azioni['salvaCampi'] = useCallback(async (n, campi, conferma = false) => {
    const r = await azione('passo', { passo: n, campi, conferma })
    if (r.ok && conferma && n < 5) vaiA(n + 1)
    return r.ok ? 'saved' : r.code === 'in_progress' ? 'deferred' : 'failed'
  }, [execute, vaiA])

  const modificaCampi = (campi: Record<string, string | boolean>) => {
    if (view.current) show({ ...view.current, campi: { ...view.current.campi, ...campi } })
  }

  const salvaBozza = async () => {
    const current = view.current, baseline = source.current
    if (!current || !baseline) return
    if (passo === 2) {
      for (const row of current.documenti) {
        if (baseline.documenti.find(item => item.indice === row.indice)?.stato !== row.stato) {
          const result = await execute('documento', { indice: row.indice, stato: row.stato })
          if (!result.ok) return
        }
      }
      const extra = String(view.current?.campi.documento_extra || '')
      if (extra.trim()) {
        const result = await execute('documento-extra', { etichetta: extra })
        if (!result.ok) return
        if (view.current?.campi.documento_extra === extra) modificaCampi({ documento_extra: '' })
      }
    }
    const fields = Object.fromEntries(Object.entries(current.campi).filter(([key, value]) =>
      preparationStepFields[passo]?.includes(key) && source.current?.campi[key] !== value))
    if (Object.keys(fields).length) await salvaCampi(passo, fields)
  }

  if (!s) return <main className="iu-content iu-pu"><p className={`iu-pu-stato-pagina ${liveError ? 'is-errore' : ''}`}>{liveError || 'Caricamento della preparazione…'}</p>{liveError ? <button onClick={() => void refresh()}>Riprova</button> : null}</main>
  if (!s.ok || !Array.isArray(s.passi) || !s.passi.length) return <main className="iu-content iu-pu"><p className="iu-pu-stato-pagina is-errore" role="alert">{s.message || 'Preparazione non disponibile.'}</p></main>
  const attuale = s.passi.find((p) => p.n === passo) || s.passi[0]
  const blocked = occupato || Boolean(pending || storageError || liveError || conflicts.length)
  const dirty = source.current && JSON.stringify(preparationSnapshot(s)) !== JSON.stringify(preparationSnapshot(source.current))
  const a: Azioni = { salvaCampi, azione, occupato: blocked, modificaCampi, puoModificare: Boolean(s.puoModificare), esitoBozza: outcomeDraft,
    modificaEsito: esito => { if (view.current) show({ ...view.current, esito }) },
    bozzaEsito: () => { outcomeDirty.current = true; setOutcomeDraft(true) } }
  const Corpo = [PassoQuadro, PassoDocumenti, PassoStrategia, PassoPartenza, PassoEsito][passo - 1]

  return (
    <main className="iu-content iu-pu iu-pu-sessione">
      <header className="iu-pu-scheda">
        <div className="iu-pu-scheda__titolo">
          <span className="iu-pu-kicker"><Gavel size={15}/> Preparazione udienza · {s.stato}</span>
          <h1>{s.titolo}</h1>
          <p className="iu-pu-quando"><CalendarDays size={16}/> {s.udienza.quando}</p>
          <p className="iu-pu-dove">
            {s.udienza.luogo ? <span><MapPin size={13}/> {s.udienza.luogo}</span> : null}
            {s.udienza.ufficio && s.udienza.ufficio !== s.udienza.luogo ? <span>{s.udienza.ufficio}</span> : null}
            {s.udienza.rg ? <span>R.G. {s.udienza.rg}</span> : null}
            {s.udienza.giudice ? <span>{s.udienza.giudice}</span> : null}
            {s.udienza.collegamento ? <a href={s.udienza.collegamento} target="_blank" rel="noreferrer"><Video size={13}/> Collegamento da remoto</a> : null}
          </p>
        </div>
        <div className="iu-pu-scheda__azioni">
          {s.causa.fascicolo?.href ? <a className="iu-pu-btn" href={s.causa.fascicolo.href}><FolderOpen size={14}/> Fascicolo</a> : null}
          <a className="iu-pu-btn" href={s.udienza.agendaHref}><CalendarDays size={14}/> Agenda</a>
          <button type="button" className="iu-pu-btn" onClick={() => window.print()}><Printer size={14}/> Stampa la scheda</button>
        </div>
      </header>

      {avviso && !conflicts.length ? <p className={`iu-pu-stato-pagina ${avviso.ok ? 'is-ok' : 'is-errore'}`} role="status">{avviso.testo}</p> : null}
      {storageError || liveError ? <p className="iu-pu-errore" role="alert">{storageError || liveError} <button onClick={() => void refresh()}>Riprova lettura</button></p> : null}
      {pending ? <p className="iu-pu-nota" role="status">Un salvataggio attende il riscontro; la bozza è conservata. <button disabled={occupato} onClick={() => void execute('', {}, true)}>Recupera salvataggio</button></p> : null}
      {conflicts.length ? <div className="iu-pu-errore iu-pu-recupero" role="alert"><span>Un altro operatore ha modificato gli stessi campi. La tua bozza è conservata: scegli quale versione usare.</span><div><button disabled={occupato || Boolean(pending)} onClick={() => { setConflicts([]); setAvviso(null) }}>Mantieni la mia bozza</button><button disabled={occupato || Boolean(pending)} onClick={() => { if (source.current) { show(source.current); setConflicts([]); setAvviso(null); outcomeDirty.current = false; setOutcomeDraft(false); setDraftEpoch(n => n + 1) } }}>Usa dati aggiornati</button></div></div> : null}
      {dirty && !conflicts.length && !pending ? <p className="iu-pu-nota iu-pu-recupero" role="status"><span>Bozza non ancora confermata.</span><button disabled={blocked} onClick={() => void salvaBozza()}>Salva bozza</button></p> : null}

      <div className="iu-pu-corpo">
        <nav className="iu-pu-passi" aria-label="Passi della preparazione">
          <ol>
            {s.passi.map((p) => (
              <li key={p.n}>
                <button type="button" disabled={p.n !== passo && Boolean(occupato || dirty || outcomeDirty.current || pending)} className={`${p.n === passo ? 'is-attivo' : ''} ${p.fatto ? 'is-fatto' : ''}`} aria-current={p.n === passo ? 'step' : undefined} onClick={() => vaiA(p.n)}>
                  <i>{p.fatto ? <Check size={13}/> : p.n}</i><span><strong>{p.titolo}</strong><small>{p.descrizione}</small></span>
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <section className="iu-pu-contenuto" aria-label={attuale.titolo}>
          <header><h2>{attuale.n}. {attuale.titolo}</h2><p>{attuale.descrizione}</p></header>
          <Corpo key={`${passo}-${s.id}-${draftEpoch}`} s={s} a={a}/>
          {passo < 5 && s.puoModificare ? (
            <footer className="iu-pu-piede">
              <span>{attuale.fatto ? 'Passo completato: puoi ancora modificarlo.' : 'Le modifiche si salvano da sole.'}</span>
              <button type="button" className="iu-pu-btn is-primario" disabled={blocked || Boolean(dirty)} onClick={() => void salvaCampi(passo, {}, true)}>
                {attuale.fatto ? 'Avanti' : 'Fatto, passo successivo'} <ArrowRight size={14}/>
              </button>
            </footer>
          ) : null}
        </section>
      </div>
      {!embedded ? <FloatingLex context="preparazione-udienza" title="Lex udienza" body="Legge fascicolo, termini e documenti dell'udienza e ti aiuta a preparare argomenti ed eccezioni."
        primaryHref="#lex" primaryLabel="Apri Lex" secondaryHref={s.causa.fascicolo?.href || '/fascicoli'} secondaryLabel="Fascicolo"/> : null}
    </main>
  )
}

export default WizardProStepPage
