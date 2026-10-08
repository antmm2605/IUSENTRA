import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { FileSearch, RefreshCw, ScanText, Square, X } from 'lucide-react'
import { Button } from '../../ui/Button'
import {
  blocksToPlainText,
  countCharacters,
  type OcrBlock,
  type OcrFigure,
} from './ocrBlocks'
import { convertiDocumentoOcr, leggiDocumentoOcr } from './ocrDocumento'
import { OcrConfronto } from './OcrConfronto'
import { OcrSaveChoices, type DaStampare, type DestinazioneOcr, type FormatoSalvataggio } from './OcrSaveChoices'
import { pdfOriginale, stampaPdf } from './ocrStampa'
import {
  elencaDocumentiRiconoscibili,
  indirizzoEditor,
  nomeCopiaRicercabile,
  nomeFileRiconosciuto,
  salvaNelFascicolo,
  scaricaSulComputer,
  etichettaCorrezione,
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
 * Il percorso è sempre lo stesso, e dichiarato: si sceglie il documento, si
 * legge, si controlla il testo accanto alla pagina, si decide dove salvarlo.
 * Nessun passaggio avviene da solo, perché ogni esito — un documento nuovo nel
 * fascicolo di un cliente, un file sul computer dell'avvocato — è una decisione
 * sua e non una conseguenza automatica del riconoscimento.
 *
 * Le pagine che hanno già un livello di testo non vengono riconosciute di
 * nuovo: si legge quello, che è il testo esatto dell'autore, e il motore ottico
 * resta per le pagine che sono immagini.
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
    setPagine([]); setBlocchi([]); setFigure([]); setTotale(0)
    setAvanzamento(''); setAvviso(''); setErrore('')
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
    let attese = 1
    try {
      await leggiDocumentoOcr(scelto, controllo.signal, (ordinate, totale, nomeDocumento) => {
        if (!vivo.current) return
        attese = totale
        lette.splice(0, lette.length, ...ordinate)
        setNome(nomeDocumento); setTotale(totale); setPagine(ordinate)
        setBlocchi(ordinate.flatMap((pagina) => pagina.blocks))
        setFigure(ordinate.flatMap((pagina) => pagina.figures))
        setAvanzamento(`Pagina ${ordinate.length} di ${totale} riconosciuta.`)
      })
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

  const daOcr = useMemo(() => pagine.filter((pagina) => pagina.origine === 'ocr'), [pagine])
  const correzioni = useMemo(() => {
    const somma = new Map<string, number>()
    for (const pagina of pagine) {
      for (const voce of pagina.correzioni) somma.set(voce.regola, (somma.get(voce.regola) || 0) + voce.occorrenze)
    }
    const etichette = new Map<string, string>()
    for (const pagina of pagine) for (const voce of pagina.correzioni) if (voce.etichetta) etichette.set(voce.regola, voce.etichetta)
    return [...somma.entries()].map(([regola, occorrenze]) => ({ regola, occorrenze, etichetta: etichette.get(regola) || '' }))
  }, [pagine])
  const consenso = useMemo(() => pagine.reduce((somma, pagina) => somma + pagina.consenso, 0), [pagine])

  const secondoLettore = useMemo(() => pagine.find((pagina) => pagina.secondoLettore)?.secondoLettore || '', [pagine])

  /** Il documento riveduto, con le correzioni: Word modificabile o PDF impaginato. */
  const documentoRiveduto = async (formato: FormatoSalvataggio, download = false): Promise<File> => {
    return convertiDocumentoOcr({ pagine, totale, blocchi, nome: nome || reference, formato, download,
      originale: () => pdfOriginale(sorgente(), async () => { throw new Error('Non è stato possibile leggere il PDF originale per la conversione. Riprova.') }),
    })
  }

  const copiaRicercabile = async (): Promise<GeneratedDocument> => {
    const filename = nomeCopiaRicercabile(nome || reference)
    if (pagine.length === 1) {
      const blob = pagine[0].pdf
      return { blob, filename, objectUrl: URL.createObjectURL(blob), pages: 1, files: 1 }
    }
    const file_ = pagine.map((pagina, indice) => new File([pagina.pdf], `pagina-${indice + 1}.pdf`, { type: 'application/pdf' }))
    return generateDocument('merge', file_, filename, [], [])
  }

  const attesaDi = (destinazione: DestinazioneOcr): string => {
    if (destinazione.tipo === 'editor') return 'Preparazione del documento per l’editor…'
    if (destinazione.tipo === 'ricercabile') return 'Creazione della copia con testo ricercabile…'
    if (destinazione.tipo === 'testo') return 'Preparazione del testo…'
    const formato = destinazione.formato === 'pdf' ? 'PDF' : 'Word'
    return destinazione.dove === 'fascicolo' ? `Salvataggio del documento ${formato} nel fascicolo…` : `Preparazione del documento ${formato}…`
  }

  const salva = async (destinazione: DestinazioneOcr) => {
    setErrore(''); setAvviso('')
    setOccupato(attesaDi(destinazione))
    let generato: GeneratedDocument | null = null
    try {
      if (destinazione.tipo === 'editor' || (destinazione.tipo === 'documento' && destinazione.dove === 'fascicolo')) {
        const documento = await documentoRiveduto(destinazione.tipo === 'editor' ? 'docx' : destinazione.formato)
        const salvato = await salvaNelFascicolo(fascicoloId, documento)
        onSaved(`${documento.name}: ${salvato.messaggio}`)
        if (destinazione.tipo === 'editor') {
          window.location.assign(indirizzoEditor(fascicoloId, salvato.documentoId))
          return
        }
        if (vivo.current) setAvviso(`${documento.name} salvato nei documenti del fascicolo.`)
        return
      }
      if (destinazione.tipo === 'documento') {
        const documento = await documentoRiveduto(destinazione.formato, true)
        scaricaSulComputer(documento, documento.name)
        if (vivo.current) setAvviso(`Download avviato: ${documento.name}.`)
        return
      }
      if (destinazione.tipo === 'ricercabile') {
        generato = await copiaRicercabile()
        if (destinazione.dove === 'fascicolo') {
          const esito = await saveGeneratedDocument(fascicoloId, generato)
          if (!vivo.current) return
          setAvviso(`${generato.filename}: ${esito}`)
          onSaved(esito)
          return
        }
        scaricaSulComputer(generato.blob, generato.filename)
        if (vivo.current) setAvviso(`${generato.filename} scaricato sul dispositivo.`)
        return
      }
      const nomeTesto = nomeFileRiconosciuto(nome || reference, 'txt')
      scaricaSulComputer(new Blob([blocksToPlainText(blocchi)], { type: 'text/plain;charset=utf-8' }), nomeTesto)
      if (vivo.current) setAvviso(`${nomeTesto} scaricato sul dispositivo.`)
    } catch (causa) {
      if (!vivo.current) return
      const testo = messaggio(causa, 'Operazione non completata.')
      setErrore(testo); onError(testo)
    } finally {
      if (generato) URL.revokeObjectURL(generato.objectUrl)
      if (vivo.current) setOccupato('')
    }
  }

  /** Stampa il PDF nativo (l'atto che fa fede) o il documento modificato in revisione. */
  const stampa = async (quale: DaStampare) => {
    setErrore(''); setAvviso('')
    setOccupato(quale === 'originale' ? 'Preparazione del PDF originale per la stampa…' : 'Preparazione del documento modificato per la stampa…')
    try {
      const pdf = quale === 'modificato'
        ? await documentoRiveduto('pdf')
        : await pdfOriginale(sorgente(), async () => {
          const copia = await copiaRicercabile()
          URL.revokeObjectURL(copia.objectUrl)
          return copia.blob
        })
      stampaPdf(pdf)
      if (vivo.current) setAvviso(quale === 'originale' ? 'PDF originale inviato alla stampa.' : 'Documento modificato inviato alla stampa.')
    } catch (causa) {
      if (!vivo.current) return
      const testo = messaggio(causa, 'Stampa non preparata.')
      setErrore(testo); onError(testo)
    } finally {
      if (vivo.current) setOccupato('')
    }
  }

  const caratteri = countCharacters(blocchi)
  const lavorando = Boolean(occupato)
  const fiducia = daOcr.length ? daOcr.reduce((somma, pagina) => somma + pagina.confidence, 0) / daOcr.length : 0

  if (!aperto) {
    return (
      <section className="iu-fascicolo-ocr iu-fascicolo-ocr--chiuso" aria-label="Riconoscimento del testo dei documenti">
        <div>
          <strong>Riconoscimento del testo</strong>
          <span>Leggi il testo di un documento del fascicolo o di un file: pagina e testo affiancati, formato conservato, poi scegli dove salvarlo.</span>
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
          <p>Fascicolo {reference}. Scegli il documento, controlla il testo accanto alla pagina, decidi dove salvarlo.</p>
        </div>
        <Button type="button" tone="neutral" disabled={lavorando} onClick={() => { interruzione.current?.abort(); azzera(); setAperto(false) }}>
          <X size={16} aria-hidden="true"/>Chiudi
        </Button>
      </header>

      <ol className="iu-ocr-passi">
        <li className={pagine.length ? 'is-fatto' : 'is-corrente'}>1. Documento</li>
        <li className={pagine.length ? 'is-corrente' : ''}>2. Controllo e correzione</li>
        <li className={pagine.length ? 'is-corrente' : ''}>3. Salvataggio</li>
      </ol>

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
              type="file"
              accept=".pdf,.p7m,image/jpeg,image/png,image/webp,image/tiff"
              disabled={lavorando}
              onChange={(evento) => { setFile(evento.target.files?.[0] || null); azzera() }}
            />
          </label>
          <small className="iu-acq-hint">PDF, immagini e atti firmati <code>.p7m</code>. Il file non entra nel fascicolo: serve solo a leggerne il testo.</small>
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
            <div><dt>Dal testo del documento</dt><dd>{pagine.length - daOcr.length}</dd></div>
            <div><dt>Con riconoscimento ottico</dt><dd>{daOcr.length}{fiducia ? ` · ${Math.round(fiducia * 100)}%` : ''}</dd></div>
            <div><dt>Caratteri riconosciuti</dt><dd>{caratteri.toLocaleString('it-IT')}</dd></div>
            {secondoLettore ? <div><dt>Secondo lettore</dt><dd>{consenso ? `${consenso} ${consenso === 1 ? 'parola riletta nel confronto' : 'parole rilette nel confronto'}` : 'Confronto eseguito'}</dd></div> : null}
          </dl>

          {correzioni.length ? (
            <p className="iu-acq-hint">
              Correzioni del formulario legale applicate automaticamente: {correzioni.map((voce) => `${etichettaCorrezione(voce)} (${voce.occorrenze})`).join(', ')}.
            </p>
          ) : null}

          <OcrConfronto pagine={pagine} blocchi={blocchi} figure={figure}
            disabled={lavorando} onChange={setBlocchi} esito={occupato || errore || avviso}
            errore={Boolean(errore)}
            azioni={(
              <OcrSaveChoices disabled={lavorando || !blocchi.length}
                copiaRicercabileDisponibile={daOcr.length > 0}
                onScegli={(destinazione) => void salva(destinazione)}
                onStampa={(quale) => void stampa(quale)} />
            )} />

          <p className="iu-acq-hint">
            Il documento originale non viene mai modificato né sostituito: la copia per immagine resta l’atto che fa fede
            (D.Lgs. 82/2005, art. 22) e il testo riconosciuto è materiale di lavoro, non una copia conforme.
          </p>
        </>
      ) : null}
    </section>
  )
}
