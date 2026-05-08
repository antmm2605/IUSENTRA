import { MAIN_NAV_ROUTES } from '../app/routes'
import './shell.css'

const MOBILE_FAMILIES = ['regia', 'fascicoli', 'agenda', 'mandato', 'telematico']

export function MobileNav({ activePath = window.location.pathname }: { activePath?: string }) {
  return (
    <nav className="iu-mobile-nav" aria-label="Navigazione mobile">
      {MAIN_NAV_ROUTES.filter((route) => MOBILE_FAMILIES.includes(route.family)).map((route) => {
        const Icon = route.icon
        const active = activePath === route.path || activePath.startsWith(`${route.path}/`)
        return (
          <a className={active ? 'is-active' : ''} href={route.path} key={route.path} aria-label={route.label}>
            <Icon size={19} aria-hidden="true" />
            <span>{route.label}</span>
          </a>
        )
      })}
    </nav>
  )
}
