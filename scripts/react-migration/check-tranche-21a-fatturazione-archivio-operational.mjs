import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(new URL('../..', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'))
const page = readFileSync(resolve(root, 'frontend/src/components/FatturazionePage.tsx'), 'utf8')
const data = readFileSync(resolve(root, 'frontend/src/fatturazioneData.ts'), 'utf8')
const api = readFileSync(resolve(root, 'web/blueprints/api_v1_react.py'), 'utf8')
const bridge = readFileSync(resolve(root, 'web/services/react_fatturazione_bridge.py'), 'utf8')
const manifest = JSON.parse(readFileSync(resolve(root, 'tools/react-migration/route-manifest.json'), 'utf8'))
const violations = []

const route = manifest.routes.find((item) => item.route === '/fatturazione')
if (route?.status !== 'react_operational_full') violations.push('manifest /fatturazione non react_operational_full.')
if (/\bLegacyPostForm\b/.test(page)) violations.push('FatturazionePage contiene LegacyPostForm.')
if (!/\bgetFatturazionePage\b/.test(page)) violations.push('FatturazionePage non usa getFatturazionePage.')
if (!/\bgetFatturazioneDetail\b/.test(page)) violations.push('FatturazionePage non usa dettaglio JSON.')
if (!/\bapiPostJson\b/.test(data)) violations.push('fatturazioneData non usa apiPostJson.')
if (/response\.blob|fetch\s*\([^)]*blob/i.test(data)) violations.push('fatturazioneData usa fetch/blob.')
if (/URL\.createObjectURL/.test(page)) violations.push('FatturazionePage usa URL.createObjectURL.')
if (!api.includes('@api_v1_react.get("/fatturazione")')) violations.push('manca GET JSON /fatturazione.')
if (!api.includes('@api_v1_react.get("/fatturazione/<id_documento>")')) violations.push('manca GET JSON /fatturazione/<id>.')
if (!/["']writes["']\s*:\s*["']json_api["']/.test(bridge)) violations.push('bridge non dichiara writes json_api.')
if (/\?_legacy=1/.test(page) && !/Rollback tecnico/.test(page)) violations.push('uso non tecnico di ?_legacy=1.')
if (/localStorage|sessionStorage/.test(`${page}\n${data}`)) violations.push('uso storage browser non ammesso.')
if (/"(token|api_key|secret|stack_trace|traceback|absolute_path|full_path)"\s*:/i.test(bridge)) violations.push('payload bridge espone campo sensibile.')
for (const state of ['loading', 'saving', 'success', 'error']) {
  if (!page.includes(state)) violations.push(`stato UI mancante: ${state}.`)
}
if (violations.length) {
  console.error(`Tranche 21A non conforme:\n- ${violations.join('\n- ')}`)
  process.exit(1)
}
console.log('Tranche 21A fatturazione archivio operational OK.')
