import { failIf, read, tsxFilesInNewReactSurface } from './full-react-check-utils.mjs'
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { root } from './full-react-check-utils.mjs'

const violations = []
const requiredComponents = [
  'ActionCard.tsx',
  'CompactCard.tsx',
  'Workspace.tsx',
  'WorkspaceHeader.tsx',
  'FilterBar.tsx',
  'AdvancedFilters.tsx',
  'ResponsiveTable.tsx',
  'PermissionDeniedState.tsx',
  'StickyActionBar.tsx',
  'NextActionPanel.tsx',
]

for (const component of requiredComponents) {
  if (!existsSync(resolve(root, 'frontend/src/ui', component))) {
    violations.push(`frontend/src/ui/${component}: componente richiesto mancante.`)
  }
}

if (!existsSync(resolve(root, 'frontend/src/theme/legal-ui.css'))) {
  violations.push('frontend/src/theme/legal-ui.css: tema legale mancante.')
}

for (const file of tsxFilesInNewReactSurface()) {
  const source = read(file)
  if (/#[0-9a-fA-F]{3,8}/.test(source)) {
    violations.push(`${file}: colore hardcoded nel TSX.`)
  }
  if (/\b(Submit|Payload|Endpoint|Forbidden|Unauthorized|Internal server error|Undefined|Loading data|Retry request)\b/.test(source)) {
    violations.push(`${file}: linguaggio tecnico o inglese visibile rilevato.`)
  }
}

for (const file of ['frontend/src/ui/ErrorState.tsx', 'frontend/src/ui/EmptyState.tsx', 'frontend/src/ui/LoadingState.tsx']) {
  if (!existsSync(resolve(root, file))) violations.push(`${file}: stato UI obbligatorio mancante.`)
}

failIf(violations, 'run-legal-ui-checks')
execFileSync(process.execPath, ['scripts/react-migration/check-no-bootstrap-primary-react.mjs'], { stdio: 'inherit' })
execFileSync(process.execPath, ['scripts/react-migration/check-responsive-workspaces.mjs'], { stdio: 'inherit' })
console.log('run-legal-ui-checks: OK')
