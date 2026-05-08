import { failIf, fullRoutes, routeSources } from './full-react-check-utils.mjs'

const violations = []

for (const route of fullRoutes()) {
  const sources = routeSources(route)
  if (/\bLegacyPostForm\b/.test(sources.component)) {
    violations.push(`${route.route}: LegacyPostForm nel componente dichiarato full React.`)
  }
}

failIf(violations, 'check-no-legacy-post-form')
