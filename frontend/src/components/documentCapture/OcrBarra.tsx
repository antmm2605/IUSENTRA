import type { MouseEvent, ReactNode } from 'react'
import {
  AlignCenter, AlignJustify, AlignLeft, AlignRight, Bold, ListIndentDecrease, ListIndentIncrease, Italic, PaintBucket, Redo2,
  Search, Strikethrough, Trash2, Underline, Undo2,
} from 'lucide-react'
import { Button } from '../../ui/Button'
import { ETICHETTE } from './OcrParte'
import {
  CORPI, ETICHETTE_MARCATORE, GRUPPI_CARATTERI, INTERLINEE, LIVELLI, RIENTRO_MASSIMO_MM, RIENTRO_PASSO_MM, fiducia,
} from './ocrBarraVoci'
import { markerOf, type OcrAlignment, type OcrBlock, type OcrBlockKind, type OcrFormat } from './ocrBlocks'

export type ChiaveStile = 'grassetto' | 'corsivo' | 'sottolineato' | 'barrato'

/** Gli stili che si accendono e si spengono: sulla parte selezionata, o sul pezzo intero se non se ne seleziona una. */
const STILI: { chiave: ChiaveStile; label: string; Icona: typeof Bold }[] = [
  { chiave: 'grassetto', label: 'Grassetto', Icona: Bold },
  { chiave: 'corsivo', label: 'Corsivo', Icona: Italic },
  { chiave: 'sottolineato', label: 'Sottolineato', Icona: Underline },
  { chiave: 'barrato', label: 'Barrato', Icona: Strikethrough },
]

const ALLINEAMENTI: { value: OcrAlignment; label: string; Icona: typeof AlignLeft }[] = [
  { value: 'sinistra', label: 'Allinea a sinistra', Icona: AlignLeft },
  { value: 'centro', label: 'Centra', Icona: AlignCenter },
  { value: 'destra', label: 'Allinea a destra', Icona: AlignRight },
  { value: 'giustificato', label: 'Giustifica', Icona: AlignJustify },
]

type Props = {
  blocks: OcrBlock[]
  corrente: OcrBlock | null
  disabled: boolean
  selezionati: number
  formatoInline?: { famiglia: string; corpo: number; famigliaMista: boolean; corpoMisto: boolean }
  applica: (patch: Partial<OcrFormat>, soloPezzo?: boolean) => void
  premuto: (chiave: ChiaveStile) => boolean
  onTipo: (kind: OcrBlockKind) => void
  onTogli: () => void
  storia: { annulla: () => void; ripeti: () => void; puoAnnullare: boolean; puoRipetere: boolean }
  trovaAperto: boolean
  onTrova: () => void
  /** Salva e Stampa, quando chi usa la revisione li offre (il fascicolo). */
  azioni?: ReactNode
}

// la barra non si prende il fuoco: la selezione nel testo resta dov'e'
const tieniLaSelezione = (event: MouseEvent) => event.preventDefault()

/**
 * La barra del formato della revisione, come quella di un programma di
 * scrittura: storia, livello, carattere, corpo, stili, allineamento,
 * interlinea, rientro, colore, ricerca.
 */
export function OcrBarra({ blocks, corrente, disabled, selezionati, formatoInline, applica, premuto, onTipo, onTogli, storia, trovaAperto, onTrova, azioni }: Props) {
  const formato = corrente && corrente.kind !== 'tabella' ? corrente.format : null
  const spento = disabled || !formato
  const famiglia = formatoInline?.famiglia ?? formato?.famiglia ?? ''
  const corpo = formatoInline?.corpo ?? formato?.corpo ?? 0
  const propri = Array.from(new Set(blocks.flatMap((block) => [block.format.famiglia, ...(block.tratti ?? []).map((tratto) => tratto.famiglia || '')]).filter(Boolean)))
  const noti = new Set(GRUPPI_CARATTERI.flatMap((voce) => voce.caratteri))
  const delDocumento = propri.filter((nome) => !noti.has(nome))
  const corpi = corpo && !CORPI.includes(corpo) ? [...CORPI, corpo].sort((a, b) => a - b) : CORPI
  const rientro = formato?.rientro || 0
  return (
    <div className="iu-ocr-barra" role="toolbar" aria-label="Formato del testo selezionato">
      {azioni ? <span className="iu-ocr-barra__azioni">{azioni}</span> : null}
      <Button type="button" tone="neutral" disabled={disabled || !storia.puoAnnullare} aria-label="Annulla (Ctrl+Z)" title="Annulla (Ctrl+Z)" onMouseDown={tieniLaSelezione} onClick={storia.annulla}>
        <Undo2 size={14} aria-hidden="true" />
      </Button>
      <Button type="button" tone="neutral" disabled={disabled || !storia.puoRipetere} aria-label="Ripeti (Ctrl+Y)" title="Ripeti (Ctrl+Y)" onMouseDown={tieniLaSelezione} onClick={storia.ripeti}>
        <Redo2 size={14} aria-hidden="true" />
      </Button>
      <label className="iu-ocr-barra__livello">
        <span className="iu-sr-only">Livello del testo</span>
        <select value={formato ? formato.livello : 0} disabled={spento} onChange={(event) => applica({ livello: Number(event.target.value) }, true)}>
          {LIVELLI.map((voce) => <option key={voce.value} value={voce.value}>{voce.label}</option>)}
        </select>
      </label>
      <label className="iu-ocr-barra__carattere">
        <span className="iu-sr-only">Carattere</span>
        <select value={famiglia} disabled={spento} onChange={(event) => applica({ famiglia: event.target.value })}>
          <option value="">{formatoInline?.famigliaMista ? 'Caratteri misti' : 'Carattere del documento'}</option>
          {delDocumento.length ? (
            <optgroup label="Usati nel documento">
              {delDocumento.map((nome) => <option key={nome} value={nome}>{nome}</option>)}
            </optgroup>
          ) : null}
          {GRUPPI_CARATTERI.map((voce) => (
            <optgroup key={voce.gruppo} label={voce.gruppo}>
              {voce.caratteri.map((nome) => <option key={nome} value={nome}>{nome}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      <label className="iu-ocr-barra__corpo">
        <span className="iu-sr-only">Dimensione del testo</span>
        <select value={corpo} disabled={spento} onChange={(event) => applica({ corpo: Number(event.target.value) })}>
          <option value={0}>{formatoInline?.corpoMisto ? 'Corpi misti' : 'Corpo del documento'}</option>
          {corpi.map((corpo) => <option key={corpo} value={corpo}>{`${String(corpo).replace('.', ',')} pt`}</option>)}
        </select>
      </label>
      {STILI.map(({ chiave, label, Icona }) => (
        <Button key={chiave} type="button" tone="neutral" disabled={spento} aria-pressed={premuto(chiave)} aria-label={label} title={label} onMouseDown={tieniLaSelezione} onClick={() => applica({ [chiave]: !premuto(chiave) })}>
          <Icona size={14} aria-hidden="true" />
        </Button>
      ))}
      {ALLINEAMENTI.map(({ value, label, Icona }) => (
        <Button key={value} type="button" tone="neutral" disabled={spento} aria-pressed={formato?.allineamento === value} aria-label={label} title={label} onMouseDown={tieniLaSelezione} onClick={() => applica({ allineamento: value }, true)}>
          <Icona size={14} aria-hidden="true" />
        </Button>
      ))}
      <label className="iu-ocr-barra__interlinea">
        <span className="iu-sr-only">Interlinea</span>
        <select value={formato?.interlinea || 0} disabled={spento} onChange={(event) => applica({ interlinea: Number(event.target.value) }, true)}>
          {INTERLINEE.map((voce) => <option key={voce.value} value={voce.value}>{voce.label}</option>)}
        </select>
      </label>
      <Button type="button" tone="neutral" disabled={spento || rientro <= 0} aria-label="Riduci il rientro" title="Riduci il rientro" onMouseDown={tieniLaSelezione} onClick={() => applica({ rientro: Math.max(0, rientro - RIENTRO_PASSO_MM) }, true)}>
        <ListIndentDecrease size={14} aria-hidden="true" />
      </Button>
      <Button type="button" tone="neutral" disabled={spento || rientro >= RIENTRO_MASSIMO_MM} aria-label="Aumenta il rientro" title="Aumenta il rientro" onMouseDown={tieniLaSelezione} onClick={() => applica({ rientro: Math.min(RIENTRO_MASSIMO_MM, rientro + RIENTRO_PASSO_MM) }, true)}>
        <ListIndentIncrease size={14} aria-hidden="true" />
      </Button>
      <label className="iu-ocr-barra__colore" title="Colore del testo">
        <span className="iu-sr-only">Colore del testo</span>
        <input type="color" value={formato?.colore || '#111827'} disabled={spento} onChange={(event) => applica({ colore: event.target.value.toLowerCase() })} />
      </label>
      <Button type="button" tone="neutral" disabled={spento} aria-label="Togli il colore e lascia quello del documento" title="Colore del documento" onMouseDown={tieniLaSelezione} onClick={() => applica({ colore: '' })}>
        <PaintBucket size={14} aria-hidden="true" />
      </Button>
      <label className="iu-ocr-barra__tipo">
        <span className="iu-sr-only">Tipo di parte</span>
        <select value={corrente ? corrente.kind : 'paragrafo'} disabled={disabled || !corrente || corrente.kind === 'tabella'} onChange={(event) => onTipo(event.target.value as OcrBlockKind)}>
          {(['titolo', 'paragrafo', 'elenco', 'numero_pagina'] as OcrBlockKind[]).map((kind) => <option key={kind} value={kind}>{ETICHETTE[kind]}</option>)}
          {corrente?.kind === 'tabella' ? <option value="tabella">{ETICHETTE.tabella}</option> : null}
        </select>
      </label>
      <Button type="button" tone="neutral" disabled={disabled || !corrente} aria-label="Togli questa parte dal documento" title="Togli questa parte" onClick={onTogli}>
        <Trash2 size={14} aria-hidden="true" />
      </Button>
      <Button type="button" tone="neutral" disabled={disabled} aria-pressed={trovaAperto} aria-label="Trova e sostituisci (Ctrl+F)" title="Trova e sostituisci (Ctrl+F)" onMouseDown={tieniLaSelezione} onClick={onTrova}>
        <Search size={14} aria-hidden="true" />
      </Button>
      <span className="iu-ocr-barra__stato">
        {corrente
          ? `${ETICHETTE[corrente.kind]}${corrente.kind === 'elenco' && markerOf(corrente) ? ` · ${ETICHETTE_MARCATORE[markerOf(corrente)!.tipo]}` : ''}${corrente.kind === 'numero_pagina' ? ' · escluso dal documento' : ''}${corrente.confidence ? ` · ${fiducia(corrente.confidence)}` : ''}${selezionati ? ` · ${selezionati} caratteri selezionati` : ''}`
          : 'Clicca nel testo per scegliere su cosa agire'}
      </span>
    </div>
  )
}
