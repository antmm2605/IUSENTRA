import { useEffect, useMemo, useState } from 'react'
import { ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { correggiPassaggio } from '../api'
import type { AmbitoRegola, AzioneRegola, EsitoCorrezione, Passaggio } from '../types'

const AZIONI: Array<{ id: AzioneRegola; etichetta: string }> = [
  { id: 'modifica_valore', etichetta: 'Usa un altro valore' },
  { id: 'chiedi_sempre', etichetta: 'Chiedimi sempre prima' },
  { id: 'non_chiedere_conferma', etichetta: 'Proponi senza chiedere conferma' },
  { id: 'non_proporre', etichetta: 'Non proporlo più' },
]

function ambiti(passaggio: Passaggio): Array<{ id: AmbitoRegola; etichetta: string; disponibile: boolean }> {
  const { ufficio, giudice } = passaggio.contesto
  return [
    { id: 'fascicolo', etichetta: 'Solo questo fascicolo', disponibile: true },
    { id: 'giudice', etichetta: giudice ? `Questo giudice (${giudice}, ${ufficio})` : 'Questo giudice (non noto)', disponibile: Boolean(giudice && ufficio) },
    { id: 'ufficio', etichetta: ufficio ? `Questo ufficio (${ufficio})` : 'Questo ufficio (non noto)', disponibile: Boolean(ufficio) },
    { id: 'tipo', etichetta: 'Tutti i casi di questo tipo, in ogni ufficio', disponibile: true },
  ]
}

// «Correggi la regola»: l'avvocato sceglie che cosa cambiare e dove vale. Il
// server ricalcola il passaggio, controlla i vincoli di legge e salva la regola
// dello studio, oppure spiega con la norma perché non può.
export function CorreggiRegolaDialog({
  fascicoloId, passaggio, onClose, onSalvata,
}: { fascicoloId: string; passaggio: Passaggio | null; onClose: () => void; onSalvata: () => void }) {
  const correggibili = useMemo(() => Object.entries(passaggio?.campi || {}).filter(([, campo]) => !campo.vincolato), [passaggio])
  const [azione, setAzione] = useState<AzioneRegola>('chiedi_sempre')
  const [campo, setCampo] = useState('')
  const [valore, setValore] = useState('')
  const [ambito, setAmbito] = useState<AmbitoRegola>('fascicolo')
  const [motivo, setMotivo] = useState('')
  const [esito, setEsito] = useState<EsitoCorrezione | null>(null)
  const [invio, setInvio] = useState(false)

  useEffect(() => {
    setAzione(correggibili.length ? 'modifica_valore' : 'chiedi_sempre')
    setCampo(correggibili[0]?.[0] || '')
    setValore(correggibili[0]?.[1].valore || '')
    setAmbito('fascicolo')
    setMotivo('')
    setEsito(null)
  }, [passaggio, correggibili])

  if (!passaggio) return null

  const salva = async () => {
    setInvio(true)
    const risposta = await correggiPassaggio(fascicoloId, {
      chiave: passaggio.chiave, azione, ambito, motivo,
      ...(azione === 'modifica_valore' ? { campo, valore } : {}),
    })
    setInvio(false)
    setEsito(risposta)
    if (risposta.ok) onSalvata()
  }

  return (
    <Dialog open onOpenChange={(aperto) => { if (!aperto) onClose() }}>
      <DialogContent className="iu-correggi-regola">
        <DialogHeader>
          <DialogTitle>Correggi la regola</DialogTitle>
          <DialogDescription>
            «{passaggio.titolo}». La correzione diventa una regola dello studio: il software la applicherà ai casi simili. Non è addestramento: è una regola che puoi rivedere o disattivare da Impostazioni › Regole dello studio.
          </DialogDescription>
        </DialogHeader>
        <form className="iu-correggi-regola__form" onSubmit={(evento) => { evento.preventDefault(); void salva() }}>
          <fieldset>
            <legend>Che cosa deve fare il software</legend>
            {AZIONI.map((voce) => (
              <label key={voce.id} className="iu-correggi-regola__scelta">
                <input type="radio" name="azione" value={voce.id} checked={azione === voce.id} disabled={voce.id === 'modifica_valore' && !correggibili.length}
                  onChange={() => setAzione(voce.id)} />
                {voce.etichetta}
              </label>
            ))}
          </fieldset>
          {azione === 'modifica_valore' ? (
            <div className="iu-correggi-regola__valore">
              <label htmlFor="correggi-campo">Campo</label>
              <select id="correggi-campo" value={campo} onChange={(evento) => { setCampo(evento.target.value); setValore(passaggio.campi[evento.target.value]?.valore || '') }}>
                {correggibili.map(([nome, voce]) => <option key={nome} value={nome}>{voce.etichetta}</option>)}
              </select>
              <label htmlFor="correggi-valore">Valore giusto</label>
              <Input id="correggi-valore" value={valore} onChange={(evento) => setValore(evento.target.value)} required />
            </div>
          ) : null}
          <fieldset>
            <legend>Dove vale la regola</legend>
            {ambiti(passaggio).map((voce) => (
              <label key={voce.id} className="iu-correggi-regola__scelta">
                <input type="radio" name="ambito" value={voce.id} checked={ambito === voce.id} disabled={!voce.disponibile} onChange={() => setAmbito(voce.id)} />
                {voce.etichetta}
              </label>
            ))}
          </fieldset>
          <label htmlFor="correggi-motivo">Motivo (facoltativo)</label>
          <Textarea id="correggi-motivo" value={motivo} maxLength={600} onChange={(evento) => setMotivo(evento.target.value)}
            placeholder="Es. il giudice chiede il deposito entro le 12:00" />
          {esito && !esito.ok ? (
            <p className="iu-correggi-regola__errore" role="alert">
              <ShieldAlert size={14} /> {esito.errore}
              {esito.rifiuto?.norme?.map((norma) => <a key={norma.id} href={norma.reader_url || norma.url} target="_blank" rel="noreferrer"> {norma.norma}</a>)}
            </p>
          ) : null}
          {esito?.ok ? <p className="iu-correggi-regola__ok" role="status">Regola dello studio salvata: {esito.regola?.descrizione}.</p> : null}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>{esito?.ok ? 'Chiudi' : 'Annulla'}</Button>
            {!esito?.ok ? <Button type="submit" disabled={invio}>{invio ? 'Salvataggio…' : 'Salva la regola dello studio'}</Button> : null}
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
