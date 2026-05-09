import { execFileSync } from 'node:child_process'
import { failIf, fullRoutes, read } from './full-react-check-utils.mjs'

execFileSync(process.execPath, ['scripts/react-migration/audit-anti-mascheramento.mjs'], { stdio: 'inherit' })
execFileSync(process.execPath, ['scripts/react-migration/check-no-fake-react-full.mjs'], { stdio: 'inherit' })

const api = read('web/blueprints/api_v1_react.py')
const violations = []
const apiAliasMarkers = new Map([
  ['/impostazioni/calendario', ['("/impostazioni")', "('/impostazioni')"]],
  ['/impostazioni/pagamenti', ['("/impostazioni")', "('/impostazioni')"]],
  ['/notifiche', ['("/impostazioni")', "('/impostazioni')"]],
  ['/notifiche-whatsapp', ['("/impostazioni")', "('/impostazioni')"]],
  ['/sincronizzazione-calendari', ['("/impostazioni")', "('/impostazioni')"]],
  ['/strumenti-legali', ['("/studio-modules/<module_id>")', "('/studio-modules/<module_id>')"]],
  ['/strumenti-operativi', ['("/studio-modules/<module_id>")', "('/studio-modules/<module_id>')"]],
  ['/deposito/checklist', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
])

for (const route of fullRoutes()) {
  const clean = route.route.replace(/\*$/, '').replace(/\/+$/, '') || '/'
  const apiPart = clean === '/' ? '/bootstrap' : clean
  const markers = apiAliasMarkers.get(route.route) || [`("${apiPart}")`, `('${apiPart}')`]
  if (!markers.some((marker) => api.includes(marker))) {
    violations.push(`${route.route}: endpoint GET JSON non rilevato in api_v1_react.py.`)
  }
}

failIf(violations, 'check-full-react-route-contract')
