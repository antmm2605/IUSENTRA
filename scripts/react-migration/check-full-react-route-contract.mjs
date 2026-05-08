import { execFileSync } from 'node:child_process'
import { failIf, fullRoutes, read } from './full-react-check-utils.mjs'

execFileSync(process.execPath, ['scripts/react-migration/audit-anti-mascheramento.mjs'], { stdio: 'inherit' })
execFileSync(process.execPath, ['scripts/react-migration/check-no-fake-react-full.mjs'], { stdio: 'inherit' })

const api = read('web/blueprints/api_v1_react.py')
const violations = []

for (const route of fullRoutes()) {
  const clean = route.route.replace(/\*$/, '').replace(/\/+$/, '') || '/'
  const apiPart = clean === '/' ? '/bootstrap' : clean
  if (!api.includes(`("${apiPart}")`) && !api.includes(`('${apiPart}')`)) {
    violations.push(`${route.route}: endpoint GET JSON non rilevato in api_v1_react.py.`)
  }
}

failIf(violations, 'check-full-react-route-contract')
