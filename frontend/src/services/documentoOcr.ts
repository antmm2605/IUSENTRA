/**
 * Riconoscimento del testo di un documento del fascicolo o di un file caricato.
 *
 * Una richiesta per pagina: l'atto puo' avere decine di pagine e l'avvocato deve
 * vedere l'avanzamento e potersi fermare appena ha quello che gli serve, invece
 * di attendere una risposta unica che rischia di scadere.
 *
 * Il server risponde con la struttura della pagina (titoli, capoversi, elenchi,
 * tabelle) e con il PDF ricercabile della sola pagina: niente viene salvato
 * finche' l'avvocato non lo chiede.
 */
import { csrfHeader } from '../api/csrf'
import { parseBlocks, parseFigures, type OcrBlock, type OcrFigure } from '../components/documentCapture/ocrBlocks'
import { pdfBlobFromBase64 } from './documentOcr'

export type OrigineTesto = 'testo' | 'ocr'

export type DocumentoRiconoscibile = {
  id: string
  nome: string
  formato: string
  sezione: string
  tipo: string
  data: string
  dimensione: string
  firmato: boolean
}

/** Immagine della pagina da affiancare al testo, con la scala dei riquadri. */
export type AnteprimaPagina = {
  url: string
  larghezza: number
  altezza: number
  scala: number
}

export type CorrezioneApplicata = { regola: string; occorrenze: number }

export type RiferimentiPagina = {
  numeroRuolo: string[]
  uffici: string[]
  date: string[]
  importi: string[]
}

export type PaginaRiconosciuta = {
  numero: number
  origine: OrigineTesto
  origineEtichetta: string
  pdf: Blob
  paragraphs: string[]
  characters: number
  blocks: OcrBlock[]
  figures: OcrFigure[]
  confidence: number
  engine: string
  anteprima: AnteprimaPagina | null
  correzioni: CorrezioneApplicata[]
  riferimenti: RiferimentiPagina
}

/** Nome leggibile delle regole di correzione forense applicate dal server. */
export const ETICHETTE_CORREZIONI: Record<string, string> = {
  'punct.art.v1': 'spaziatura di «art.»',
  'punct.n.v1': 'spaziatura di «N.»',
  'ocr.rg.zero.v1': 'numero di ruolo letto male',
  'space.pec.v1': 'spazi nell\'indirizzo PEC',
}

export type EsitoPagina = { nome: string; pagineTotali: number; pagina: PaginaRiconosciuta }

export type SorgenteOcr =
  | { tipo: 'fascicolo'; fascicoloId: string; documentoId: string }
  | { tipo: 'file'; file: File }

type Payload = {
  ok?: boolean
  message?: string
  nome?: string
  pagine_totali?: number
  documents?: unknown
  pagina?: Record<string, unknown>
}

async function leggiPayload(response: Response): Promise<Payload> {
  const payload = (await response.json().catch(() => null)) as Payload | null
  if (!response.ok || !payload?.ok) {
    throw new Error(payload?.message || 'Riconoscimento del testo non completato. Riprova tra qualche istante.')
  }
  return payload
}

/** Documenti del fascicolo su cui il riconoscimento puo' lavorare. */
export async function elencaDocumentiRiconoscibili(fascicoloId: string, signal?: AbortSignal): Promise<DocumentoRiconoscibile[]> {
  const response = await fetch(`/api/v1/ui/document-tools/fascicoli/${encodeURIComponent(fascicoloId)}/documenti-riconoscibili`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
    signal,
  })
  const payload = await leggiPayload(response)
  if (!Array.isArray(payload.documents)) return []
  return payload.documents.flatMap((raw) => {
    const voce = (raw ?? {}) as Record<string, unknown>
    const id = String(voce.id ?? '').trim()
    if (!id) return []
    return [{
      id,
      nome: String(voce.nome ?? '').trim() || 'Documento',
      formato: String(voce.formato ?? '').trim(),
      sezione: String(voce.sezione ?? '').trim(),
      tipo: String(voce.tipo ?? '').trim(),
      data: String(voce.data ?? '').trim(),
      dimensione: String(voce.dimensione ?? '').trim(),
      firmato: Boolean(voce.firmato),
    }]
  })
}

function anteprimaDaPayload(value: unknown): AnteprimaPagina | null {
  if (!value || typeof value !== 'object') return null
  const voce = value as Record<string, unknown>
  const codificato = String(voce.immagine_base64 ?? '')
  if (!codificato) return null
  const tipo = String(voce.tipo ?? 'image/jpeg')
  return {
    url: `data:${tipo};base64,${codificato}`,
    larghezza: Number(voce.larghezza ?? 0) || 0,
    altezza: Number(voce.altezza ?? 0) || 0,
    scala: Number(voce.scala ?? 1) || 1,
  }
}

function testiDaPayload(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? '').trim()).filter(Boolean) : []
}

function correzioniDaPayload(value: unknown): CorrezioneApplicata[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((raw) => {
    const voce = (raw ?? {}) as Record<string, unknown>
    const regola = String(voce.regola ?? '').trim()
    if (!regola) return []
    return [{ regola, occorrenze: Number(voce.occorrenze ?? 0) || 0 }]
  })
}

function riferimentiDaPayload(value: unknown): RiferimentiPagina {
  const voce = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  return {
    numeroRuolo: testiDaPayload(voce.numero_ruolo),
    uffici: testiDaPayload(voce.uffici),
    date: testiDaPayload(voce.date),
    importi: testiDaPayload(voce.importi),
  }
}

function paginaDaPayload(raw: Record<string, unknown> | undefined, richiesta: number): PaginaRiconosciuta {
  const voce = raw ?? {}
  const codificato = String(voce.pdf_base64 ?? '')
  if (!codificato) throw new Error('La pagina riconosciuta non è leggibile. Riprova.')
  const numero = Number(voce.numero ?? richiesta) || richiesta
  const origine: OrigineTesto = String(voce.origine ?? '') === 'testo' ? 'testo' : 'ocr'
  const paragraphs = Array.isArray(voce.paragraphs)
    ? voce.paragraphs.map((item) => String(item ?? '').trim()).filter(Boolean)
    : []
  return {
    numero,
    origine,
    origineEtichetta: String(voce.origine_etichetta ?? '') || (origine === 'testo' ? 'testo già presente nel documento' : 'riconoscimento ottico (OCR)'),
    pdf: pdfBlobFromBase64(codificato),
    paragraphs,
    characters: Number(voce.characters ?? 0) || 0,
    blocks: parseBlocks(voce.blocks, numero),
    figures: parseFigures(voce.figures, numero),
    confidence: Number(voce.confidence ?? 0) || 0,
    engine: String(voce.engine ?? ''),
    anteprima: anteprimaDaPayload(voce.anteprima),
    correzioni: correzioniDaPayload(voce.correzioni),
    riferimenti: riferimentiDaPayload(voce.riferimenti),
  }
}

/** Riconosce la pagina richiesta e dice quante pagine ha il documento. */
export async function riconosciPagina(sorgente: SorgenteOcr, pagina: number, signal?: AbortSignal): Promise<EsitoPagina> {
  const body = new FormData()
  body.append('pagina', String(Math.max(1, Math.trunc(pagina))))
  if (sorgente.tipo === 'fascicolo') {
    body.append('fascicolo_id', sorgente.fascicoloId)
    body.append('documento_id', sorgente.documentoId)
  } else {
    body.append('file', sorgente.file, sorgente.file.name)
  }
  const response = await fetch('/api/v1/ui/document-tools/ocr-documento', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...csrfHeader() },
    body,
    signal,
  })
  const payload = await leggiPayload(response)
  return {
    nome: String(payload.nome ?? '').trim() || 'documento',
    pagineTotali: Math.max(1, Number(payload.pagine_totali ?? 1) || 1),
    pagina: paginaDaPayload(payload.pagina, pagina),
  }
}

/** Nome del PDF con testo ricercabile: copia in più, mai il posto dell'originale. */
export function nomeCopiaRicercabile(nome: string): string {
  const gambo = String(nome || '')
    .replace(/\.[^.]+$/, '')
    .replace(/[\\/:*?"<>|\x00-\x1f]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return `${(gambo || 'documento').slice(0, 100)} - testo ricercabile.pdf`
}

/** Il testo riconosciuto e corretto, come documento `.docx` pronto per l'editor. */
export async function documentoModificabile(html: string, nome: string): Promise<File> {
  const body = new FormData()
  body.append('html', html)
  body.append('nome', nome)
  const response = await fetch('/api/v1/ui/document-tools/documento-testo-riconosciuto', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { ...csrfHeader() },
    body,
  })
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as Payload | null
    throw new Error(payload?.message || 'Il testo riconosciuto non è stato trasformato in documento. Riprova.')
  }
  const blob = await response.blob()
  const intestazione = response.headers.get('Content-Disposition') || ''
  const dichiarato = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(intestazione)?.[1]
  const nomeFile = decodeURIComponent(dichiarato || '') || 'testo riconosciuto.docx'
  return new File([blob], nomeFile, { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' })
}

type SalvataggioPayload = { ok?: boolean; documento_id?: string; message?: string; messaggio?: string }

/** Salva un documento nel fascicolo e restituisce l'identificativo creato. */
export async function salvaNelFascicolo(fascicoloId: string, file: File): Promise<{ documentoId: string; messaggio: string }> {
  const body = new FormData()
  body.append('files', file, file.name)
  body.append('classificazione_modalita', 'automatica')
  const response = await fetch(`/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/carica`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...csrfHeader() },
    body,
  })
  const payload = (await response.json().catch(() => null)) as SalvataggioPayload | null
  if (!response.ok || payload?.ok !== true || !payload.documento_id) {
    throw new Error(payload?.message || payload?.messaggio || 'Salvataggio non confermato. Controlla i documenti del fascicolo prima di riprovare.')
  }
  return { documentoId: String(payload.documento_id), messaggio: payload.message || payload.messaggio || 'Documento salvato nel fascicolo.' }
}

/** Indirizzo dell'editor del fascicolo per il documento appena creato. */
export function indirizzoEditor(fascicoloId: string, documentoId: string): string {
  return `/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/${encodeURIComponent(documentoId)}/editor`
}

/** Salva un file sul computer dell'avvocato, senza passare dal server. */
export function scaricaSulComputer(blob: Blob, nomeFile: string): void {
  const indirizzo = URL.createObjectURL(blob)
  const collegamento = document.createElement('a')
  collegamento.href = indirizzo
  collegamento.download = nomeFile
  document.body.appendChild(collegamento)
  collegamento.click()
  collegamento.remove()
  window.setTimeout(() => URL.revokeObjectURL(indirizzo), 2000)
}

/** Nome del file di lavoro con l'estensione richiesta. */
export function nomeFileRiconosciuto(nome: string, estensione: string): string {
  const gambo = String(nome || 'documento')
    .replace(/\.[^.]+$/, '')
    .replace(/[\\/:*?"<>|\x00-\x1f]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return `${(gambo || 'documento').slice(0, 100)} - testo riconosciuto.${estensione}`
}
