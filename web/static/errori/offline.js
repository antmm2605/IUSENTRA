// Una riattivazione del server può avvenire senza un evento «online» del browser.
const riprova = document.getElementById('riprova');
let timer;
let verificaInCorso = false;

function riapriPagina() {
  if (window.location.pathname === '/offline') window.location.replace('/');
  else window.location.reload();
}

async function verificaServizio() {
  if (verificaInCorso) return;
  if (navigator.onLine && document.visibilityState === 'visible') {
    verificaInCorso = true;
    try {
      const risposta = await fetch('/api/pronto', { cache: 'no-store', signal: AbortSignal.timeout(3500) });
      if (risposta.ok && (await risposta.json()).ok === true) {
        riapriPagina();
        return;
      }
    } catch (_) {
      // Durante il riavvio il server può ancora interrompere la connessione.
    } finally {
      verificaInCorso = false;
    }
  }
  timer = window.setTimeout(verificaServizio, 5000);
}

riprova.addEventListener('click', (evento) => {
  evento.preventDefault();
  riapriPagina();
});
window.addEventListener('online', () => {
  window.clearTimeout(timer);
  timer = window.setTimeout(verificaServizio, 0);
});
timer = window.setTimeout(verificaServizio, 2000);
