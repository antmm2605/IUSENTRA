/**
 * PCT Studio — Browser Notification API
 *
 * Funzionalità:
 *  1. Chiede il permesso notifiche la prima volta (pulsante nella topbar)
 *  2. Al caricamento: recupera scadenze urgenti e mostra notifiche OS
 *  3. Ascolta gli eventi SSE sync e notifica gli aggiornamenti degli altri
 *     operatori quando la tab è in background (document.hidden)
 */

const PCT_NOTIFICHE = {

  init() {
    if (!('Notification' in window)) return; // browser non supporta

    const btn = document.getElementById('btn-notifiche');

    if (Notification.permission === 'granted') {
      // Già autorizzato — controlla subito le scadenze urgenti
      if (btn) btn.remove();
      this.controllaPendenti();
    } else if (Notification.permission === 'default') {
      // Non ancora chiesto — mostra il pulsante
      if (btn) btn.style.display = '';
    } else {
      // 'denied' — niente da fare, rispettiamo la scelta
      if (btn) btn.remove();
    }

    // Ascolta gli eventi custom lanciati dal blocco SSE in base.html
    document.addEventListener('pct:sync', e => this._suSyncEvent(e.detail));
  },

  /** Chiamato dal click sul pulsante campana */
  async richiediPermesso() {
    const perm = await Notification.requestPermission();
    const btn = document.getElementById('btn-notifiche');
    if (perm === 'granted') {
      if (btn) btn.remove();
      this._mostra('PCT Studio', 'Notifiche abilitate — riceverai avvisi per le scadenze urgenti.', '/scadenziario');
      this.controllaPendenti();
    } else {
      if (btn) btn.remove(); // nasconde comunque se rifiutato
    }
  },

  /** Recupera dal server le notifiche urgenti da mostrare */
  async controllaPendenti() {
    try {
      const resp = await fetch('/api/notifiche/pending');
      if (!resp.ok) return;
      const alerts = await resp.json();
      alerts.forEach((a, i) => {
        // Scaloname leggermente per non sovrapporle
        setTimeout(() => this._mostra(a.titolo, a.corpo, a.url), (a.delay || 0) + i * 800);
      });
    } catch (_) {}
  },

  /** Mostra una notifica OS */
  _mostra(titolo, corpo, url = '/') {
    if (Notification.permission !== 'granted') return;
    try {
      const n = new Notification(titolo, {
        body: corpo,
        icon: '/static/icons/icon.svg',
        badge: '/static/icons/icon.svg',
        tag: 'pct-' + titolo.replace(/\s/g, '-'),   // raggruppa per tipo
        requireInteraction: titolo.includes('SCADUT'), // sticky se scaduta
      });
      n.onclick = () => {
        window.focus();
        location.href = url;
        n.close();
      };
    } catch (_) {}
  },

  /** Gestisce eventi SSE sync — notifica solo se la tab è in background */
  _suSyncEvent(ev) {
    if (!document.hidden) return;
    if (!ev || ev.tipo === 'info') return;

    const etichette = { crea: 'Nuovo', modifica: 'Aggiornato', elimina: 'Eliminato' };
    const moduli   = { scadenze: 'Scadenza', fascicoli: 'Fascicolo', clienti: 'Cliente', agenda: 'Appuntamento' };

    const titolo = `PCT Studio — ${moduli[ev.modulo] || 'Record'} ${etichette[ev.tipo] || ''}`;
    const corpo  = ev.messaggio || 'Dati aggiornati da un altro operatore.';
    const url    = { scadenze: '/scadenziario', fascicoli: '/fascicoli', clienti: '/clienti', agenda: '/agenda' }[ev.modulo] || '/';

    this._mostra(titolo, corpo, url);
  }
};

document.addEventListener('DOMContentLoaded', () => PCT_NOTIFICHE.init());
