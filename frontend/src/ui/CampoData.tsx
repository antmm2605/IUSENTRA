import { Popover } from 'radix-ui'
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'

import {
  GIORNI_BREVI_IT,
  GIORNI_IT,
  dataInLettere,
  erroreCampoData,
  giornoDiIso,
  grigliaMese,
  isoDaValore,
  leggiTestoData,
  oggiRoma,
  oraDiIso,
  spostaGiorni,
  spostaMesi,
  testoDaValore,
  titoloMese,
} from './campoDataValore'

// Stili in src/index.css (globale): il campo serve in tutte le pagine e nei portali.

/**
 * Campo data italiano: l'avvocato vede e scrive gg/mm/aaaa (con `conOra`
 * gg/mm/aaaa hh:mm) indipendentemente dalla lingua del browser; il codice
 * chiamante riceve lo stesso valore tecnico dell'input nativo
 * (YYYY-MM-DD / YYYY-MM-DDTHH:MM, stringa vuota se la data manca o non è valida).
 * Con `name` il valore tecnico viaggia nel form in un campo nascosto, così
 * FormData e i POST classici non cambiano.
 */
export type CampoDataProps = {
  value?: string
  defaultValue?: string
  onChange?: (valore: string) => void
  onBlur?: () => void
  conOra?: boolean
  name?: string
  id?: string
  min?: string
  max?: string
  required?: boolean
  disabled?: boolean
  readOnly?: boolean
  autoFocus?: boolean
  form?: string
  /** Classi del contenitore. */
  className?: string
  /** Classi del campo di testo visibile (dove prima si stilava l'input nativo). */
  classeTesto?: string
  title?: string
  placeholder?: string
  'aria-label'?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean | 'true' | 'false'
}

export function CampoData({
  value,
  defaultValue,
  onChange,
  onBlur,
  conOra = false,
  name,
  id,
  min,
  max,
  required,
  disabled,
  readOnly,
  autoFocus,
  form,
  className,
  classeTesto,
  title,
  placeholder,
  'aria-label': ariaLabel,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
}: CampoDataProps) {
  const controllato = value !== undefined
  const formato = conOra ? 'gg/mm/aaaa hh:mm' : 'gg/mm/aaaa'
  const [testo, setTesto] = useState(() => testoDaValore(controllato ? value : defaultValue, conOra))
  const [toccato, setToccato] = useState(false)
  const [aperto, setAperto] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const ultimoEmesso = useRef(isoDaValore(controllato ? value : defaultValue, conOra))
  const idErrore = useId()

  const lettura = useMemo(() => leggiTestoData(testo, conOra), [testo, conOra])
  const errore = erroreCampoData(lettura, conOra, min, max, testo)

  // Il valore del chiamante prevale quando cambia davvero, non quando è l'eco di ciò che si sta scrivendo.
  const isoCorrente = useRef(lettura.iso)
  isoCorrente.current = lettura.iso
  useEffect(() => {
    if (!controllato) return
    const esterno = String(value ?? '')
    const isoEsterno = isoDaValore(esterno, conOra)
    if (isoEsterno === isoCorrente.current) return
    setTesto(testoDaValore(esterno, conOra))
    ultimoEmesso.current = isoEsterno
  }, [controllato, value, conOra])

  useEffect(() => {
    inputRef.current?.setCustomValidity(errore)
  }, [errore])

  // Un form azzerato riporta il campo al valore iniziale, come l'input nativo.
  useEffect(() => {
    const modulo = inputRef.current?.form
    if (!modulo || controllato) return undefined
    const azzera = () => {
      setTesto(testoDaValore(defaultValue, conOra))
      ultimoEmesso.current = isoDaValore(defaultValue, conOra)
      setToccato(false)
    }
    modulo.addEventListener('reset', azzera)
    return () => modulo.removeEventListener('reset', azzera)
  }, [controllato, defaultValue, conOra])

  const aggiorna = (nuovoTesto: string) => {
    setTesto(nuovoTesto)
    const iso = leggiTestoData(nuovoTesto, conOra).iso
    if (iso !== ultimoEmesso.current) {
      ultimoEmesso.current = iso
      onChange?.(iso)
    }
  }

  const sceltaDalCalendario = (giorno: string) => {
    if (!conOra) {
      aggiorna(testoDaValore(giorno))
      setAperto(false)
      return
    }
    const ora = lettura.stato === 'valido' ? oraDiIso(lettura.iso) : ''
    aggiorna(`${testoDaValore(giorno)} ${ora}`.trimEnd() + (ora ? '' : ' '))
    setAperto(false)
  }

  const chiudiCalendario = () => {
    // Con l'ora ancora da scrivere il cursore torna in fondo al campo.
    window.requestAnimationFrame(() => {
      const campo = inputRef.current
      if (!campo) return
      campo.focus()
      const fine = campo.value.length
      campo.setSelectionRange(fine, fine)
    })
  }

  const mostraErrore = Boolean(errore) && toccato
  const bloccato = disabled || readOnly
  const giornoScelto = lettura.stato === 'valido' ? giornoDiIso(lettura.iso) : ''
  const classi = ['iu-campo-data', conOra ? 'iu-campo-data--ora' : '', className || ''].filter(Boolean).join(' ')

  return (
    <span className={classi} data-invalid={mostraErrore ? 'true' : undefined}>
      <span className="iu-campo-data__riga">
        <input
          ref={inputRef}
          id={id}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          spellCheck={false}
          className={['iu-campo-data__testo', classeTesto || ''].filter(Boolean).join(' ')}
          value={testo}
          placeholder={placeholder || formato}
          maxLength={conOra ? 22 : 16}
          required={required}
          disabled={disabled}
          readOnly={readOnly}
          autoFocus={autoFocus}
          form={form}
          title={title || `Data nel formato ${formato}`}
          aria-label={ariaLabel}
          aria-describedby={[ariaDescribedBy, mostraErrore ? idErrore : ''].filter(Boolean).join(' ') || undefined}
          aria-invalid={mostraErrore || ariaInvalid === true || ariaInvalid === 'true' ? true : undefined}
          data-valore={lettura.iso || undefined}
          onChange={(evento) => aggiorna(evento.currentTarget.value)}
          onPaste={(evento) => {
            const incollato = evento.clipboardData.getData('text')
            const letto = leggiTestoData(incollato, conOra)
            if (letto.stato !== 'valido') return
            evento.preventDefault()
            aggiorna(testoDaValore(letto.iso, conOra))
          }}
          onBlur={() => {
            setToccato(true)
            if (lettura.stato === 'valido') setTesto(testoDaValore(lettura.iso, conOra))
            onBlur?.()
          }}
          onKeyDown={(evento) => {
            if (evento.key === 'ArrowDown' && evento.altKey && !bloccato) {
              evento.preventDefault()
              setAperto(true)
            }
          }}
        />
        {name ? <input type="hidden" name={name} value={lettura.iso} form={form} disabled={disabled} /> : null}
        <Popover.Root open={aperto && !bloccato} onOpenChange={(prossimo) => setAperto(prossimo && !bloccato)}>
          <Popover.Trigger asChild>
            <button
              type="button"
              className="iu-campo-data__apri"
              disabled={bloccato}
              aria-label={giornoScelto ? `Apri il calendario, data scelta ${dataInLettere(giornoScelto)}` : 'Apri il calendario'}
              title="Apri il calendario"
            >
              <CalendarDays aria-hidden="true" size={16} />
            </button>
          </Popover.Trigger>
          <Popover.Portal>
            <Popover.Content
              className="iu-calendario"
              // Niente role="dialog": le finestre di lavoro dello studio (ExistingWorkWindows)
              // adottano ogni dialog visibile e trasformerebbero il calendario in una finestra.
              role="group"
              aria-label="Calendario per scegliere la data"
              // Esc chiude solo il calendario, non la finestra di lavoro che lo contiene (ManagedWindowDock).
              data-esc-locale=""
              align="end"
              sideOffset={6}
              collisionPadding={12}
              onOpenAutoFocus={(evento) => evento.preventDefault()}
              onCloseAutoFocus={(evento) => {
                evento.preventDefault()
                chiudiCalendario()
              }}
            >
              <CalendarioMese scelto={giornoScelto} min={min ? isoDaValore(min.slice(0, 10)) : ''} max={max ? isoDaValore(max.slice(0, 10)) : ''} onScegli={sceltaDalCalendario} />
            </Popover.Content>
          </Popover.Portal>
        </Popover.Root>
      </span>
      {mostraErrore ? <span id={idErrore} className="iu-campo-data__errore" role="alert">{errore}</span> : null}
    </span>
  )
}

type CalendarioMeseProps = {
  scelto: string
  min: string
  max: string
  onScegli: (giorno: string) => void
}

/** Griglia del mese in italiano, settimana da lunedì, navigabile da tastiera (frecce, Pagina su/giù, Inizio/Fine). */
export function CalendarioMese({ scelto, min, max, onScegli }: CalendarioMeseProps) {
  const oggi = oggiRoma()
  const [attivo, setAttivo] = useState(scelto || oggi)
  const grigliaRef = useRef<HTMLTableElement>(null)
  const settimane = useMemo(() => grigliaMese(attivo), [attivo])
  const fuoriLimite = (giorno: string) => Boolean((min && giorno < min) || (max && giorno > max))

  useEffect(() => {
    grigliaRef.current?.querySelector<HTMLButtonElement>(`button[data-giorno="${attivo}"]`)?.focus()
  }, [attivo])

  const tasto = (evento: ReactKeyboardEvent<HTMLTableElement>) => {
    const spostamenti: Record<string, () => string> = {
      ArrowLeft: () => spostaGiorni(attivo, -1),
      ArrowRight: () => spostaGiorni(attivo, 1),
      ArrowUp: () => spostaGiorni(attivo, -7),
      ArrowDown: () => spostaGiorni(attivo, 7),
      PageUp: () => spostaMesi(attivo, evento.shiftKey ? -12 : -1),
      PageDown: () => spostaMesi(attivo, evento.shiftKey ? 12 : 1),
      Home: () => spostaGiorni(attivo, -grigliaGiornoSettimana(attivo)),
      End: () => spostaGiorni(attivo, 6 - grigliaGiornoSettimana(attivo)),
    }
    const calcola = spostamenti[evento.key]
    if (!calcola) return
    evento.preventDefault()
    setAttivo(calcola())
  }

  return (
    <div className="iu-calendario__corpo">
      <div className="iu-calendario__testata">
        <button type="button" className="iu-calendario__mese" onClick={() => setAttivo(spostaMesi(attivo, -1))} aria-label="Mese precedente">
          <ChevronLeft aria-hidden="true" size={16} />
        </button>
        <strong aria-live="polite">{titoloMese(attivo)}</strong>
        <button type="button" className="iu-calendario__mese" onClick={() => setAttivo(spostaMesi(attivo, 1))} aria-label="Mese successivo">
          <ChevronRight aria-hidden="true" size={16} />
        </button>
      </div>
      <table ref={grigliaRef} role="grid" aria-label={`Calendario di ${titoloMese(attivo)}`} onKeyDown={tasto}>
        <thead>
          <tr>
            {GIORNI_BREVI_IT.map((giorno, indice) => <th key={giorno} scope="col" abbr={GIORNI_IT[indice]}>{giorno}</th>)}
          </tr>
        </thead>
        <tbody>
          {settimane.map((settimana) => (
            <tr key={settimana[0].iso}>
              {settimana.map((cella) => {
                const disabilitato = fuoriLimite(cella.iso)
                const classi = [
                  'iu-calendario__giorno',
                  cella.delMese ? '' : 'iu-calendario__giorno--fuori',
                  cella.iso === oggi ? 'iu-calendario__giorno--oggi' : '',
                  cella.iso === scelto ? 'iu-calendario__giorno--scelto' : '',
                ].filter(Boolean).join(' ')
                return (
                  <td key={cella.iso} role="gridcell" aria-selected={cella.iso === scelto}>
                    <button
                      type="button"
                      className={classi}
                      data-giorno={cella.iso}
                      tabIndex={cella.iso === attivo ? 0 : -1}
                      disabled={disabilitato}
                      aria-label={`${dataInLettere(cella.iso)}${cella.iso === oggi ? ', oggi' : ''}`}
                      aria-current={cella.iso === oggi ? 'date' : undefined}
                      onClick={() => onScegli(cella.iso)}
                      onFocus={() => { if (cella.iso !== attivo) setAttivo(cella.iso) }}
                    >
                      {cella.giorno}
                    </button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="iu-calendario__piede">
        <button type="button" className="iu-calendario__oggi" disabled={fuoriLimite(oggi)} onClick={() => onScegli(oggi)}>Oggi</button>
      </div>
    </div>
  )
}

function grigliaGiornoSettimana(giorno: string): number {
  const [anno, mese, numero] = giorno.split('-').map(Number)
  return (new Date(Date.UTC(anno, mese - 1, numero)).getUTCDay() + 6) % 7
}
