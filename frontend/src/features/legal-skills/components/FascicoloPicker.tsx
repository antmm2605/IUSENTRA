import { useEffect, useState } from 'react'
import { FolderOpen, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getFascicoliPage, type FascicoloRow } from '../../../fascicoliData'

export type FascicoloSelezionato = { id: string; etichetta: string }

type FascicoloPickerProps = {
  fascicolo: FascicoloSelezionato | null
  onSelect: (fascicolo: FascicoloSelezionato) => void
  onClear: () => void
  etichettaVuota?: string
}

export function fascicoloDaUrl(): FascicoloSelezionato | null {
  const id = new URLSearchParams(window.location.search).get('fascicolo')?.trim()
  return id ? { id, etichetta: '' } : null
}

export function FascicoloPicker({ fascicolo, onSelect, onClear, etichettaVuota }: FascicoloPickerProps) {
  const [ricerca, setRicerca] = useState('')
  const [opzioni, setOpzioni] = useState<FascicoloRow[]>([])

  useEffect(() => {
    if (!ricerca.trim()) {
      setOpzioni([])
      return
    }
    const timer = window.setTimeout(() => {
      getFascicoliPage({ q: ricerca.trim(), pageSize: 8 }).then((pagina) => {
        setOpzioni(pagina.items || [])
      })
    }, 300)
    return () => window.clearTimeout(timer)
  }, [ricerca])

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="flex items-center gap-1 text-muted-foreground">
          <FolderOpen aria-hidden="true" className="size-4" /> Fascicolo collegato:
        </span>
        {fascicolo ? (
          <Badge variant="secondary" className="flex items-center gap-1">
            {fascicolo.etichetta || `Fascicolo ${fascicolo.id}`}
            <button type="button" aria-label="Rimuovi fascicolo" onClick={onClear}>
              <X aria-hidden="true" className="size-3" />
            </button>
          </Badge>
        ) : (
          <span className="text-muted-foreground">{etichettaVuota || 'nessun fascicolo collegato.'}</span>
        )}
      </div>
      {!fascicolo ? (
        <div className="relative md:max-w-md">
          <Input
            value={ricerca}
            onChange={(event) => setRicerca(event.target.value)}
            placeholder="Cerca fascicolo per titolo, cliente o RG…"
            aria-label="Cerca fascicolo da collegare"
          />
          {opzioni.length ? (
            <div className="mt-2 grid gap-1">
              {opzioni.map((riga) => (
                <Button
                  key={riga.id}
                  size="sm"
                  variant="outline"
                  className="justify-start"
                  onClick={() => {
                    onSelect({
                      id: riga.id,
                      etichetta: [riga.ref || riga.internalRef, riga.title].filter(Boolean).join(' — '),
                    })
                    setRicerca('')
                    setOpzioni([])
                  }}
                >
                  {[riga.ref || riga.internalRef, riga.title, riga.client].filter(Boolean).join(' — ')}
                </Button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
