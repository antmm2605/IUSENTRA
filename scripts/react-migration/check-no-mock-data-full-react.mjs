import { failIf, fullRoutes, routeSources } from './full-react-check-utils.mjs'

const violations = []
const mockPattern = /\bmock_fallback\s*:\s*true\b|\bmockDashboard\b|dati demo|dati finti|demoMode\s*:\s*true/i

for (const route of fullRoutes()) {
  const sources = routeSources(route)
  const combined = `${sources.component}\n${sources.data}`
  if (mockPattern.test(combined)) {
    violations.push(`${route.route}: dati mock/demo rilevati in superficie full React.`)
  }
}

failIf(violations, 'check-no-mock-data-full-react')
