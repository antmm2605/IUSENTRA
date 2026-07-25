import { execFileSync } from 'node:child_process'
import { failIf, fullRoutes, read } from './full-react-check-utils.mjs'

execFileSync(process.execPath, ['scripts/react-migration/audit-anti-mascheramento.mjs'], { stdio: 'inherit' })
execFileSync(process.execPath, ['scripts/react-migration/check-no-fake-react-full.mjs'], { stdio: 'inherit' })

const api = [
  read('web/blueprints/api_v1_react.py'),
  read('web/blueprints/api_v1_client_portal.py'),
  read('web/blueprints/api_v1_daily_plan.py'),
  read('web/blueprints/api_v1_legal_skills.py'),
].join('\n')
const violations = []
const apiAliasMarkers = new Map([
  ['/app/portale-clienti', ['@api_v1_client_portal.get("/dashboard")', '@api_v1_client_portal.get("/studio/dashboard")']],
  ['/workspace-intelligente', ['("/dashboard")', "('/dashboard')"]],
  ['/regia-operativa', ['("/dashboard")', "('/dashboard')"]],
  ['/ricerca-studio', ['("/global-search")', "('/global-search')"]],
  ['/agenda/nuovo', ['("/agenda")', "('/agenda')"]],
  ['/clienti/:id/cartella', ['("/clienti/<id_cliente>/cartella")', "('/clienti/<id_cliente>/cartella')"]],
  ['/soggetti/nuovo', ['("/clienti/nuovo")', "('/clienti/nuovo')"]],
  ['/privacy/registro/nuovo', ['("/privacy/registro")', "('/privacy/registro')"]],
  ['/registro-gdpr', ['("/privacy/registro")', "('/privacy/registro')"]],
  ['/importa-pratiche', ['("/import/quickorganizer")', "('/import/quickorganizer')"]],
  ['/importa-pratiche-studio-telematico', ['("/import/quickorganizer")', "('/import/quickorganizer')"]],
  ['/scadenziario/:id', ['("/scadenziario")', "('/scadenziario')"]],
  ['/scadenziario/:id/modifica', ['("/scadenziario/nuova")', "('/scadenziario/nuova')"]],
  ['/fascicoli/:id/deposito/prepara', ['@api_v1_react.get("/fascicoli/<id_fasc>")']],
  ['/impostazioni/calendario', ['("/impostazioni")', "('/impostazioni')"]],
  ['/impostazioni/pagamenti', ['("/impostazioni")', "('/impostazioni')"]],
  ['/impostazioni/sdi', ['("/impostazioni")', "('/impostazioni')"]],
  ['/notifiche', ['("/impostazioni")', "('/impostazioni')"]],
  ['/notifiche-whatsapp', ['("/impostazioni")', "('/impostazioni')"]],
  ['/sincronizzazione-calendari', ['("/impostazioni")', "('/impostazioni')"]],
  ['/documenti', ['("/studio-modules/<module_id>")', "('/studio-modules/<module_id>')"]],
  ['/strumenti-legali', ['("/studio-modules/<module_id>")', "('/studio-modules/<module_id>')"]],
  ['/strumenti-operativi', ['("/studio-modules/<module_id>")', "('/studio-modules/<module_id>')"]],
  ['/deposito/checklist', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/polisWeb', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/pdp', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/pat', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/sigit', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/tribunali', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/guida/firma-digitale', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/portali/pst/acquisizione', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/portali/pdp/acquisizione', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/portali/pat/acquisizione', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/portali/ptt/acquisizione', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/portali/sigit/acquisizione', ['("/telematico/surface/<surface>")', "('/telematico/surface/<surface>')"]],
  ['/servizi-telematici', ['("/telematico")', "('/telematico')"]],
  ['/preventivi/conferimento/:id', ['("/preventivi/conferimento/<id_conferimento>")', "('/preventivi/conferimento/<id_conferimento>')"]],
  ['/legal-skills', ['@api_v1_legal_skills.get("/packs")', '@api_v1_legal_skills.get("/profile")']],
  ['/portale-cliente', ['@api_v1_client_portal.get("/public/dashboard")', '@api_v1_client_portal.get("/public/invites/<path:token>")']],
  ['/oggi', ['@api_v1_daily_plan.get("/daily-plan")']],
  ['/sito-studio/articoli/:id/modifica', ['("/sito-studio/articoli/<int:article_id>/modifica")', "('/sito-studio/articoli/<int:article_id>/modifica')"]],
])

for (const route of fullRoutes()) {
  const isStaticReactHub = route.targetBridge === 'web/blueprints/react_shell.py'
    && route.targetData === route.targetComponent
    && !/\bapiJson\b|\bapiPostJson\b|\bfetch\s*\(/.test(read(route.targetComponent || ''))
  if (isStaticReactHub) {
    continue
  }
  const clean = route.route.replace(/\*$/, '').replace(/\/+$/, '') || '/'
  const apiPart = clean === '/' ? '/bootstrap' : clean
  const markers = apiAliasMarkers.get(route.route) || [`("${apiPart}")`, `('${apiPart}')`]
  if (!markers.some((marker) => api.includes(marker))) {
    violations.push(`${route.route}: endpoint GET JSON non rilevato nei blueprint API React.`)
  }
}

failIf(violations, 'check-full-react-route-contract')
