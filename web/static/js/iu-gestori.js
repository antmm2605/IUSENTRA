/*
 * Gestori evento dei template legacy senza codice in linea.
 *
 * La CSP non ammette 'unsafe-inline' per gli script: gli attributi on<evento>
 * dei template sono stati convertiti in data-iu-on="evento:chiave" e il codice
 * sta in iu-gestori-registro.js (scripts/csp_gestori_legacy.py).
 * Qui ogni elemento con data-iu-on riceve il gestore come proprietà on<evento>,
 * cioè con la stessa semantica dell'attributo: `this` è l'elemento, `event`
 * l'evento, `return false` annulla l'azione predefinita, stesso ordine rispetto
 * agli altri ascoltatori. I valori data-iu-v-<evento>-<n> arrivano come testo.
 * Anche gli elementi aggiunti dopo il caricamento vengono collegati.
 */
(function () {
  'use strict';
  var R = (window.IU_GESTORI = window.IU_GESTORI || {});
  var collegati = typeof WeakMap === 'function' ? new WeakMap() : null;

  function valori(el, evento) {
    var elenco = [];
    for (var i = 0; ; i++) {
      var v = el.getAttribute('data-iu-v-' + evento + '-' + i);
      if (v === null) return elenco;
      elenco.push(v);
    }
  }

  function gestore(evento, chiave) {
    return function (event) {
      var f = R[chiave];
      if (typeof f !== 'function') {
        if (window.console) console.warn('IUSENTRA: gestore evento non registrato', chiave);
        return undefined;
      }
      return f.call(this, event, valori(this, evento));
    };
  }

  function collega(el) {
    var spec = el.getAttribute('data-iu-on');
    if (!spec) return;
    if (collegati && collegati.get(el) === spec) return;
    if (collegati) collegati.set(el, spec);
    var coppie = spec.trim().split(/\s+/);
    for (var i = 0; i < coppie.length; i++) {
      var p = coppie[i].split(':');
      if (p.length === 2 && p[0] && p[1]) el['on' + p[0]] = gestore(p[0], p[1]);
    }
  }

  function scansiona(radice) {
    if (!radice || radice.nodeType !== 1) return;
    if (radice.hasAttribute('data-iu-on')) collega(radice);
    var elenco = radice.querySelectorAll('[data-iu-on]');
    for (var i = 0; i < elenco.length; i++) collega(elenco[i]);
  }

  window.IU_GESTORI_SCANSIONA = scansiona;

  if (typeof MutationObserver === 'function') {
    new MutationObserver(function (mutazioni) {
      for (var i = 0; i < mutazioni.length; i++) {
        var m = mutazioni[i];
        if (m.type === 'attributes') {
          collega(m.target);
        } else {
          for (var j = 0; j < m.addedNodes.length; j++) scansiona(m.addedNodes[j]);
        }
      }
    }).observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['data-iu-on'],
    });
  }
  scansiona(document.documentElement);
  document.addEventListener('DOMContentLoaded', function () {
    scansiona(document.documentElement);
  });
})();
