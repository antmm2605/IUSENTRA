import { useState } from 'react'
import { Calculator } from 'lucide-react'
import { OperationalModal } from '../OperationalModal'
import { ContoEconomicoPanel } from './ContoEconomicoPanel'

// Dalla vista economica dei fascicoli: apre lo stesso conto economico che si trova dentro il fascicolo.
export function ContoEconomicoPulsante({ fascicoloId, riferimento, cliente }:{ fascicoloId:string; riferimento:string; cliente:string }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" className="iu-fas-economic-evidence-trigger" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)}>
        <Calculator size={15} aria-hidden="true"/> Conto economico
      </button>
      {open ? (
        <OperationalModal open ariaLabel={`Conto economico ${riferimento}`} eyebrow="Vista economica" title="Conto economico" subtitle={`${riferimento} · ${cliente}`} onClose={() => setOpen(false)}>
          <ContoEconomicoPanel fascicoloId={fascicoloId}/>
        </OperationalModal>
      ) : null}
    </>
  )
}
