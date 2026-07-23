import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const requiredFiles = [
  'src/features/legal-skills/api.ts',
  'src/features/legal-skills/types.ts',
  'src/features/legal-skills/pages/LegalSkillsCatalogPage.tsx',
  'src/features/legal-skills/pages/LegalSkillsProfilePage.tsx',
  'src/features/legal-skills/pages/LegalSkillsRunPage.tsx',
  'src/features/legal-skills/pages/LegalSkillsReviewPage.tsx',
  'src/features/legal-skills/pages/PracticeProfilePage.tsx',
  'src/features/legal-skills/pages/ColdStartInterviewPage.tsx',
  'src/features/legal-skills/pages/LegalSkillRunPage.tsx',
  'src/features/legal-skills/pages/SkillRunDetailPage.tsx',
  'src/features/legal-skills/pages/ReviewerQueuePage.tsx',
  'src/features/legal-skills/pages/PromptLibraryPage.tsx',
  'src/features/legal-skills/components/ReviewerNoteBox.tsx',
  'src/features/legal-skills/components/CitationList.tsx',
  'src/features/legal-skills/components/SkillFindingTable.tsx',
  'src/features/legal-skills/components/SkillRunStatusBadge.tsx',
  'src/features/legal-skills/components/TrustCheckReport.tsx',
  'src/features/legal-skills/components/EscalationBox.tsx',
]

for (const file of requiredFiles) {
  if (!existsSync(resolve(root, file))) {
    throw new Error(`File Legal Skills mancante: ${file}`)
  }
}

const app = readFileSync(resolve(root, 'src/App.tsx'), 'utf8')
const flags = readFileSync(resolve(root, 'src/lib/featureFlags.ts'), 'utf8')
const api = readFileSync(resolve(root, 'src/features/legal-skills/api.ts'), 'utf8')
const runPage = readFileSync(resolve(root, 'src/features/legal-skills/pages/LegalSkillsRunPage.tsx'), 'utf8')

for (const token of [
  'routes.appV2.legalSkills.catalog',
  'routes.appV2.legalSkills.profile',
  'routes.appV2.legalSkills.run',
  'routes.appV2.legalSkills.reviewQueue',
  'routes.appV2.legalSkills.promptLibrary',
]) {
  if (!flags.includes(token)) throw new Error(`Feature flag Legal Skills non dichiarato: ${token}`)
}

for (const route of ['/legal-skills', '/legal-skills/profile', '/legal-skills/profile/cold-start', '/legal-skills/run', '/legal-skills/review-queue', '/legal-skills/runs', '/legal-skills/prompt']) {
  const direct = app.includes(route) || flags.includes(route)
  const regexGoverned = route === '/legal-skills/runs' && flags.includes('legal-skills') && flags.includes('runs')
  if (!direct && !regexGoverned) throw new Error(`Route Legal Skills non governata: ${route}`)
}

for (const component of ['PracticeProfilePage', 'ColdStartInterviewPage', 'LegalSkillRunPage', 'SkillRunDetailPage', 'ReviewerQueuePage', 'PromptLibraryPage']) {
  if (!app.includes(component)) throw new Error(`Pagina Legal Skills non agganciata alla shell: ${component}`)
}

if (api.includes('tenant_id') || api.includes('studio_id')) {
  throw new Error('La UI Legal Skills non deve inviare identificativi studio controllati dal client.')
}

if (!runPage.includes('ReviewerNoteBox') || !runPage.includes('CitationList') || !runPage.includes('legal_skills.approva')) {
  throw new Error('La pagina esecuzione deve mostrare revisione, fonti e approvazione governata.')
}

console.log('check-legal-skills ok')
