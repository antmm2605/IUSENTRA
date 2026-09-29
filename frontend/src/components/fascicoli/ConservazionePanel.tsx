import { useEffect, useRef, useState } from 'react'
import { CheckCircle2, Download, FileArchive, TriangleAlert } from 'lucide-react'
import './ConservazionePanel.css'

type Documento = { id: string; nome: string; tipo: string; data: string; formato: string; idoneo: boolean; nota: string; firmato: boolean; versato: boolean }
type Versamento = {
  id: string; creato_il: string; creato_da: string; documenti: Array<{ id: string; nome: string }>; impronta_pacchetto: string; dimensione: number
  anni_conservazione: number; stato: string; stato_etichetta: string; conservatore: string; data_versamento: string; id_rapporto: string
}
type Dati = { ok: boolean; message?: string; puoModificare?: boolean; documenti?: Documento[]; versamenti?: Versamento[]; anniPredefiniti?: number }

const dataIt = (v: string) => (v ? v.slice(0, 10).split('-').reverse().join('/') : '')
const oggiIso = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Rome' })
const peso = (byte: number) => (byte > 1048576 ? `${(byte / 1048576).toFixed(1).replace('.', ',')} MB` : `${Math.max(1, Math.round(byte / 1024))} KB`)

async function invia(url: string, corpo: Record<string, unknown>): Promise<Record<string, unknown>> {
  const risposta = await fetch(url, {
    method: 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(corpo),
  }).catch(() => null)
  if (!risposta) return { ok: false, message: 'Connessione non riuscita.' }
  return await risposta.json().catch(() => ({ ok: false, message: 'Risposta non valida.' })) as Record<string, unknown>
}

/** Pacchetto di versamento per il conservatore (CAD artt. 43-44; Linee guida AgID, Allegati 2 e 5) e registro degli esiti. */
export default function ConservazionePanel({ fascicoloId }:{ fascicoloId: string }) {
  const [dati, setDati] = useState<Dati>({ ok: true })
  const [scelti, setScelti] = useState<Set<string>>(new Set())
  const [anni, setAnni] = useState('10')
  const [riservato, setRiservato] = useState(true)
  const [messaggio, setMessaggio] = useState('')
  const [occupato, setOccupato] = useState(false)
  const [esito, setEsito] = useState<{ id: string; stato: string; conservatore: string; data: string; idRapporto: string } | null>(null)
  const base = `/fascicoli/${encodeURIComponent(fascicoloId)}/conservazione`

  const carica = async () => {
    const risposta = await fetch(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/conservazione`, { credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(() => null)
    const valori = risposta ? await risposta.json().catch(() => null) as Dati | null : null
    if (valori) {
      setDati(valori)
      if (valori.anniPredefiniti) setAnni((a) => a || String(valori.anniPredefiniti))
      const documenti = valori.documenti || []
      setScelti(new Set(documenti.filter((d) => !d.versato).map((d) => d.id)))
    }
  }
  const radice = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    // La sezione del fascicolo è chiusa per default: i dati si chiedono solo quando si apre.
    const sezione = radice.current?.closest('details')
    if (!sezione || sezione.open) { void carica(); return }
    const apri = () => { if (sezione.open) { sezione.removeEventListener('toggle', apri); void carica() } }
    sezione.addEventListener('toggle', apri)
    return () => sezione.removeEventListener('toggle', apri)
  }, [fascicoloId])

  const documenti = dati.documenti || []
  const nonIdonei = documenti.filter((d) => scelti.has(d.id) && !d.idoneo)
  const crea = async () => {
    setOccupato(true)
    const r = await invia(`${base}/pacchetto`, { ids: [...scelti], anni: Number(anni) || 10, riservato })
    setOccupato(false)
    setMessaggio(String(r.message || ''))
    if (r.ok) { await carica(); if (r.download) window.location.assign(String(r.download)) }
  }
  const registraEsito = async () => {
    if (!esito) return
    setOccupato(true)
    const r = await invia(`${base}/${encodeURIComponent(esito.id)}/esito`, esito)
    setOccupato(false)
    setMessaggio(String(r.message || ''))
    if (r.ok) { setEsito(null); await carica() }
  }

  if (!dati.ok) return <p className="iu-cons__msg" role="alert">{dati.message || 'Conservazione non disponibile.'}</p>
  return (
    <div className="iu-cons" ref={radice}>
      <p className="iu-cons__nota">IUSENTRA prepara il <strong>pacchetto di versamento</strong> con i documenti, l'impronta SHA-256 e le informazioni descrittive previste dall'Allegato 5 alle Linee guida AgID. La conservazione a norma (art. 44 CAD) la svolge il conservatore scelto dallo studio, che rilascia il rapporto di versamento.</p>
      {messaggio ? <p className="iu-cons__msg" role="status">{messaggio}</p> : null}

      {documenti.length ? (
        <ul className="iu-cons__documenti" aria-label="Documenti da versare">
          {documenti.map((d) => (
            <li key={d.id}>
              <label><input type="checkbox" checked={scelti.has(d.id)} disabled={!dati.puoModificare} onChange={(e) => setScelti((s) => { const n = new Set(s); if (e.target.checked) n.add(d.id); else n.delete(d.id); return n })}/>
                <span><strong>{d.nome}</strong><small>{d.formato}{d.firmato ? ' · firmato' : ''}{d.data ? ` · ${dataIt(d.data)}` : ''}{d.versato ? ' · già versato' : ''}</small></span></label>
              {!d.idoneo ? <TriangleAlert size={14} aria-label="Formato da verificare"/> : d.versato ? <CheckCircle2 size={14} aria-label="Già versato"/> : null}
            </li>
          ))}
        </ul>
      ) : <p className="iu-cons__nota">Nessun documento nel fascicolo.</p>}
      {nonIdonei.length ? <p className="iu-cons__avviso"><TriangleAlert size={14}/> {nonIdonei.length === 1 ? '1 documento in un formato non compreso' : `${nonIdonei.length} documenti in formati non compresi`} nell'Allegato 2 (es. {nonIdonei[0].formato}): valuta la conversione in PDF/A o concorda il formato con il conservatore.</p> : null}

      {dati.puoModificare ? (
        <div className="iu-cons__azioni">
          <label><span>Tempo di conservazione (anni)</span><input type="number" min="1" max="9999" value={anni} onChange={(e) => setAnni(e.target.value)}/></label>
          <label className="iu-cons__spunta"><input type="checkbox" checked={riservato} onChange={(e) => setRiservato(e.target.checked)}/><span>Documenti riservati</span></label>
          <button type="button" disabled={occupato || !scelti.size} onClick={() => void crea()}><FileArchive size={14}/> Prepara il pacchetto ({scelti.size})</button>
        </div>
      ) : null}

      {(dati.versamenti || []).length ? (
        <section className="iu-cons__registro" aria-label="Pacchetti di versamento">
          <h4>Pacchetti preparati</h4>
          {(dati.versamenti || []).map((v) => (
            <article key={v.id}>
              <header><strong>{v.id}</strong><span className={`iu-cons__stato iu-cons__stato--${v.stato}`}>{v.stato_etichetta}</span></header>
              <small>{dataIt(v.creato_il)} · {v.documenti.length} documenti · {peso(v.dimensione)} · {v.anni_conservazione} anni{v.creato_da ? ` · ${v.creato_da}` : ''}</small>
              <code title="Impronta SHA-256 del pacchetto">{v.impronta_pacchetto}</code>
              {v.conservatore ? <small>{v.conservatore} · {dataIt(v.data_versamento)}{v.id_rapporto ? ` · rapporto ${v.id_rapporto}` : ''}</small> : null}
              <div className="iu-cons__azioni">
                <a href={`${base}/${encodeURIComponent(v.id)}/pacchetto.zip`}><Download size={14}/> Scarica</a>
                {dati.puoModificare && v.stato === 'preparato' ? <button type="button" onClick={() => setEsito({ id: v.id, stato: 'versato', conservatore: '', data: oggiIso(), idRapporto: '' })}>Registra l'esito</button> : null}
              </div>
              {esito?.id === v.id ? (
                <div className="iu-cons__esito" role="form" aria-label={`Esito del versamento ${v.id}`}>
                  <label><span>Esito</span><select value={esito.stato} onChange={(e) => setEsito({ ...esito, stato: e.target.value })}><option value="versato">Accettato: rapporto di versamento ricevuto</option><option value="rifiutato">Rifiutato</option></select></label>
                  <label><span>Conservatore</span><input value={esito.conservatore} onChange={(e) => setEsito({ ...esito, conservatore: e.target.value })}/></label>
                  <label><span>Data del rapporto</span><input type="date" value={esito.data} max={oggiIso()} onChange={(e) => setEsito({ ...esito, data: e.target.value })}/></label>
                  <label><span>Identificativo del rapporto</span><input value={esito.idRapporto} onChange={(e) => setEsito({ ...esito, idRapporto: e.target.value })}/></label>
                  <div className="iu-cons__azioni"><button type="button" disabled={occupato || !esito.conservatore.trim()} onClick={() => void registraEsito()}>Salva l'esito</button><button type="button" onClick={() => setEsito(null)}>Annulla</button></div>
                </div>
              ) : null}
            </article>
          ))}
        </section>
      ) : null}
    </div>
  )
}
