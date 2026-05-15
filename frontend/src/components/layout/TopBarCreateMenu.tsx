import {
  BriefcaseBusiness,
  CalendarPlus,
  ClipboardList,
  FilePlus2,
  MailPlus,
  Plus,
  ReceiptText,
  UserPlus,
} from 'lucide-react'
import { useCallback, useMemo, useRef, type ReactNode } from 'react'
import { useClickOutside } from '../../hooks/useClickOutside'
import { useKeyboardShortcut } from '../../hooks/useKeyboardShortcut'
import type { TopbarCreateAction, TopbarCreateContext } from '../../types/topbar'

const iconMap: Record<string, ReactNode> = {
  case: <BriefcaseBusiness size={17} />,
  client: <UserPlus size={17} />,
  deadline: <CalendarPlus size={17} />,
  hearing: <CalendarPlus size={17} />,
  activity: <ClipboardList size={17} />,
  document: <FilePlus2 size={17} />,
  communication: <MailPlus size={17} />,
  invoice: <ReceiptText size={17} />,
}

function withContext(href: string, context: TopbarCreateContext) {
  if (!context.contextId || context.contextType === 'global') return href
  const params = new URLSearchParams()
  if (context.contextType === 'case') params.set('id_fascicolo', context.contextId)
  if (context.contextType === 'client') params.set('id_cliente', context.contextId)
  return `${href}${href.includes('?') ? '&' : '?'}${params.toString()}`
}

function buildActions(context: TopbarCreateContext): TopbarCreateAction[] {
  const caseId = context.contextType === 'case' ? context.contextId : null
  const clientId = context.contextType === 'client' ? context.contextId : null
  const contextual: TopbarCreateAction[] = []
  if (caseId) {
    contextual.push(
      {
        id: 'case-activity',
        label: 'Nuova attivita',
        description: 'Registra un passaggio operativo nel fascicolo corrente.',
        icon: 'activity',
        href: `/fascicoli/${encodeURIComponent(caseId)}?focus=attivita`,
        requiresPermission: 'fascicoli.scrivi',
      },
      {
        id: 'case-document',
        label: 'Nuovo documento',
        description: 'Apri gli strumenti documento collegati al fascicolo.',
        icon: 'document',
        href: `/fascicoli/${encodeURIComponent(caseId)}?focus=documenti`,
        requiresPermission: 'fascicoli.scrivi',
      },
      {
        id: 'case-deadline',
        label: 'Nuova scadenza',
        description: 'Crea una scadenza gia collegata al fascicolo.',
        icon: 'deadline',
        href: withContext('/scadenziario/nuova', context),
        requiresPermission: 'scadenziario.scrivi',
      },
      {
        id: 'case-hearing',
        label: 'Nuova udienza',
        description: 'Inserisci un appuntamento processuale nel calendario.',
        icon: 'hearing',
        href: withContext('/agenda/nuovo', context),
        requiresPermission: 'agenda.scrivi',
      },
    )
  }
  if (clientId) {
    contextual.push(
      {
        id: 'client-case',
        label: 'Nuovo fascicolo',
        description: 'Apri un fascicolo per il cliente corrente.',
        icon: 'case',
        href: withContext('/fascicoli/nuovo', context),
        requiresPermission: 'fascicoli.scrivi',
      },
      {
        id: 'client-invoice',
        label: 'Nuova fattura',
        description: 'Prepara una parcella o proforma per il cliente.',
        icon: 'invoice',
        href: `/fatturazione/nuova/${encodeURIComponent(clientId)}`,
        requiresPermission: null,
      },
      {
        id: 'client-communication',
        label: 'Nuova PEC',
        description: 'Componi una comunicazione collegata al cliente.',
        icon: 'communication',
        href: withContext('/email/scrivi', context),
        requiresPermission: 'messaggi.scrivi',
      },
    )
  }
  const general: TopbarCreateAction[] = [
    {
      id: 'new-case',
      label: 'Nuovo fascicolo',
      description: 'Crea una pratica di studio.',
      icon: 'case',
      href: '/fascicoli/nuovo',
      requiresPermission: 'fascicoli.scrivi',
    },
    {
      id: 'new-client',
      label: 'Nuovo cliente',
      description: 'Inserisci una nuova anagrafica.',
      icon: 'client',
      href: '/clienti/nuovo',
      requiresPermission: 'clienti.scrivi',
    },
    {
      id: 'new-deadline',
      label: 'Nuova scadenza',
      description: 'Aggiungi un termine allo scadenziario.',
      icon: 'deadline',
      href: '/scadenziario/nuova',
      requiresPermission: 'scadenziario.scrivi',
    },
    {
      id: 'new-hearing',
      label: 'Nuova udienza',
      description: 'Crea un appuntamento in agenda.',
      icon: 'hearing',
      href: '/agenda/nuovo',
      requiresPermission: 'agenda.scrivi',
    },
    {
      id: 'new-activity',
      label: 'Nuova attivita',
      description: 'Registra tempo o lavoro svolto nel timesheet.',
      icon: 'activity',
      href: '/timesheet',
      requiresPermission: null,
    },
    {
      id: 'new-document',
      label: 'Nuovo documento',
      description: 'Apri redazione atti e modelli documento.',
      icon: 'document',
      href: '/redazione-atti',
      requiresPermission: 'fascicoli.scrivi',
    },
    {
      id: 'new-communication',
      label: 'Nuova PEC',
      description: 'Componi una comunicazione dalla casella studio.',
      icon: 'communication',
      href: '/email/scrivi',
      requiresPermission: 'messaggi.scrivi',
    },
    {
      id: 'new-invoice',
      label: 'Nuova fattura',
      description: 'Apri il flusso parcella o proforma.',
      icon: 'invoice',
      href: '/fatturazione/nuova',
      requiresPermission: null,
    },
  ]
  const seen = new Set(contextual.map((action) => action.id.replace(/^case-|^client-/, 'new-')))
  return [...contextual, ...general.filter((action) => !seen.has(action.id))]
}

export function TopBarCreateMenu({
  context,
  open,
  onToggle,
  onClose,
  icon,
}: {
  context: TopbarCreateContext
  open: boolean
  onToggle: () => void
  onClose: () => void
  icon: ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const actions = useMemo(() => buildActions(context), [context])
  const matchAnyKey = useCallback(() => true, [])
  const handleEscape = useCallback((event: KeyboardEvent) => {
    if (event.key !== 'Escape' || !open) return
    event.preventDefault()
    onClose()
  }, [onClose, open])
  useKeyboardShortcut(matchAnyKey, handleEscape, open)
  useClickOutside(ref, open, onClose)

  return (
    <div className="iu-topbar-popover" ref={ref}>
      <button className="iu-new iu-topbar-new" type="button" onClick={onToggle} aria-haspopup="menu" aria-expanded={open} aria-label="Crea nuovo elemento" title="Crea nuovo elemento">
        {icon}
        <span>Nuovo</span>
      </button>
      {open ? (
        <div className="iu-topbar-panel iu-create-menu" role="menu" aria-label="Crea nuovo elemento">
          <header>
            <strong>{context.contextType === 'case' ? 'Azioni fascicolo' : context.contextType === 'client' ? 'Azioni cliente' : 'Crea rapidamente'}</strong>
            <small>{context.contextId ? 'Contesto corrente rilevato' : 'Azioni generali dello studio'}</small>
          </header>
          <div className="iu-create-menu__list">
            {actions.map((action) => (
              <a href={action.href} role="menuitem" key={action.id} onClick={onClose}>
                <span>{iconMap[action.icon] ?? <Plus size={17} />}</span>
                <span>
                  <strong>{action.label}</strong>
                  <small>{action.description}</small>
                </span>
              </a>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
