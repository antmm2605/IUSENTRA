// Esegue il trasporto realmente installato con soli messaggi di prova innocui.
// Processo isolato: nessun browser dello studio e nessuna scrittura di story.
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';

const requireFrontend = createRequire(new URL('../../../frontend/package.json', import.meta.url));
globalThis.CONFIG_TYPE = 'DEVELOPMENT';
globalThis.FEATURES = {};
globalThis.location = new URL('http://localhost:6006/iframe.html');
globalThis.document = { location: globalThis.location, querySelectorAll: () => [] };
const { PostMessageTransport } = await import(pathToFileURL(requireFrontend.resolve('storybook/internal/channels')));
const results = [];
for (const origin of ['https://controlled-foreign.invalid', 'http://localhost.attacker.invalid', 'null',
  'http://localhost:6006', 'http://localhost:6007']) {
  for (const representation of ['object', 'json']) {
    const transport = new PostMessageTransport({ page: 'preview' });
    const delivered = [];
    transport.setHandler((event) => delivered.push(event.type));
    const data = { key: 'storybook-channel', event: { type: 'iusentra-controlled-probe', args: [] } };
    transport.handleEvent({ origin, data: representation === 'json' ? JSON.stringify(data) : data });
    results.push({ origin, representation, delivered: delivered.length });
  }
}
console.log(JSON.stringify(results));
