import { useEffect, useRef, useState } from 'react'
import { ExternalLink, X } from 'lucide-react'
import { apiPostJson, ensureJson } from '../api/client'
import { Badge } from '../ui/Badge'
import { Button, ButtonLink } from '../ui/Button'
import { type Annotazione, type Fonte, type Norma, type Scheda, type StatoAttuale, type Voce, SEZIONI, STATI, chiaveFonte, dataOraIt, divisioneAncora } from './conoscenzaDati'

const base = '/api/v1/ui/conoscenza'
type Risposta = { scheda: Scheda; stato_attuale: StatoAttuale; annotazioni: Annotazione[]; annotazioni_disponibili: boolean; puo_annotare: boolean }
const ESITI = ['', 'favorevole', 'contrario', 'non pertinente', 'da approfondire']

function PassaggioNorma({ fonte }: { fonte: Fonte }) {
  const [norma, setNorma] = useState<Norma | null>(null)
  const [errore, setErrore] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    ensureJson<{ norma: Norma }>(`${base}/norma/${encodeURIComponent(fonte.chiave)}?${new URLSearchParams({ ancora: fonte.ancora || '' })}`, { signal: controller.signal })
      .then(d => { if (!controller.signal.aborted) setNorma(d.norma) })
      .catch(() => { if (!controller.signal.aborted) setErrore('Testo della norma non disponibile nell’archivio.') })
    return () => controller.abort()
  }, [fonte.chiave, fonte.ancora])
  if (errore) return <p role="alert">{errore}</p>
  if (!norma) return <p>Caricamento del testo vigente…</p>
  const [prima, passaggio, dopo] = divisioneAncora(norma)
  return <div className="iu-cn-norma">
    <p><strong>{norma.citazione}</strong>{norma.rubrica ? ` — ${norma.rubrica}` : ''} · testo vigente{norma.aggiornamento ? `, aggiornamento dell’archivio ${norma.aggiornamento}` : ''}{fonte.versione ? ` · versione ${fonte.versione}` : ''}</p>
    <blockquote>{prima}{passaggio ? <mark>{passaggio}</mark> : null}{dopo}</blockquote>
    {norma.url ? <a href={norma.url} target="_blank" rel="noreferrer">Apri su Normattiva <ExternalLink size={14} aria-hidden="true" /></a> : null}
  </div>
}

function FonteVoce({ fonte, aperta, onApri }: { fonte: Fonte; aperta: boolean; onApri: () => void }) {
  const etichetta = fonte.tipo === 'norma' ? `${fonte.citazione}${fonte.comma ? `, comma ${fonte.comma}` : ''}${fonte.stato === 'abrogata' ? ' (abrogato)' : ''}` : fonte.citazione
  return <span className="iu-cn-fonte">
    {fonte.tipo === 'norma'
      ? <Button tone="neutral" aria-expanded={aperta} onClick={onApri}>{etichetta}</Button>
      : <a href={fonte.url} target="_blank" rel="noreferrer">{etichetta}{fonte.tipo_testo ? ` (${fonte.tipo_testo})` : ''} <ExternalLink size={14} aria-hidden="true" /></a>}
  </span>
}

function VoceScheda({ voce }: { voce: Voce }) {
  const [aperta, setAperta] = useState('')
  const fonteAperta = voce.fonti.find(f => chiaveFonte(f) === aperta)
  return <li>
    {voce.etichetta ? <Badge tone="info">{voce.etichetta}</Badge> : null}
    <p>{voce.orientamento ? <q>{voce.testo}</q> : voce.testo}</p>
    <div className="iu-cn-fonti">{voce.fonti.map(f => <FonteVoce key={chiaveFonte(f)} fonte={f} aperta={aperta === chiaveFonte(f)} onApri={() => setAperta(aperta === chiaveFonte(f) ? '' : chiaveFonte(f))} />)}</div>
    <small>{voce.verifica}{voce.orientamento ? ` · ${voce.orientamento}` : ''} · {voce.provenienza}</small>
    {voce.calcolo ? <ButtonLink tone="neutral" href={voce.calcolo.calcolatore}>Calcola la scadenza</ButtonLink> : null}
    {fonteAperta ? <PassaggioNorma fonte={fonteAperta} /> : null}
  </li>
}

export function ConoscenzaScheda({ schedaId, puoAnnotare, onClose }: { schedaId: string; puoAnnotare: boolean; onClose: () => void }) {
  const [dati, setDati] = useState<Risposta | null>(null)
  const [errore, setErrore] = useState('')
  const [carica, setCarica] = useState(0)
  const [nota, setNota] = useState({ sezione: 'generale', esito: '', testo: '' })
  const [messaggio, setMessaggio] = useState('')
  const [salva, setSalva] = useState(false)
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const controller = new AbortController()
    setErrore('')
    ensureJson<Risposta>(`${base}/schede/${encodeURIComponent(schedaId)}`, { signal: controller.signal })
      .then(d => { if (!controller.signal.aborted) setDati(d) })
      .catch(e => { if (!controller.signal.aborted) setErrore(e.status === 404 ? 'Scheda non trovata.' : 'Non riesco a caricare la scheda. Riprova.') })
    return () => controller.abort()
  }, [schedaId, carica])
  useEffect(() => { ref.current?.scrollIntoView({ block: 'start' }) }, [schedaId])
  async function annota(e: React.FormEvent) {
    e.preventDefault()
    if (salva) return
    setSalva(true); setMessaggio('')
    try {
      const r = await apiPostJson<{ ok: boolean; message: string }>(`${base}/schede/${encodeURIComponent(schedaId)}/annotazioni`, nota, { ok: false, message: 'Annotazione non registrata.' })
      setMessaggio(r.message)
      if (r.ok) { setNota({ sezione: 'generale', esito: '', testo: '' }); setCarica(n => n + 1) }
    } catch { setMessaggio('Annotazione non registrata. Verifica il collegamento e riprova.') } finally { setSalva(false) }
  }
  const s = dati?.scheda
  const st = dati ? (STATI[dati.stato_attuale.stato] || STATI.lacune) : STATI.lacune
  return <section ref={ref} tabIndex={-1} className="iu-od-source-card iu-cn-dettaglio" aria-label="Scheda di istituto">
    <div className="iu-cn-dettaglio-head">
      <div>{s ? <><p>{s.materia} · {s.id} · revisione {s.revisione} · ultimo controllo {dataOraIt(s.ultimo_controllo)}</p><h2>{s.titolo}</h2></> : <h2>{errore || 'Caricamento della scheda…'}</h2>}</div>
      <Button tone="neutral" onClick={onClose} aria-label="Chiudi la scheda"><X size={16} aria-hidden="true" /></Button>
    </div>
    {s && dati ? <>
      <div className="iu-cn-badges"><Badge tone={st.tono}>{st.etichetta}</Badge><Badge tone="neutral">Vista generata dalle fonti, non fonte primaria</Badge></div>
      {dati.stato_attuale.motivi.length ? <ul className="iu-cn-motivi" role="alert">{dati.stato_attuale.motivi.map(m => <li key={m}>{m}</li>)}</ul> : null}
      <p className="iu-cn-sintesi">{s.sintesi}</p>
      {SEZIONI.map(([k, titolo]) => {
        const sez = s.sezioni[k]
        if (!sez) return null
        return <section key={k} className="iu-cn-sezione" aria-label={titolo}>
          <h3>{titolo}</h3>
          {sez.stato === 'mancante' ? <p className="iu-cn-mancante">Sezione mancante: {sez.motivo}.</p> : <ul>{sez.voci.map(v => <VoceScheda key={v.testo} voce={v} />)}</ul>}
        </section>
      })}
      <section className="iu-cn-sezione" aria-label="Strumenti del software"><h3>Strumenti del software</h3>
        <ul className="iu-cn-strumenti">{s.strumenti.map(x => <li key={`${x.tipo}:${x.id}`}>{x.collegamento ? <ButtonLink tone="neutral" href={x.collegamento}>{x.titolo}</ButtonLink> : <span>{x.titolo}</span>}</li>)}</ul>
      </section>
      <details className="iu-cn-sezione"><summary>Limiti e lacune dichiarate ({s.lacune.length})</summary><ul>{s.lacune.map(x => <li key={x}>{x}</li>)}</ul></details>
      <details className="iu-cn-sezione"><summary>Fonti con versione ({s.fonti.length})</summary><ul>{s.fonti.map(f => <li key={chiaveFonte(f)}>{f.citazione}{f.rubrica ? ` — ${f.rubrica}` : ''}{f.tipo === 'norma' ? (f.stato === 'abrogata' ? ` · norma abrogata (${f.nota_abrogazione || ''})` : ` · testo vigente, aggiornamento ${f.aggiornamento || 'n.d.'}`) : ` · ${f.tipo_testo || ''}`}{f.nota_commi ? ` · comma pertinente ${f.comma_pertinente}: ${f.nota_commi}` : ''} · versione {f.versione}{f.url ? <> · <a href={f.url} target="_blank" rel="noreferrer">fonte ufficiale</a></> : null}</li>)}</ul></details>
      {s.norme_abrogate?.length ? <section className="iu-cn-sezione" aria-label="Norme abrogate"><h3>Norme abrogate (storico, non norme di riferimento)</h3><ul>{s.norme_abrogate.map(a => <li key={a.citazione}>{a.citazione}: abrogato dal {a.abrogata_da}; decorrenza: {a.decorrenza}; sede vigente: {a.sede_vigente}</li>)}</ul></section> : null}
      <details className="iu-cn-sezione"><summary>Cronologia delle revisioni ({s.storia.length})</summary><ol>{s.storia.map(r => <li key={r.revisione}>Revisione {r.revisione} · {dataOraIt(r.data)} · {r.motivo}</li>)}</ol></details>
      <section className="iu-cn-sezione" aria-label="Annotazioni dello studio"><h3>Annotazioni dello studio</h3>
        {!dati.annotazioni_disponibili ? <p>Annotazioni non leggibili in questo momento.</p> : null}
        {dati.annotazioni.length ? <ul>{dati.annotazioni.map(a => <li key={a.id}>
          <p>{a.esito ? <Badge tone="info">{a.esito}</Badge> : null} {a.testo}</p>
          <small>{a.attore} · {dataOraIt(a.creato_il)} · sezione {a.sezione}{a.voce ? ` · ${a.voce}` : ''}{a.scheda_cambiata_dopo ? ` · scritta sulla revisione ${a.revisione_scheda}: la scheda è cambiata dopo` : ''}{a.voce_presente ? '' : ' · la voce non è più nella scheda'}</small>
        </li>)}</ul> : <p>Nessuna annotazione.</p>}
        {puoAnnotare ? <form className="iu-cn-nota" onSubmit={annota}>
          <label>Sezione<select value={nota.sezione} onChange={e => setNota({ ...nota, sezione: e.target.value })}><option value="generale">Scheda in generale</option>{SEZIONI.map(([k, t]) => <option key={k} value={k}>{t}</option>)}<option value="fonti">Fonti</option></select></label>
          <label>Valutazione<select value={nota.esito} onChange={e => setNota({ ...nota, esito: e.target.value })}>{ESITI.map(x => <option key={x} value={x}>{x || 'Nessuna'}</option>)}</select></label>
          <label className="iu-cn-nota-testo">Nota<textarea value={nota.testo} onChange={e => setNota({ ...nota, testo: e.target.value })} rows={3} /></label>
          <Button type="submit" disabled={salva}>Salva l’annotazione</Button>
          {messaggio ? <p role="status">{messaggio}</p> : null}
        </form> : null}
      </section>
    </> : null}
  </section>
}
