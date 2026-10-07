import { useEffect, useRef, useState } from 'react'
import './DocumentChecksTool.css'

type FileCheck = { name: string; bytes: number; hash: string }
type Difference = { kind: 'same' | 'removed' | 'added'; text: string; before?: number; after?: number }

function compareLines(before: string, after: string): Difference[] {
  const left = before.replace(/\r\n?/g, '\n').split('\n')
  const right = after.replace(/\r\n?/g, '\n').split('\n')
  if (left.length > 500 || right.length > 500) throw new Error('Confronta fino a 500 righe per versione. Dividi i testi più lunghi in sezioni.')
  const width = right.length + 1
  const lengths = new Uint16Array((left.length + 1) * width)
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      lengths[i * width + j] = left[i] === right[j]
        ? lengths[(i + 1) * width + j + 1] + 1
        : Math.max(lengths[(i + 1) * width + j], lengths[i * width + j + 1])
    }
  }
  const result: Difference[] = []
  let i = 0; let j = 0
  while (i < left.length || j < right.length) {
    if (i < left.length && j < right.length && left[i] === right[j]) {
      result.push({ kind: 'same', text: left[i], before: ++i, after: ++j })
    } else if (i < left.length && (j === right.length || lengths[(i + 1) * width + j] >= lengths[i * width + j + 1])) {
      result.push({ kind: 'removed', text: left[i], before: ++i })
    } else {
      result.push({ kind: 'added', text: right[j], after: ++j })
    }
  }
  return result
}

export default function DocumentChecksTool({ mode }: { mode: 'hash' | 'text' }) {
  const [checks, setChecks] = useState<(FileCheck | null)[]>([null, null])
  const [pending, setPending] = useState([false, false])
  const [errors, setErrors] = useState(['', ''])
  const [texts, setTexts] = useState(['', ''])
  const [differences, setDifferences] = useState<Difference[] | null>(null)
  const [textError, setTextError] = useState('')
  const [onlyChanges, setOnlyChanges] = useState(false)
  const generations = useRef([0, 0])
  useEffect(() => () => { generations.current = generations.current.map((value) => value + 1) }, [])

  async function readFile(index: number, file?: File) {
    const generation = ++generations.current[index]
    setChecks((values) => values.map((value, i) => i === index ? null : value))
    setErrors((values) => values.map((value, i) => i === index ? '' : value))
    setPending((values) => values.map((value, i) => i === index ? Boolean(file) : value))
    if (!file) return
    try {
      if (file.size > 64 * 1024 * 1024) throw new Error('Scegli un documento fino a 64 MB.')
      if (!window.crypto?.subtle) throw new Error('Il controllo richiede una connessione sicura a IUSENTRA.')
      const digest = await window.crypto.subtle.digest('SHA-256', await file.arrayBuffer())
      const hash = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
      if (generation === generations.current[index]) setChecks((values) => values.map((value, i) => i === index ? { name: file.name, bytes: file.size, hash } : value))
    } catch (error) {
      if (generation === generations.current[index]) setErrors((values) => values.map((value, i) => i === index ? error instanceof Error ? error.message : 'Documento non leggibile. Selezionalo di nuovo.' : value))
    } finally {
      if (generation === generations.current[index]) setPending((values) => values.map((value, i) => i === index ? false : value))
    }
  }

  if (mode === 'hash') return (
    <div className="iu-document-checks">
      <p>I documenti restano sul dispositivo. L’impronta confronta i file byte per byte; la validità della firma si controlla con gli strumenti di firma.</p>
      <div className="iu-document-checks__inputs">
        {[0, 1].map((index) => <div key={index} className="iu-field">
          <label className="iu-field__label" htmlFor={`impronta-file-${index}`}>{index ? 'Documento da confrontare (facoltativo)' : 'Documento di riferimento'}</label>
          <input className="iu-input" id={`impronta-file-${index}`} type="file" onChange={(event) => void readFile(index, event.target.files?.[0])} />
          <div aria-live="polite">
            {pending[index] ? <p>Calcolo dell’impronta…</p> : null}
            {errors[index] ? <p role="alert" className="iu-alert iu-alert--danger">{errors[index]}</p> : null}
            {checks[index] ? <dl className="iu-document-checks__fingerprint">
              <dt>Documento</dt><dd>{checks[index]!.name}</dd>
              <dt>Dimensione</dt><dd>{checks[index]!.bytes.toLocaleString('it-IT')} byte</dd>
              <dt>SHA-256</dt><dd><code>{checks[index]!.hash}</code></dd>
            </dl> : null}
          </div>
        </div>)}
      </div>
      {checks[0] && checks[1] ? <p role="status" className="iu-alert iu-alert--info">{checks[0].hash === checks[1].hash ? 'I documenti sono identici byte per byte.' : 'I documenti sono diversi. L’impronta non indica quali contenuti sono cambiati.'}</p> : null}
    </div>
  )

  const removed = differences?.filter((row) => row.kind === 'removed').length ?? 0
  const added = differences?.filter((row) => row.kind === 'added').length ?? 0
  return <div className="iu-document-checks">
    <p>Confronto letterale: evidenzia righe aggiunte e rimosse, incluse differenze di accenti, punteggiatura e spazi. I testi restano sul dispositivo.</p>
    <div className="iu-document-checks__inputs">
      {[0, 1].map((index) => <div className="iu-field" key={index}>
        <label className="iu-field__label" htmlFor={`confronto-testo-${index}`}>{index ? 'Versione nuova' : 'Versione precedente'}</label>
        <textarea className="iu-input" id={`confronto-testo-${index}`} rows={8} maxLength={100000} value={texts[index]} onChange={(event) => { const value = event.target.value; setTexts((values) => values.map((text, i) => i === index ? value : text)); setDifferences(null); setTextError('') }} />
      </div>)}
    </div>
    <div className="iu-document-checks__actions">
      <button type="button" className="iu-button iu-button--primary" disabled={!texts[0] || !texts[1]} onClick={() => {
        try { setDifferences(compareLines(texts[0], texts[1])); setTextError('') } catch (error) { setDifferences(null); setTextError(error instanceof Error ? error.message : 'Confronto non eseguito.') }
      }}>Confronta testi</button>
      {differences ? <label><input type="checkbox" checked={onlyChanges} onChange={(event) => setOnlyChanges(event.target.checked)} /> Solo differenze</label> : null}
    </div>
    {textError ? <p role="alert" className="iu-alert iu-alert--danger">{textError}</p> : null}
    {differences ? <>
      <p role="status">{removed || added ? `${removed} righe rimosse · ${added} righe aggiunte` : 'I testi sono identici.'}</p>
      <ol className="iu-document-checks__diff" aria-label="Risultato del confronto">
        {differences.filter((row) => !onlyChanges || row.kind !== 'same').map((row, index) => <li key={index} data-kind={row.kind}>
          <span className="iu-document-checks__line">{row.before ?? '–'} / {row.after ?? '–'}</span>
          <span className="iu-document-checks__kind">{row.kind === 'same' ? 'Uguale' : row.kind === 'added' ? 'Aggiunta' : 'Rimossa'}</span>
          <span className="iu-document-checks__text">{row.text || ' '}</span>
        </li>)}
      </ol>
    </> : null}
  </div>
}
