import { test } from 'node:test'
import assert from 'node:assert/strict'
import { EditorHistory } from '../../frontend/src/editorHistory.ts'

test('testo dopo una modifica strutturale ritorna anche al secondo Ripeti', () => {
  const history = new EditorHistory()
  history.reset('tabella3')
  history.record('tabella4', null, '', 0)
  history.record('tabella4 testo', null, 'insertText', 10)
  assert.equal(history.move('undo', 'tabella4 testo').html, 'tabella4')
  assert.equal(history.move('undo', 'tabella4').html, 'tabella3')
  assert.equal(history.move('redo', 'tabella3').html, 'tabella4')
  assert.equal(history.move('redo', 'tabella4').html, 'tabella4 testo')
})

test('scrittura contigua raggruppata, nuova modifica invalida il ramo Ripeti', () => {
  const history = new EditorHistory()
  history.reset('')
  history.record('a', null, 'insertText', 0)
  history.record('ab', null, 'insertText', 100)
  assert.equal(history.move('undo', 'ab').html, '')
  history.record('x', null, 'insertText', 200)
  assert.equal(history.move('redo', 'x'), null)
})

test('riapertura azzera la cronologia e una mutazione esterna non viene sovrascritta', () => {
  const history = new EditorHistory()
  history.reset('a')
  history.record('b', null)
  assert.equal(history.move('undo', 'dato non registrato'), null)
  history.reset('nuovo documento')
  assert.equal(history.move('undo', 'nuovo documento'), null)
})
