import { ArrowLeft, ArrowRight } from 'lucide-react'
import './MailboxPagination.css'

type Props = {
  position: 'top' | 'bottom'
  offset: number
  total: number
  limit: number
  loading: boolean
  onChange: (offset: number) => void
}

export function MailboxPagination({ position, offset, total, limit, loading, onChange }: Props) {
  if (total <= limit && offset === 0) return null
  return (
    <nav className="iu-mail-pagination" data-iusentra-sequence-slot={position === 'top' ? 'primary-actions' : 'pagination-footer'} aria-label={`Pagine dei messaggi ${position === 'top' ? "sopra" : "sotto"} l'elenco`}>
      <span role="status">{loading ? 'Caricamento messaggi...' : `Pagina ${Math.floor(offset / limit) + 1} di ${Math.max(1, Math.ceil(total / limit))}`}</span>
      <div>
        <button className="iu-button iu-button--secondary" type="button" disabled={loading || offset === 0} onClick={() => onChange(Math.max(0, offset - limit))}>
          <ArrowLeft size={15} aria-hidden="true" /> Precedenti
        </button>
        <button className="iu-button iu-button--secondary" type="button" disabled={loading || offset + limit >= total} onClick={() => onChange(offset + limit)}>
          Successivi <ArrowRight size={15} aria-hidden="true" />
        </button>
      </div>
    </nav>
  )
}
