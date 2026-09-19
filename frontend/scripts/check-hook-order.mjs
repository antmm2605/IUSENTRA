#!/usr/bin/env node
/**
 * Ordine degli hook React: nessun hook dopo un'uscita anticipata.
 *
 * React esegue gli hook sempre nello stesso ordine e nello stesso numero. Un
 * hook dichiarato sotto un `return` condizionato (il classico
 * `if (loading) return <Caricamento/>`) viene eseguito solo in alcuni render:
 * al primo render "pieno" React solleva l'errore #310 e l'error boundary
 * sostituisce la pagina con la schermata di cortesia.
 *
 * È successo davvero: il Portale Cliente dichiarava `useConversazioneViva` e lo
 * scorrimento della chat sotto le uscite anticipate, e il cliente che entrava
 * dall'invito vedeva «Pagina temporaneamente non disponibile» invece della
 * propria pratica. Questo controllo impedisce che ricapiti.
 *
 * Regola applicata: dentro una funzione che usa hook, è un errore chiamare un
 * hook al primo livello del corpo dopo un `return` al primo livello o dentro un
 * `if (...) { ... }` di primo livello. I `return` dentro funzioni annidate
 * (callback, handler, closure) non contano: non interrompono il render.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(here, '..', 'src')

const HOOK = /(?:^|[^A-Za-z0-9_.])(use[A-Z][A-Za-z0-9_]*)\s*\(/
const FUNCTION_START = /^(?:export\s+)?(?:default\s+)?function\s+([A-Za-z0-9_]+)\s*[(<]/
const INLINE_RETURN = /^\s*(?:if\s*\(.*\)\s*)?return\b/
const IF_BLOCK_START = /^\s*(?:\}\s*else\s+)?if\s*\(.*\)\s*\{\s*$/

function sourceFiles(dir) {
  const out = []
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry)
    if (statSync(full).isDirectory()) {
      out.push(...sourceFiles(full))
    } else if (entry.endsWith('.tsx')) {
      out.push(full)
    }
  }
  return out
}

/** Profondità di graffe introdotte dalla riga, ignorando stringhe e commenti semplici. */
function braceDelta(line) {
  const clean = line
    .replace(/\/\/.*$/, '')
    .replace(/'(?:\\.|[^'\\])*'/g, "''")
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/`(?:\\.|[^`\\])*`/g, '``')
  let delta = 0
  for (const char of clean) {
    if (char === '{') delta += 1
    if (char === '}') delta -= 1
  }
  return delta
}

function findingsForFile(file) {
  const lines = readFileSync(file, 'utf8').split('\n')
  const findings = []
  let inFunction = false
  let functionName = ''
  let depth = 0
  let earlyReturn = 0
  let ifBlockDepth = 0

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const opening = FUNCTION_START.exec(line)
    if (!inFunction && opening) {
      inFunction = true
      functionName = opening[1]
      depth = 0
      earlyReturn = 0
      ifBlockDepth = 0
    }
    if (!inFunction) continue

    const before = depth
    if (before === 1) {
      if (INLINE_RETURN.test(line) && !earlyReturn) earlyReturn = index + 1
      if (IF_BLOCK_START.test(line)) ifBlockDepth = 2
    }
    if (before === 2 && ifBlockDepth === 2 && INLINE_RETURN.test(line) && !earlyReturn) {
      earlyReturn = index + 1
    }
    // `return useContext(...)` è l'uscita unica di un hook personalizzato: il
    // return e l'hook stanno sulla stessa riga e nessun render viene saltato.
    if (before === 1 && earlyReturn && earlyReturn !== index + 1) {
      const hook = HOOK.exec(line)
      if (hook) {
        findings.push({
          file,
          line: index + 1,
          functionName,
          hook: hook[1],
          earlyReturn,
        })
      }
    }

    depth += braceDelta(line)
    if (depth <= 1) ifBlockDepth = 0
    if (depth <= 0 && before > 0) {
      inFunction = false
      functionName = ''
    }
  }
  return findings
}

const findings = sourceFiles(SRC).flatMap(findingsForFile)

if (findings.length) {
  console.error('Hook React dichiarati dopo un\'uscita anticipata (React #310):')
  for (const item of findings) {
    const relative = path.relative(path.join(here, '..', '..'), item.file)
    console.error(
      `  ${relative}:${item.line} — ${item.hook} in ${item.functionName}() dopo il return di riga ${item.earlyReturn}.`,
    )
  }
  console.error('Sposta gli hook sopra le uscite anticipate: React li vuole sempre tutti, in ordine.')
  process.exit(1)
}

console.log('Ordine hook React: nessun hook dopo un\'uscita anticipata.')
