import { useRef, type ReactNode } from 'react'
import { Download, FileText, FolderOpen, Laptop, PenLine, Printer, Save } from 'lucide-react'

export type FormatoSalvataggio = 'docx' | 'pdf'
export type LuogoSalvataggio = 'fascicolo' | 'computer'
export type DaStampare = 'originale' | 'modificato'

export type DestinazioneOcr =
  | { tipo: 'documento'; formato: FormatoSalvataggio; dove: LuogoSalvataggio }
  | { tipo: 'editor' }
  | { tipo: 'ricercabile'; dove: LuogoSalvataggio }
  | { tipo: 'testo' }

type Props = {
  disabled: boolean
  copiaRicercabileDisponibile: boolean
  onScegli: (destinazione: DestinazioneOcr) => void
  onStampa: (quale: DaStampare) => void
}

/** Un menu a icona della barra: si apre, si sceglie, si richiude. */
function MenuIcona({ etichetta, icona, disabled, children }: { etichetta: string; icona: ReactNode; disabled: boolean; children: (chiudi: () => void) => ReactNode }) {
  const menu = useRef<HTMLDetailsElement | null>(null)
  const chiudi = () => { if (menu.current) menu.current.open = false }
  return (
    <details ref={menu} className={`iu-ocr-menu${disabled ? ' is-spento' : ''}`}>
      <summary className="iu-ocr-menu__icona" aria-label={etichetta} title={etichetta} aria-disabled={disabled || undefined}>
        {icona}
      </summary>
      <div className="iu-ocr-menu__voci" role="menu" aria-label={etichetta}>{disabled ? null : children(chiudi)}</div>
    </details>
  )
}

function Voce({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return <button type="button" role="menuitem" className="iu-ocr-menu__voce" onClick={onClick}>{children}</button>
}

/**
 * Salva e Stampa nella barra degli strumenti, come in un programma di scrittura.
 *
 * Salva: nel fascicolo o sul computer, in Word (.docx, modificabile) o in PDF
 * (impaginato): entrambi con le correzioni fatte. Salvare nel fascicolo di un
 * cliente non e' un gesto neutro: la voce lo dice, e il documento entra come
 * atto nuovo senza toccare l'originale. Stampa: il PDF nativo, cioe' l'atto
 * che fa fede, oppure il documento modificato in revisione.
 */
export function OcrSaveChoices({ disabled, copiaRicercabileDisponibile, onScegli, onStampa }: Props) {
  return (
    <>
      <MenuIcona etichetta="Salva" icona={<Save size={15} aria-hidden="true" />} disabled={disabled}>
        {(chiudi) => {
          const scegli = (destinazione: DestinazioneOcr) => { chiudi(); onScegli(destinazione) }
          return (
            <>
              <span className="iu-ocr-menu__gruppo"><FolderOpen size={13} aria-hidden="true" />Nel fascicolo (atto nuovo, l’originale non cambia)</span>
              <Voce onClick={() => scegli({ tipo: 'documento', formato: 'docx', dove: 'fascicolo' })}><FileText size={14} aria-hidden="true" />Word (.docx) — modificabile</Voce>
              <Voce onClick={() => scegli({ tipo: 'documento', formato: 'pdf', dove: 'fascicolo' })}><FileText size={14} aria-hidden="true" />PDF — impaginato</Voce>
              <Voce onClick={() => scegli({ tipo: 'editor' })}><PenLine size={14} aria-hidden="true" />Word e apri nell’editor</Voce>
              <span className="iu-ocr-menu__gruppo"><Laptop size={13} aria-hidden="true" />Sul computer</span>
              <Voce onClick={() => scegli({ tipo: 'documento', formato: 'docx', dove: 'computer' })}><Download size={14} aria-hidden="true" />Word (.docx) — modificabile</Voce>
              <Voce onClick={() => scegli({ tipo: 'documento', formato: 'pdf', dove: 'computer' })}><Download size={14} aria-hidden="true" />PDF — impaginato</Voce>
              <Voce onClick={() => scegli({ tipo: 'testo' })}><Download size={14} aria-hidden="true" />Testo semplice (.txt)</Voce>
              {copiaRicercabileDisponibile ? (
                <>
                  <span className="iu-ocr-menu__gruppo"><FileText size={13} aria-hidden="true" />Copia PDF con testo ricercabile (senza correzioni)</span>
                  <Voce onClick={() => scegli({ tipo: 'ricercabile', dove: 'fascicolo' })}><FolderOpen size={14} aria-hidden="true" />Nel fascicolo</Voce>
                  <Voce onClick={() => scegli({ tipo: 'ricercabile', dove: 'computer' })}><Download size={14} aria-hidden="true" />Sul computer</Voce>
                </>
              ) : null}
            </>
          )
        }}
      </MenuIcona>
      <MenuIcona etichetta="Stampa" icona={<Printer size={15} aria-hidden="true" />} disabled={disabled}>
        {(chiudi) => (
          <>
            <span className="iu-ocr-menu__gruppo"><Printer size={13} aria-hidden="true" />Cosa stampare</span>
            <Voce onClick={() => { chiudi(); onStampa('modificato') }}><FileText size={14} aria-hidden="true" />Documento modificato (con le correzioni)</Voce>
            <Voce onClick={() => { chiudi(); onStampa('originale') }}><FileText size={14} aria-hidden="true" />PDF nativo (l’originale, com’è)</Voce>
          </>
        )}
      </MenuIcona>
    </>
  )
}
