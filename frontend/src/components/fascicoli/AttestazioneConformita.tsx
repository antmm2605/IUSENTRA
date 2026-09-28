import { useEffect, useRef, useState, type FormEvent } from 'react'
import { BadgeCheck, Eye, RefreshCw } from 'lucide-react'
import { csrfHeader } from '../../api/csrf'
import { Modal } from '../../ui/Modal'
import './attestazioneConformita.css'

type Voce = { id: string; etichetta: string }
type Opzioni = {
  ok: boolean
  tipi: Voce[]
  caratteri: Voce[]
  stiliFirma: Voce[]
  posizioni: Voce[]
  formula: string
  mancano: string[]
  predefiniti: Record<string, string | number>
}
type Valori = Record<string, string>

const PREFERENZE = 'iusentra.attestazione.preferenze'
const CAMPI_PREFERITI = ['carattereTesto', 'dimensioneTesto', 'carattereFirma', 'stileFirma', 'dimensioneFirma', 'posizione', 'firma']

function leggiPreferenze(): Valori {
  try {
    const grezzo = window.localStorage.getItem(PREFERENZE)
    return grezzo ? JSON.parse(grezzo) as Valori : {}
  } catch {
    return {}
  }
}

function salvaPreferenze(valori: Valori) {
  try {
    window.localStorage.setItem(PREFERENZE, JSON.stringify(Object.fromEntries(CAMPI_PREFERITI.map((c) => [c, valori[c] || '']))))
  } catch {
    // le preferenze sono una comodità: senza archivio del browser si riparte dai valori dello studio
  }
}

function testoFormula(formula: string, valori: Valori, tipi: Voce[]) {
  const origine = valori.tipo === 'informatico' ? 'al documento informatico' : "all'originale analogico"
  return tipi.length ? formula.replace('{avvocato}', valori.avvocato || '…').replace('{origine}', origine) : formula
}

/**
 * «Attesta»: copia informatica con l'attestazione di conformità del difensore (art. 22 e 23-bis CAD;
 * art. 196-octies disp. att. c.p.c.; art. 136 c.p.a.). Nome, città e data vengono dallo studio e si
 * possono correggere; carattere e dimensioni del testo e della firma li sceglie l'avvocato. La copia si
 * vede in anteprima e si salva nel fascicolo accanto all'originale, pronta per la firma digitale.
 */
export function AttestazioneConformitaAzione({ action, documento, onDone, onError }: {
  action: string
  documento: string
  onDone?: (message?: string) => void
  onError?: (message: string) => void
}) {
  const [aperta, setAperta] = useState(false)
  const [opzioni, setOpzioni] = useState<Opzioni | null>(null)
  const [valori, setValori] = useState<Valori>({})
  const [anteprima, setAnteprima] = useState('')
  const [stato, setStato] = useState('')
  const [inCorso, setInCorso] = useState(false)
  const urlAnteprima = useRef('')

  useEffect(() => () => { if (urlAnteprima.current) URL.revokeObjectURL(urlAnteprima.current) }, [])

  const apri = async () => {
    setAperta(true)
    setStato('')
    if (opzioni) return
    try {
      const risposta = await fetch(action, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      const dati = await risposta.json() as Opzioni
      if (!risposta.ok || !dati.ok) throw new Error('Dati per l’attestazione non disponibili.')
      const base = Object.fromEntries(Object.entries(dati.predefiniti).map(([k, v]) => [k, String(v ?? '')]))
      const iniziali: Valori = { ...base, ...leggiPreferenze(), avvocato: base.avvocato, luogo: base.luogo, data: base.data, tipo: base.tipo }
      if (!iniziali.firma) iniziali.firma = base.avvocato
      setOpzioni(dati)
      setValori({ ...iniziali, testo: testoFormula(dati.formula, iniziali, dati.tipi) })
    } catch (errore) {
      setStato(errore instanceof Error ? errore.message : 'Dati per l’attestazione non disponibili.')
    }
  }

  const aggiorna = (campo: string, valore: string) => setValori((prima) => {
    const prossimi = { ...prima, [campo]: valore }
    // Se l'avvocato non ha riscritto il testo, la formula segue nome e tipo di originale.
    if (opzioni && (campo === 'avvocato' || campo === 'tipo') && prima.testo === testoFormula(opzioni.formula, prima, opzioni.tipi)) {
      prossimi.testo = testoFormula(opzioni.formula, prossimi, opzioni.tipi)
    }
    return prossimi
  })

  const invia = async (anteprimaSola: boolean) => {
    setInCorso(true)
    setStato(anteprimaSola ? 'Preparo l’anteprima…' : 'Salvo la copia conforme…')
    try {
      const risposta = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: anteprimaSola ? 'application/pdf' : 'application/json', 'Content-Type': 'application/json', ...csrfHeader() },
        body: JSON.stringify({ ...valori, anteprima: anteprimaSola }),
      })
      if (anteprimaSola && risposta.ok && (risposta.headers.get('content-type') || '').includes('pdf')) {
        if (urlAnteprima.current) URL.revokeObjectURL(urlAnteprima.current)
        urlAnteprima.current = URL.createObjectURL(await risposta.blob())
        setAnteprima(urlAnteprima.current)
        setStato('')
        return
      }
      const esito = await risposta.json().catch(() => ({ ok: false, messaggio: 'Risposta non valida.' })) as { ok: boolean; messaggio?: string }
      if (!risposta.ok || !esito.ok) throw new Error(esito.messaggio || 'Attestazione non generata.')
      salvaPreferenze(valori)
      setAperta(false)
      onDone?.(esito.messaggio)
    } catch (errore) {
      const messaggio = errore instanceof Error ? errore.message : 'Attestazione non generata.'
      setStato(messaggio)
      if (!anteprimaSola) onError?.(messaggio)
    } finally {
      setInCorso(false)
    }
  }

  const conferma = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    void invia(false)
  }

  const scelta = (campo: string, etichetta: string, voci: Voce[]) => (
    <label>{etichetta}
      <select value={valori[campo] || ''} onChange={(e) => aggiorna(campo, e.currentTarget.value)}>
        {voci.map((v) => <option key={v.id} value={v.id}>{v.etichetta}</option>)}
      </select></label>
  )

  return (
    <>
      <button className="iu-fas-post iu-fas-post--secondary" type="button" onClick={() => void apri()} title="Crea la copia con l’attestazione di conformità">
        <BadgeCheck size={14}/><span>Attesta</span>
      </button>
      <Modal title={`Attestazione di conformità · ${documento}`} open={aperta} onClose={() => setAperta(false)}>
        {!opzioni ? <p role="status">{stato || 'Carico i dati dello studio…'}</p> : (
          <form className="iu-attestazione" onSubmit={conferma}>
            {opzioni.mancano.length ? <p className="iu-attestazione__avviso">Nelle Impostazioni dello studio manca: {opzioni.mancano.join(', ')}. Indicalo qui o completalo in Impostazioni → Studio.</p> : null}
            <div className="iu-attestazione__griglia">
              {scelta('tipo', 'Tipo di copia', opzioni.tipi)}
              <label>Avvocato che attesta<input value={valori.avvocato || ''} onChange={(e) => aggiorna('avvocato', e.currentTarget.value)} maxLength={120} required/></label>
              <label>Luogo<input value={valori.luogo || ''} onChange={(e) => aggiorna('luogo', e.currentTarget.value)} maxLength={80} required/></label>
              <label>Data<input type="date" value={valori.data || ''} onChange={(e) => aggiorna('data', e.currentTarget.value)} required/></label>
            </div>
            <label className="iu-attestazione__testo">Testo dell’attestazione
              <textarea rows={4} value={valori.testo || ''} onChange={(e) => aggiorna('testo', e.currentTarget.value)} maxLength={1200}/></label>
            <div className="iu-attestazione__griglia">
              {scelta('carattereTesto', 'Carattere del testo', opzioni.caratteri)}
              <label>Dimensione del testo (pt)<input type="number" min={8} max={16} step={0.5} value={valori.dimensioneTesto || '11'} onChange={(e) => aggiorna('dimensioneTesto', e.currentTarget.value)}/></label>
              <label>Nome nella firma<input value={valori.firma || ''} onChange={(e) => aggiorna('firma', e.currentTarget.value)} maxLength={120} placeholder="Cognome Nome"/></label>
              {scelta('carattereFirma', 'Carattere della firma', opzioni.caratteri)}
              {scelta('stileFirma', 'Stile della firma', opzioni.stiliFirma)}
              <label>Dimensione della firma (pt)<input type="number" min={8} max={28} step={0.5} value={valori.dimensioneFirma || '14'} onChange={(e) => aggiorna('dimensioneFirma', e.currentTarget.value)}/></label>
              {scelta('posizione', 'Dove si aggiunge', opzioni.posizioni)}
            </div>
            <p className="iu-attestazione__nota">La copia conforme si salva nel fascicolo accanto all’originale, che resta invariato. L’attestazione va sottoscritta con firma digitale: dopo il salvataggio usa «Firma» sulla copia.</p>
            {anteprima ? <object className="iu-attestazione__anteprima" data={anteprima} type="application/pdf" aria-label="Anteprima della copia conforme"><a href={anteprima} target="_blank" rel="noreferrer">Apri l’anteprima</a></object> : null}
            {stato ? <p role="status" className="iu-attestazione__stato">{stato}</p> : null}
            <div className="iu-modal__actions">
              <button type="button" className="iu-fas-post iu-fas-post--secondary" onClick={() => void invia(true)} disabled={inCorso}>{inCorso ? <RefreshCw size={14}/> : <Eye size={14}/>} Anteprima</button>
              <button type="submit" className="iu-fas-post iu-fas-post--primary" disabled={inCorso}><BadgeCheck size={14}/> Salva la copia conforme</button>
            </div>
          </form>
        )}
      </Modal>
    </>
  )
}
