import test from 'node:test'
import assert from 'node:assert/strict'
import { articleNumbers, normativeReaderHref, openOfficialOutsideReader } from '../../frontend/src/normativeArticleLinks.ts'

test('disposizione singola, suffissi e più articoli senza scambiare anni o numeri di legge', () => {
  assert.deepEqual(articleNumbers('167'), ['167'])
  assert.deepEqual(articleNumbers('473-bis.12'), ['473-bis.12'])
  assert.deepEqual(articleNumbers('art. 171-ter c.p.c.'), ['171-ter'])
  assert.deepEqual(articleNumbers('artt. 5 e 6 c.p.c.'), ['5', '6'])
  assert.deepEqual(articleNumbers('L. 53/1994'), [])
  assert.deepEqual(articleNumbers('art. 18 L. 300/1970'), ['18'])
})
test('lettore nativo lega ID o atto/articolo alla SHA senza inoltrare testi al browser', () => {
  const href=normativeReaderHref({url:'https://www.normattiva.it/atto',article:'167',act:'codice_procedura_civile',sha:'abc'})
  const url=new URL(href,'http://localhost')
  assert.equal(url.pathname,'/api/v1/ui/ricerca-legale/normativa/visualizza')
  assert.equal(url.searchParams.get('articolo'),'167')
  assert.equal(url.searchParams.get('sha'),'abc')
  assert.equal(normativeReaderHref({url:'https://example.test',article:'L.53/1994'}),'')
  assert.match(normativeReaderHref({id:8}),/id=8/)
})

test('verifica ufficiale esplicita fuori iframe, senza aprire schemi arbitrari o altri documenti', () => {
  const origin='https://app.iusentra.it'
  const reader='/api/v1/ui/ricerca-legale/normativa/visualizza?id=1'
  assert.equal(openOfficialOutsideReader(reader,'https://www.normattiva.it/uri-res/N2Ls?urn:x','1',origin),true)
  assert.equal(openOfficialOutsideReader(reader,'https://evil.test/x','1',origin),false)
  assert.equal(openOfficialOutsideReader(reader,'javascript:alert(1)','1',origin),false)
  assert.equal(openOfficialOutsideReader('/email','https://www.normattiva.it','1',origin),false)
  assert.equal(openOfficialOutsideReader(reader,'https://www.normattiva.it',null,origin),false)
})


test('la stesura resta legata a modello, pratica, cliente e dati correnti', async () => {
  const { stesuraSnapshot } = await import('../../frontend/src/stesuraLexSnapshot.ts')
  const first=stesuraSnapshot('modello','pratica','cliente','richiesta','attore',{b:'2',a:'1'})
  assert.equal(first,stesuraSnapshot('modello','pratica','cliente','richiesta','attore',{a:'1',b:'2'}))
  assert.notEqual(first,stesuraSnapshot('modello','altra-pratica','cliente','richiesta','attore',{a:'1',b:'2'}))
  assert.notEqual(first,stesuraSnapshot('modello','pratica','cliente','richiesta','attore',{a:'diverso',b:'2'}))
})
