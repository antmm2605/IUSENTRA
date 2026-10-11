import assert from 'node:assert/strict'
import test from 'node:test'
import { publicModule } from '../../frontend/src/components/mediazione/publicModule.ts'

const resource = { url: 'https://ente.example/moduli/istanza.pdf?rev=2', kind: 'istanza', label: 'Domanda', source_url: 'https://ente.example/modulistica/' }
const resources = [resource]

test('il clic sulla fonte esatta conserva la revisione da acquisire', () => {
 assert.equal(publicModule(resource.url + '#page=1', resources).resource, resource)
 assert.equal(publicModule('https://ente.example/moduli/istanza.pdf?rev=1', resources).resource, null)
 assert.equal(publicModule('https://altro.example/moduli/istanza.pdf?rev=2', resources).resource, null)
})
test('non acquisisce pagine, risorse estranee o indirizzi con credenziali', () => {
 assert.equal(publicModule('https://ente.example/modulistica/', resources).file, false)
 assert.equal(publicModule('https://utente:segreto@ente.example/moduli/istanza.pdf?rev=2', resources).file, false)
 assert.equal(publicModule('javascript:alert(1)', resources).file, false)
 assert.equal(publicModule('', resources).file, false)
 assert.equal(publicModule(resource.url, [{ ...resource, kind: 'sedi' }]).resource, null)
 assert.equal(publicModule('https://ente.example/sconosciuto.docx', resources).file, true)
 assert.equal(publicModule('https://ente.example/sconosciuto.docx', resources).resource, null)
})
