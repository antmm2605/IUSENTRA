import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, FileSearch } from 'lucide-react'
import { OperationalModal } from '../OperationalModal'
import { SourceDocumentModal, type SourceDocument } from '../SourceDocumentModal'
import { csrfHeader } from '../../api/csrf'
import './DiscordanzeAccesso.css'

type Fonte = { id: string; href: string; label: string; valore: string; citazione: string }
type Discordanza = { chiave: string; codice: string; revisione: string; giaLetta: boolean; titolo: string; cliente: string; fascicolo: string; fascicoloId: string; rg: string; numeroFascicolo: string; valoreAnagrafica: string; valoriAtto: string[]; fonti: Fonte[]; nota: string }
type Riepilogo = { ok: boolean; nonLette: number; revisione: string; voci: Discordanza[]; lettureInCorso: number; totale: number; pagina: number; altre: boolean }

export default function DiscordanzeAccesso({ sessionKey }: { sessionKey: string }) {
  const [payload, setPayload] = useState<Riepilogo | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [saving, setSaving] = useState(false)
  const seen = useRef('')
  const refresh = useRef<() => void>(() => {})
  const storageKey = `iusentra.discordanze.${sessionKey}`

  useEffect(() => {
    seen.current = ""
    setPayload(null)
    setOpen(false)
    setSource(null)
    setError("")
    let active = true
    const controller = new AbortController()
    const load = async () => {
      try {
        const response = await fetch('/api/v1/ui/controllo-studio/discordanze', { credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal })
        if (response.status === 403) return
        if (!response.ok) throw new Error('Il riepilogo delle verifiche non è disponibile. Riprova tra poco.')
        const result = await response.json() as Riepilogo
        if (!active) return
        setPayload(previous => previous?.revisione === result.revisione && previous.pagina > 1 ? { ...previous, lettureInCorso: result.lettureInCorso } : result)
        setError('')
        let previous = seen.current
        try { previous ||= sessionStorage.getItem(storageKey) || '' } catch { /* Il digest resta in memoria. */ }
        if (result.nonLette > 0 && !result.lettureInCorso && previous !== result.revisione) {
          seen.current = result.revisione
          setOpen(true)
        }
      } catch (cause) {
        if (active && !(cause instanceof DOMException && cause.name === 'AbortError')) setError('Il riepilogo delle verifiche non è disponibile. Riprova tra poco.')
      }
    }
    refresh.current = () => { void load() }
    const startup = window.setTimeout(() => { void load() }, 1200)
    const timer = window.setInterval(() => { void load() }, 60000)
    return () => { active = false; controller.abort(); window.clearTimeout(startup); window.clearInterval(timer) }
  }, [storageKey])

  const close = () => {
    if (payload) {
      seen.current = payload.revisione
      try { sessionStorage.setItem(storageKey, payload.revisione) } catch { /* Nessun dato personale viene salvato nel browser. */ }
    }
    setOpen(false)
  }
  const acknowledge = async () => {
    if (!payload?.voci.some(voce => !voce.giaLetta) || saving) return
    setSaving(true)
    try {
      const response = await fetch('/api/v1/ui/controllo-studio/discordanze/lette', {
        method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', ...csrfHeader() },
        body: JSON.stringify({ voci: payload.voci.filter(voce => !voce.giaLetta).map(({ fascicoloId, codice, chiave, revisione }) => ({ fascicoloId, codice, chiave, revisione })) }),
      })
      const result = await response.json()
      if (!response.ok || !result.ok) throw new Error(result.message || 'Presa visione non salvata. Riprova.')
      setPayload({ ...payload, nonLette: Math.max(0, payload.nonLette - payload.voci.filter(v => !v.giaLetta).length), voci: payload.voci.map(v => ({ ...v, giaLetta: true })) }); close(); refresh.current()
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Presa visione non salvata. Riprova.') }
    finally { setSaving(false) }
  }
  if (!payload && !error) return null
  const count = payload?.totale || 0
  const daLeggere = payload?.voci.some(voce => !voce.giaLetta) ?? false
  const more = async () => {
    if (!payload || loadingMore) return
    setLoadingMore(true)
    try {
      const response = await fetch(`/api/v1/ui/controllo-studio/discordanze?pagina=${payload.pagina + 1}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      if (!response.ok) throw new Error()
      const result = await response.json() as Riepilogo
      if (result.revisione !== payload.revisione) { setPayload(result); refresh.current(); return }
      setPayload({ ...result, voci: [...payload.voci, ...result.voci] })
    } catch { setError('Le altre verifiche non sono disponibili. Riprova tra poco.') }
    finally { setLoadingMore(false) }
  }
  return <div className="iu-discordanze-accesso-root">
    <button type="button" className={`iu-icon iu-discordanze-accesso__trigger${count ? ' has-issues' : ''}`} title="Verifiche documentali" aria-label={`Verifiche documentali${count ? `: ${count} ${count === 1 ? 'discordanza' : 'discordanze'}` : ''}`} onClick={() => { setOpen(true); refresh.current() }}>
      <FileSearch size={18} aria-hidden="true" />{count ? <span className="iu-discordanze-accesso__count">{count}</span> : null}
    </button>
    <OperationalModal boxClassName="iu-discordanze-accesso-box" open={open} onClose={close} ariaLabel="Discordanze da verificare" eyebrow={<><AlertTriangle size={16} /> Verifiche documentali</>} title={count ? `${count} ${count === 1 ? 'discordanza' : 'discordanze'}` : 'Verifiche documentali'} subtitle="Confronto tra gli atti letti e i dati dello studio. Gli originali e l’anagrafica restano consultabili." actions={<button type="button" className="iu-button" aria-label={!saving && !daLeggere ? "Presa visione salvata" : undefined} disabled={saving || !daLeggere} onClick={() => void acknowledge()}>{saving ? 'Salvataggio…' : daLeggere ? 'Ho letto' : 'Già letta'}</button>}>
      <div className="iu-discordanze-accesso">
        {error ? <p role="alert">{error} <button type="button" onClick={() => refresh.current()}>Riprova</button></p> : null}
        {payload?.lettureInCorso ? <p role="status">Letture in corso su {payload.lettureInCorso} {payload.lettureInCorso === 1 ? 'fascicolo' : 'fascicoli'}. Le nuove discordanze appariranno al termine della verifica.</p> : null}
        {!count && !error ? <p>Nessuna discordanza pubblicata dai verificatori completati.</p> : null}
        {payload?.voci.map(voce => <article key={`${voce.fascicoloId}:${voce.chiave}`}>
          <h3>{voce.titolo}</h3>
          <p role="status">{voce.giaLetta ? 'Già letta · presa visione memorizzata per il tuo utente.' : 'Nuova verifica · presa visione da confermare.'}</p>
          <p><strong>{voce.cliente}</strong> · RG {voce.rg} {voce.numeroFascicolo ? `· Fascicolo ${voce.numeroFascicolo}` : ''}</p>
          <p className="iu-discordanze-accesso__practice">{voce.fascicolo}</p>
          <dl><div><dt>In anagrafica</dt><dd>{voce.valoreAnagrafica}</dd></div><div><dt>Negli atti</dt><dd>{voce.valoriAtto.join(' · ')}</dd></div></dl>
          <p>{voce.nota}</p>
          <details><summary>Documenti da confrontare ({voce.fonti.length})</summary><ul>{voce.fonti.map(fonte => <li key={fonte.id}><button type="button" className="iu-button" onClick={() => setSource({ href: fonte.href, label: fonte.label, context: `${voce.cliente} · RG ${voce.rg}` })}><FileSearch size={15} aria-hidden="true" /> {fonte.label}</button><blockquote>{fonte.citazione}</blockquote></li>)}</ul></details>
          <a className="iu-button" href={`/fascicoli/${encodeURIComponent(voce.fascicoloId)}#lettura-fascicolo`}>Apri questa verifica nel fascicolo</a>
        </article>)}
        {payload?.altre ? <button type="button" className="iu-button" disabled={loadingMore} onClick={() => { void more() }}>{loadingMore ? 'Caricamento…' : `Mostra altre verifiche (${payload.voci.length} di ${payload.totale})`}</button> : null}
        {count ? <p className="iu-discordanze-accesso__note">«Ho letto» memorizza la presa visione delle verifiche mostrate per il tuo utente, anche al prossimo accesso. La discordanza resta segnalata finché il confronto delle fonti non la supera.</p> : null}
      </div>
    </OperationalModal>
    <SourceDocumentModal source={source} onClose={() => setSource(null)} />
  </div>
}
