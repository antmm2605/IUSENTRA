import { useEffect, useRef, useState, type CSSProperties, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { ChevronLeft, ChevronRight, Eye, PenLine, RefreshCw, Signature, SquareDashed, Trash2 } from 'lucide-react'
import { csrfHeader } from '../../api/csrf'
import { Modal } from '../../ui/Modal'
import './attestazioneConformita.css'

type Voce = { id: string; etichetta: string }
type Opzioni = {
  ok: boolean
  tipi: Voce[]
  caratteri: Voce[]
  caratteriFirma?: Voce[]
  stiliFirma: Voce[]
  posizioni: Voce[]
  formula: string
  firmato?: boolean
  mancano: string[]
  pagine?: { meta: string; pagina: string }
  predefiniti: Record<string, string | number>
}
type Valori = Record<string, string>
type Riquadro = { pagina: number; x: number; y: number; larghezza: number; altezza: number }
type Strumento = 'attestazione' | 'firma'
type Punto = { x: number; y: number }

const PREFERENZE = 'iusentra.attestazione.preferenze'
const CAMPI_PREFERITI = ['carattereTesto', 'dimensioneTesto', 'carattereFirma', 'stileFirma', 'dimensioneFirma', 'firma', 'testoFirma']
const ETICHETTE: Record<Strumento, string> = { attestazione: 'Attestazione', firma: 'Firma testo' }

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
  const origine = valori.tipo === 'informatico' ? 'al documento informatico' : 'all’originale analogico'
  return tipi.length ? formula.replace('{avvocato}', valori.avvocato || '…').replace('{origine}', origine) : formula
}

function riquadroDa(pagina: number, a: Punto, b: Punto): Riquadro {
  return { pagina, x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), larghezza: Math.abs(b.x - a.x), altezza: Math.abs(b.y - a.y) }
}

/** Posizione del riquadro come variabili CSS: l'aspetto resta nel foglio di stile. */
function stileRiquadro(r: Riquadro): CSSProperties {
  return { '--iu-att-x': `${r.x * 100}%`, '--iu-att-y': `${r.y * 100}%`, '--iu-att-w': `${r.larghezza * 100}%`, '--iu-att-h': `${r.altezza * 100}%` } as CSSProperties
}

/**
 * «Attesta»: l'avvocato apre il documento nel lettore, disegna col mouse il riquadro dell'attestazione
 * e quello della firma testo (nome e cognome sotto «Vera ed autentica»), sceglie carattere e dimensione
 * di ciascuno, vede l'anteprima e passa subito alla firma digitale con la firma visibile «Per autentica e
 * sottoscrizione» (art. 22 e 23-bis CAD; art. 196-octies disp. att. c.p.c.; art. 136 c.p.a.). Senza
 * riquadro l'attestazione va nello spazio libero dell'ultima pagina. La versione precedente del documento
 * resta nello storico.
 */
export default function AttestazioneConformitaFinestra({ action, documento, onChiudi, onDone, onError }: {
  action: string
  documento: string
  onChiudi: () => void
  onDone?: (message?: string) => void
  onError?: (message: string) => void
}) {
  const [aperta, setAperta] = useState(true)
  const [opzioni, setOpzioni] = useState<Opzioni | null>(null)
  const [valori, setValori] = useState<Valori>({})
  const [numeroPagine, setNumeroPagine] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [strumento, setStrumento] = useState<Strumento>('attestazione')
  const [riquadri, setRiquadri] = useState<Partial<Record<Strumento, Riquadro>>>({})
  const [bozza, setBozza] = useState<Riquadro | null>(null)
  const inizio = useRef<Punto | null>(null)
  const [anteprima, setAnteprima] = useState<Array<{ numero: number; immagine: string }>>([])
  const [esitoAnteprima, setEsitoAnteprima] = useState('')
  const [stato, setStato] = useState('')
  const [inCorso, setInCorso] = useState(false)
  useEffect(() => { void apri() }, [])
  const chiudi = () => { setAperta(false); onChiudi() }

  const apri = async () => {
    setStato('')
    try {
      const risposta = await fetch(action, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      const dati = await risposta.json() as Opzioni
      if (!risposta.ok || !dati.ok) throw new Error('Dati per l’attestazione non disponibili.')
      const base = Object.fromEntries(Object.entries(dati.predefiniti).map(([k, v]) => [k, String(v ?? '')]))
      const iniziali: Valori = { ...base, ...leggiPreferenze(), avvocato: base.avvocato, luogo: base.luogo, data: base.data, tipo: base.tipo }
      if (!iniziali.firma) iniziali.firma = base.firma
      if (!iniziali.testoFirma) iniziali.testoFirma = base.testoFirma
      setOpzioni(dati)
      setValori({ ...iniziali, testo: testoFormula(dati.formula, iniziali, dati.tipi) })
      if (dati.pagine?.meta) {
        const meta = await fetch(dati.pagine.meta, { credentials: 'same-origin', headers: { Accept: 'application/json' } }).then((r) => r.json()) as { ok?: boolean; pageCount?: number }
        const totale = Number(meta.pageCount || 0)
        setNumeroPagine(totale)
        setPagina(Math.max(1, totale))
      }
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

  const punto = (evento: ReactPointerEvent<HTMLDivElement>): Punto | null => {
    const rect = evento.currentTarget.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    return { x: Math.min(1, Math.max(0, (evento.clientX - rect.left) / rect.width)), y: Math.min(1, Math.max(0, (evento.clientY - rect.top) / rect.height)) }
  }
  const premi = (evento: ReactPointerEvent<HTMLDivElement>) => {
    const p = punto(evento)
    if (!p) return
    evento.preventDefault()
    try { evento.currentTarget.setPointerCapture(evento.pointerId) } catch { /* il browser non lo sostiene */ }
    inizio.current = p
    setBozza(riquadroDa(pagina, p, p))
  }
  const trascina = (evento: ReactPointerEvent<HTMLDivElement>) => {
    const p = punto(evento)
    if (inizio.current && p) setBozza(riquadroDa(pagina, inizio.current, p))
  }
  const rilascia = (evento: ReactPointerEvent<HTMLDivElement>) => {
    const p = punto(evento)
    const partenza = inizio.current
    inizio.current = null
    setBozza(null)
    if (!partenza || !p) return
    const nuovo = riquadroDa(pagina, partenza, p)
    if (nuovo.larghezza < 0.02 || nuovo.altezza < 0.01) return
    setRiquadri((prima) => ({ ...prima, [strumento]: nuovo }))
    setAnteprima([])
    if (strumento === 'attestazione' && !riquadri.firma) setStrumento('firma')
  }
  const togli = (quale: Strumento) => { setRiquadri((prima) => ({ ...prima, [quale]: undefined })); setAnteprima([]) }

  const invia = async (anteprimaSola: boolean) => {
    setInCorso(true)
    setStato(anteprimaSola ? 'Preparo l’anteprima…' : 'Scrivo l’attestazione sul documento…')
    try {
      const risposta = await fetch(action, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json', ...csrfHeader() },
        body: JSON.stringify({ ...valori, riquadroAttestazione: riquadri.attestazione || null, riquadroFirma: riquadri.firma || null, anteprima: anteprimaSola }),
      })
      const esito = await risposta.json().catch(() => ({ ok: false, messaggio: 'Risposta non valida.' })) as { ok: boolean; messaggio?: string; firmaUrl?: string; esito?: string; pagine?: Array<{ numero: number; immagine: string }> }
      if (!risposta.ok || !esito.ok) throw new Error(esito.messaggio || 'Attestazione non generata.')
      if (anteprimaSola) {
        setAnteprima(esito.pagine || [])
        setEsitoAnteprima(esito.esito || '')
        setStato('')
        return
      }
      salvaPreferenze(valori)
      chiudi()
      onDone?.(esito.messaggio)
      // Subito alla firma: l'attestazione si sottoscrive con firma digitale.
      if (esito.firmaUrl) window.location.assign(esito.firmaUrl)
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
  const immagine = opzioni?.pagine ? opzioni.pagine.pagina.replace('{n}', String(pagina)) : ''
  const sullaPagina = (Object.entries(riquadri) as Array<[Strumento, Riquadro | undefined]>).filter(([, r]) => r && r.pagina === pagina) as Array<[Strumento, Riquadro]>
  const bloccato = inCorso || Boolean(opzioni?.firmato)

  return (
    <>
      <Modal title={`Attestazione di conformità · ${documento}`} open={aperta} onClose={chiudi}>
        {!opzioni ? <p role="status">{stato || 'Carico il documento e i dati dello studio…'}</p> : (
          <form className="iu-attestazione" onSubmit={conferma}>
            <section className="iu-attestazione__lettore" aria-label="Documento: disegna i riquadri">
              {anteprima.length ? (
                <>
                  <div className="iu-attestazione__strumenti">
                    <button type="button" className="iu-attestazione__strumento" onClick={() => setAnteprima([])}><SquareDashed size={14}/> Torna ai riquadri</button>
                    {esitoAnteprima ? <span className="iu-attestazione__nota">{esitoAnteprima}</span> : null}
                  </div>
                  <div className="iu-attestazione__anteprima">
                    {anteprima.map((p) => <img key={p.numero} src={p.immagine} alt={`Anteprima di pagina ${p.numero} con l’attestazione`}/>)}
                  </div>
                </>
              ) : (
                <>
                  <div className="iu-attestazione__strumenti" role="group" aria-label="Riquadro da disegnare">
                    {(['attestazione', 'firma'] as Strumento[]).map((quale) => (
                      <button key={quale} type="button" aria-pressed={strumento === quale} className={`iu-attestazione__strumento${strumento === quale ? ' iu-attestazione__strumento--attivo' : ''}`} onClick={() => setStrumento(quale)}>
                        {quale === 'attestazione' ? <SquareDashed size={14}/> : <Signature size={14}/>} Riquadro {ETICHETTE[quale].toLowerCase()}{riquadri[quale] ? ` · pag. ${riquadri[quale]?.pagina}` : ''}
                      </button>
                    ))}
                    <span className="iu-attestazione__pagine">
                      <button type="button" aria-label="Pagina precedente" disabled={pagina <= 1} onClick={() => setPagina((p) => Math.max(1, p - 1))}><ChevronLeft size={16}/></button>
                      Pagina {pagina}{numeroPagine ? ` di ${numeroPagine}` : ''}
                      <button type="button" aria-label="Pagina successiva" disabled={!numeroPagine || pagina >= numeroPagine} onClick={() => setPagina((p) => Math.min(numeroPagine, p + 1))}><ChevronRight size={16}/></button>
                    </span>
                  </div>
                  <p className="iu-attestazione__nota">Trascina col mouse sul documento: prima il riquadro dell’attestazione, poi quello della firma testo sotto «Vera ed autentica». Ridisegnalo per spostarlo.</p>
                  <div className="iu-attestazione__foglio" onPointerDown={premi} onPointerMove={trascina} onPointerUp={rilascia} onPointerCancel={() => { inizio.current = null; setBozza(null) }}>
                    {immagine ? <img src={immagine} alt={`Pagina ${pagina} di ${documento}`} draggable={false}/> : <p>Lettore non disponibile per questo documento.</p>}
                    {sullaPagina.map(([quale, r]) => <span key={quale} className={`iu-attestazione__riquadro iu-attestazione__riquadro--${quale}`} style={stileRiquadro(r)}>{ETICHETTE[quale]}</span>)}
                    {bozza ? <span className={`iu-attestazione__riquadro iu-attestazione__riquadro--${strumento} iu-attestazione__riquadro--bozza`} style={stileRiquadro(bozza)}/> : null}
                  </div>
                </>
              )}
            </section>
            <section className="iu-attestazione__campi">
              {opzioni.firmato ? <p className="iu-attestazione__avviso">Il documento è già firmato: l’attestazione si scrive prima della firma, altrimenti la firma non sarebbe più valida. Riparti dalla copia non firmata.</p> : null}
              {opzioni.mancano.length ? <p className="iu-attestazione__avviso">Nelle Impostazioni dello studio manca: {opzioni.mancano.join(', ')}. Indicalo qui o completalo in Impostazioni → Studio.</p> : null}
              <fieldset>
                <legend>Attestazione {riquadri.attestazione ? <button type="button" className="iu-attestazione__togli" onClick={() => togli('attestazione')}><Trash2 size={13}/> togli riquadro</button> : <small>senza riquadro: spazio libero dell’ultima pagina</small>}</legend>
                <div className="iu-attestazione__griglia">
                  {scelta('tipo', 'Tipo di copia', opzioni.tipi)}
                  <label>Avvocato che attesta<input value={valori.avvocato || ''} onChange={(e) => aggiorna('avvocato', e.currentTarget.value)} maxLength={120} required/></label>
                  <label>Luogo<input value={valori.luogo || ''} onChange={(e) => aggiorna('luogo', e.currentTarget.value)} maxLength={80} required/></label>
                  <label>Data<input type="date" value={valori.data || ''} onChange={(e) => aggiorna('data', e.currentTarget.value)} required/></label>
                </div>
                <label>Testo<textarea rows={3} value={valori.testo || ''} onChange={(e) => aggiorna('testo', e.currentTarget.value)} maxLength={1200}/></label>
                <div className="iu-attestazione__griglia">
                  <label>Firma sotto la data<input value={valori.firma || ''} onChange={(e) => aggiorna('firma', e.currentTarget.value)} maxLength={120} placeholder="Cognome Nome"/></label>
                  {scelta('carattereTesto', 'Carattere', opzioni.caratteri)}
                  <label>Dimensione (pt)<input type="number" min={7} max={16} step={0.5} value={valori.dimensioneTesto || '12'} onChange={(e) => aggiorna('dimensioneTesto', e.currentTarget.value)}/></label>
                </div>
              </fieldset>
              <fieldset>
                <legend>Firma testo sotto «Vera ed autentica» {riquadri.firma ? <button type="button" className="iu-attestazione__togli" onClick={() => togli('firma')}><Trash2 size={13}/> togli riquadro</button> : <small>disegna il riquadro per inserirla</small>}</legend>
                <div className="iu-attestazione__griglia">
                  <label>Nome e cognome<input value={valori.testoFirma || ''} onChange={(e) => aggiorna('testoFirma', e.currentTarget.value)} maxLength={120}/></label>
                  {scelta('carattereFirma', 'Carattere', opzioni.caratteriFirma || opzioni.caratteri)}
                  {scelta('stileFirma', 'Stile', opzioni.stiliFirma)}
                  <label>Dimensione (pt)<input type="number" min={7} max={40} step={0.5} value={valori.dimensioneFirma || '18'} onChange={(e) => aggiorna('dimensioneFirma', e.currentTarget.value)}/></label>
                </div>
              </fieldset>
              <p className="iu-attestazione__nota">L’attestazione si scrive sul documento; la versione precedente resta nello storico. Con «Applica e firma» si apre la firma digitale, con la firma visibile «Per autentica e sottoscrizione» in basso.</p>
              {stato ? <p role="status" className="iu-attestazione__stato">{stato}</p> : null}
              <div className="iu-attestazione__azioni">
                <button type="button" className="iu-attestazione__strumento" onClick={() => void invia(true)} disabled={bloccato}>{inCorso ? <RefreshCw size={14}/> : <Eye size={14}/>} Anteprima</button>
                <button type="submit" className="iu-attestazione__strumento iu-attestazione__strumento--primario" disabled={bloccato}><PenLine size={14}/> Applica e firma</button>
              </div>
            </section>
          </form>
        )}
      </Modal>
    </>
  )
}
