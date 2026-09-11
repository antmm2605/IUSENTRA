import type { ComponentType, MouseEvent as ReactMouseEvent } from 'react'
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  Code2,
  Highlighter,
  IndentDecrease,
  IndentIncrease,
  Italic,
  List,
  ListOrdered,
  PanelLeftOpen,
  PanelRightOpen,
  Printer,
  Redo2,
  RemoveFormatting,
  SeparatorHorizontal,
  Strikethrough,
  Underline,
  Undo2,
} from 'lucide-react'
import type { BlockFormat, SelectionFormats } from './useSelectionFormats'

export const TEXT_COLORS = [
  { id: 'ink', label: 'Nero documento', value: 'rgb(27, 34, 48)' },
  { id: 'navy', label: 'Blu scuro', value: 'rgb(30, 58, 107)' },
  { id: 'blue', label: 'Blu', value: 'rgb(29, 95, 191)' },
  { id: 'green', label: 'Verde', value: 'rgb(31, 122, 77)' },
  { id: 'red', label: 'Rosso', value: 'rgb(180, 35, 24)' },
  { id: 'orange', label: 'Arancio', value: 'rgb(180, 83, 9)' },
  { id: 'purple', label: 'Viola', value: 'rgb(107, 63, 160)' },
  { id: 'gray', label: 'Grigio', value: 'rgb(91, 102, 120)' },
]

export const HIGHLIGHT_COLORS = [
  { id: 'yellow-mark', label: 'Evidenziatore giallo', value: 'rgb(255, 242, 168)' },
  { id: 'green-mark', label: 'Evidenziatore verde', value: 'rgb(216, 245, 208)' },
  { id: 'blue-mark', label: 'Evidenziatore azzurro', value: 'rgb(214, 232, 255)' },
  { id: 'pink-mark', label: 'Evidenziatore rosa', value: 'rgb(255, 217, 230)' },
  { id: 'none', label: 'Nessuna evidenziazione', value: 'transparent' },
]

export const LINE_SPACING_OPTIONS = [1.2, 1.5, 1.9, 2, 2.5]

const BLOCK_OPTIONS: Array<{ value: BlockFormat; label: string }> = [
  { value: 'p', label: 'Normale' },
  { value: 'h1', label: 'Titolo 1' },
  { value: 'h2', label: 'Titolo 2' },
  { value: 'h3', label: 'Titolo 3' },
  { value: 'blockquote', label: 'Citazione' },
]

type ToolButton = {
  label: string
  icon: ComponentType<{ size?: number; 'aria-hidden'?: boolean | 'true' }>
  action: () => void
  active?: boolean
  disabled?: boolean
}

type Props = {
  fonts: Array<{ key: string; label: string }>
  fontKey: string
  fontSizes: number[]
  fontSize: number
  formats: SelectionFormats
  documentAlign: string
  lineHeight: number
  canUndo: boolean
  canRedo: boolean
  catalogOpen: boolean
  panelOpen: boolean
  placeholdersActive: boolean
  onUndo: () => void
  onRedo: () => void
  onBlockFormat: (block: BlockFormat) => void
  onFont: (fontKey: string) => void
  onFontSize: (size: number) => void
  onCommand: (command: string) => void
  onTextColor: (color: string) => void
  onHighlight: (color: string) => void
  onLineHeight: (value: number) => void
  onPageBreak: () => void
  onClearFormatting: () => void
  onPlaceholders: () => void
  onToggleCatalog: () => void
  onTogglePanel: () => void
  onPrint: () => void
}

const keepSelection = (event: ReactMouseEvent) => event.preventDefault()

function closeMenu(event: ReactMouseEvent<HTMLElement>) {
  event.currentTarget.closest('details')?.removeAttribute('open')
}

function IconButtons({ tools }: { tools: ToolButton[] }) {
  return (
    <>
      {tools.map((tool) => {
        const Icon = tool.icon
        return (
          <button
            type="button"
            className={tool.active ? 'is-active' : ''}
            title={tool.label}
            aria-label={tool.label}
            aria-pressed={tool.active === undefined ? undefined : Boolean(tool.active)}
            disabled={tool.disabled}
            key={tool.label}
            onMouseDown={keepSelection}
            onClick={tool.action}
          >
            <Icon size={15} aria-hidden="true" />
          </button>
        )
      })}
    </>
  )
}

export function DocumentToolbar(props: Props) {
  const align = props.formats.align || props.documentAlign
  const sizeOptions = props.fontSizes.includes(props.fontSize) ? props.fontSizes : [...props.fontSizes, props.fontSize].sort((left, right) => left - right)
  return (
    <div className="iu-template-pro-toolbar" role="toolbar" aria-label="Barra strumenti documento">
      <div className="iu-ted-toolbar-group">
        <IconButtons tools={[
          { label: 'Annulla', icon: Undo2, action: props.onUndo, disabled: !props.canUndo },
          { label: 'Ripristina', icon: Redo2, action: props.onRedo, disabled: !props.canRedo },
        ]} />
      </div>
      <div className="iu-ted-toolbar-group">
        <select className="iu-ted-toolbar-select iu-ted-toolbar-select--style" aria-label="Stile paragrafo" value={props.formats.block} onChange={(event) => props.onBlockFormat(event.currentTarget.value as BlockFormat)}>
          {BLOCK_OPTIONS.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
        </select>
        <select className="iu-ted-toolbar-select iu-ted-toolbar-select--font" aria-label="Font testo selezionato" value={props.fontKey} onChange={(event) => props.onFont(event.currentTarget.value)}>
          {props.fonts.map((font) => <option value={font.key} key={font.key}>{font.label}</option>)}
        </select>
        <select className="iu-ted-toolbar-select iu-ted-toolbar-select--size" aria-label="Dimensione testo selezionato" value={props.fontSize} onChange={(event) => props.onFontSize(Number(event.currentTarget.value))}>
          {sizeOptions.map((size) => <option value={size} key={size}>{size} pt</option>)}
        </select>
      </div>
      <div className="iu-ted-toolbar-group">
        <IconButtons tools={[
          { label: 'Grassetto', icon: Bold, action: () => props.onCommand('bold'), active: props.formats.bold },
          { label: 'Corsivo', icon: Italic, action: () => props.onCommand('italic'), active: props.formats.italic },
          { label: 'Sottolineato', icon: Underline, action: () => props.onCommand('underline'), active: props.formats.underline },
          { label: 'Barrato', icon: Strikethrough, action: () => props.onCommand('strikeThrough'), active: props.formats.strikeThrough },
        ]} />
        <details className="iu-ted-color">
          <summary title="Colore testo" aria-label="Colore testo" onMouseDown={keepSelection}>
            <Baseline size={15} aria-hidden="true" />
          </summary>
          <div className="iu-ted-color__panel" role="menu" aria-label="Colori testo">
            <span className="iu-ted-color__title" aria-hidden="true">Colore testo</span>
            {TEXT_COLORS.map((color) => (
              <button type="button" role="menuitem" className={`iu-ted-swatch--${color.id}`} title={color.label} aria-label={color.label} key={color.id} onMouseDown={keepSelection} onClick={(event) => { props.onTextColor(color.value); closeMenu(event) }} />
            ))}
          </div>
        </details>
        <details className="iu-ted-color">
          <summary title="Evidenzia" aria-label="Evidenzia" onMouseDown={keepSelection}>
            <Highlighter size={15} aria-hidden="true" />
          </summary>
          <div className="iu-ted-color__panel" role="menu" aria-label="Colori evidenziatore">
            <span className="iu-ted-color__title" aria-hidden="true">Evidenziatore</span>
            {HIGHLIGHT_COLORS.map((color) => (
              <button type="button" role="menuitem" className={`iu-ted-swatch--${color.id}`} title={color.label} aria-label={color.label} key={color.id} onMouseDown={keepSelection} onClick={(event) => { props.onHighlight(color.value); closeMenu(event) }} />
            ))}
          </div>
        </details>
      </div>
      <div className="iu-ted-toolbar-group">
        <IconButtons tools={[
          { label: 'Allinea a sinistra', icon: AlignLeft, action: () => props.onCommand('justifyLeft'), active: align === 'left' },
          { label: 'Centra', icon: AlignCenter, action: () => props.onCommand('justifyCenter'), active: align === 'center' },
          { label: 'Allinea a destra', icon: AlignRight, action: () => props.onCommand('justifyRight'), active: align === 'right' },
          { label: 'Giustifica', icon: AlignJustify, action: () => props.onCommand('justifyFull'), active: align === 'justify' },
        ]} />
      </div>
      <div className="iu-ted-toolbar-group">
        <IconButtons tools={[
          { label: 'Elenco puntato', icon: List, action: () => props.onCommand('insertUnorderedList'), active: props.formats.unorderedList },
          { label: 'Elenco numerato', icon: ListOrdered, action: () => props.onCommand('insertOrderedList'), active: props.formats.orderedList },
          { label: 'Riduci rientro', icon: IndentDecrease, action: () => props.onCommand('outdent') },
          { label: 'Aumenta rientro', icon: IndentIncrease, action: () => props.onCommand('indent') },
        ]} />
        <select className="iu-ted-toolbar-select iu-ted-toolbar-select--spacing" aria-label="Interlinea documento" title="Interlinea documento" value={String(props.lineHeight)} onChange={(event) => props.onLineHeight(Number(event.currentTarget.value))}>
          {(LINE_SPACING_OPTIONS.includes(props.lineHeight) ? LINE_SPACING_OPTIONS : [...LINE_SPACING_OPTIONS, props.lineHeight].sort((left, right) => left - right))
            .map((value) => <option value={String(value)} key={value}>{value.toLocaleString('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 2 })}</option>)}
        </select>
      </div>
      <div className="iu-ted-toolbar-group">
        <IconButtons tools={[
          { label: 'Interruzione di pagina (Ctrl+Invio)', icon: SeparatorHorizontal, action: props.onPageBreak },
          { label: 'Cancella formattazione', icon: RemoveFormatting, action: props.onClearFormatting },
          { label: 'Segnaposto', icon: Code2, action: props.onPlaceholders, active: props.placeholdersActive },
        ]} />
      </div>
      <span className="iu-template-pro-toolbar__spacer" />
      <div className="iu-ted-toolbar-group">
        <IconButtons tools={[
          { label: props.catalogOpen ? 'Chiudi catalogo template' : 'Apri catalogo template', icon: PanelLeftOpen, action: props.onToggleCatalog, active: props.catalogOpen },
          { label: props.panelOpen ? 'Chiudi pannello campi' : 'Mostra campi', icon: PanelRightOpen, action: props.onTogglePanel, active: props.panelOpen },
        ]} />
        <button type="button" className="iu-template-pro-print-button" title="Stampa documento" onClick={props.onPrint}>
          <Printer size={15} aria-hidden="true" />
          Stampa
        </button>
      </div>
    </div>
  )
}
