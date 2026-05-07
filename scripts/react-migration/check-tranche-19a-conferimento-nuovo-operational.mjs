import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const page = readFileSync(resolve(root, 'frontend/src/components/PreventiviPage.tsx'), 'utf8')
const data = readFileSync(resolve(root, 'frontend/src/preventiviData.ts'), 'utf8')
const api = readFileSync(resolve(root, 'web/blueprints/api_v1_react.py'), 'utf8')
const bridge = readFileSync(resolve(root, 'web/services/react_preventivi_bridge.py'), 'utf8')
const manifest = JSON.parse(readFileSync(resolve(root, 'tools/react-migration/route-manifest.json'), 'utf8'))
const violations = []

const route = manifest.routes.find((item) => item.route === '/preventivi/conferimento/nuovo')
if (route?.status !== 'react_operational_full') violations.push('manifest /preventivi/conferimento/nuovo non react_operational_full.')
if (/\bLegacyPostForm\b/.test(page)) violations.push('PreventiviPage contiene LegacyPostForm.')
if (!/\bcreateConferimento\b/.test(page)) violations.push('PreventiviPage non usa createConferimento.')
if (!/\bapiPostJson\b/.test(data)) violations.push('preventiviData non usa apiPostJson.')
if (/response\.blob|fetch\s*\([^)]*blob/i.test(data)) violations.push('preventiviData usa fetch/blob.')
if (/URL\.createObjectURL/.test(page)) violations.push('PreventiviPage usa URL.createObjectURL.')
if (!api.includes('@api_v1_react.post("/preventivi/conferimento/nuovo")')) violations.push('manca POST JSON /preventivi/conferimento/nuovo.')
if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) violations.push('bridge non dichiara writes json_api.')
if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) violations.push('uso non tecnico di ?_legacy=1.')
if (/localStorage|sessionStorage/.test(`${page}\n${data}`)) violations.push('uso storage browser non ammesso.')
if (/"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:/i.test(bridge)) violations.push('payload bridge espone campo sensibile.')
for (const state of ['loading', 'saving', 'success', 'error']) {
  if (!page.includes(state)) violations.push(`stato UI mancante: ${state}.`)
}

if (violations.length) {
  console.error(`Tranche 19A non conforme:\n- ${violations.join('\n- ')}`)
  process.exit(1)
}
console.log('Tranche 19A conferimento operational OK.')
