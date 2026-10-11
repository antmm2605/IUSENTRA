/* Confidential drafts/history belong in RAM in ordinary online mode.
 * Persistent study data is confined to the approved, encrypted offline vault.
 * UI preferences and authentication credentials keep their existing lifecycle.
 */
(function () {
  'use strict';
  if (typeof window === 'undefined' || !window.Storage || window.__iusentraPrivateMemory) return;
  const sensitive = (key) => /(?:bozza-anagrafica|ricerca\.recenti|studio-voice-(?:notes|profile|command-feedback)|portali\.acquisition\.history|ctu\.pending|contributoUnificato|iusentra-pct-ai-layout-v1:session|:conversation)/i.test(String(key));
  const prototype = window.Storage.prototype;
  const original = {get: prototype.getItem, set: prototype.setItem, remove: prototype.removeItem, clear: prototype.clear};
  const memories = new WeakMap();
  function memory(storage) {
    if (!memories.has(storage)) memories.set(storage, new Map());
    return memories.get(storage);
  }
  prototype.getItem = function (key) {
    key = String(key);
    if (!sensitive(key)) return original.get.call(this,key);
    const map = memory(this);
    // Preserve a pre-existing draft in this tab, then remove its plaintext copy.
    if (!map.has(key)) {
      const previous = original.get.call(this,key);
      if (previous !== null) {map.set(key,previous); original.remove.call(this,key);}
    }
    return map.get(key) ?? null;
  };
  prototype.setItem = function (key,value) {
    key = String(key);
    if (!sensitive(key)) return original.set.call(this,key,String(value));
    original.remove.call(this,key); memory(this).set(key,String(value));
  };
  prototype.removeItem = function (key) {memory(this).delete(String(key));return original.remove.call(this,String(key));};
  prototype.clear = function () {memory(this).clear();return original.clear.call(this);};
  // Remove known pre-existing plaintext caches without losing the current tab's draft.
  for (const storage of [window.localStorage,window.sessionStorage]) {
    for (const key of Object.keys(storage)) if (sensitive(key)) storage.getItem(key);
  }
  window.__iusentraPrivateMemory = true;
  window.addEventListener('beforeunload', function (event) {
    for (const storage of [window.localStorage,window.sessionStorage]) {
      if (memory(storage).size) {event.preventDefault();event.returnValue='';return;}
    }
  });
})();
