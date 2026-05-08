import { Sparkles } from 'lucide-react'
import './shell.css'

export function LexFloatingButton({ href = '/lex-operativo' }: { href?: string }) {
  return (
    <a className="iu-btn iu-btn--primary iu-lex-floating" href={href} aria-label="Apri Lex">
      <Sparkles size={18} aria-hidden="true" />
      Lex
    </a>
  )
}
