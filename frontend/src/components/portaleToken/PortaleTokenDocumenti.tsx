import { useRef, useState, type DragEvent, type FormEvent } from 'react'
import {
  Camera,
  CircleAlert,
  CircleCheck,
  CloudUpload,
  File as IconaFile,
  FileCheck,
  FileText,
  FolderOpen,
  House,
  Image,
  MessageSquare,
  Paperclip,
  TriangleAlert,
  X,
} from 'lucide-react'
import { percorsoSezione, type DatiDocumenti } from '../../portaleTokenData'
import { ErroreModulo, LinkSezione, type Naviga } from './PortaleTokenComuni'

const FORMATO_MB = new Intl.NumberFormat('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const TIPI_ACCETTATI = 'image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt,.p7m'

function dimensione(file: File): string {
  return `${FORMATO_MB.format(file.size / 1024 / 1024)} MB`
}

function IconaTipo({ file }: { file: File }) {
  if (file.type.startsWith('image/')) return <Image size={16} aria-hidden="true" />
  if (file.type === 'application/pdf') return <FileText size={16} aria-hidden="true" />
  return <IconaFile size={16} aria-hidden="true" />
}

type Props = {
  dati: DatiDocumenti
  occupato: boolean
  errore: string
  onInvia: (files: File[], idFascicolo: string, note: string) => void
}

export function PortaleTokenDocumenti({ dati, occupato, errore, onInvia }: Props) {
  const [files, setFiles] = useState<File[]>([])
  const [idFascicolo, setIdFascicolo] = useState('')
  const [note, setNote] = useState('')
  const [trascinamento, setTrascinamento] = useState(false)
  const selettore = useRef<HTMLInputElement>(null)
  const fotocamera = useRef<HTMLInputElement>(null)
  const maxMb = dati.intestazione.permessi.maxUploadMb

  function aggiungi(elenco: FileList | null) {
    if (!elenco || !elenco.length) return
    const nuovi = Array.from(elenco)
    setFiles((correnti) => [...correnti, ...nuovi])
  }

  function rimuovi(indice: number) {
    setFiles((correnti) => correnti.filter((_, i) => i !== indice))
  }

  function rilascia(event: DragEvent<HTMLElement>) {
    event.preventDefault()
    setTrascinamento(false)
    aggiungi(event.dataTransfer.files)
  }

  function invia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!files.length || occupato) return
    onInvia(files, idFascicolo, note)
  }

  return (
    <div className="iu-ptk-pagina">
      <header className="iu-ptk-intro">
        <h1>Carica documenti</h1>
        <p>Invia file direttamente al tuo avvocato — massimo {maxMb} MB per file.</p>
      </header>

      {errore ? <ErroreModulo>{errore}</ErroreModulo> : null}

      <form className="iu-ptk-modulo" onSubmit={invia} noValidate>
        {dati.fascicoli.length ? (
          <div className="iu-ptk-card">
            <label className="iu-ptk-etichetta" htmlFor="iu-ptk-fascicolo">
              <FolderOpen size={16} aria-hidden="true" />Collega a una pratica (opzionale)
            </label>
            <select id="iu-ptk-fascicolo" className="iu-ptk-campo" value={idFascicolo} onChange={(event) => setIdFascicolo(event.target.value)}>
              <option value="">— Nessuna pratica (invio generico) —</option>
              {dati.fascicoli.map((fascicolo) => (
                <option key={fascicolo.id} value={fascicolo.id}>
                  {fascicolo.titolo}{fascicolo.numeroRg ? ` · RG ${fascicolo.numeroRg}` : ''}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div className="iu-ptk-card">
          <span className="iu-ptk-etichetta" id="iu-ptk-file-etichetta"><Paperclip size={16} aria-hidden="true" />Seleziona file</span>
          <button
            type="button"
            className={`iu-ptk-zona-upload${trascinamento ? ' is-trascinamento' : ''}`}
            onClick={() => selettore.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setTrascinamento(true) }}
            onDragLeave={() => setTrascinamento(false)}
            onDrop={rilascia}
            aria-describedby="iu-ptk-file-etichetta"
          >
            <CloudUpload size={36} aria-hidden="true" />
            <strong>Tocca per scegliere i file</strong>
            <span>oppure trascina qui · foto, PDF, Word, immagini</span>
          </button>
          <input
            ref={selettore}
            type="file"
            multiple
            accept={TIPI_ACCETTATI}
            className="iu-ptk-nascosto"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => { aggiungi(event.target.files); event.target.value = '' }}
          />
          {files.length ? (
            <ul className="iu-ptk-file" aria-label="File selezionati">
              {files.map((file, indice) => (
                <li key={`${file.name}-${indice}`}>
                  <IconaTipo file={file} />
                  <span className="iu-ptk-flessibile iu-ptk-tronca">{file.name}</span>
                  <span className="iu-ptk-muted">{dimensione(file)}</span>
                  <button type="button" className="iu-ptk-icona-btn" onClick={() => rimuovi(indice)} aria-label={`Rimuovi ${file.name}`}>
                    <X size={16} aria-hidden="true" />
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          <button type="button" className="iu-ptk-btn iu-ptk-btn--contorno iu-ptk-btn--pieno" onClick={() => fotocamera.current?.click()}>
            <Camera size={18} aria-hidden="true" />Scatta foto con la fotocamera
          </button>
          <input
            ref={fotocamera}
            type="file"
            accept="image/*"
            capture="environment"
            className="iu-ptk-nascosto"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(event) => { aggiungi(event.target.files); event.target.value = '' }}
          />
        </div>

        <div className="iu-ptk-card">
          <label className="iu-ptk-etichetta" htmlFor="iu-ptk-note"><MessageSquare size={16} aria-hidden="true" />Note (opzionale)</label>
          <textarea
            id="iu-ptk-note"
            className="iu-ptk-campo"
            rows={2}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Es: Carta d'identità fronte/retro, contratto..."
          />
        </div>

        <button type="submit" className="iu-ptk-btn iu-ptk-btn--primario iu-ptk-btn--grande" disabled={!files.length || occupato}>
          {occupato ? <span className="iu-ptk-spinner iu-ptk-spinner--piccolo" aria-hidden="true" /> : <CloudUpload size={18} aria-hidden="true" />}
          {occupato ? 'Invio in corso...' : 'Invia al tuo avvocato'}
        </button>
      </form>
    </div>
  )
}

export function PortaleTokenDocumentiOk({
  token,
  caricati,
  errori,
  onNaviga,
  onAltri,
}: {
  token: string
  caricati: string[]
  errori: string[]
  onNaviga: Naviga
  onAltri: () => void
}) {
  return (
    <div className="iu-ptk-pagina">
      <header className="iu-ptk-intestazione-centrata">
        {caricati.length ? (
          <>
            <CircleCheck size={48} className="iu-ptk-icona-ok" aria-hidden="true" />
            <h1>Documenti inviati!</h1>
            <p className="iu-ptk-muted">Il tuo avvocato riceverà una notifica.</p>
          </>
        ) : (
          <>
            <CircleAlert size={48} className="iu-ptk-icona-avviso" aria-hidden="true" />
            <h1>Nessun file inviato</h1>
          </>
        )}
      </header>

      {caricati.length ? (
        <section className="iu-ptk-card" aria-labelledby="iu-ptk-inviati-titolo">
          <h2 id="iu-ptk-inviati-titolo" className="iu-ptk-card-titolo is-ok">File inviati ({caricati.length})</h2>
          <ul className="iu-ptk-file">
            {caricati.map((nome, indice) => (
              <li key={`${nome}-${indice}`}><FileCheck size={16} aria-hidden="true" /><span className="iu-ptk-tronca">{nome}</span></li>
            ))}
          </ul>
        </section>
      ) : null}

      {errori.length ? (
        <section className="iu-ptk-card is-errore" aria-labelledby="iu-ptk-errori-titolo">
          <h2 id="iu-ptk-errori-titolo" className="iu-ptk-card-titolo is-errore"><TriangleAlert size={16} aria-hidden="true" />Errori ({errori.length})</h2>
          <ul className="iu-ptk-file">
            {errori.map((errore, indice) => <li key={`${errore}-${indice}`} className="is-errore">{errore}</li>)}
          </ul>
        </section>
      ) : null}

      <div className="iu-ptk-colonna">
        <button type="button" className="iu-ptk-btn iu-ptk-btn--contorno" onClick={onAltri}>
          <CloudUpload size={18} aria-hidden="true" />Carica altri documenti
        </button>
        <LinkSezione href={percorsoSezione(token, 'home')} sezione="home" onNaviga={onNaviga} className="iu-ptk-btn iu-ptk-btn--primario">
          <House size={18} aria-hidden="true" />Torna alla home
        </LinkSezione>
      </div>
    </div>
  )
}
