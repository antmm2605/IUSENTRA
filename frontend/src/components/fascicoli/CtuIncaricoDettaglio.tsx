import { useEffect, useState } from 'react'
import { Calculator, ClipboardList, FilePlus2, Plus, Save, Trash2 } from 'lucide-react'
import './CtuIncaricoDettaglio.css'

export type CtuOperazione = { id: string; data: string; ora: string; tipo: string; luogo: string; descrizione: string; minuti: number; presenza_giudice: boolean }
export type CtuDettaglio = {
  id: string
  ruoloStudio: string
  stato: string
  dataDepositoRelazione: string
  dataComunicazioneDecreto: string
  importoLiquidato: string
  operazioni: CtuOperazione[]
  vacazioniRegistro: { vacazioni: number; escluse_per_tetto: number }
  compensoInput: Record<string, unknown>
  stati: Array<{ value: string; label: string }>
  actions: { aggiorna: string; operazioni: string; compenso: string; istanza: string; deposito: string }
}
type Voce = { codice: string; valore: string; quantita: string }
type Calcolo = {
  ok: boolean; message?: string; righe?: Array<{ titolo: string; minimo: number; massimo: number; note: string[] }>
  minimo?: number; massimo?: number; onorario_base?: number; passaggi?: Array<{ voce: string; onorario: number }>
  onorario?: number; contributo?: number; iva?: number; spese_documentate?: number; spese_viaggio?: number; totale?: number; note?: string[]
}
type VoceTabella = { value: string; label: string; tipo: string; base: string; unita: string }

const euro = (v: number | undefined) => {
  const [intero, decimali] = Math.abs(Number(v || 0)).toFixed(2).split('.')
  return `€ ${intero.replace(/\B(?=(\d{3})+(?!\d))/g, '.')},${decimali}`
}
const testo = (v: unknown, predefinito = '') => (v === undefined || v === null ? predefinito : String(v))

async function invia(url: string, corpo: Record<string, unknown>): Promise<Record<string, unknown>> {
  const risposta = await fetch(url, {
    method: 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(corpo),
  }).catch(() => null)
  if (!risposta) return { ok: false, message: 'Connessione non riuscita.' }
  return await risposta.json().catch(() => ({ ok: false, message: 'Risposta non valida.' })) as Record<string, unknown>
}

/** Gestione dell'incarico CTU: stato e date, operazioni peritali, compenso (D.P.R. 115/2002) e istanza di liquidazione. */
export default function CtuIncaricoDettaglio({ incarico, onAggiornato }:{ incarico: CtuDettaglio; onAggiornato: () => void }) {
  const [messaggio, setMessaggio] = useState('')
  const [occupato, setOccupato] = useState(false)
  const [date, setDate] = useState({ stato: incarico.stato, dataDepositoRelazione: incarico.dataDepositoRelazione, dataComunicazioneDecreto: incarico.dataComunicazioneDecreto, importoLiquidato: incarico.importoLiquidato })
  const [op, setOp] = useState({ data: '', ora: '', tipo: 'sopralluogo', luogo: '', descrizione: '', ore: '', minuti: '', presenza_giudice: false })
  const salvato = incarico.compensoInput || {}
  const [modalita, setModalita] = useState(testo(salvato.modalita, 'tabella'))
  const [voci, setVoci] = useState<Voce[]>(Array.isArray(salvato.voci) && salvato.voci.length ? (salvato.voci as Voce[]).map((v) => ({ codice: testo(v.codice), valore: testo(v.valore), quantita: testo(v.quantita, '1') })) : [{ codice: '', valore: '', quantita: '1' }])
  const [opzioni, setOpzioni] = useState({
    posizione: testo(salvato.posizione, '50'), vacazioni: testo(salvato.vacazioni), termine_giorni: testo(salvato.termine_giorni),
    aumento_eccezionale: testo(salvato.aumento_eccezionale, '1'), motivazione_aumento: testo(salvato.motivazione_aumento),
    componenti_collegio: testo(salvato.componenti_collegio, '1'), collegio_per_intero: Boolean(salvato.collegio_per_intero), ritardo: Boolean(salvato.ritardo),
    patrocinio: testo(salvato.patrocinio), spese_documentate: testo(salvato.spese_documentate), spese_viaggio: testo(salvato.spese_viaggio),
    contributo_perc: testo(salvato.contributo_perc, '4'), iva_perc: testo(salvato.iva_perc, '22'),
  })
  const [tabella, setTabella] = useState<VoceTabella[]>([])
  const [calcolo, setCalcolo] = useState<Calcolo | null>(null)
  const [bozza, setBozza] = useState('')
  const ausiliario = incarico.ruoloStudio === 'AUSILIARIO'

  useEffect(() => {
    fetch('/api/v1/ui/ctu/tabella', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then((r) => r.ok ? r.json() : { voci: [] }).then((p: { voci?: VoceTabella[] }) => setTabella(p.voci || [])).catch(() => setTabella([]))
  }, [])

  const esegui = async (url: string, corpo: Record<string, unknown>) => {
    setOccupato(true)
    const esito = await invia(url, corpo)
    setOccupato(false)
    setMessaggio(testo(esito.message, esito.ok ? 'Operazione completata.' : 'Operazione non riuscita.'))
    return esito
  }
  const salvaDate = async () => { if ((await esegui(incarico.actions.aggiorna, date)).ok) onAggiornato() }
  const aggiungiOperazione = async () => {
    const minuti = Math.round(Number(op.ore || 0) * 60 + Number(op.minuti || 0))
    const esito = await esegui(incarico.actions.operazioni, { ...op, minuti })
    if (esito.ok) { setOp({ ...op, data: '', ora: '', luogo: '', descrizione: '', ore: '', minuti: '' }); onAggiornato() }
  }
  const rimuovi = async (id: string) => { if ((await esegui(`${incarico.actions.operazioni}/${encodeURIComponent(id)}/rimuovi`, {})).ok) onAggiornato() }
  const corpoCompenso = () => ({ modalita, voci: voci.filter((v) => v.codice), ...opzioni })
  const calcola = async () => {
    const esito = await esegui(incarico.actions.compenso, corpoCompenso()) as Calcolo
    setCalcolo(esito.ok ? esito : null)
  }
  const creaIstanza = async () => {
    const esito = await esegui(incarico.actions.istanza, corpoCompenso())
    if (esito.ok) { setBozza(testo(esito.url)); onAggiornato() }
  }
  const voceInfo = (codice: string) => tabella.find((t) => t.value === codice)

  return (
    <div className="iu-ctu-det">
      {messaggio ? <p className="iu-ctu-det__msg" role="status">{messaggio}</p> : null}

      <section aria-label="Stato e liquidazione">
        <h4>Stato e liquidazione</h4>
        <div className="iu-ctu-det__campi">
          <label><span>Stato</span><select value={date.stato} onChange={(e) => setDate({ ...date, stato: e.target.value })}>{incarico.stati.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}</select></label>
          <label><span>Relazione depositata il</span><input type="date" value={date.dataDepositoRelazione} onChange={(e) => setDate({ ...date, dataDepositoRelazione: e.target.value })}/></label>
          <label><span>Decreto di liquidazione comunicato il</span><input type="date" value={date.dataComunicazioneDecreto} onChange={(e) => setDate({ ...date, dataComunicazioneDecreto: e.target.value })}/></label>
          <label><span>Importo liquidato (€)</span><input inputMode="decimal" value={date.importoLiquidato} onChange={(e) => setDate({ ...date, importoLiquidato: e.target.value })}/></label>
        </div>
        <button type="button" disabled={occupato} onClick={() => void salvaDate()}><Save size={14}/> Salva</button>
        <p className="iu-ctu-det__nota">{ausiliario ? 'Dal deposito della relazione: istanza di liquidazione entro 100 giorni, a pena di decadenza (art. 71 D.P.R. 115/2002).' : 'Dalla comunicazione del decreto: opposizione entro 30 giorni (art. 170 D.P.R. 115/2002, art. 15 D.Lgs. 150/2011).'} Le scadenze nascono con «Proponi scadenze».</p>
      </section>

      <section aria-label="Operazioni peritali">
        <h4><ClipboardList size={15}/> Operazioni peritali</h4>
        {incarico.operazioni.length ? (
          <ul className="iu-ctu-det__operazioni">
            {incarico.operazioni.map((o) => (
              <li key={o.id}>
                <span><strong>{o.data.split('-').reverse().join('/')}{o.ora ? ` ${o.ora}` : ''}</strong> {o.descrizione || o.tipo}{o.luogo ? ` — ${o.luogo}` : ''}</span>
                <small>{o.minuti ? `${Math.floor(o.minuti / 60)} h ${String(o.minuti % 60).padStart(2, '0')} min` : 'durata non indicata'}{o.presenza_giudice ? ' · alla presenza del giudice' : ''}</small>
                <button type="button" aria-label={`Rimuovi operazione del ${o.data}`} disabled={occupato} onClick={() => void rimuovi(o.id)}><Trash2 size={13}/></button>
              </li>
            ))}
          </ul>
        ) : <p className="iu-ctu-det__nota">Nessuna operazione registrata.</p>}
        <p className="iu-ctu-det__nota">Vacazioni dal registro: <strong>{incarico.vacazioniRegistro.vacazioni}</strong>{incarico.vacazioniRegistro.escluse_per_tetto ? ` (${incarico.vacazioniRegistro.escluse_per_tetto} oltre il tetto di quattro al giorno)` : ''}.</p>
        <div className="iu-ctu-det__campi">
          <label><span>Data</span><input type="date" value={op.data} onChange={(e) => setOp({ ...op, data: e.target.value })}/></label>
          <label><span>Ora</span><input type="time" value={op.ora} onChange={(e) => setOp({ ...op, ora: e.target.value })}/></label>
          <label><span>Attività</span><select value={op.tipo} onChange={(e) => setOp({ ...op, tipo: e.target.value })}>
            <option value="inizio">Inizio operazioni</option><option value="sopralluogo">Sopralluogo</option><option value="riunione">Riunione con i consulenti</option>
            <option value="udienza">Udienza</option><option value="studio">Studio e redazione</option></select></label>
          <label><span>Luogo</span><input value={op.luogo} onChange={(e) => setOp({ ...op, luogo: e.target.value })}/></label>
          <label className="iu-ctu-det__largo"><span>Descrizione</span><input value={op.descrizione} onChange={(e) => setOp({ ...op, descrizione: e.target.value })}/></label>
          <label><span>Ore</span><input type="number" min="0" inputMode="numeric" value={op.ore} onChange={(e) => setOp({ ...op, ore: e.target.value })}/></label>
          <label><span>Minuti</span><input type="number" min="0" max="59" inputMode="numeric" value={op.minuti} onChange={(e) => setOp({ ...op, minuti: e.target.value })}/></label>
          <label className="iu-ctu-det__spunta"><input type="checkbox" checked={op.presenza_giudice} onChange={(e) => setOp({ ...op, presenza_giudice: e.target.checked })}/><span>Alla presenza del giudice</span></label>
        </div>
        <button type="button" disabled={occupato || !op.data} onClick={() => void aggiungiOperazione()}><Plus size={14}/> Registra operazione</button>
      </section>

      <section aria-label="Compenso dell'ausiliario">
        <h4><Calculator size={15}/> Compenso (D.P.R. 115/2002, D.M. 30/05/2002)</h4>
        <div className="iu-ctu-det__campi">
          <label><span>Criterio</span><select value={modalita} onChange={(e) => setModalita(e.target.value)}>
            <option value="tabella">Tabella (onorari fissi e variabili)</option><option value="vacazioni">Vacazioni (onorario a tempo)</option></select></label>
        </div>
        {modalita === 'tabella' ? (
          <div className="iu-ctu-det__voci">
            {voci.map((v, i) => {
              const info = voceInfo(v.codice)
              return (
                <div className="iu-ctu-det__campi" key={i}>
                  <label className="iu-ctu-det__largo"><span>Voce della tabella</span><select value={v.codice} onChange={(e) => setVoci(voci.map((x, j) => j === i ? { ...x, codice: e.target.value } : x))}>
                    <option value="">Scegli la voce</option>{tabella.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}</select></label>
                  {info?.tipo === 'scaglioni' ? <label><span>Valore (€): {info.base}</span><input inputMode="decimal" value={v.valore} onChange={(e) => setVoci(voci.map((x, j) => j === i ? { ...x, valore: e.target.value } : x))}/></label>
                    : <label><span>Quantità{info?.unita ? ` (${info.unita})` : ''}</span><input type="number" min="1" value={v.quantita} onChange={(e) => setVoci(voci.map((x, j) => j === i ? { ...x, quantita: e.target.value } : x))}/></label>}
                  {voci.length > 1 ? <button type="button" aria-label="Togli la voce" onClick={() => setVoci(voci.filter((_, j) => j !== i))}><Trash2 size={13}/></button> : null}
                </div>
              )
            })}
            <button type="button" onClick={() => setVoci([...voci, { codice: '', valore: '', quantita: '1' }])}><Plus size={14}/> Aggiungi voce</button>
            <label className="iu-ctu-det__forbice"><span>Posizione nella forbice fra minimo e massimo: {opzioni.posizione}% (art. 51)</span>
              <input type="range" min="0" max="100" step="5" value={opzioni.posizione} onChange={(e) => setOpzioni({ ...opzioni, posizione: e.target.value })}/></label>
          </div>
        ) : (
          <div className="iu-ctu-det__campi">
            <label><span>Vacazioni (da due ore)</span><input inputMode="decimal" value={opzioni.vacazioni} placeholder={String(incarico.vacazioniRegistro.vacazioni || '')} onChange={(e) => setOpzioni({ ...opzioni, vacazioni: e.target.value })}/></label>
            <label><span>Termine assegnato (giorni)</span><input type="number" min="0" value={opzioni.termine_giorni} onChange={(e) => setOpzioni({ ...opzioni, termine_giorni: e.target.value })}/></label>
            <button type="button" onClick={() => setOpzioni({ ...opzioni, vacazioni: String(incarico.vacazioniRegistro.vacazioni || '') })}>Usa il registro</button>
          </div>
        )}
        <div className="iu-ctu-det__campi">
          <label><span>Aumento (art. 52 c. 1, fino a 2)</span><input inputMode="decimal" value={opzioni.aumento_eccezionale} onChange={(e) => setOpzioni({ ...opzioni, aumento_eccezionale: e.target.value })}/></label>
          {Number(String(opzioni.aumento_eccezionale).replace(',', '.')) > 1 ? <label className="iu-ctu-det__largo"><span>Motivazione dell'aumento</span><input value={opzioni.motivazione_aumento} onChange={(e) => setOpzioni({ ...opzioni, motivazione_aumento: e.target.value })}/></label> : null}
          <label><span>Componenti del collegio</span><input type="number" min="1" value={opzioni.componenti_collegio} onChange={(e) => setOpzioni({ ...opzioni, componenti_collegio: e.target.value })}/></label>
          <label><span>Patrocinio a spese dello Stato</span><select value={opzioni.patrocinio} onChange={(e) => setOpzioni({ ...opzioni, patrocinio: e.target.value })}>
            <option value="">No</option><option value="civile">Sì, processo civile</option><option value="penale">Sì, processo penale</option></select></label>
          <label><span>Spese documentate (€)</span><input inputMode="decimal" value={opzioni.spese_documentate} onChange={(e) => setOpzioni({ ...opzioni, spese_documentate: e.target.value })}/></label>
          <label><span>Viaggio (€)</span><input inputMode="decimal" value={opzioni.spese_viaggio} onChange={(e) => setOpzioni({ ...opzioni, spese_viaggio: e.target.value })}/></label>
          <label><span>Contributo cassa %</span><input inputMode="decimal" value={opzioni.contributo_perc} onChange={(e) => setOpzioni({ ...opzioni, contributo_perc: e.target.value })}/></label>
          <label><span>IVA %</span><input inputMode="decimal" value={opzioni.iva_perc} onChange={(e) => setOpzioni({ ...opzioni, iva_perc: e.target.value })}/></label>
          {Number(opzioni.componenti_collegio) > 1 ? <label className="iu-ctu-det__spunta"><input type="checkbox" checked={opzioni.collegio_per_intero} onChange={(e) => setOpzioni({ ...opzioni, collegio_per_intero: e.target.checked })}/><span>Ognuno svolge l'incarico per intero</span></label> : null}
          <label className="iu-ctu-det__spunta"><input type="checkbox" checked={opzioni.ritardo} onChange={(e) => setOpzioni({ ...opzioni, ritardo: e.target.checked })}/><span>Completata oltre il termine (art. 52 c. 2)</span></label>
        </div>
        <div className="iu-ctu-det__azioni">
          <button type="button" disabled={occupato} onClick={() => void calcola()}><Calculator size={14}/> Calcola</button>
          {ausiliario ? <button type="button" disabled={occupato} onClick={() => void creaIstanza()}><FilePlus2 size={14}/> Bozza istanza di liquidazione</button> : null}
          {bozza ? <a href={bozza}>Apri la bozza nell'editor</a> : null}
          {ausiliario ? <a href={incarico.actions.deposito}>Prepara il deposito</a> : null}
        </div>
        {calcolo ? (
          <div className="iu-ctu-det__risultato" aria-label="Risultato del calcolo">
            <dl>
              {(calcolo.righe || []).map((r) => <div key={r.titolo}><dt>{r.titolo}</dt><dd>{r.minimo === r.massimo ? euro(r.minimo) : `${euro(r.minimo)} – ${euro(r.massimo)}`}</dd></div>)}
              <div><dt>Onorario richiesto</dt><dd>{euro(calcolo.onorario_base)}</dd></div>
              {(calcolo.passaggi || []).map((p) => <div key={p.voce}><dt>{p.voce}</dt><dd>{euro(p.onorario)}</dd></div>)}
              {calcolo.contributo ? <div><dt>Contributo previdenziale</dt><dd>{euro(calcolo.contributo)}</dd></div> : null}
              {calcolo.iva ? <div><dt>IVA</dt><dd>{euro(calcolo.iva)}</dd></div> : null}
              {calcolo.spese_viaggio ? <div><dt>Viaggio</dt><dd>{euro(calcolo.spese_viaggio)}</dd></div> : null}
              {calcolo.spese_documentate ? <div><dt>Spese documentate</dt><dd>{euro(calcolo.spese_documentate)}</dd></div> : null}
              <div className="is-totale"><dt>Totale</dt><dd>{euro(calcolo.totale)}</dd></div>
            </dl>
            {[...(calcolo.note || []), ...(calcolo.righe || []).flatMap((r) => r.note)].map((n) => <p key={n} className="iu-ctu-det__nota">{n}</p>)}
            <p className="iu-ctu-det__nota">La misura del compenso la decide il giudice con il decreto di pagamento (art. 168 D.P.R. 115/2002).</p>
          </div>
        ) : null}
      </section>
    </div>
  )
}
