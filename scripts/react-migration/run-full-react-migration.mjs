import { execFileSync } from 'node:child_process'

const checks = [
  'audit-react-migration.mjs',
  'audit-anti-mascheramento.mjs',
  'check-no-primary-legacy-links.mjs',
  'check-no-legacy-post-form.mjs',
  'check-no-primary-html-post.mjs',
  'check-no-mock-data-full-react.mjs',
  'check-no-hardcoded-domain-logic.mjs',
  'check-full-react-route-contract.mjs',
  'check-responsive-workspaces.mjs',
  'check-no-bootstrap-primary-react.mjs',
]

for (const check of checks) {
  console.log(`\n> ${check}`)
  execFileSync(process.execPath, [`scripts/react-migration/${check}`], { stdio: 'inherit' })
}

console.log('\nrun-full-react-migration: OK')
