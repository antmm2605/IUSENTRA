import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, FileDown, SearchCheck, ShieldCheck } from 'lucide-react'
import { csrfHeader } from '../../api/csrf'
import './ClienteAntiriciclaggio.css'

type Indice = { macro_area: string; descrizione: string; punteggio: number; note: string }
type Evidenza = { outcome: string; subject_label: string; checked_at: string }
type Scheda = {
  id: string; stato: string; stato_etichetta: string; prestazione: string; prestazione_etichetta: string; in_ambito: boolean
  scopo_natura: string; descrizione_prestazione: string; note: string
  documento_tipo?: string; documento_numero?: string; documento_rilasciato_da?: string; documento_data_rilascio?: string; documento_scadenza?: string
  documento_scaduto: boolean; cliente_pep: boolean; paese_alto_rischio: boolean; impossibile_completare?: boolean
  titolare_effettivo?: { nome?: string; codice_fiscale?: string; criterio?: string; note?: string } | null
  indici: Indice[]; punteggio_medio: number; livello_suggerito: string; livello_scelto: string; scadenza_controllo: string
  conservazione_fino_al: string; sos_valutazione?: string; sos_data?: string; sos_note?: string; sos_etichetta: string
  promemoria: string[]; evidenze: Evidenza[]
}
type Stato = {
  ok: boolean; message?: string; cliente?: string; puoModificare?: boolean; schede?: Scheda[]
  opzioni?: { prestazioni: { value: string; label: string }[]; livelli: { value: string; label: string }[]; sos: { value: string; label: string }[]; documenti: string[] }
}
type Modulo = Record<string, string | boolean | Indice[]>

const AREE: Record<string, string> = { CLIENTE: 'Cliente', OPERAZIONE: 'Operazione', AREA_GEOGRAFICA: 'Area geografica' }
const DOCUMENTI: Record<string, string> = { carta_identita: "Carta d'identità", passaporto: 'Passaporto', patente: 'Patente', permesso_soggiorno: 'Permesso di soggiorno', altro: 'Altro' }
const dataIt = (valore?: string) => (valore && valore.length >= 10 ? `${valore.slice(8, 10)}/${valore.slice(5, 7)}/${valore.slice(0, 4)}` : '—')

function moduloDa(s?: Scheda): Modulo {
  return {
    prestazione: s?.prestazione || '', scopoNatura: s?.scopo_natura || '', descrizionePrestazione: s?.descrizione_prestazione || '',
    documentoTipo: s?.documento_tipo || '', documentoNumero: s?.documento_numero || '', documentoRilasciatoDa: s?.documento_rilasciato_da || '',
    documentoDataRilascio: s?.documento_data_rilascio || '', documentoScadenza: s?.documento_scadenza || '',
    titolareNome: s?.titolare_effettivo?.nome || '', titolareCf: s?.titolare_effettivo?.codice_fiscale || '', titolareCriterio: s?.titolare_effettivo?.criterio || '',
    clientePep: Boolean(s?.cliente_pep), paeseAltoRischio: Boolean(s?.paese_alto_rischio), impossibileCompletare: Boolean(s?.impossibile_completare),
    sosValutazione: s?.sos_valutazione || '', sosData: s?.sos_data || '', sosNote: s?.sos_note || '', note: s?.note || '',
    indici: s?.indici || [], livello: s?.livello_scelto || s?.livello_suggerito || '', motivazioneScostamento: '',
  }
}

async function invia(url: string, corpo: Record<string, unknown>): Promise<{ ok: boolean; message: string }> {
  try {
    const risposta = await fetch(url, { method: 'POST', credentials: 'same-origin', body: JSON.stringify(corpo),
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest', ...csrfHeader() } })
    const dati = await risposta.json().catch(() => ({})) as { ok?: boolean; message?: string }
    return { ok: Boolean(dati.ok), message: dati.message || (risposta.ok ? 'Fatto.' : 'Operazione non riuscita.') }
  } catch {
    return { ok: false, message: 'Operazione non riuscita.' }
  }
}

/** Adeguata verifica antiriciclaggio del cliente (D.Lgs. 231/2007): scheda, griglia CNF, screening UE, fascicolo PDF. */
export function ClienteAntiriciclaggio({ idCliente }: { idCliente: string }) {
  const [stato, setStato] = useState<Stato | null>(null)
  const [aperta, setAperta] = useState(false)
  const [modulo, setModulo] = useState<Modulo>(moduloDa())
  const [messaggio, setMessaggio] = useState('')
  const [occupato, setOccupato] = useState(false)
  const base = `/clienti/${encodeURIComponent(idCliente)}/antiriciclaggio`

  const carica = useCallback(async () => {
    const risposta = await fetch(`/api/v1/ui${base}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } }).catch(() => null)
    const dati = risposta ? await risposta.json().catch(() => null) as Stato | null : null
    setStato(dati || { ok: false, message: 'Antiriciclaggio non disponibile.' })
    return dati
  }, [base])
  useEffect(() => { void carica() }, [carica])

  if (!stato) return <p role="status">Carico l'adeguata verifica…</p>
  if (!stato.ok) return <p role="alert">{stato.message}</p>
  const scheda = stato.schede?.[0]
  const opzioni = stato.opzioni
  const campo = (nome: string, valore: string | boolean | Indice[]) => setModulo((m) => ({ ...m, [nome]: valore }))
  const testo = (nome: string) => String(modulo[nome] ?? '')
  const indici = (modulo.indici as Indice[]) || []

  const esegui = async (azione: () => Promise<{ ok: boolean; message: string }>, chiudi = false) => {
    setOccupato(true); setMessaggio('')
    const esito = await azione()
    setOccupato(false); setMessaggio(esito.message)
    if (esito.ok) { const dati = await carica(); if (chiudi) setAperta(false); else setModulo(moduloDa(dati?.schede?.[0])) }
  }
  const corpo = () => ({
    prestazione: testo('prestazione'), scopoNatura: testo('scopoNatura'), descrizionePrestazione: testo('descrizionePrestazione'),
    documentoTipo: testo('documentoTipo'), documentoNumero: testo('documentoNumero'), documentoRilasciatoDa: testo('documentoRilasciatoDa'),
    documentoDataRilascio: testo('documentoDataRilascio'), documentoScadenza: testo('documentoScadenza'),
    titolareEffettivo: { nome: testo('titolareNome'), codice_fiscale: testo('titolareCf'), criterio: testo('titolareCriterio') },
    clientePep: modulo.clientePep ? '1' : '0', paeseAltoRischio: modulo.paeseAltoRischio ? '1' : '0', impossibileCompletare: modulo.impossibileCompletare ? '1' : '0',
    sosValutazione: testo('sosValutazione'), sosData: testo('sosData'), sosNote: testo('sosNote'), note: testo('note'),
    ...(indici.length ? { indici } : {}),
  })
  const salva = () => esegui(() => invia(scheda ? `${base}/${scheda.id}/aggiorna` : `${base}/avvia`, corpo()))
  const conferma = () => scheda && esegui(() => invia(`${base}/${scheda.id}/conferma`, { livello: testo('livello'), motivazioneScostamento: testo('motivazioneScostamento') }))
  const screening = () => scheda && esegui(() => invia(`${base}/${scheda.id}/screening-ue`, {}))

  return (
    <div className="iu-cli-aml">
      {scheda ? (
        <div className="iu-cli-aml__stato">
          <div>
            <strong>{scheda.stato_etichetta}</strong>
            <span>{scheda.prestazione_etichetta}</span>
            {scheda.in_ambito ? <span>Rischio medio {scheda.punteggio_medio} · suggerita {scheda.livello_suggerito.toLowerCase()}{scheda.livello_scelto ? ` · scelta ${scheda.livello_scelto.toLowerCase()}` : ''}</span> : null}
            {scheda.scadenza_controllo ? <span>Controllo costante entro il {dataIt(scheda.scadenza_controllo)} · conservazione fino al {dataIt(scheda.conservazione_fino_al)}</span> : null}
            {scheda.evidenze?.[0] ? <span>Screening UE del {dataIt(scheda.evidenze[0].checked_at)}: {scheda.evidenze[0].outcome.replaceAll('_', ' ').toLowerCase()}</span> : null}
            <span>Segnalazione di operazione sospetta: {scheda.sos_etichetta.toLowerCase()}</span>
          </div>
          <a href={`${base}/${scheda.id}/fascicolo.pdf`}><FileDown size={15}/> Fascicolo PDF</a>
        </div>
      ) : <p>Nessuna adeguata verifica per questo cliente. Serve per le prestazioni dell'art. 3 c. 4 lett. c D.Lgs. 231/2007; la difesa in giudizio ne è esclusa (art. 17 c. 7).</p>}
      {(scheda?.promemoria || []).length ? (
        <ul className="iu-cli-aml__promemoria">{scheda!.promemoria.map((p) => <li key={p}><AlertTriangle size={14}/> {p}</li>)}</ul>
      ) : null}
      {stato.puoModificare ? (
        <div className="iu-cli-aml__azioni">
          <button type="button" onClick={() => { setModulo(moduloDa(scheda)); setAperta(!aperta) }}><ShieldCheck size={15}/> {scheda ? (aperta ? 'Chiudi scheda' : 'Apri e aggiorna') : 'Avvia adeguata verifica'}</button>
          {scheda?.in_ambito ? <button type="button" disabled={occupato} onClick={() => void screening()}><SearchCheck size={15}/> Screening lista UE</button> : null}
        </div>
      ) : null}
      {aperta && opzioni ? (
        <div className="iu-cli-aml__modulo" role="form" aria-label="Scheda di adeguata verifica">
          <label className="is-wide"><span>Prestazione *</span><select value={testo('prestazione')} onChange={(e) => campo('prestazione', e.target.value)}>
            <option value="">Scegli la prestazione</option>{opzioni.prestazioni.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
          <label className="is-wide"><span>Scopo e natura del rapporto *</span><input value={testo('scopoNatura')} onChange={(e) => campo('scopoNatura', e.target.value)}/></label>
          <label className="is-wide"><span>Descrizione</span><input value={testo('descrizionePrestazione')} onChange={(e) => campo('descrizionePrestazione', e.target.value)}/></label>
          <div className="iu-cli-aml__gruppo"><strong className="iu-cli-aml__titolo">Documento d'identità (art. 19)</strong>
            <label><span>Tipo</span><select value={testo('documentoTipo')} onChange={(e) => campo('documentoTipo', e.target.value)}><option value="">—</option>{opzioni.documenti.map((d) => <option key={d} value={d}>{DOCUMENTI[d] || d}</option>)}</select></label>
            <label><span>Numero</span><input value={testo('documentoNumero')} onChange={(e) => campo('documentoNumero', e.target.value)} autoComplete="off"/></label>
            <label><span>Rilasciato da</span><input value={testo('documentoRilasciatoDa')} onChange={(e) => campo('documentoRilasciatoDa', e.target.value)}/></label>
            <label><span>Rilascio</span><input type="date" value={testo('documentoDataRilascio')} onChange={(e) => campo('documentoDataRilascio', e.target.value)}/></label>
            <label><span>Scadenza</span><input type="date" value={testo('documentoScadenza')} onChange={(e) => campo('documentoScadenza', e.target.value)}/></label>
          </div>
          <div className="iu-cli-aml__gruppo"><strong className="iu-cli-aml__titolo">Titolare effettivo (art. 20)</strong>
            <label><span>Nome e cognome</span><input value={testo('titolareNome')} onChange={(e) => campo('titolareNome', e.target.value)}/></label>
            <label><span>Codice fiscale</span><input value={testo('titolareCf')} onChange={(e) => campo('titolareCf', e.target.value)}/></label>
            <label><span>Criterio</span><input value={testo('titolareCriterio')} onChange={(e) => campo('titolareCriterio', e.target.value)} placeholder="Es. proprietà diretta oltre il 25%"/></label>
          </div>
          <div className="iu-cli-aml__flag">
            <label><input type="checkbox" checked={Boolean(modulo.clientePep)} onChange={(e) => campo('clientePep', e.target.checked)}/> Persona politicamente esposta</label>
            <label><input type="checkbox" checked={Boolean(modulo.paeseAltoRischio)} onChange={(e) => campo('paeseAltoRischio', e.target.checked)}/> Paese terzo ad alto rischio</label>
            <label><input type="checkbox" checked={Boolean(modulo.impossibileCompletare)} onChange={(e) => campo('impossibileCompletare', e.target.checked)}/> Impossibile completare la verifica (art. 42)</label>
          </div>
          {indici.length ? (
            <div className="iu-cli-aml__gruppo iu-cli-aml__griglia"><strong className="iu-cli-aml__titolo">Profilatura del rischio (griglia CNF, 1 = inesistente, 5 = elevato)</strong>
              {indici.map((indice, i) => (
                <label key={`${indice.macro_area}-${i}`}><span>{AREE[indice.macro_area] || indice.macro_area} · {indice.descrizione}</span>
                  <select value={indice.punteggio} onChange={(e) => campo('indici', indici.map((x, j) => (j === i ? { ...x, punteggio: Number(e.target.value) } : x)))}>
                    {[1, 2, 3, 4, 5].map((p) => <option key={p} value={p}>{p}</option>)}
                  </select></label>
              ))}
            </div>
          ) : null}
          <div className="iu-cli-aml__gruppo"><strong className="iu-cli-aml__titolo">Segnalazione di operazione sospetta (art. 35)</strong>
            <label><span>Esito della valutazione</span><select value={testo('sosValutazione')} onChange={(e) => campo('sosValutazione', e.target.value)}>{opzioni.sos.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
            <label><span>Data</span><input type="date" value={testo('sosData')} onChange={(e) => campo('sosData', e.target.value)}/></label>
            <label className="is-wide"><span>Note (riservate, art. 39)</span><input value={testo('sosNote')} onChange={(e) => campo('sosNote', e.target.value)}/></label>
          </div>
          <label className="is-wide"><span>Note</span><textarea rows={2} value={testo('note')} onChange={(e) => campo('note', e.target.value)}/></label>
          <div className="iu-cli-aml__azioni">
            <button type="button" disabled={occupato || !testo('prestazione') || !testo('scopoNatura').trim()} onClick={() => void salva()}>{scheda ? 'Salva la scheda' : 'Crea la scheda'}</button>
          </div>
          {scheda?.in_ambito ? (
            <div className="iu-cli-aml__conferma">
              <label><span>Livello di verifica</span><select value={testo('livello')} onChange={(e) => campo('livello', e.target.value)}>{opzioni.livelli.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>
              <label className="is-wide"><span>Motivazione se meno rigoroso del suggerito</span><input value={testo('motivazioneScostamento')} onChange={(e) => campo('motivazioneScostamento', e.target.value)}/></label>
              <button type="button" disabled={occupato || !testo('livello')} onClick={() => void conferma()}>Conferma l'adeguata verifica</button>
            </div>
          ) : null}
        </div>
      ) : null}
      {messaggio ? <p role="status" className="iu-cli-aml__messaggio">{messaggio}</p> : null}
    </div>
  )
}

export default ClienteAntiriciclaggio
