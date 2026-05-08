import { MAIN_NAV_ROUTES } from '../app/routes'
import './shell.css'

export function Sidebar({ activePath = window.location.pathname }: { activePath?: string }) {
  return (
    <aside className="iu-shell-sidebar" aria-label="Navigazione principale">
      <div className="iu-shell-sidebar__brand">
        <strong>IUSENTRA</strong>
        <span>Studio legale</span>
      </div>
      <nav>
        {MAIN_NAV_ROUTES.map((route) => {
          const Icon = route.icon
          const active = activePath === route.path || activePath.startsWith(`${route.path}/`)
          return (
            <a className={`iu-shell-nav-link ${active ? 'is-active' : ''}`} href={route.path} key={route.path}>
              <Icon size={18} aria-hidden="true" />
              <span>{route.label}</span>
            </a>
          )
        })}
      </nav>
    </aside>
  )
}
