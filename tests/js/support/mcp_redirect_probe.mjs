import http from 'node:http';
import { createRequire } from 'node:module';

const frontendRequire = createRequire(new URL('../../../frontend/package.json', import.meta.url));
const shadcnRequire = createRequire(frontendRequire.resolve('shadcn'));
const { Client } = shadcnRequire('@modelcontextprotocol/sdk/client/index.js');
const { StreamableHTTPClientTransport } = shadcnRequire('@modelcontextprotocol/sdk/client/streamableHttp.js');
const listen = (server) => new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', () => {
    server.removeListener('error', reject);
    resolve(`http://127.0.0.1:${server.address().port}`);
  });
});
const close = (server) => new Promise((resolve) => {
  server.close(resolve);
  server.closeAllConnections();
});

/** Loopback only: synthetic header, initialize and empty tools/list, no real credentials. */
export async function probeMcpRedirect(crossOrigin, status = 307) {
  const received = [];
  let destination;
  const sink = http.createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    received.push({ marker: request.headers['x-probe-key'], body });
    if (request.method !== 'POST') {
      response.writeHead(405).end();
      return;
    }
    const message = JSON.parse(body);
    if (!Object.hasOwn(message, 'id')) {
      response.writeHead(202).end();
      return;
    }
    const result = message.method === 'initialize'
      ? { protocolVersion: message.params.protocolVersion, capabilities: { tools: {} }, serverInfo: { name: 'controlled', version: '1' } }
      : { tools: [] };
    response.writeHead(200, { 'Content-Type': 'application/json' });
    response.end(JSON.stringify({ jsonrpc: '2.0', id: message.id, result }));
  });
  const source = http.createServer((request, response) => {
    if (request.url === '/target') sink.emit('request', request, response);
    else response.writeHead(status, { Location: destination }).end();
  });
  const client = new Client({ name: 'controlled-redirect-probe', version: '1' }, { capabilities: {} });
  let error = '';
  let tools = null;
  try {
    const target = await listen(sink);
    const origin = await listen(source);
    destination = crossOrigin ? `${target}/mcp` : `${origin}/target`;
    const transport = new StreamableHTTPClientTransport(new URL(`${origin}/redirect`), {
      requestInit: { headers: { 'X-Probe-Key': 'SYNTHETIC_MCP_SECURITY_MARKER' } },
    });
    await client.connect(transport, { timeout: 3000 });
    tools = (await client.listTools({}, { timeout: 3000 })).tools.length;
  } catch (caught) {
    error = String(caught.message);
  } finally {
    const cleanup = await Promise.allSettled([client.close(), close(source), close(sink)]);
    const errors = cleanup.filter((result) => result.status === 'rejected').map((result) => result.reason);
    if (errors.length) throw new AggregateError(errors, 'MCP test cleanup failed');
  }
  return { received: received.length, markerReceived: received.some((r) => r.marker === 'SYNTHETIC_MCP_SECURITY_MARKER'), tools, error };
}
