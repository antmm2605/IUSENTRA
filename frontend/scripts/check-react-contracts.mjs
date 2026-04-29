import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

function read(path) {
  return readFileSync(resolve(root, path), 'utf8')
}

function assertContains(source, expected, label) {
  if (!source.includes(expected)) {
    throw new Error(`${label}: manca "${expected}"`)
  }
}

function assertNotContains(source, unexpected, label) {
  if (source.includes(unexpected)) {
    throw new Error(`${label}: contiene ancora "${unexpected}"`)
  }
}

const app = read('src/App.tsx')
const agenda = read('src/components/AgendaPage.tsx')
const agendaData = read('src/agendaData.ts')
const search = read('src/components/RicercaStudioPage.tsx')
const searchData = read('src/searchData.ts')
const css = read('src/index.css')

assertContains(app, '/app-v2/ricerca-studio', 'nav ricerca studio')
assertContains(app, '/app-v2/agenda', 'nav agenda')
assertContains(app, "isSearchPage?<RicercaStudioPage", 'route ricerca studio')
assertContains(app, "isAgendaPage?<AgendaPage/>", 'route agenda')
assertContains(app, 'openSections[section.id] === true', 'nav sezioni chiuse')
assertContains(app, 'onCloseMobile', 'nav drawer mobile')
assertNotContains(app, 'Centro operativo di oggi', 'panoramica separata')

assertNotContains(search, 'mockResults', 'ricerca studio')
assertContains(searchData, '/api/global-search', 'api ricerca studio')
assertContains(searchData, 'reindexStudioSearch', 'reindicizzazione ricerca studio')

assertContains(agenda, 'AgendaPage', 'pagina agenda')
assertContains(agenda, 'FloatingLex', 'lex agenda')
assertContains(agendaData, '/api/v1/ui/agenda', 'api agenda react')
assertContains(agendaData, '/api/v1/agenda', 'fallback agenda storico')
assertContains(agendaData, 'moveEventToDay', 'spostamento agenda')

assertContains(css, '.iu-search-page', 'stili ricerca studio')
assertContains(css, '.iu-agenda-page', 'stili agenda')
assertContains(css, '@media(max-width:760px)', 'responsive agenda')
assertContains(css, 'prefers-reduced-motion', 'motion agenda')

console.log('Contratti React verificati.')
