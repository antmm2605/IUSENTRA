import { useCallback, useEffect, useRef, useState } from 'react'
import { ClipboardCheck, Download, FileSearch, FileText, PenLine, RefreshCw, ScanText, Square, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import {
  blocksToHtml,
  blocksToPlainText,
  countCharacters,
  type OcrBlock,
  type OcrFigure,
} from './ocrBlocks'
import { OcrReview } from './OcrReview'
import {
  documentoModificabile,
  elencaDocumentiRiconoscibili,
  indirizzoEditor,
  nomeCopiaRicercabile,
  riconosciPagina,
  salvaNelFascicolo,
  type DocumentoRiconoscibile,
  type PaginaRiconosciuta,
  type SorgenteOcr,
} from '../../services/documentoOcr'
import { generateDocument, saveGeneratedDocument, type GeneratedDocument } from '../../documentToolsData'
import './acquisition.css'
import './fascicoloOcr.css'

type Scelta = 'fascicolo' | 'file'

function messaggio(errore: unknown, ripiego: string): string {
  return errore instanceof Error && errore.message ? errore.message : ripiego
}

function etichettaDocumento(documento: DocumentoRiconoscibile): string {
  const dettagli = [documento.formato.toUpperCase(), documento.dimensione, documento.sezione].filter(Boolean)
  return dettagli.length ? `${documento.nome} (${dettagli.join(' · ')})` : documento.nome
}

/**
 * Riconoscimento del testo di un documento del fascicolo o di un file caricato.
 *
 * L'acquisizione da scanner e fotocamera porta nel fascicolo delle immagini; qui
 * si fa il passo dopo, e sui documenti che nel fascicolo ci sono già: leggerne
 * il testo per poterlo cercare, citare e riscrivere. Le pagine che hanno già un
 * livello di testo non vengono riconosciute due volte — si legge quello, che è
 * il testo esatto dell'autore — e l'OCR resta per le pagine che sono immagini.
 *
 * Il testo riconosciuto non entra da nessuna parte senza che l'avvocato lo
 * abbia riletto: la revisione è modificabile e solo da lì partono il documento
 * per l'editor, la copia del testo e la copia PDF ricercabile.
 */
export default function FascicoloOcr({ fascicoloId, reference, onSaved, onError }: {
  fascicoloId: string
  reference: string
  onSaved: (message?: string) => void
  onError: (message: string) => void
}) {
  const [aperto, setAperto] = useState(false)
  const [scelta, setScelta] = useState<Scelta>('fascicolo')
  const [documenti, setDocumenti] = useState<DocumentoRiconoscibile[]>([])
  const [documentoId, setDocumentoId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [nome, setNome] = useState('')
  const [pagine, setPagine] = useState<PaginaRiconosciuta[]>([])
  const [totale, setTotale] = useState(0)
  const [blocchi, setBlocchi] = useState<OcrBlock[]>([])
  const [figure, setFigure] = useState<OcrFigure[]>([])
  const [avanzamento, setAvanzamento] = useState('')
  const [occupato, setOccupato] = useState('')
  const [riconoscendo, setRiconoscendo] = useState(false)
  const [errore, setErrore] = useState('')
  const [avviso, setAvviso] = useState('')
  const vivo = useRef(true)
  const interruzione = useRef<AbortController | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  useEffect(() => () => { vivo.current = false; interruzione.current?.abort() }, [])

  const caricaDocumenti = useCallback(async () => {
    setOccupato('Lettura dei documenti del fascicolo…')
    setErrore('')
    try {
      const elenco = await elencaDocumentiRiconoscibili(fascicoloId)
      if (!vivo.current) return
      setDocumenti(elenco)
      setDocumentoId((corrente) => (elenco.some((voce) => voce.id === corrente) ? corrente : elenco[0]?.id || ''))
    } catch (causa) {
      if (vivo.current) setErrore(messaggio(causa, 'Elenco dei documenti non disponibile.'))
    } finally {
      if (vivo.current) setOccupato('')
    }
  }, [fascicoloId])

  useEffect(() => { if (aperto) void caricaDocumenti() }, [aperto, caricaDocumenti])

  const azzera = () => {
    setPagine([]); setBlocchi([]); setFigure([]); setTotale(0); setAvanzamento(''); setAvviso(''); setErrore('')
  }

  const sorgente = (): SorgenteOcr | null => {
    if (scelta === 'file') return file ? { tipo: 'file', file } : null
    return documentoId ? { tipo: 'fascicolo', fascicoloId, documentoId } : null
  }

  const riconosci = async () => {
    const scelto = sorgente()
    if (!scelto) {
      setErrore(scelta === 'file' ? 'Scegli il file da riconoscere.' : 'Scegli il documento del fascicolo da riconoscere.')
      return
    }
    azzera()
    const controllo = new AbortController()
    interruzione.current = controllo
    setRiconoscendo(true)
    setOccupato('Riconoscimento in corso…')
    const lette: PaginaRiconosciuta[] = []
    try {
      let attese = 1
      for (let numero = 1; numero <= attese; numero += 1) {
        if (controllo.signal.aborted) break
        setAvanzamento(`Pagina ${numero}${attese > 1 ? ` di ${attese}` : ''} in lettura…`)
        const esito = await riconosciPagina(scelto, numero, controllo.signal)
        if (!vivo.current) return
        attese = esito.pagineTotali
        lette.push(esito.pagina)
        setNome(esito.nome)
        setTotale(esito.pagineTotali)
        setPagine([...lette])
        setBlocchi((precedenti) => [...precedenti, ...esito.pagina.blocks])
        setFigure((precedenti) => [...precedenti, ...esito.pagina.figures])
        setAvanzamento(`Pagina ${numero} di ${esito.pagineTotali} riconosciuta.`)
      }
      if (!vivo.current) return
      setAvanzamento(
        controllo.signal.aborted
          ? `Riconoscimento interrotto: ${lette.length} ${lette.length === 1 ? 'pagina letta' : 'pagine lette'} su ${attese}.`
          : `Riconoscimento completato: ${lette.length} ${lette.length === 1 ? 'pagina' : 'pagine'}.`,
      )
    } catch (causa) {
      if (!vivo.current) return
      if (controllo.signal.aborted) setAvanzamento(`Riconoscimento interrotto: ${lette.length} ${lette.length === 1 ? 'pagina letta' : 'pagine lette'}.`)
      else setErrore(messaggio(causa, 'Riconoscimento del testo non completato.'))
    } finally {
      interruzione.current = null
      if (vivo.current) { setRiconoscendo(false); setOccupato('') }
    }
  }

  const apriNellEditor = async () => {
    setOccupato('Preparazione del documento per l’editor…')
    setErrore('')
    try {
      const documento = await documentoModificabile(blocksToHtml(blocchi), nome || reference)
      const salvato = await salvaNelFascicolo(fascicoloId, documento)
      onSaved(`${documento.name}: ${salvato.messaggio}`)
      window.location.assign(indirizzoEditor(fascicoloId, salvato.documentoId))
    } catch (causa) {
      if (!vivo.current) return
      const testo = messaggio(causa, 'Documento per l’editor non creato.')
      setErrore(testo); onError(testo)
    } finally {
      if (vivo.current) setOccupato('')
    }
  }

  const copiaTesto = async () => {
    try {
      await navigator.clipboard.writeText(blocksToPlainText(blocchi))
      setAvviso('Testo copiato negli appunti.')
    } catch {
      setErrore('Il browser non ha consentito la copia: seleziona il testo nella revisione e copialo a mano.')
    }
  }

  const scaricaTesto = () => {
    const blob = new Blob([blocksToPlainText(blocchi)], { type: 'text/plain;charset=utf-8' })
    const indirizzo = URL.createObjectURL(blob)
    const collegamento = document.createElement('a')
    collegamento.href = indirizzo
    collegamento.download = `${(nome || 'documento').replace(/\.[^.]+$/, '')} - testo riconosciuto.txt`
    collegamento.click()
    window.setTimeout(() => URL.revokeObjectURL(indirizzo), 2000)
    setAvviso('Testo scaricato sul dispositivo.')
  }

  const salvaCopiaRicercabile = async () => {
    setOccupato('Creazione della copia con testo ricercabile…')
    setErrore('')
    let generato: GeneratedDocument | null = null
    try {
      const filename = nomeCopiaRicercabile(nome || reference)
      if (pagine.length === 1) {
        const blob = pagine[0].pdf
        generato = { blob, filename, objectUrl: URL.createObjectURL(blob), pages: 1, files: 1 }
      } else {
        const file_ = pagine.map((pagina, indice) => new File([pagina.pdf], `pagina-${indice + 1}.pdf`, { type: 'application/pdf' }))
        generato = await generateDocument('merge', file_, filename, [], [])
      }
      const esito = await saveGeneratedDocument(fascicoloId, generato)
      if (!vivo.current) return
      setAvviso(`${generato.filename}: ${esito}`)
      onSaved(esito)
    } catch (causa) {
      if (!vivo.current) return
      const testo = messaggio(causa, 'Copia con testo ricercabile non salvata.')
      setErrore(testo); onError(testo)
    } finally {
      if (generato) URL.revokeObjectURL(generato.objectUrl)
      if (vivo.current) setOccupato('')
    }
  }

  const daOcr = pagine.filter((pagina) => pagina.origine === 'ocr')
  const daTesto = pagine.length - daOcr.length
  const fiducia = daOcr.length ? daOcr.reduce((somma, pagina) => somma + pagina.confidence, 0) / daOcr.length : 0
  const caratteri = countCharacters(blocchi)
  const lavorando = Boolean(occupato)

  if (!aperto) {
    return (
      <section className="iu-fascicolo-ocr iu-fascicolo-ocr--chiuso" aria-label="Riconoscimento del testo dei documenti">
        <div>
          <strong>Riconoscimento del testo</strong>
          <span>Leggi il testo di un documento già nel fascicolo o di un file da caricare: revisione, editor e copia ricercabile.</span>
        </div>
        <Button type="button" tone="neutral" onClick={() => setAperto(true)}><ScanText size={17} aria-hidden="true"/>Riconosci il testo</Button>
      </section>
    )
  }

  return (
    <section className="iu-fascicolo-ocr" aria-label="Riconoscimento del testo dei documenti">
      <header className="iu-fascicolo-ocr__testata">
        <div>
          <h3>Riconoscimento del testo</h3>
          <p>Fascicolo {reference}. Le pagine con testo già presente non vengono riconosciute di nuovo: si legge il testo originale.</p>
        </div>
        <Button type="button" tone="neutral" disabled={lavorando} onClick={() => { interruzione.current?.abort(); azzera(); setAperto(false) }}>
          <X size={16} aria-hidden="true"/>Chiudi
        </Button>
      </header>

      <fieldset className="iu-fascicolo-ocr__sorgente" disabled={lavorando}>
        <legend>Documento da riconoscere</legend>
        <label>
          <input type="radio" name="sorgente-ocr" value="fascicolo" checked={scelta === 'fascicolo'} onChange={() => { setScelta('fascicolo'); azzera() }}/>
          Documento già nel fascicolo
        </label>
        <label>
          <input type="radio" name="sorgente-ocr" value="file" checked={scelta === 'file'} onChange={() => { setScelta('file'); azzera() }}/>
          File dal computer
        </label>
      </fieldset>

      {scelta === 'fascicolo' ? (
        <div className="iu-fascicolo-ocr__scelta">
          <label className="iu-fascicolo-ocr__campo">
            <span>Documento</span>
            <select value={documentoId} disabled={lavorando || !documenti.length} onChange={(evento) => { setDocumentoId(evento.target.value); azzera() }}>
              {documenti.length ? null : <option value="">Nessun documento riconoscibile in questo fascicolo</option>}
              {documenti.map((documento) => <option key={documento.id} value={documento.id}>{etichettaDocumento(documento)}</option>)}
            </select>
          </label>
          <Button type="button" tone="neutral" disabled={lavorando} onClick={() => void caricaDocumenti()}><RefreshCw size={15} aria-hidden="true"/>Aggiorna elenco</Button>
        </div>
      ) : (
        <div className="iu-fascicolo-ocr__scelta">
          <label className="iu-fascicolo-ocr__campo">
            <span>File da riconoscere</span>
            <input
              ref={fileInput}
              type="file"
              accept=".pdf,.p7m,image/jpeg,image/png,image/webp,image/tiff"
              disabled={lavorando}
              onChange={(evento) => { setFile(evento.target.files?.[0] || null); azzera() }}
            />
          </label>
          <small className="iu-acq-hint">PDF, immagini e atti firmati <code>.p7m</code>. Il file non viene salvato nel fascicolo: serve solo a leggerne il testo.</small>
        </div>
      )}

      <div className="iu-fascicolo-ocr__comandi">
        <Button type="button" disabled={lavorando} onClick={() => void riconosci()}><FileSearch size={16} aria-hidden="true"/>Riconosci il testo</Button>
        {riconoscendo ? (
          <Button type="button" tone="neutral" onClick={() => interruzione.current?.abort()}><Square size={15} aria-hidden="true"/>Interrompi</Button>
        ) : null}
      </div>

      {occupato ? <p role="status" aria-live="polite">{occupato}</p> : null}
      {avanzamento ? <p className="iu-acq-status" role="status" aria-live="polite">{avanzamento}</p> : null}
      {errore ? <p role="alert">{errore}</p> : null}
      {avviso ? <p role="status">{avviso}</p> : null}

      {pagine.length ? (
        <>
          <dl className="iu-fascicolo-ocr__riepilogo">
            <div><dt>Pagine lette</dt><dd>{pagine.length}{totale > pagine.length ? ` di ${totale}` : ''}</dd></div>
            <div><dt>Dal testo del documento</dt><dd>{daTesto}</dd></div>
            <div><dt>Con riconoscimento ottico</dt><dd>{daOcr.length}{fiducia ? ` · ${Math.round(fiducia * 100)}% di confidenza` : ''}</dd></div>
            <div><dt>Caratteri riconosciuti</dt><dd>{caratteri.toLocaleString('it-IT')}</dd></div>
          </dl>
          <OcrReview blocks={blocchi} figures={figure} disabled={lavorando} onChange={setBlocchi}/>
          <div className="iu-fascicolo-ocr__comandi">
            <Button type="button" disabled={lavorando || !blocchi.length} onClick={() => void apriNellEditor()}>
              <PenLine size={16} aria-hidden="true"/>Apri nell’editor del fascicolo
            </Button>
            <Button type="button" tone="neutral" disabled={lavorando || !blocchi.length} onClick={() => void copiaTesto()}>
              <ClipboardCheck size={15} aria-hidden="true"/>Copia il testo
            </Button>
            <Button type="button" tone="neutral" disabled={lavorando || !blocchi.length} onClick={scaricaTesto}>
              <Download size={15} aria-hidden="true"/>Scarica il testo
            </Button>
            {daOcr.length ? (
              <Button type="button" tone="neutral" disabled={lavorando} onClick={() => void salvaCopiaRicercabile()}>
                <FileText size={15} aria-hidden="true"/>Salva la copia con testo ricercabile
              </Button>
            ) : null}
          </div>
          <p className="iu-acq-hint">
            «Apri nell’editor» salva nel fascicolo un documento di lavoro con il testo che hai corretto qui e lo apre subito per la modifica.
            La copia con testo ricercabile conserva invece la pagina com’è e vi aggiunge il testo riconosciuto dalla macchina, senza le tue correzioni.
            In nessun caso il documento originale viene modificato o sostituito: la trascrizione è materiale di lavoro, non una copia conforme.
          </p>
        </>
      ) : null}
    </section>
  )
}
