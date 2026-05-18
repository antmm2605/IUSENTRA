import { execSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'

mkdirSync('artifacts/react-migration/patches', { recursive: true })

const args = process.argv.slice(2)
const TRANCHE_2A_FLAG = '--tranche=2a'
const TRANCHE_3A_FLAG = '--tranche=3a'
const TRANCHE_4A_FLAG = '--tranche=4a'
const TRANCHE_5A_FLAG = '--tranche=5a'
const TRANCHE_6A_FLAG = '--tranche=6a'
const TRANCHE_7A_FLAG = '--tranche=7a'
const TRANCHE_8A_FLAG = '--tranche=8a'
const TRANCHE_9A_FLAG = '--tranche=9a'
const TRANCHE_10A_FLAG = '--tranche=10a'
const tranche = args.find((arg) => arg.startsWith('--tranche='))?.split('=')[1] || ''
const EXEC_BUFFER = 1024 * 1024 * 200

const migrationPaths = [
  'CHANGELOG.md',
  'Dockerfile',
  'README.md',
  'docs/REACT_MIGRATION_MASTER_PLAN.md',
  'frontend/package.json',
  'pnpm-lock.yaml',
  'frontend/scripts/check-react-contracts.mjs',
  'frontend/src/theme',
  'frontend/src/ui',
  'pct/__init__.py',
  'railway.toml',
  'setup.py',
  'scripts/react-migration',
  'tools/react-migration',
  'artifacts/react-migration/audit.md',
  'artifacts/react-migration/legacy-contracts',
  'artifacts/react-migration/route-gate.md',
  'artifacts/react-migration/route-inventory.json',
  'artifacts/react-migration/ui-consistency.md',
]

const tranche2aContracts = [
  '/statistiche',
  '/audit',
  '/registro-attivita',
  '/utenti',
  '/profili',
  '/backup',
]

const tranche3aContracts = [
  '/utenti',
  '/utenti/nuovo',
  '/profili',
  '/backup',
]

const tranche4aContracts = [
  '/backup',
  '/sito-studio',
  '/sito-studio/contatti',
  '/sito-studio/builder',
  '/studio',
  '/impostazioni',
]

const tranche5aContracts = [
  '/studio',
  '/amministrazione',
  '/impostazioni',
  '/impostazioni-studio',
  '/impostazioni/calendario',
  '/impostazioni/pagamenti',
  '/sincronizzazione-calendari',
]

const tranche6aContracts = [
  '/fatturazione',
  '/fatturazione/nuova',
  '/incassi-pagamenti',
  '/impostazioni/pagamenti',
  '/preventivi',
  '/compensi-forensi',
  '/tariffario',
]

const tranche7aContracts = [
  '/preventivi',
  '/preventivi/nuovo',
  '/preventivi/conferimento/nuovo',
  '/preventivi/wizard',
  '/compensi-forensi',
  '/tariffario',
]

const tranche8aContracts = [
  '/compensi-forensi',
  '/tariffario',
  '/preventivi/wizard',
  '/preventivi',
  '/fatturazione',
  '/template-atti',
  '/redazione-atti',
]

const tranche9aContracts = [
  '/template-atti',
  '/template-atti/catalogo',
  '/template-atti/nuovo',
  '/redazione-atti',
  '/checklist',
  '/deposito/checklist',
  '/giurisprudenza',
  '/legal-intelligence',
]

const tranche10aContracts = [
  '/giurisprudenza',
  '/giurisprudenza/nuova',
  '/legal-intelligence',
  '/legal-intelligence/news',
  '/legal-intelligence/mediazione',
  '/ricerca-legale',
  '/checklist',
  '/deposito/checklist',
]

const tranche2aPatchGroups = {
  backend: [
    'web/services/react_statistiche_bridge.py',
    'web/services/react_audit_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/lib/apiClient.ts',
    'frontend/src/statisticheData.ts',
    'frontend/src/auditData.ts',
    'frontend/src/components/StatistichePage.tsx',
    'frontend/src/components/StatistichePage.css',
    'frontend/src/components/AuditPage.tsx',
    'frontend/src/components/AuditPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-2a-gate.py',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-2a-preflight.md',
    'artifacts/react-migration/tranche-2a-route-map.md',
    'artifacts/react-migration/tranche-2a-gate.md',
    'artifacts/react-migration/tranche-2a-report.md',
    'artifacts/react-migration/legacy-contracts/statistiche.json',
    'artifacts/react-migration/legacy-contracts/audit.json',
    'artifacts/react-migration/legacy-contracts/registro-attivita.json',
    'artifacts/react-migration/legacy-contracts/utenti.json',
    'artifacts/react-migration/legacy-contracts/profili.json',
    'artifacts/react-migration/legacy-contracts/backup.json',
  ],
}

const tranche3aPatchGroups = {
  backend: [
    'web/services/react_utenti_bridge.py',
    'web/services/react_profili_bridge.py',
    'web/services/react_backup_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/utentiData.ts',
    'frontend/src/profiliData.ts',
    'frontend/src/backupData.ts',
    'frontend/src/components/UtentiPage.tsx',
    'frontend/src/components/UtentiPage.css',
    'frontend/src/components/ProfiliPage.tsx',
    'frontend/src/components/ProfiliPage.css',
    'frontend/src/components/BackupPage.tsx',
    'frontend/src/components/BackupPage.css',
    'frontend/src/ui/LegacyPostForm.tsx',
    'frontend/src/ui/ui.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-3a-gate.py',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-3a-route-map.md',
    'artifacts/react-migration/tranche-3a-gate.md',
    'artifacts/react-migration/tranche-3a-report.md',
    'artifacts/react-migration/legacy-contracts/utenti.json',
    'artifacts/react-migration/legacy-contracts/utenti__nuovo.json',
    'artifacts/react-migration/legacy-contracts/profili.json',
    'artifacts/react-migration/legacy-contracts/backup.json',
  ],
}

const tranche4aPatchGroups = {
  backend: [
    'web/services/react_backup_bridge.py',
    'web/services/react_sito_studio_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/backupData.ts',
    'frontend/src/sitoStudioData.ts',
    'frontend/src/components/BackupPage.tsx',
    'frontend/src/components/BackupPage.css',
    'frontend/src/components/SitoStudioPage.tsx',
    'frontend/src/components/SitoStudioPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-4a-gate.py',
    'scripts/react-migration/check-tranche-4a-secrets.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-4a-route-map.md',
    'artifacts/react-migration/tranche-4a-gate.md',
    'artifacts/react-migration/tranche-4a-secrets.md',
    'artifacts/react-migration/tranche-4a-report.md',
    'artifacts/react-migration/legacy-contracts/backup.json',
    'artifacts/react-migration/legacy-contracts/sito-studio.json',
    'artifacts/react-migration/legacy-contracts/sito-studio__contatti.json',
    'artifacts/react-migration/legacy-contracts/sito-studio__builder.json',
    'artifacts/react-migration/legacy-contracts/studio.json',
    'artifacts/react-migration/legacy-contracts/impostazioni.json',
  ],
}

const tranche5aPatchGroups = {
  backend: [
    'web/services/react_studio_bridge.py',
    'web/services/react_amministrazione_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/studioData.ts',
    'frontend/src/amministrazioneData.ts',
    'frontend/src/components/StudioPage.tsx',
    'frontend/src/components/StudioPage.css',
    'frontend/src/components/AmministrazionePage.tsx',
    'frontend/src/components/AmministrazionePage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-tranche-5a-gate.py',
    'scripts/react-migration/check-tranche-5a-secrets.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-5a-route-map.md',
    'artifacts/react-migration/tranche-5a-gate.md',
    'artifacts/react-migration/tranche-5a-secrets.md',
    'artifacts/react-migration/tranche-5a-report.md',
    'artifacts/react-migration/legacy-contracts/studio.json',
    'artifacts/react-migration/legacy-contracts/amministrazione.json',
    'artifacts/react-migration/legacy-contracts/impostazioni.json',
    'artifacts/react-migration/legacy-contracts/impostazioni-studio.json',
    'artifacts/react-migration/legacy-contracts/impostazioni__calendario.json',
    'artifacts/react-migration/legacy-contracts/impostazioni__pagamenti.json',
    'artifacts/react-migration/legacy-contracts/sincronizzazione-calendari.json',
  ],
}

const tranche6aPatchGroups = {
  backend: [
    'web/services/react_fatturazione_bridge.py',
    'web/services/react_incassi_pagamenti_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/fatturazioneData.ts',
    'frontend/src/incassiPagamentiData.ts',
    'frontend/src/components/FatturazionePage.tsx',
    'frontend/src/components/FatturazionePage.css',
    'frontend/src/components/IncassiPagamentiPage.tsx',
    'frontend/src/components/IncassiPagamentiPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-6a-gate.py',
    'scripts/react-migration/check-tranche-6a-secrets.mjs',
    'scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-6a-route-map.md',
    'artifacts/react-migration/tranche-6a-gate.md',
    'artifacts/react-migration/tranche-6a-secrets.md',
    'artifacts/react-migration/tranche-6a-no-fiscal-logic.md',
    'artifacts/react-migration/tranche-6a-report.md',
    'artifacts/react-migration/legacy-contracts/fatturazione.json',
    'artifacts/react-migration/legacy-contracts/fatturazione__nuova.json',
    'artifacts/react-migration/legacy-contracts/fatturazione__detail.json',
    'artifacts/react-migration/legacy-contracts/incassi-pagamenti.json',
    'artifacts/react-migration/legacy-contracts/impostazioni__pagamenti.json',
    'artifacts/react-migration/legacy-contracts/preventivi.json',
    'artifacts/react-migration/legacy-contracts/compensi-forensi.json',
    'artifacts/react-migration/legacy-contracts/tariffario.json',
  ],
}

const tranche7aPatchGroups = {
  backend: [
    'web/services/react_preventivi_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/preventiviData.ts',
    'frontend/src/components/PreventiviPage.tsx',
    'frontend/src/components/PreventiviPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-7a-gate.py',
    'scripts/react-migration/check-tranche-7a-secrets.mjs',
    'scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs',
    'scripts/react-migration/check-tranche-7a-no-document-generation.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-7a-route-map.md',
    'artifacts/react-migration/tranche-7a-gate.md',
    'artifacts/react-migration/tranche-7a-secrets.md',
    'artifacts/react-migration/tranche-7a-no-compensi-logic.md',
    'artifacts/react-migration/tranche-7a-no-document-generation.md',
    'artifacts/react-migration/tranche-7a-report.md',
    'artifacts/react-migration/legacy-contracts/preventivi.json',
    'artifacts/react-migration/legacy-contracts/preventivi__nuovo.json',
    'artifacts/react-migration/legacy-contracts/preventivi__conferimento__nuovo.json',
    'artifacts/react-migration/legacy-contracts/preventivi__wizard.json',
    'artifacts/react-migration/legacy-contracts/preventivi__detail.json',
    'artifacts/react-migration/legacy-contracts/compensi-forensi.json',
    'artifacts/react-migration/legacy-contracts/tariffario.json',
  ],
}

const tranche8aPatchGroups = {
  backend: [
    'web/services/react_compensi_forensi_bridge.py',
    'web/services/react_tariffario_bridge.py',
    'web/services/react_preventivi_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/compensiForensiData.ts',
    'frontend/src/tariffarioData.ts',
    'frontend/src/components/CompensiForensiPage.tsx',
    'frontend/src/components/CompensiForensiPage.css',
    'frontend/src/components/TariffarioPage.tsx',
    'frontend/src/components/TariffarioPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  design: [
    'frontend/src/theme/impeccable-open-design.css',
    'frontend/src/ui/openDesign.ts',
    'artifacts/react-migration/tranche-8a-open-design.md',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-8a-gate.py',
    'scripts/react-migration/check-tranche-8a-secrets.mjs',
    'scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs',
    'scripts/react-migration/check-tranche-8a-no-document-generation.mjs',
    'scripts/react-migration/check-tranche-8a-open-design.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-8a-route-map.md',
    'artifacts/react-migration/tranche-8a-gate.md',
    'artifacts/react-migration/tranche-8a-secrets.md',
    'artifacts/react-migration/tranche-8a-no-compensi-logic.md',
    'artifacts/react-migration/tranche-8a-no-document-generation.md',
    'artifacts/react-migration/tranche-8a-open-design-check.md',
    'artifacts/react-migration/tranche-8a-report.md',
    'artifacts/react-migration/legacy-contracts/compensi-forensi.json',
    'artifacts/react-migration/legacy-contracts/tariffario.json',
    'artifacts/react-migration/legacy-contracts/preventivi__wizard.json',
    'artifacts/react-migration/legacy-contracts/preventivi.json',
    'artifacts/react-migration/legacy-contracts/fatturazione.json',
    'artifacts/react-migration/legacy-contracts/template-atti.json',
    'artifacts/react-migration/legacy-contracts/redazione-atti.json',
  ],
}

const tranche9aPatchGroups = {
  backend: [
    'web/services/react_template_atti_bridge.py',
    'web/services/react_redazione_atti_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/package.json',
    'pnpm-lock.yaml',
    'frontend/src/templateAttiData.ts',
    'frontend/src/redazioneAttiData.ts',
    'frontend/src/components/TemplateAttiPage.tsx',
    'frontend/src/components/TemplateAttiPage.css',
    'frontend/src/components/RedazioneAttiPage.tsx',
    'frontend/src/components/RedazioneAttiPage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  design: [
    'frontend/src/theme/impeccable-open-design.css',
    'frontend/src/ui/openDesign.ts',
    'artifacts/react-migration/tranche-9a-open-design.md',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-9a-gate.py',
    'scripts/react-migration/check-tranche-9a-secrets.mjs',
    'scripts/react-migration/check-tranche-9a-no-document-raw.mjs',
    'scripts/react-migration/check-tranche-9a-no-legal-generation.mjs',
    'scripts/react-migration/check-tranche-9a-no-document-generation.mjs',
    'scripts/react-migration/check-tranche-9a-open-design.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-9a-route-map.md',
    'artifacts/react-migration/tranche-9a-gate.md',
    'artifacts/react-migration/tranche-9a-secrets.md',
    'artifacts/react-migration/tranche-9a-no-document-raw.md',
    'artifacts/react-migration/tranche-9a-no-legal-generation.md',
    'artifacts/react-migration/tranche-9a-no-document-generation.md',
    'artifacts/react-migration/tranche-9a-open-design-check.md',
    'artifacts/react-migration/tranche-9a-report.md',
    'artifacts/react-migration/legacy-contracts/template-atti.json',
    'artifacts/react-migration/legacy-contracts/template-atti__catalogo.json',
    'artifacts/react-migration/legacy-contracts/template-atti__nuovo.json',
    'artifacts/react-migration/legacy-contracts/redazione-atti.json',
    'artifacts/react-migration/legacy-contracts/checklist.json',
    'artifacts/react-migration/legacy-contracts/deposito__checklist.json',
    'artifacts/react-migration/legacy-contracts/giurisprudenza.json',
    'artifacts/react-migration/legacy-contracts/legal-intelligence.json',
  ],
}

const tranche10aPatchGroups = {
  backend: [
    'web/services/react_giurisprudenza_bridge.py',
    'web/services/react_legal_intelligence_bridge.py',
    'web/blueprints/api_v1_react.py',
  ],
  frontend: [
    'frontend/src/giurisprudenzaData.ts',
    'frontend/src/legalIntelligenceData.ts',
    'frontend/src/components/GiurisprudenzaPage.tsx',
    'frontend/src/components/GiurisprudenzaPage.css',
    'frontend/src/components/LegalIntelligencePage.tsx',
    'frontend/src/components/LegalIntelligencePage.css',
    'frontend/src/App.tsx',
    'web/static/react',
  ],
  gate: [
    'web/bootstrap/react_route_gate.py',
    'web/blueprints/react_shell.py',
    'tools/react-migration/route-manifest.json',
  ],
  design: [
    'frontend/src/theme/impeccable-open-design.css',
    'frontend/src/ui/openDesign.ts',
    'artifacts/react-migration/tranche-10a-open-design.md',
  ],
  tests: [
    'frontend/scripts/check-react-contracts.mjs',
    'scripts/react-migration/check-route-gate.mjs',
    'scripts/react-migration/check-tranche-10a-gate.py',
    'scripts/react-migration/check-tranche-10a-secrets.mjs',
    'scripts/react-migration/check-tranche-10a-no-external-fetch.mjs',
    'scripts/react-migration/check-tranche-10a-no-ai-generation.mjs',
    'scripts/react-migration/check-tranche-10a-no-document-raw.mjs',
    'scripts/react-migration/check-tranche-10a-open-design.mjs',
    'scripts/react-migration/run-safe-react-migration.mjs',
  ],
  reports: [
    'CHANGELOG.md',
    'Dockerfile',
    'README.md',
    'docs/REACT_MIGRATION_MASTER_PLAN.md',
    'pct/__init__.py',
    'railway.toml',
    'setup.py',
    'artifacts/react-migration/audit.md',
    'artifacts/react-migration/route-inventory.json',
    'artifacts/react-migration/route-gate.md',
    'artifacts/react-migration/ui-consistency.md',
    'artifacts/react-migration/tranche-10a-route-map.md',
    'artifacts/react-migration/tranche-10a-open-design.md',
    'artifacts/react-migration/tranche-10a-gate.md',
    'artifacts/react-migration/tranche-10a-secrets.md',
    'artifacts/react-migration/tranche-10a-no-external-fetch.md',
    'artifacts/react-migration/tranche-10a-no-ai-generation.md',
    'artifacts/react-migration/tranche-10a-no-document-raw.md',
    'artifacts/react-migration/tranche-10a-open-design-check.md',
    'artifacts/react-migration/tranche-10a-report.md',
    'artifacts/react-migration/legacy-contracts/giurisprudenza.json',
    'artifacts/react-migration/legacy-contracts/giurisprudenza__nuova.json',
    'artifacts/react-migration/legacy-contracts/giurisprudenza__detail.json',
    'artifacts/react-migration/legacy-contracts/legal-intelligence.json',
    'artifacts/react-migration/legacy-contracts/legal-intelligence__news.json',
    'artifacts/react-migration/legacy-contracts/legal-intelligence__mediazione.json',
    'artifacts/react-migration/legacy-contracts/legal-intelligence__detail.json',
    'artifacts/react-migration/legacy-contracts/ricerca-legale.json',
    'artifacts/react-migration/legacy-contracts/ricerca-legale__detail.json',
    'artifacts/react-migration/legacy-contracts/checklist.json',
    'artifacts/react-migration/legacy-contracts/deposito__checklist.json',
  ],
}

function run(cmd, options = {}) {
  console.log(`\n> ${cmd}`)
  execSync(cmd, { stdio: 'inherit', ...options })
}

function cleanRequired() {
  if (process.env.ALLOW_DIRTY === '1') return
  const status = execSync('git status --short', { encoding: 'utf8' }).trim()
  if (status) {
    throw new Error(`Working tree non pulito. Usa ALLOW_DIRTY=1 solo se sai cosa stai facendo.\n${status}`)
  }
}

function textArtifact(cmd) {
  return execSync(cmd, { encoding: 'utf8', maxBuffer: EXEC_BUFFER })
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .join('\n')
}

function diffOutput(cmd) {
  try {
    return execSync(cmd, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      maxBuffer: EXEC_BUFFER,
    })
  } catch (error) {
    return `${error.stdout || ''}${error.stderr || ''}`
  }
}

function existingPaths(paths) {
  return paths.filter((path) => existsSync(path))
}

function untrackedPaths(paths) {
  const candidates = existingPaths(paths)
  if (!candidates.length) return []
  return textArtifact(`git ls-files --others --exclude-standard -- ${candidates.join(' ')}`)
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function trackedPaths(paths) {
  const candidates = existingPaths(paths)
  if (!candidates.length) return []
  return textArtifact(`git ls-files -- ${candidates.join(' ')}`)
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function patchForPaths(paths) {
  const existing = existingPaths(paths)
  if (!existing.length) return ''
  const tracked = trackedPaths(existing)
  const trackedPatch = tracked.length ? textArtifact(`git diff --binary -- ${tracked.join(' ')}`) : ''
  const untracked = untrackedPaths(existing)
    .map((path) => diffOutput(`git diff --binary --no-index -- /dev/null ${path}`))
    .join('\n')
  return [trackedPatch, untracked].filter((part) => part.trim()).join('\n').trimEnd() + '\n'
}

function writePatch(trancheName, name, paths) {
  writeFileSync(`artifacts/react-migration/patches/tranche-${trancheName}.${name}.patch`, patchForPaths(paths), 'utf8')
}

function writeTranche2aPatches() {
  for (const [name, paths] of Object.entries(tranche2aPatchGroups)) {
    writePatch('2a', name, paths)
  }
}

function writeTranche3aPatches() {
  for (const [name, paths] of Object.entries(tranche3aPatchGroups)) {
    writePatch('3a', name, paths)
  }
}

function writeTranche4aPatches() {
  for (const [name, paths] of Object.entries(tranche4aPatchGroups)) {
    writePatch('4a', name, paths)
  }
}

function writeTranche5aPatches() {
  for (const [name, paths] of Object.entries(tranche5aPatchGroups)) {
    writePatch('5a', name, paths)
  }
}

function writeTranche6aPatches() {
  for (const [name, paths] of Object.entries(tranche6aPatchGroups)) {
    writePatch('6a', name, paths)
  }
}

function writeTranche7aPatches() {
  for (const [name, paths] of Object.entries(tranche7aPatchGroups)) {
    writePatch('7a', name, paths)
  }
}

function writeTranche8aPatches() {
  for (const [name, paths] of Object.entries(tranche8aPatchGroups)) {
    writePatch('8a', name, paths)
  }
}

function writeTranche9aPatches() {
  for (const [name, paths] of Object.entries(tranche9aPatchGroups)) {
    writePatch('9a', name, paths)
  }
}

function writeTranche10aPatches() {
  for (const [name, paths] of Object.entries(tranche10aPatchGroups)) {
    writePatch('10a', name, paths)
  }
}

function runDefault() {
  cleanRequired()
  run('node scripts/react-migration/audit-react-migration.mjs')
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeFileSync(
    'artifacts/react-migration/patches/working-tree.patch',
    textArtifact(`git diff --binary -- ${migrationPaths.join(' ')}`),
    'utf8',
  )
  writeFileSync(
    'artifacts/react-migration/patches/status.txt',
    textArtifact(`git status --short -- ${migrationPaths.join(' ')}`),
    'utf8',
  )
  run('git diff --stat')
  run('git status --short')
}

function runTranche2a() {
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche2aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('python scripts/react-migration/check-tranche-2a-gate.py')
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche2aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche3a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche3aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('python scripts/react-migration/check-tranche-3a-gate.py')
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche3aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche4a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche4aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-4a-secrets.mjs')
  run('python scripts/react-migration/check-tranche-4a-gate.py')
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche4aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche5a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche5aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-5a-secrets.mjs')
  run('python scripts/react-migration/check-tranche-5a-gate.py')
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche5aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche6a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche6aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-6a-secrets.mjs')
  run('node scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs')
  run('python scripts/react-migration/check-tranche-6a-gate.py')
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche6aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche7a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche7aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-7a-secrets.mjs')
  run('node scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs')
  run('node scripts/react-migration/check-tranche-7a-no-document-generation.mjs')
  if (existsSync('scripts/react-migration/check-tranche-7a-gate.py')) {
    run('python scripts/react-migration/check-tranche-7a-gate.py')
  }
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche7aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche8a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche8aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-8a-secrets.mjs')
  run('node scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs')
  run('node scripts/react-migration/check-tranche-8a-no-document-generation.mjs')
  run('node scripts/react-migration/check-tranche-8a-open-design.mjs')
  if (existsSync('scripts/react-migration/check-tranche-8a-gate.py')) {
    run('python scripts/react-migration/check-tranche-8a-gate.py')
  }
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche8aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche9a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche9aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-9a-secrets.mjs')
  run('node scripts/react-migration/check-tranche-9a-no-document-raw.mjs')
  run('node scripts/react-migration/check-tranche-9a-no-legal-generation.mjs')
  run('node scripts/react-migration/check-tranche-9a-no-document-generation.mjs')
  run('node scripts/react-migration/check-tranche-9a-open-design.mjs')
  if (existsSync('scripts/react-migration/check-tranche-9a-gate.py')) {
    run('python scripts/react-migration/check-tranche-9a-gate.py')
  }
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche9aPatches()
  run('git diff --stat')
  run('git status --short')
}

function runTranche10a() {
  cleanRequired()
  run('git status --short')
  run('node scripts/react-migration/audit-react-migration.mjs')
  run(`python scripts/react-migration/capture-legacy-contracts.py ${tranche10aContracts.join(' ')}`)
  run('node scripts/react-migration/check-route-gate.mjs')
  run('node scripts/react-migration/check-ui-consistency.mjs')
  run('node scripts/react-migration/check-tranche-10a-secrets.mjs')
  run('node scripts/react-migration/check-tranche-10a-no-external-fetch.mjs')
  run('node scripts/react-migration/check-tranche-10a-no-ai-generation.mjs')
  run('node scripts/react-migration/check-tranche-10a-no-document-raw.mjs')
  run('node scripts/react-migration/check-tranche-10a-open-design.mjs')
  if (existsSync('scripts/react-migration/check-tranche-10a-gate.py')) {
    run('python scripts/react-migration/check-tranche-10a-gate.py')
  }
  run('pnpm --filter @iusentra/studio test')
  run('pnpm --filter @iusentra/studio typecheck')
  run('pnpm --filter @iusentra/studio build')
  writeTranche10aPatches()
  run('git diff --stat')
  run('git status --short')
}

if (tranche === '2a') {
  runTranche2a()
} else if (tranche === '3a') {
  runTranche3a()
} else if (tranche === '4a') {
  runTranche4a()
} else if (tranche === '5a') {
  runTranche5a()
} else if (tranche === '6a') {
  runTranche6a()
} else if (tranche === '7a') {
  runTranche7a()
} else if (tranche === '8a') {
  runTranche8a()
} else if (tranche === '9a') {
  runTranche9a()
} else if (tranche === '10a') {
  runTranche10a()
} else {
  runDefault()
}
