import { failIf, fullRoutes, routeSources } from './full-react-check-utils.mjs'

const violations = []

for (const route of fullRoutes()) {
  const sources = routeSources(route)
  const combined = `${sources.component}\n${sources.data}\n${sources.bridge}`
  if (!combined.includes('?_legacy=1')) continue
  if (!/Rollback tecnico|fallback tecnico|legacy_fallback/i.test(combined)) {
    violations.push(`${route.route}: contiene ?_legacy=1 senza confinamento a rollback tecnico.`)
  }
}

failIf(violations, 'check-no-primary-legacy-links')
