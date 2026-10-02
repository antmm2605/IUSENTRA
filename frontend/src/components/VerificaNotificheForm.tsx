import { useState, type FormEvent } from 'react'
import type { VerificaNotifiche } from './VerificaNotifichePanel'

export type ContestoVerificato = { fonte_documento_id?: string; verifica_documento_id?: string; revisione?: number; atto_studio?: boolean; regime_corrente?: boolean
  notifica_estero?: boolean; sospensione_feriale?: boolean; udienza?: string; pronuncia_decreto?: string; pubblicazione?: string; conoscenza?: string }

export default function VerificaNotificheForm({ fascicoloId, documentoId, documenti, contesto, onSaved, onRead }: {
  fascicoloId: string; documentoId: string; documenti: Array<{ id: string; nome: string }>; contesto?: ContestoVerificato; onSaved: (data: VerificaNotifiche) => void; onRead?: (id: string) => void
}) {
  const [saving, setSaving] = useState(false)
  const [errore, setErrore] = useState('')
  const [saved, setSaved] = useState(false)
  const [fonte, setFonte] = useState(contesto?.fonte_documento_id || documentoId)
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setErrore(''); setSaved(false)
    const form = new FormData(event.currentTarget)
    const payload: Record<string, unknown> = { revisione: contesto?.revisione || 0, dati_verificati: form.get('dati_verificati') === 'on' }
    for (const campo of ['fonte_documento_id', 'udienza', 'pronuncia_decreto', 'pubblicazione', 'conoscenza']) payload[campo] = form.get(campo) || ''
    for (const campo of ['atto_studio', 'regime_corrente', 'notifica_estero', 'sospensione_feriale']) payload[campo] = form.get(campo) === 'si'
    setSaving(true)
    try {
      const response = await fetch(`/api/v1/ui/controllo-studio/fascicoli/${encodeURIComponent(fascicoloId)}/verifica-notifiche/${encodeURIComponent(contesto?.verifica_documento_id || documentoId)}`, {
        method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      })
      const data = await response.json() as VerificaNotifiche
      if (!response.ok || !data.ok) throw new Error(data.message || 'Salvataggio non riuscito.')
      onSaved(data); setSaved(true)
    } catch (error: unknown) { setErrore(error instanceof Error ? error.message : 'Salvataggio non riuscito.') }
    finally { setSaving(false) }
  }
  return <details className="iu-cs-verifica-form"><summary>Verifica i dati del caso e calcola il termine</summary>
    <form onSubmit={(event) => { void submit(event) }}>
      <p>Indica solo le date documentate. Il salvataggio registra i dati e aggiorna il calcolo; non attesta l’avvenuta notifica.</p>
      <label>Documento fonte<select name="fonte_documento_id" required value={fonte} onChange={(event) => { setFonte(event.target.value); setSaved(false) }}><option value="">Seleziona il documento</option>{documenti.map((doc) => <option key={doc.id} value={doc.id}>{doc.nome}</option>)}</select></label>
      {onRead ? <button type="button" disabled={!fonte} onClick={() => onRead(fonte)}>Leggi il documento fonte selezionato</button> : null}
      <div className="iu-cs-verifica-form__campi">{([
        ['atto_studio', 'L’atto è dello studio'], ['regime_corrente', 'Si applica il regime vigente'],
        ['notifica_estero', 'La notifica va eseguita all’estero'], ['sospensione_feriale', 'Il termine è soggetto alla sospensione feriale'],
      ] as const).map(([campo, label]) => <label key={campo}>{label}<select name={campo} required defaultValue={typeof contesto?.[campo] === 'boolean' ? contesto[campo] ? 'si' : 'no' : ''}><option value="">Da verificare</option><option value="si">Sì</option><option value="no">No</option></select></label>)}</div>
      <div className="iu-cs-verifica-form__campi">{([
        ['udienza', 'Udienza collegata all’atto'], ['pronuncia_decreto', 'Pronuncia del decreto collegato'],
        ['pubblicazione', 'Pubblicazione della sentenza impugnata'], ['conoscenza', 'Notifica, comunicazione o piena conoscenza dell’atto impugnato'],
      ] as const).map(([campo, label]) => <label key={campo}>{label}<input type="date" name={campo} defaultValue={contesto?.[campo] || ''}/></label>)}</div>
      <label className="iu-cs-verifica-form__conferma"><input type="checkbox" name="dati_verificati" required/>Ho verificato questi dati nel documento fonte e la disciplina applicabile al caso.</label>
      {errore ? <p role="alert">{errore}</p> : null}{saved ? <p role="status">Dati verificati salvati. Calcolo aggiornato.</p> : null}
      <button type="submit" disabled={saving}>{saving ? 'Salvataggio…' : 'Salva i dati verificati'}</button>
    </form>
  </details>
}
