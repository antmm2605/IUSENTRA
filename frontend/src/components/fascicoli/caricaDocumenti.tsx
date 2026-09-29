import { CheckCircle2, FileText, Loader2 } from 'lucide-react'
import { csrfToken } from '../../formSubmit'

export type StatoCaricamento = {
  fase: 'invio' | 'registrazione' | 'fatto'
  percento: number
  inviati: number
  totale: number
  nomi: string[]
}

export type EsitoCaricamento = { message: string; documentIds: string[] }

/**
 * Carica i file nel fascicolo mostrando l'avanzamento reale dell'invio al server
 * (XMLHttpRequest espone i byte trasmessi, fetch no).
 */
export function caricaDocumentiConAvanzamento(
  url: string,
  formData: FormData,
  onStato: (stato: StatoCaricamento) => void,
): Promise<EsitoCaricamento> {
  const nomi = formData.getAll('files').filter((value): value is File => value instanceof File && Boolean(value.name)).map((file) => file.name)
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.withCredentials = true
    xhr.setRequestHeader('Accept', 'application/json')
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest')
    const token = csrfToken()
    if (token) xhr.setRequestHeader('X-CSRF-Token', token)
    xhr.upload.onprogress = (evento) => {
      const totale = evento.lengthComputable ? evento.total : 0
      const percento = totale ? Math.min(100, Math.round((evento.loaded / totale) * 100)) : 0
      onStato({ fase: percento >= 100 ? 'registrazione' : 'invio', percento, inviati: evento.loaded, totale, nomi })
    }
    xhr.upload.onload = () => onStato({ fase: 'registrazione', percento: 100, inviati: 0, totale: 0, nomi })
    xhr.onerror = () => reject(new Error('Connessione interrotta durante il caricamento: controlla la rete e riprova.'))
    xhr.ontimeout = () => reject(new Error('Il server non ha risposto in tempo: riprova tra poco.'))
    xhr.onload = () => {
      const tipo = xhr.getResponseHeader('content-type') || ''
      if (!tipo.includes('application/json')) {
        const allaLogin = /\/login(?:\?|$)/.test(xhr.responseURL || '')
        reject(new Error(allaLogin ? 'Sessione scaduta: rientra in IUSENTRA e ripeti il caricamento.' : 'Il server non ha confermato il caricamento. Ricarica la pagina e riprova.'))
        return
      }
      let dati: Record<string, unknown> = {}
      try {
        dati = JSON.parse(xhr.responseText || '{}') as Record<string, unknown>
      } catch {
        dati = {}
      }
      if (xhr.status >= 400 || dati.ok === false) {
        reject(new Error(String(dati.messaggio || dati.message || dati.errore || 'Caricamento non riuscito.')))
        return
      }
      const ids = [
        String(dati.documento_id || '').trim(),
        ...(Array.isArray(dati.documenti_id) ? dati.documenti_id.map((item) => String(item || '').trim()) : []),
      ].filter(Boolean)
      onStato({ fase: 'fatto', percento: 100, inviati: 0, totale: 0, nomi })
      resolve({ message: String(dati.message || dati.messaggio || 'Documenti caricati.'), documentIds: Array.from(new Set(ids)) })
    }
    onStato({ fase: 'invio', percento: 0, inviati: 0, totale: 0, nomi })
    xhr.send(formData)
  })
}

function dimensione(byte: number): string {
  if (!byte) return ''
  if (byte < 1024 * 1024) return `${Math.max(1, Math.round(byte / 1024))} KB`
  return `${(byte / (1024 * 1024)).toFixed(1).replace('.', ',')} MB`
}

/** Riquadro che dice all'avvocato cosa sta succedendo mentre i file salgono sul server. */
export function AvanzamentoCaricamento({ stato }: { stato: StatoCaricamento }) {
  const titolo = stato.fase === 'invio'
    ? `Invio a IUSENTRA in corso… ${stato.percento}%`
    : stato.fase === 'registrazione'
      ? 'File ricevuti: registrazione nel fascicolo…'
      : 'Caricati: aggiorno l’elenco dei documenti'
  const dettaglio = stato.fase === 'invio' && stato.totale
    ? `${dimensione(stato.inviati)} di ${dimensione(stato.totale)}`
    : stato.fase === 'registrazione'
      ? 'Cifratura e salvataggio sicuro; la lettura del contenuto prosegue in sfondo.'
      : ''
  return (
    <div className={`iu-fas-upload-progress is-${stato.fase}`} role="status" aria-live="polite">
      <div className="iu-fas-upload-progress__head">
        {stato.fase === 'fatto' ? <CheckCircle2 size={16} aria-hidden="true"/> : <Loader2 className="iu-spin" size={16} aria-hidden="true"/>}
        <strong>{titolo}</strong>
        {dettaglio ? <span>{dettaglio}</span> : null}
      </div>
      {stato.fase === 'registrazione'
        ? <progress className="iu-fas-upload-progress__bar" aria-label="Registrazione nel fascicolo"/>
        : <progress className="iu-fas-upload-progress__bar" max={100} value={stato.fase === 'invio' ? stato.percento : 100} aria-label="Avanzamento del caricamento"/>}
      {stato.nomi.length ? (
        <ul>
          {stato.nomi.slice(0, 6).map((nome) => <li key={nome}><FileText size={13} aria-hidden="true"/> {nome}</li>)}
          {stato.nomi.length > 6 ? <li>e altri {stato.nomi.length - 6} file</li> : null}
        </ul>
      ) : null}
    </div>
  )
}
