/**
 * Compatibilita' per vecchie pagine Jinja.
 *
 * Le notifiche di sistema sono ora gestite dalla PWA con Service Worker e
 * subscription esplicita da Impostazioni -> Notifiche. Questo file non mostra
 * notifiche OS dal contenuto della pagina, cosi' evita payload sensibili e
 * non chiede permessi al caricamento.
 */

const PCT_NOTIFICHE = {
  init() {
    document.addEventListener('pct:sync', () => undefined);
  },

  richiediPermesso() {
    window.location.href = '/notifiche';
  },

  controllaPendenti() {
    return undefined;
  },
};

document.addEventListener('DOMContentLoaded', () => PCT_NOTIFICHE.init());
