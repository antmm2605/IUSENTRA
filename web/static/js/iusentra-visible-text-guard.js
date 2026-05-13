(function () {
  'use strict';

  var skipTags = {
    SCRIPT: true,
    STYLE: true,
    TEXTAREA: true,
    INPUT: true,
    SELECT: true,
    OPTION: true,
    PRE: true,
    CODE: true,
    KBD: true,
    SAMP: true
  };
  var attributeSkipTags = {
    SCRIPT: true,
    STYLE: true,
    PRE: true,
    CODE: true,
    KBD: true,
    SAMP: true
  };

  function clean(value) {
    return String(value || '')
      .replace(/\bDati\s+applicativi\s*-\s*Consultazione\b/gi, 'Dati dello studio')
      .replace(/\bDati\s+applicativi\b/gi, 'Dati dello studio')
      .replace(/Editor,\s*compilazione\s+assistita,\s*esportazioni\s+e\s+stampe\s+restano\s+nei\s+percorsi\s+[^.]+[.]/gi, 'Redazione, controlli, esportazioni e stampe sono disponibili dai comandi operativi dedicati.')
      .replace(/React\s+riceve\s+solo\s+metadati[^.]+[.]/gi, 'La pagina mostra solo informazioni utili e collegamenti operativi sicuri.')
      .replace(/\bImpeccable\s*\/\s*Open\s+Design\b/gi, 'Presidio qualita studio')
      .replace(/\bOpen\s+Designer?\b/gi, 'Presidio qualita')
      .replace(/\bContratto\s+dati\b/gi, 'Dati disponibili')
      .replace(/\bOwner\s+route\b/gi, 'Responsabile funzione')
      .replace(/\bMock\s+fallback\b/gi, 'Dati non disponibili')
      .replace(/\bDashboard\b/gi, 'Cruscotto')
      .replace(/\bworkflow\b/gi, 'percorso')
      .replace(/\bWizard\b/gi, 'Percorso guidato')
      .replace(/\bBuilder\b/gi, 'Editor')
      .replace(/\bGET\s+JSON\b/gi, 'consultazione dati')
      .replace(/\bPOST\s+JSON\b/gi, 'salvataggio dati')
      .replace(/\bread-only\b/gi, 'sola consultazione')
      .replace(/\bReact\b/gi, 'pagina')
      .replace(/\bFlask\b/gi, 'percorso applicativo')
      .replace(/\bJSON\b/g, 'dati')
      .replace(/\bUI\b/g, 'pagina')
      .replace(/\bMetadati\b/gi, 'Informazioni')
      .replace(/\bmetadati\b/gi, 'informazioni')
      .replace(/\bmetadata\b/gi, 'informazioni')
      .replace(/\bInterfaccia\b/gi, 'Pagina')
      .replace(/\bKPI\b/g, 'indicatori')
      .replace(/\bAudit\s+Log\b/gi, 'Registro audit')
      .replace(/\bauditati\b/gi, 'tracciati')
      .replace(/\bauditate\b/gi, 'tracciate')
      .replace(/\brollback\s+tecnico(?:\s+legacy)?\b/gi, 'Percorso di recupero')
      .replace(/\broute\s+Flask\b/gi, 'percorso applicativo')
      .replace(/\broute\b/gi, 'percorso')
      .replace(/\bGET\b/g, 'consulta')
      .replace(/\bPOST\b/g, 'salva')
      .replace(/\bsnapshot\b/gi, 'rilevazione')
      .replace(/\brepository\b/gi, 'archivio')
      .replace(/\bbackend\b/gi, 'controlli operativi')
      .replace(/\bfrontend\b/gi, 'pagina')
      .replace(/\bserver-side\b/gi, 'lato applicazione')
      .replace(/\bserver\b/gi, 'ambiente')
      .replace(/\bjson_api\b/gi, 'azioni protette')
      .replace(/\bpayload\b/gi, 'dati')
      .replace(/\bruntime\b/gi, 'ambiente di lavoro')
      .replace(/\bendpoint\b/gi, 'comando')
      .replace(/\bbridge\b/gi, 'collegamento')
      .replace(/\bprovider\b/gi, 'fornitore')
      .replace(/\bwebhook\b/gi, 'notifica automatica')
      .replace(/\bcache\b/gi, 'elenco locale')
      .replace(/\bRBAC\b/g, 'permessi')
      .replace(/\bCMS\b/g, 'contenuti')
      .replace(/\blegacy\b/gi, 'percorso di recupero')
      .replace(/\bfallback\s+tecnico\b/gi, 'verifica prudenziale')
      .replace(/\bdemo\b/gi, 'da verificare')
      .replace(/\b(undefined|null|todo|sample)\b/gi, 'non indicato');
  }

  function allowedText(node) {
    var element = node.nodeType === 1 ? node : node.parentElement;
    while (element) {
      if (skipTags[element.tagName]) return false;
      if (element.getAttribute && element.getAttribute('data-allow-technical-text') === 'true') return false;
      element = element.parentElement;
    }
    return true;
  }

  function allowedAttribute(element) {
    var current = element;
    while (current) {
      if (attributeSkipTags[current.tagName]) return false;
      if (current.getAttribute && current.getAttribute('data-allow-technical-text') === 'true') return false;
      current = current.parentElement;
    }
    return true;
  }

  function sanitize(root) {
    root = root || document.body;
    if (!root) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var nodes = [];
    var current = walker.nextNode();
    while (current) {
      if (current.textContent && allowedText(current)) nodes.push(current);
      current = walker.nextNode();
    }
    nodes.forEach(function (node) {
      var original = node.textContent || '';
      var next = clean(original);
      if (next !== original) node.textContent = next;
    });
    ['title', 'aria-label', 'aria-description', 'placeholder', 'alt'].forEach(function (attribute) {
      root.querySelectorAll('[' + attribute + ']').forEach(function (element) {
        if (!allowedAttribute(element)) return;
        var original = element.getAttribute(attribute);
        var next = clean(original);
        if (next !== original) element.setAttribute(attribute, next);
      });
    });
    var title = clean(document.title);
    if (title !== document.title) document.title = title;
  }

  function start() {
    var frame = 0;
    var schedule = function () {
      if (frame) return;
      frame = window.requestAnimationFrame(function () {
        frame = 0;
        sanitize(document.body);
      });
    };
    schedule();
    new MutationObserver(schedule).observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ['title', 'aria-label', 'aria-description', 'placeholder', 'alt']
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
