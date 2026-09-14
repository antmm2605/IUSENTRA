import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Check, FileSearch, FileText, FolderOpen, Laptop, Square, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import { blocksToHtml, countCharacters, type OcrBlock, type OcrFigure } from '../documentCapture/ocrBlocks'
import { OcrReview } from '../documentCapture/OcrReview'
import { OcrPageViewer } from '../documentCapture/OcrPageViewer'
import { MatterPicker } from '../documentCapture/MatterPicker'
import {
  documentoModificabile,
  etichettaCorrezione,
  indirizzoEditor,
  riconosciPagina,
  salvaNelFascicolo,
  scaricaSulComputer,
  type FormatoDocumento,
  type PaginaRiconosciuta,
} from '../../services/documentoOcr'
import { generateDocument } from '../../documentToolsData'
import '../documentCapture/acquisition.css'
import '../documentCapture/fascicoloOcr.css'
import './OcrDocumentoTool.css'

type Destinazione = 'computer' | 'fascicolo'

const IMMAGINI = /\.(jpe?g|png|webp|tiff?|bmp)$/i
/** Pagine lette insieme: il server ne accetta due per volta senza rallentare le altre richieste. */
const PAGINE_IN_PARALLELO = 2

function messaggio(errore: unknown, ripiego: string): string {
  return errore instanceof Error && errore.message ? errore.message : ripiego
}

function nomeSenzaEstensione(nome: string): string {
  return nome.replace(/\.[^.]+$/, '') || 'documento'
}

/**
 * Da scansione a Word o PDF: la utility della suite Strumenti forensi.
 *
 * Il percorso e' dichiarato passo per passo: si sceglie il file (immagini o
 * PDF), si decide dove andra' il risultato (sul computer o nel fascicolo di un
 * cliente, cercato per nome e cognome e mostrato con il suo stato), si legge
 * il testo con il motore OCR dello studio, lo si controlla accanto alla pagina
 * e lo si corregge, e solo alla fine si conferma il formato (Word o PDF) e il
 * salvataggio. Nessun documento entra nel fascicolo senza la conferma.
 */
export default function OcrDocumentoTool() {
  const [files, setFiles] = useState<File[]>([])
  const [destinazione, setDestinazione] = useState<Destinazione>('computer')
  const [fascicoloId, setFascicoloId] = useState('')
  const [fascicoloEtichetta, setFascicoloEtichetta] = useState('')
  const [nome, setNome] = useState('')
  const [pagine, setPagine] = useState<PaginaRiconosciuta[]>([])
  const [paginaAttiva, setPaginaAttiva] = useState(1)
  const [sovrapposizione, setSovrapposizione] = useState(true)
  const [selezionato, setSelezionato] = useState('')
  const [totale, setTotale] = useState(0)
  const [blocchi, setBlocchi] = useState<OcrBlock[]>([])
  const [figure, setFigure] = useState<OcrFigure[]>([])
  const [avanzamento, setAvanzamento] = useState('')
  const [occupato, setOccupato] = useState('')
  const [riconoscendo, setRiconoscendo] = useState(false)
  const [errore, setErrore] = useState('')
  const [avviso, setAvviso] = useState('')
  const [formato, setFormato] = useState<FormatoDocumento>('docx')
  const [confermaAperta, setConfermaAperta] = useState(false)
  const [esitoSalvataggio, setEsitoSalvataggio] = useState<{ testo: string; href?: string } | null>(null)
  const vivo = useRef(true)
  const interruzione = useRef<AbortController | null>(null)

  useEffect(() => () => { vivo.current = false; interruzione.current?.abort() }, [])

  const azzera = useCallback(() => {
    setPagine([]); setBlocchi([]); setFigure([]); setTotale(0); setPaginaAttiva(1); setSelezionato('')
    setAvanzamento(''); setAvviso(''); setErrore(''); setConfermaAperta(false); setEsitoSalvataggio(null)
  }, [])

  /** Il file da leggere: piu' immagini diventano un solo PDF multipagina. */
  const sorgente = async (): Promise<File> => {
    if (!files.length) throw new Error('Scegli il file da convertire.')
    if (files.length === 1) return files[0]
    if (!files.every((file) => IMMAGINI.test(file.name))) throw new Error('Più file insieme solo se sono immagini: per i PDF convertine uno alla volta.')
    const unito = await generateDocument('multipage', files, nomeSenzaEstensione(files[0].name), [], files.map(() => 0), 'a4')
    return new File([unito.blob], unito.filename, { type: 'application/pdf' })
  }

  const riconosci = async () => {
    azzera()
    if (destinazione === 'fascicolo' && !fascicoloId) {
      setErrore('Scegli il fascicolo del cliente in cui salvare il documento, oppure salva sul computer.')
      return
    }
    const controllo = new AbortController()
    interruzione.current = controllo
    setRiconoscendo(true)
    setOccupato('Preparazione del documento…')
    const lette = new Map<number, PaginaRiconosciuta>()
    try {
      const file = await sorgente()
      setNome(file.name)
      setOccupato('Riconoscimento in corso…')
      const prima = await riconosciPagina({ tipo: 'file', file }, 1, controllo.signal)
      if (!vivo.current) return
      lette.set(1, prima.pagina)
      setTotale(prima.pagineTotali)
      const pubblica = () => {
        const ordinate = [...lette.values()].sort((a, b) => a.numero - b.numero)
        setPagine(ordinate)
        setBlocchi(ordinate.flatMap((pagina) => pagina.blocks))
        setFigure(ordinate.flatMap((pagina) => pagina.figures))
      }
      pubblica()
      setAvanzamento(`Pagina 1 di ${prima.pagineTotali} riconosciuta.`)
      let prossima = 2
      const lettore = async () => {
        while (prossima <= prima.pagineTotali && !controllo.signal.aborted) {
          const numero = prossima
          prossima += 1
          const esito = await riconosciPagina({ tipo: 'file', file }, numero, controllo.signal)
          if (!vivo.current) return
          lette.set(numero, esito.pagina)
          pubblica()
          setAvanzamento(`Pagina ${lette.size} di ${prima.pagineTotali} riconosciuta.`)
        }
      }
      await Promise.all(Array.from({ length: Math.min(PAGINE_IN_PARALLELO, Math.max(0, prima.pagineTotali - 1)) }, () => lettore()))
      if (!vivo.current) return
      setAvanzamento(
        controllo.signal.aborted
          ? `Riconoscimento interrotto: ${lette.size} ${lette.size === 1 ? 'pagina letta' : 'pagine lette'} su ${prima.pagineTotali}.`
          : `Riconoscimento completato: ${lette.size} ${lette.size === 1 ? 'pagina' : 'pagine'}.`,
      )
    } catch (causa) {
      if (!vivo.current) return
      if (controllo.signal.aborted) setAvanzamento(`Riconoscimento interrotto: ${lette.size} ${lette.size === 1 ? 'pagina letta' : 'pagine lette'}.`)
      else setErrore(messaggio(causa, 'Riconoscimento del testo non completato.'))
    } finally {
      interruzione.current = null
      if (vivo.current) { setRiconoscendo(false); setOccupato('') }
    }
  }

  const salva = async () => {
    setConfermaAperta(false)
    setErrore(''); setAvviso('')
    setOccupato(formato === 'pdf' ? 'Preparazione del PDF…' : 'Preparazione del documento Word…')
    try {
      const documento = await documentoModificabile(blocksToHtml(blocchi), nome || 'documento', formato)
      if (destinazione === 'computer') {
        scaricaSulComputer(documento, documento.name)
        if (vivo.current) setEsitoSalvataggio({ testo: `${documento.name} scaricato sul computer.` })
        return
      }
      const salvato = await salvaNelFascicolo(fascicoloId, documento)
      if (!vivo.current) return
      setEsitoSalvataggio({
        testo: `${documento.name} salvato nel fascicolo ${fascicoloEtichetta || fascicoloId}: ${salvato.messaggio}`,
        href: formato === 'docx' ? indirizzoEditor(fascicoloId, salvato.documentoId) : `/fascicoli/${encodeURIComponent(fascicoloId)}`,
      })
    } catch (causa) {
      if (vivo.current) setErrore(messaggio(causa, 'Salvataggio non completato.'))
    } finally {
      if (vivo.current) setOccupato('')
    }
  }

  const daOcr = useMemo(() => pagine.filter((pagina) => pagina.origine === 'ocr'), [pagine])
  const correzioni = useMemo(() => {
    const somma = new Map<string, { occorrenze: number; etichetta: string }>()
    for (const pagina of pagine) {
      for (const voce of pagina.correzioni) {
        const corrente = somma.get(voce.regola)
        somma.set(voce.regola, { occorrenze: (corrente?.occorrenze || 0) + voce.occorrenze, etichetta: voce.etichetta || corrente?.etichetta || '' })
      }
    }
    return [...somma.entries()].map(([regola, voce]) => ({ regola, ...voce }))
  }, [pagine])
  const consenso = useMemo(() => pagine.reduce((somma, pagina) => somma + pagina.consenso, 0), [pagine])
  const secondoLettore = useMemo(() => pagine.find((pagina) => pagina.secondoLettore)?.secondoLettore || '', [pagine])
  const caratteri = countCharacters(blocchi)
  const lavorando = Boolean(occupato)
  const fiducia = daOcr.length ? daOcr.reduce((somma, pagina) => somma + pagina.confidence, 0) / daOcr.length : 0
  const passo = esitoSalvataggio ? 5 : pagine.length ? 3 : files.length ? 2 : 1

  return (
    <section className="iu-ocr-tool" aria-label="Da scansione a Word o PDF">
      <p className="iu-ocr-tool__intro">
        Immagini e PDF letti dal motore OCR dello studio: il testo conserva titoli, capoversi, elenchi e tabelle; le
        forme forensi (art., c.p.c., D.Lgs., R.G., €, accenti) vengono corrette e dichiarate. Tu controlli il testo
        accanto alla pagina, poi scegli se salvarlo in Word o in PDF, sul computer o nel fascicolo del cliente.
      </p>

      <ol className="iu-ocr-passi">
        <li className={passo > 1 ? 'is-fatto' : 'is-corrente'}>1. File</li>
        <li className={passo > 2 ? 'is-fatto' : passo === 2 ? 'is-corrente' : ''}>2. Destinazione</li>
        <li className={passo > 3 ? 'is-fatto' : passo === 3 ? 'is-corrente' : ''}>3. Lettura e correzione</li>
        <li className={passo === 5 ? 'is-fatto' : passo === 3 ? 'is-corrente' : ''}>4. Formato e conferma</li>
      </ol>

      <div className="iu-fascicolo-ocr__scelta">
        <label className="iu-fascicolo-ocr__campo">
          <span>File da convertire (immagini o PDF)</span>
          <input
            type="file"
            multiple
            accept=".pdf,.p7m,image/jpeg,image/png,image/webp,image/tiff"
            disabled={lavorando}
            onChange={(evento) => { setFiles(Array.from(evento.target.files || [])); azzera() }}
          />
        </label>
        <small className="iu-acq-hint">
          Un PDF, un&apos;immagine o piu&#768; immagini della stessa scansione (diventano un solo documento). Il file non
          viene conservato: serve solo a leggerne il testo.
        </small>
      </div>

      <fieldset className="iu-fascicolo-ocr__sorgente" disabled={lavorando}>
        <legend>Dove salvare il risultato</legend>
        <label>
          <input type="radio" name="destinazione-ocr" value="computer" checked={destinazione === 'computer'} onChange={() => { setDestinazione('computer'); setEsitoSalvataggio(null) }} />
          <Laptop size={15} aria-hidden="true" /> Sul mio computer
        </label>
        <label>
          <input type="radio" name="destinazione-ocr" value="fascicolo" checked={destinazione === 'fascicolo'} onChange={() => { setDestinazione('fascicolo'); setEsitoSalvataggio(null) }} />
          <FolderOpen size={15} aria-hidden="true" /> Nel fascicolo di un cliente
        </label>
      </fieldset>

      {destinazione === 'fascicolo' ? (
        <div className="iu-ocr-tool__fascicolo">
          <MatterPicker
            matters={[]}
            value={fascicoloId}
            disabled={lavorando}
            onChange={(id, etichetta) => { setFascicoloId(id); setFascicoloEtichetta(etichetta); setEsitoSalvataggio(null) }}
          />
        </div>
      ) : null}

      <div className="iu-fascicolo-ocr__comandi">
        <Button type="button" disabled={lavorando || !files.length} onClick={() => void riconosci()}>
          <FileSearch size={16} aria-hidden="true" />Leggi il testo
        </Button>
        {riconoscendo ? (
          <Button type="button" tone="neutral" onClick={() => interruzione.current?.abort()}><Square size={15} aria-hidden="true" />Interrompi</Button>
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
            <div><dt>Dal testo del documento</dt><dd>{pagine.length - daOcr.length}</dd></div>
            <div><dt>Con riconoscimento ottico</dt><dd>{daOcr.length}{fiducia ? ` · ${Math.round(fiducia * 100)}%` : ''}</dd></div>
            <div><dt>Caratteri riconosciuti</dt><dd>{caratteri.toLocaleString('it-IT')}</dd></div>
            {secondoLettore ? <div><dt>Secondo lettore</dt><dd>{consenso ? `${consenso} ${consenso === 1 ? 'parola confermata' : 'parole confermate'}` : 'in accordo'}</dd></div> : null}
          </dl>
          {correzioni.length ? (
            <p className="iu-acq-hint">
              Correzioni del formulario legale applicate: {correzioni.map((voce) => `${etichettaCorrezione(voce)} (${voce.occorrenze})`).join(', ')}.
            </p>
          ) : null}

          <div className="iu-ocr-affiancato">
            <OcrPageViewer
              pagine={pagine}
              paginaAttiva={paginaAttiva}
              onPagina={setPaginaAttiva}
              blocchi={blocchi}
              selezionato={selezionato}
              onSeleziona={setSelezionato}
              sovrapposizione={sovrapposizione}
              onSovrapposizione={setSovrapposizione}
            />
            <div className="iu-ocr-affiancato__testo">
              <OcrReview blocks={blocchi} figures={figure} disabled={lavorando} onChange={setBlocchi} selectedId={selezionato} onSelect={setSelezionato} />
            </div>
          </div>

          <section className="iu-ocr-tool__formato" aria-label="Formato e conferma">
            <h4>In che formato salvare</h4>
            <div className="iu-ocr-tool__formati">
              <label>
                <input type="radio" name="formato-ocr" value="docx" checked={formato === 'docx'} onChange={() => setFormato('docx')} disabled={lavorando} />
                <FileText size={15} aria-hidden="true" /> Documento Word (modificabile)
              </label>
              <label>
                <input type="radio" name="formato-ocr" value="pdf" checked={formato === 'pdf'} onChange={() => setFormato('pdf')} disabled={lavorando} />
                <FileText size={15} aria-hidden="true" /> PDF del testo corretto
              </label>
            </div>
            {!confermaAperta ? (
              <Button type="button" disabled={lavorando || !blocchi.length || (destinazione === 'fascicolo' && !fascicoloId)} onClick={() => setConfermaAperta(true)}>
                <Check size={15} aria-hidden="true" />
                {destinazione === 'fascicolo' ? 'Salva nel fascicolo' : 'Salva sul computer'}
              </Button>
            ) : (
              <div className="iu-ocr-tool__conferma" role="dialog" aria-label="Conferma del salvataggio">
                <p>
                  Salvare <strong>{nomeSenzaEstensione(nome || 'documento')}</strong> come{' '}
                  <strong>{formato === 'pdf' ? 'PDF' : 'documento Word'}</strong>{' '}
                  {destinazione === 'fascicolo' ? <>nel fascicolo <strong>{fascicoloEtichetta || fascicoloId}</strong></> : 'sul tuo computer'}?
                </p>
                <div className="iu-ocr-tool__conferma-azioni">
                  <Button type="button" onClick={() => void salva()}><Check size={15} aria-hidden="true" />Conferma</Button>
                  <Button type="button" tone="neutral" onClick={() => setConfermaAperta(false)}><X size={15} aria-hidden="true" />Annulla</Button>
                </div>
              </div>
            )}
            {esitoSalvataggio ? (
              <p className="iu-ocr-tool__esito" role="status">
                {esitoSalvataggio.testo}
                {esitoSalvataggio.href ? <> <a href={esitoSalvataggio.href}>{formato === 'docx' ? 'Apri nell’editor' : 'Apri il fascicolo'}</a></> : null}
              </p>
            ) : null}
          </section>

          <p className="iu-acq-hint">
            L&apos;originale non viene modificato ne&#768; sostituito: la copia per immagine resta l&apos;atto che fa fede
            (D.Lgs. 82/2005, art. 22) e il testo riconosciuto e&#768; materiale di lavoro, non una copia conforme.
          </p>
        </>
      ) : null}
    </section>
  )
}
