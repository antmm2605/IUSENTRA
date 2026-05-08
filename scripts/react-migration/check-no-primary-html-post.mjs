import { failIf, fullRoutes, routeSources } from './full-react-check-utils.mjs'

const violations = []
const htmlPostPattern = /<form[^>]*method=["']post["']|method=["']post["'][^>]*action=/i

for (const route of fullRoutes()) {
  const sources = routeSources(route)
  if (htmlPostPattern.test(sources.component)) {
    violations.push(`${route.route}: form HTML method=post nel componente dichiarato full React.`)
  }
}

failIf(violations, 'check-no-primary-html-post')
