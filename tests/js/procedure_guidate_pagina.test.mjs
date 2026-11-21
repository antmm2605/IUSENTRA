import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

const leggi = (percorso) => readFileSync(new URL(`../../frontend/src/${percorso}`, import.meta.url), 'utf8')

test('«Procedure guidate» mostra le procedure per procedimento con il titolo del menu', () => {
  const catalogo = leggi('features/legal-skills/pages/LegalSkillsCatalogPage.tsx')
  const app = leggi('App.tsx')
  assert.match(app, /label: 'Procedure guidate'[^\n]*href: '\/legal-skills'/)
  assert.match(catalogo, /title="Procedure guidate"/)
  assert.match(catalogo, /<PercorsiGuidati \/>/)
  assert.match(leggi('features/legal-skills/pages/PromptPathwaysPage.tsx'), /<PercorsiGuidati \/>/)
  assert.match(leggi('app/routes.ts'), /'\/app\/legal-skills', label: 'Procedure guidate'/)
})

test('nessuna parola tecnica a video nelle procedure guidate', () => {
  for (const file of [
    'features/legal-skills/pages/LegalSkillsCatalogPage.tsx',
    'features/legal-skills/components/PercorsiGuidati.tsx',
    'features/legal-skills/pages/PromptPathwaysPage.tsx',
  ]) {
    const testo = leggi(file).replace(/^\s*(import|\/\/|\/\*\*|\*).*$/gm, '')
    for (const vietata of ['Apri pack', 'skill disponibili', 'Tutti i pack', 'Legal Skills', 'LegalSkills Italia', 'Apri prompt', 'agente schedulato']) {
      assert.ok(!testo.includes(vietata), `${vietata} in ${file}`)
    }
  }
})
