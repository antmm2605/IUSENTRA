import { failIf, read, tsxFilesInNewReactSurface } from './full-react-check-utils.mjs'

const violations = []
const bootstrapTokens = new Set(['btn', 'card', 'container', 'row', 'navbar', 'dropdown'])

for (const file of tsxFilesInNewReactSurface()) {
  const source = read(file)
  for (const match of source.matchAll(/className\s*=\s*["']([^"']+)["']/g)) {
    const tokens = match[1].split(/\s+/).filter(Boolean)
    const found = tokens.find((token) => bootstrapTokens.has(token) || token.startsWith('col-'))
    if (found) violations.push(`${file}: classe Bootstrap vietata "${found}".`)
  }
}

failIf(violations, 'check-no-bootstrap-primary-react')
