import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import './QuadroFascicolo.css'

/**
 * Le otto sezioni della pagina del fascicolo (riorganizzazione approvata dall'avvocato il 10/11/2026).
 * Ogni sezione è un contenitore numerato che raggruppa i pannelli esistenti, senza riscriverli:
 * 1 Pratica · 2 Andamento · 3 Udienze e termini · 4 Atti e documenti · 5 Comunicazioni, PEC e notifiche ·
 * 6 Economia · 7 Deposito telematico · 8 Registro.
 * Gli id dei pannelli restano quelli di sempre: un collegamento diretto (#documenti, #conto-economico,
 * #presidio-fascicolo…) apre la sezione che lo contiene e poi il pannello.
 */
export const SEZIONI_FASCICOLO = [
  { id: 'sezione-pratica', numero: 1, titolo: 'Pratica', breve: 'Pratica', descrizione: 'Profilo, cliente, controparti e difensori, uffici competenti' },
  { id: 'sezione-andamento', numero: 2, titolo: 'Andamento', breve: 'Andamento', descrizione: 'Di cosa tratta il fascicolo e cronologia della pratica' },
  { id: 'sezione-termini', numero: 3, titolo: 'Udienze e termini', breve: 'Udienze e termini', descrizione: 'Agenda, udienze e scadenze' },
  { id: 'sezione-documenti', numero: 4, titolo: 'Atti e documenti', breve: 'Documenti', descrizione: 'Documenti catalogati, editor e redazione' },
  { id: 'sezione-comunicazioni', numero: 5, titolo: 'Comunicazioni, PEC e notifiche', breve: 'Comunicazioni e PEC', descrizione: 'PEC, cancelleria, relate e prove di notifica' },
  { id: 'sezione-economia', numero: 6, titolo: 'Economia', breve: 'Economia', descrizione: 'Conto economico, preventivo, conferimento e fatturazione' },
  { id: 'sezione-deposito', numero: 7, titolo: 'Deposito telematico', breve: 'Deposito', descrizione: 'Checklist, documenti richiesti, busta e servizi telematici' },
  { id: 'sezione-registro', numero: 8, titolo: 'Registro', breve: 'Registro', descrizione: 'Audit, eventi tecnici, conservazione, gestione e controlli' },
] as const

export type SezioneFascicoloId = typeof SEZIONI_FASCICOLO[number]['id']

export function isSezioneFascicoloId(value: string): value is SezioneFascicoloId {
  return SEZIONI_FASCICOLO.some((sezione) => sezione.id === value)
}

/** Apre ogni contenitore chiuso che racchiude l'elemento: sezione e pannello. */
export function apriContenitoriDi(element: Element | null) {
  let current: Element | null = element
  while (current) {
    if (current instanceof HTMLDetailsElement && !current.open) current.open = true
    current = current.parentElement
  }
}

export function SezioneFascicolo({
  id,
  avviso,
  apriQuando = true,
  evidenza = false,
  children,
}:{
  id: SezioneFascicoloId
  /** Frase breve sotto il titolo: lo stato della sezione quando è chiusa (es. «Nessun deposito da preparare»). */
  avviso?: ReactNode
  /** Apre la sezione quando diventa vero; non la richiude mai da sola. */
  apriQuando?: boolean
  /** Sezione da guardare subito: bordo e titolo in evidenza. */
  evidenza?: boolean
  children: ReactNode
}) {
  const ref = useRef<HTMLDetailsElement | null>(null)
  const sezione = SEZIONI_FASCICOLO.find((item) => item.id === id) || SEZIONI_FASCICOLO[0]
  useEffect(() => {
    if (apriQuando && ref.current && !ref.current.open) ref.current.open = true
  }, [apriQuando])
  useEffect(() => {
    // Collegamento diretto a un pannello di questa sezione (es. #presidio-fascicolo): la sezione nasce aperta.
    const richiesto = decodeURIComponent(window.location.hash.replace(/^#/, ''))
    const bersaglio = richiesto ? document.getElementById(richiesto) : null
    if (ref.current && bersaglio && ref.current.contains(bersaglio)) ref.current.open = true
  }, [])
  return (
    <details ref={ref} id={id} className={`iu-fas-sezione${evidenza ? ' iu-fas-sezione--evidenza' : ''}`}>
      <summary className="iu-fas-sezione__summary">
        <span className="iu-fas-sezione__numero">{sezione.numero}</span>
        <span className="iu-fas-sezione__testi">
          <span className="iu-fas-sezione__titolo" id={`${id}-titolo`}>{sezione.titolo}</span>
          <span className="iu-fas-sezione__descrizione">{avviso || sezione.descrizione}</span>
        </span>
        <ChevronDown className="iu-fas-sezione__chevron" size={18} aria-hidden="true"/>
      </summary>
      <div className="iu-fas-sezione__corpo">{children}</div>
    </details>
  )
}
