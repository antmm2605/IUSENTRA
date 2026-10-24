import { useEffect, useState } from 'react'
import { apiJson, apiPostJson } from '../lib/apiClient'
import type { OpenGADecision } from '../opengaSearch'

type Reading = {
  ok: boolean; stato: string; job_id?: string; message?: string
  documento?: { testo: string; sezioni: Record<string, string>; raw_sha256: string
    provenienza: { url: string; versione: string; acquisita_il: string; sha256: string } }
}
const unavailable: Reading = { ok: false, stato: 'intervento_necessario', message: 'Lettura non disponibile. Il risultato resta uno spunto.' }

export function OpenGAOfficialDocument({ decision }: { decision: OpenGADecision }) {
  const [result, setResult] = useState<Reading>({ ok: true, stato: 'in_corso', message: 'Avvio del recupero ufficiale…' })
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    let polls = 0
    const options = { signal: controller.signal, activity: false as const }
    async function observe(value: Reading): Promise<void> {
      if (controller.signal.aborted) return
      setResult(value)
      if (value.stato !== 'in_corso' || !value.job_id) return
      if (++polls > 120) {
        setResult({ ...value, message: 'La lettura prosegue nello studio. Riapri questo pannello per verificarne l’esito.' })
        return
      }
      timer = setTimeout(() => {
        void apiJson<Reading>('/api/v1/ui/giurisprudenza/testo-ufficiale/' + encodeURIComponent(value.job_id!), unavailable, options)
          .then(observe).catch(() => { if (!controller.signal.aborted) setResult(unavailable) })
      }, 2000)
    }
    void apiPostJson<Reading>('/api/v1/ui/giurisprudenza/testo-ufficiale',
      { relazione_id: decision.relazione_id, resource_id: decision.resource_id, resource_sha256: decision.resource_sha256 },
      unavailable, options).then(observe).catch(() => { if (!controller.signal.aborted) setResult(unavailable) })
    return () => { controller.abort(); if (timer) clearTimeout(timer) }
  }, [decision.relazione_id, decision.resource_id, decision.resource_sha256])
  const document = result.documento
  return <section aria-label="Lettura del testo ufficiale">
    <p role="status">{result.message || (result.stato === 'acquisito' ? 'Testo ufficiale acquisito e identità riscontrata.' : 'Testo non acquisito: il risultato resta uno spunto.')}</p>
    {result.stato === 'acquisito' && document && <>
      <p>Il testo è disponibile per la verifica dell’avvocato. Non approva automaticamente la scheda.</p>
      <p><a href={document.provenienza.url} target="_blank" rel="noopener noreferrer">Apri questo documento ufficiale</a></p>
      <dl className="iu-legal-meta">
        <div><dt>Pubblicazione</dt><dd>{document.provenienza.versione}</dd></div>
        <div><dt>Acquisizione</dt><dd>{document.provenienza.acquisita_il}</dd></div>
      </dl>
      {Object.entries(document.sezioni).map(([name, text]) => <details key={name}>
        <summary>{name.replace('Ted', ' (seconda lingua)')}</summary><p className="whitespace-pre-wrap">{text}</p>
      </details>)}
      <details><summary>Provenienza e integrità</summary>
        <p>SHA-256 del testo: {document.provenienza.sha256}</p>
        <p>SHA-256 dell’originale: {document.raw_sha256}</p>
      </details>
    </>}
  </section>
}
