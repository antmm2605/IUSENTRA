import assert from 'node:assert/strict'
import test from 'node:test'
import { workWindowUrl } from '../../frontend/src/components/workWindowRoutes.ts'
const origin = 'https://app.iusentra.it'
test('la casella in finestra conserva filtri e resta una casella', () => {
 for (const path of ['/email', '/email/', '/email-ordinaria', '/email-ordinaria/']) {
  const url=workWindowUrl(`${path}?cartella=INBOX&q=ricerca`,origin)
  assert.equal(url?.searchParams.get('view'),'mailbox')
  assert.equal(url?.searchParams.get('embed'),'source')
  assert.equal(url?.searchParams.get('q'),'ricerca')
  assert.equal(url?.searchParams.get('cartella'),'INBOX')
 }
})
test('la fonte puntuale mantiene il lettore del messaggio', () => {
 for(const path of ['/email/ID1','/email-ordinaria/ID2','/email/?id=ID3','/email/?audit_id=A1']) {
  const url=workWindowUrl(path,origin)
  assert.equal(url?.searchParams.get('view'),null)
  assert.equal(url?.searchParams.get('embed'),'source')
 }
})
test('le altre finestre mantengono contesto e confini di origine', () => {
 const url=workWindowUrl('/agenda/ID4?vista=week&data=2026-10-05',origin)
 assert.equal(url?.searchParams.get('vista'),'week')
 assert.equal(url?.searchParams.get('view'),null)
 for(const path of ['https://example.test/email','https://utente:password@app.iusentra.it/email','/email/ID4/elimina','/logout','javascript:alert(1)']) assert.equal(workWindowUrl(path,origin),null)
})
