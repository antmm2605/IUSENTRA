import { useState, type FormEvent } from 'react'
import { Plus, Save, Trash2 } from 'lucide-react'
import type { AttoImpugnato, CatalogoPtt, QuadroPtt } from './types'

const euro = (n: number) => `€ ${n.toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

/** I dati della nota di iscrizione a ruolo: Corte, trattazione, atti impugnati con il valore della lite, CUT. */
export function ProcedimentoPtt({ quadro, catalogo, tipo, onSalva }: {
  quadro: QuadroPtt
  catalogo: CatalogoPtt | null
  tipo: string
  onSalva: (dati: Record<string, unknown>) => Promise<void>
}) {
  const p = quadro.procedimento
  const [atti, setAtti] = useState<AttoImpugnato[]>(p.atti?.length ? p.atti : [{}])
  const [modalita, setModalita] = useState(p.cutEsenzione || p.cutModalita || '')
  const [stato, setStato] = useState('')
  const corte = catalogo?.sedi.find((s) => s.codice === p.corte)
  const aggiornaAtto = (i: number, campo: keyof AttoImpugnato, valore: string | boolean) =>
    setAtti((v) => v.map((a, j) => j === i ? { ...a, [campo]: valore } : a))
  const esente = modalita === 'Prenotazione a debito' || modalita === 'Patrocinio a spese dello Stato'

  const salva = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const f = new FormData(evento.currentTarget)
    const testo = (n: string) => String(f.get(n) || '').trim()
    const dati: Record<string, unknown> = {
      corte: testo('corte'), posizione: testo('posizione'), rg: testo('rg'), notificaRicorso: testo('notificaRicorso'),
      pubblicaUdienza: testo('pubblicaUdienza'), sospensione: f.get('sospensione') === '1', prova: f.get('prova') === '1',
      atto: testo('atto'), note: testo('note'), atti: atti.filter((a) => Object.values(a).some(Boolean)),
      cutModalita: esente ? '' : modalita, cutEsenzione: esente ? modalita : '', cutEstremi: testo('cutEstremi'), cutData: testo('cutData'),
      sentenza: { corte: testo('sentCorte'), numero: testo('sentNumero'), sezione: testo('sentSezione'), anno: testo('sentAnno'), data: testo('sentData') },
    }
    setStato('Salvataggio…')
    try {
      await onSalva(dati)
      setStato('Dati della nota di iscrizione salvati.')
    } catch (e) {
      setStato(e instanceof Error ? e.message : 'Salvataggio non riuscito.')
    }
  }
  const sentenza = p.sentenza || {}
  return (
    <form className="iu-pat-procedimento" onSubmit={(e) => void salva(e)}>
      <section>
        <h5>Corte e dati generali</h5>
        <div className="iu-pat-form">
          <label className="iu-pat-largo">Corte di giustizia tributaria
            <select name="corte" defaultValue={p.corte || ''}>
              <option value="">Scegli la Corte</option>
              {['1', '2'].map((grado) => (
                <optgroup key={grado} label={grado === '1' ? 'Primo grado' : 'Secondo grado'}>
                  {(catalogo?.sedi || []).filter((s) => s.grado === grado).map((s) => <option key={s.codice} value={s.codice}>{s.nome}</option>)}
                </optgroup>
              ))}
            </select>
            <small>{corte ? `${corte.citta} (${corte.provincia}) · PEC ${corte.pec} · codice ufficio F23 ${corte.codiceF23}` : 'Competente la Corte della sede dell’ente impositore (art. 4 D.Lgs. 546/1992).'}</small></label>
          <label>Posizione dell’assistito
            <select name="posizione" defaultValue={p.posizione || 'ricorrente'}><option value="ricorrente">Ricorrente / appellante</option><option value="resistente">Resistente (controdeduzioni)</option></select></label>
          <label>Numero di ruolo (RGR/RGA)<input name="rg" defaultValue={p.rg || ''} placeholder="es. 1234/2026"/></label>
          <label>Ricorso notificato il<input type="date" name="notificaRicorso" defaultValue={p.notificaRicorso || ''}/><small>Da qui i 30 giorni per costituirsi (art. 22).</small></label>
          <label>Trattazione
            <select name="pubblicaUdienza" defaultValue={p.pubblicaUdienza || ''}><option value="">No (camera di consiglio)</option>{(catalogo?.pubblicaUdienza || []).slice(1).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
          {tipo === 'altri-atti' ? (
            <label>Atto processuale
              <select name="atto" defaultValue={p.atto || ''}><option value="">Scegli dall’Appendice C</option>{(catalogo?.altriAtti || []).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
          ) : (
            <label>Atto principale
              <select name="atto" defaultValue={p.atto || ''}><option value="">Come il tipo di deposito</option>{(catalogo?.attiPrincipali || []).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
          )}
        </div>
        <div className="iu-pat-spunte">
          <label className="iu-pat-spunta"><input type="checkbox" name="sospensione" value="1" defaultChecked={Boolean(p.sospensione)}/> Istanza di sospensione dell’atto</label>
          <label className="iu-pat-spunta"><input type="checkbox" name="prova" value="1" defaultChecked={Boolean(p.prova)}/> Richiesta di prova testimoniale</label>
        </div>
        {tipo === 'nota-documenti' ? <label className="iu-pat-largo">Motivazione del deposito dei documenti<textarea name="note" rows={2} maxLength={500} defaultValue={p.note || ''}/></label> : <input type="hidden" name="note" value={p.note || ''}/>}
      </section>
      {tipo === 'appello' ? (
        <section>
          <h5>Sentenza impugnata</h5>
          <div className="iu-pat-form">
            <label>Corte che l’ha emessa<input name="sentCorte" defaultValue={sentenza.corte || ''}/></label>
            <label>Numero<input name="sentNumero" defaultValue={sentenza.numero || ''}/></label>
            <label>Sezione<input name="sentSezione" defaultValue={sentenza.sezione || ''}/></label>
            <label>Anno<input name="sentAnno" inputMode="numeric" maxLength={4} defaultValue={sentenza.anno || ''}/></label>
            <label>Data<input type="date" name="sentData" defaultValue={sentenza.data || ''}/></label>
          </div>
        </section>
      ) : null}
      <section>
        <h5>Atti impugnati e valore della lite</h5>
        {atti.map((a, i) => (
          <div key={i} className="iu-pat-form iu-ptt-atto">
            <label>Atto (Tabella B)<select value={a.tipo || ''} onChange={(e) => aggiornaAtto(i, 'tipo', e.target.value)}><option value="">Scegli</option>{(catalogo?.attiImpugnati || []).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
            <label>Numero dell’atto<input value={a.numero || ''} onChange={(e) => aggiornaAtto(i, 'numero', e.target.value)}/></label>
            <label>Ufficio che l’ha emesso<input value={a.ufficio || ''} onChange={(e) => aggiornaAtto(i, 'ufficio', e.target.value)} placeholder="es. Direzione provinciale di Bari"/></label>
            <label>Notificato il<input type="date" value={a.dataNotifica || ''} onChange={(e) => aggiornaAtto(i, 'dataNotifica', e.target.value)}/></label>
            <label>Periodo d’imposta<input value={a.periodo || ''} onChange={(e) => aggiornaAtto(i, 'periodo', e.target.value)} placeholder="es. 2021"/></label>
            <label>Tributo in lite (€, senza interessi e sanzioni)<input inputMode="decimal" value={a.tributo || ''} onChange={(e) => aggiornaAtto(i, 'tributo', e.target.value)}/></label>
            <label>Sanzioni (€, se in lite solo queste)<input inputMode="decimal" value={a.sanzioni || ''} onChange={(e) => aggiornaAtto(i, 'sanzioni', e.target.value)}/></label>
            <label>Materia<select value={a.materia || ''} onChange={(e) => aggiornaAtto(i, 'materia', e.target.value)}><option value="">Scegli</option>{(catalogo?.materie || []).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
            <label>Tributo<select value={a.tributo_tipo || ''} onChange={(e) => aggiornaAtto(i, 'tributo_tipo', e.target.value)}><option value="">Scegli</option>{(catalogo?.tributi || []).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
            <label className="iu-pat-spunta"><input type="checkbox" checked={Boolean(a.indeterminabile)} onChange={(e) => aggiornaAtto(i, 'indeterminabile', e.target.checked)}/> Valore indeterminabile</label>
            {atti.length > 1 ? <button type="button" onClick={() => setAtti((v) => v.filter((_, j) => j !== i))}><Trash2 size={14}/> Togli l’atto</button> : null}
          </div>
        ))}
        <div className="iu-pat-barra"><button type="button" onClick={() => setAtti((v) => [...v, {}])}><Plus size={14}/> Aggiungi un atto impugnato</button></div>
      </section>
      <section>
        <h5>Contributo unificato tributario</h5>
        <p className="iu-pat-nota">{quadro.cut.righe.map((r) => `Atto ${r.atto}: ${r.indeterminabile ? 'valore indeterminabile' : r.valore === null ? 'valore non dichiarato' : euro(r.valore)} → ${euro(r.cut)}`).join(' · ') || 'Indica gli atti impugnati per il calcolo.'}
          {' '}Totale <strong>{euro(quadro.cut.totale)}</strong>{quadro.cut.maggiorazione ? ` (con l’aumento di ${euro(quadro.cut.maggiorazione)})` : ''}. {quadro.cut.nota}</p>
        <div className="iu-pat-form">
          <label>Pagamento
            <select value={modalita} onChange={(e) => setModalita(e.target.value)}><option value="">Scegli</option>{(catalogo?.modalitaCut || []).map((v) => <option key={v} value={v}>{v}</option>)}</select>
            <small>{modalita === 'F23' ? `Codice tributo 171T${corte ? `, codice ufficio ${corte.codiceF23}` : ''}.` : modalita === 'pagoPA' ? 'Dal link nella PEC con il numero di ruolo o dal menu «PagoPA effettua pagamenti».' : ''}</small></label>
          {!esente ? <label>Estremi del versamento<input name="cutEstremi" defaultValue={p.cutEstremi || ''} placeholder="IUV, n. contrassegno, ABI…"/></label> : null}
          {!esente ? <label>Data del versamento<input type="date" name="cutData" defaultValue={p.cutData || ''}/></label> : null}
        </div>
      </section>
      <div className="iu-pat-barra">
        <button type="submit" className="iu-pat-primario"><Save size={15}/> Salva la nota di iscrizione</button>
        {stato ? <span role="status">{stato}</span> : null}
      </div>
    </form>
  )
}
