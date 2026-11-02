import { useCallback, useEffect, useState } from 'react'
import { Power, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { IusEmptyState, IusStatusBadge } from '@/components/iusentra'
import { aggiornaRegolaStudio, leggiRegoleStudio } from '../api'
import type { RegolaStudio } from '../types'
import '../passaggi.css'

function RegolaRiga({ regola, onAggiornata }: { regola: RegolaStudio; onAggiornata: () => void }) {
  const [valore, setValore] = useState(regola.valore)
  const [messaggio, setMessaggio] = useState('')
  const salva = async (modifiche: { valore?: string; attiva?: boolean }) => {
    const esito = await aggiornaRegolaStudio(regola.id, modifiche)
    setMessaggio(esito.ok ? '' : esito.errore || 'Regola non aggiornata.')
    if (esito.ok) onAggiornata()
  }
  return (
    <li className={`iu-regola-studio${regola.attiva ? '' : ' is-disattiva'}`}>
      <div className="iu-regola-studio__testa">
        <IusStatusBadge tone={regola.attiva ? 'success' : 'neutral'}>{regola.attiva ? 'attiva' : 'disattivata'}</IusStatusBadge>
        <strong>{regola.descrizione}</strong>
      </div>
      <p>Corregge: «{regola.passaggioOriginale?.titolo || regola.regolaId}» ({regola.produttore || 'software'}) · {regola.etichetta}{regola.autoreNome ? `, ${regola.autoreNome}` : ''}</p>
      {regola.motivo ? <p>Motivo: {regola.motivo}</p> : null}
      <p>Applicata a {regola.applicazioni || 0} {regola.applicazioni === 1 ? 'caso' : 'casi'}.</p>
      <div className="iu-regola-studio__azioni">
        {regola.azione === 'modifica_valore' ? (
          <>
            <label htmlFor={`valore-${regola.id}`}>{regola.campo}</label>
            <Input id={`valore-${regola.id}`} value={valore} onChange={(evento) => setValore(evento.target.value)} />
            <Button type="button" size="sm" variant="outline" disabled={!valore.trim() || valore === regola.valore} onClick={() => void salva({ valore })}>
              <Save data-icon="inline-start" /> Salva
            </Button>
          </>
        ) : null}
        <Button type="button" size="sm" variant="outline" onClick={() => void salva({ attiva: !regola.attiva })}>
          <Power data-icon="inline-start" /> {regola.attiva ? 'Disattiva' : 'Riattiva'}
        </Button>
      </div>
      {messaggio ? <p role="alert">{messaggio}</p> : null}
    </li>
  )
}

// Le regole dello studio: le correzioni degli avvocati che il software applica
// ai casi simili. Si vedono, si modificano, si disattivano; ogni cambio va nel diario.
export function RegoleStudioPanel() {
  const [regole, setRegole] = useState<RegolaStudio[]>([])
  const [errore, setErrore] = useState('')
  const [caricato, setCaricato] = useState(false)
  const carica = useCallback(async (signal?: AbortSignal) => {
    try {
      const risposta = await leggiRegoleStudio(signal)
      setRegole(risposta.regole || [])
      setErrore(risposta.ok ? '' : risposta.errore || 'Regole dello studio non disponibili.')
      setCaricato(true)
    } catch (eccezione) {
      if (!(eccezione instanceof DOMException && eccezione.name === 'AbortError')) setErrore('Regole dello studio non disponibili.')
    }
  }, [])
  useEffect(() => {
    const controllo = new AbortController()
    void carica(controllo.signal)
    return () => controllo.abort()
  }, [carica])

  return (
    <div className="iu-regole-studio">
      {errore ? <p role="alert">{errore}</p> : null}
      {caricato && !regole.length && !errore ? (
        <IusEmptyState title="Nessuna regola dello studio" message="Quando correggi un passaggio del software in un fascicolo («Correggi la regola»), la correzione compare qui." />
      ) : null}
      <ul className="iu-regole-studio__lista">
        {regole.map((regola) => <RegolaRiga key={`${regola.id}-${regola.valore}-${regola.attiva}`} regola={regola} onAggiornata={() => void carica()} />)}
      </ul>
    </div>
  )
}
