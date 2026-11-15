import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { apriBozzaNote } from '../api'

export function ApriBozzaNote({ fascicoloId, chiave, documentoId }: { fascicoloId: string; chiave: string; documentoId: string }) {
  const [apertura, setApertura] = useState(false)
  const [errore, setErrore] = useState('')

  async function apri() {
    setApertura(true)
    setErrore('')
    try {
      const risposta = await apriBozzaNote(fascicoloId, chiave, documentoId)
      const prefisso = `/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/`
      if (risposta.ok && risposta.openUrl?.startsWith(prefisso) && risposta.openUrl.endsWith('/editor')) {
        window.location.assign(risposta.openUrl)
      } else {
        setErrore(risposta.errore || 'Bozza delle note non disponibile.')
      }
    } catch {
      setErrore('Bozza delle note non disponibile.')
    } finally {
      setApertura(false)
    }
  }

  return (
    <div>
      <Button type="button" size="sm" onClick={() => void apri()} disabled={apertura}>
        {apertura ? 'Apertura della bozza…' : 'Apri la bozza delle note'}
      </Button>
      {errore ? <p role="alert">{errore}</p> : null}
    </div>
  )
}
