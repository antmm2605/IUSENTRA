// Guardia: in frontend/src le date si inseriscono solo con CampoData (gg/mm/aaaa).
// L'input nativo type="date"/"datetime-local" mostra il formato della lingua del
// browser (in inglese 07/27/2026): non deve ricomparire fuori dal componente.
import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { test } from 'node:test'

const radice = resolve(import.meta.dirname, '../../frontend/src')

// Eccezione dichiarata: il componente stesso.
const ECCEZIONI = new Set([
  'ui/CampoData.tsx',
])

function sorgenti(cartella, uscita = []) {
  for (const voce of readdirSync(cartella)) {
    const percorso = join(cartella, voce)
    if (statSync(percorso).isDirectory()) sorgenti(percorso, uscita)
    else if (/\.(tsx|ts|jsx|js)$/.test(voce) && !/\.(stories|test)\./.test(voce)) uscita.push(percorso)
  }
  return uscita
}

/** Testo del tag JSX che inizia in `inizio`, rispettando graffe e stringhe. */
function tagJsx(testo, inizio) {
  let profondita = 0
  let virgolette = ''
  for (let i = inizio; i < testo.length; i += 1) {
    const c = testo[i]
    if (virgolette) {
      if (c === '\\') { i += 1; continue }
      if (c === virgolette) virgolette = ''
      continue
    }
    if (c === '"' || (profondita > 0 && (c === "'" || c === '`'))) virgolette = c
    else if (c === '{') profondita += 1
    else if (c === '}') profondita -= 1
    else if (profondita === 0 && c === '>') return testo.slice(inizio, i + 1)
  }
  return testo.slice(inizio)
}

const TIPO_NATIVO = /\btype\s*=\s*(?:["'](?:date|datetime-local)["']|\{[^}]*["'](?:date|datetime-local)["'][^}]*\})/

export function violazioni(testo) {
  const trovate = []
  const riga = (indice) => testo.slice(0, indice).split('\n').length
  for (const match of testo.matchAll(/<(?:input|Input)\b/g)) {
    if (TIPO_NATIVO.test(tagJsx(testo, match.index))) trovate.push(riga(match.index))
  }
  for (const match of testo.matchAll(/\.type\s*=\s*["'](?:date|datetime-local)["']|setAttribute\(\s*["']type["']\s*,\s*["'](?:date|datetime-local)["']/g)) {
    trovate.push(riga(match.index))
  }
  return trovate
}

test('la guardia riconosce gli input nativi di data', () => {
  assert.deepEqual(violazioni('<input type="date" value={x} />'), [1])
  assert.deepEqual(violazioni('<input\n  name="a"\n  type="datetime-local"\n/>'), [1])
  assert.deepEqual(violazioni('<input type={tipo === \'date\' ? \'date\' : \'text\'} />'), [1])
  assert.deepEqual(violazioni('<Input onChange={(e) => f(e)} type="date" />'), [1])
  assert.deepEqual(violazioni('campo.type = "date"'), [1])
  assert.deepEqual(violazioni('<CampoData value={x} />'), [])
  assert.deepEqual(violazioni('<DepositTextInput type="date" />'), [])
  assert.deepEqual(violazioni('<input type="text" />'), [])
})

test('nessun input nativo di data fuori da CampoData', () => {
  const errori = []
  for (const file of sorgenti(radice)) {
    const nome = relative(radice, file).replace(/\\/g, '/')
    if (ECCEZIONI.has(nome)) continue
    for (const riga of violazioni(readFileSync(file, 'utf8'))) errori.push(`${nome}:${riga}`)
  }
  assert.deepEqual(errori, [], `Usa <CampoData> (frontend/src/ui/CampoData.tsx) al posto di type="date"/"datetime-local":\n${errori.join('\n')}`)
})
