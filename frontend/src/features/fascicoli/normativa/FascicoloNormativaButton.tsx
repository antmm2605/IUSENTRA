import { lazy, Suspense, useState } from 'react'
import { Scale } from 'lucide-react'
import { Drawer } from '../../../ui/Drawer'
import { useFinestraInteraSuTelefono } from './useFinestraInteraSuTelefono'
import './fascicoloNormativa.css'

const TITOLO = 'Normativa del fascicolo'

// Il contenuto si scarica alla prima apertura: la pagina del fascicolo non ne paga il peso.
const FascicoloNormativaPanel = lazy(() => import('./FascicoloNormativaPanel').then((m) => ({ default: m.FascicoloNormativaPanel })))

/**
 * Icona «Normativa» nell'intestazione del fascicolo (richiesta dell'avvocato del 02/11/2026).
 * Apre un pannello laterale su computer e un foglio a tutto schermo sul telefono, senza lasciare
 * il fascicolo; i dati si leggono solo all'apertura.
 */
export function FascicoloNormativaButton({ fascicoloId }: { fascicoloId: string }) {
  const [aperto, setAperto] = useState(false)
  useFinestraInteraSuTelefono(aperto, TITOLO)
  return (
    <>
      <button type="button" className="iu-button iu-button--secondary iu-fas-tools-shortcut" aria-label="Normativa del fascicolo" title="Normativa del fascicolo: norme del rito, dei termini aperti e dei documenti" aria-haspopup="dialog" aria-expanded={aperto} onClick={() => setAperto(true)}>
        <Scale size={18} aria-hidden="true"/>
      </button>
      <Drawer title={TITOLO} open={aperto} onClose={() => setAperto(false)}>
        {aperto && fascicoloId ? (
          <Suspense fallback={<div className="iu-fas-normativa"><p className="iu-fas-normativa__nota" role="status">Apertura della normativa…</p></div>}>
            <FascicoloNormativaPanel fascicoloId={fascicoloId}/>
          </Suspense>
        ) : null}
      </Drawer>
    </>
  )
}
