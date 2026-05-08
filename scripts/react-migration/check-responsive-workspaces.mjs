import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { failIf, read, root } from './full-react-check-utils.mjs'

const required = [
  'frontend/src/theme/layout.css',
  'frontend/src/theme/tokens.css',
  'frontend/src/theme/legal-ui.css',
  'frontend/src/ui/ui.css',
  'frontend/src/shell/shell.css',
]
const violations = []

for (const path of required) {
  if (!existsSync(resolve(root, path))) violations.push(`${path}: file responsive/token mancante.`)
}

for (const path of ['frontend/src/ui/ui.css', 'frontend/src/shell/shell.css']) {
  if (!read(path).includes('@media')) violations.push(`${path}: media query responsive non rilevate.`)
}

failIf(violations, 'check-responsive-workspaces')
