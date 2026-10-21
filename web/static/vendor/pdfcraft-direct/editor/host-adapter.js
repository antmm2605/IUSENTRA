/* IUSENTRA modification, 2026-10-21. SPDX-License-Identifier: AGPL-3.0-only
 * Generic PDF document exchange; no application API or credentials here.
 */
import * as editor from './app.js';
import { translateHostControls } from './host-it.js';
import { verifyFontForPdf } from './font-verifier.js';

const token = new URLSearchParams(location.hash.slice(1)).get('host_token');
if (token) {
  translateHostControls();
  // The host owns the native file chooser. Only selected font bytes cross
  // the isolated frame boundary; the engine has no device permissions.
  const fontsButton = document.getElementById('sysFonts');
  if (fontsButton) fontsButton.hidden = true;
  const imageButton = document.getElementById('addImage');
  if (imageButton) imageButton.hidden = true;
  const pending = new Map();
  const pendingFonts = new Map();
  let fontCatalog = [], verifyingFonts = false, cancelFonts = false;
  const readPcFont = fontId => new Promise((resolve, reject) => {
    const id = crypto.randomUUID();
    const timer = setTimeout(() => { pendingFonts.delete(id); reject(new Error('Lettura del carattere non riuscita.')); }, 30000);
    pendingFonts.set(id, { resolve, reject, timer });
    post('IUSENTRA_PDF_FONT_BYTES', { id, fontId });
  });
  const post = (type, payload = {}, transfer = []) =>
    window.parent.postMessage({ type, token, ...payload }, '*', transfer);
  editor.setHostStatus(message => post('IUSENTRA_PDF_STATUS', { message }));
  let dirty = Boolean(editor.state.dirty);
  Object.defineProperty(editor.state, 'dirty', {
    configurable: true, enumerable: true,
    get: () => dirty,
    set: value => { dirty = Boolean(value); post('IUSENTRA_PDF_DIRTY', { dirty }); },
  });

  editor.setHostSave(async (bytes, name) => {
    const id = crypto.randomUUID();
    const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error('Conferma del salvataggio non ricevuta. Riprova: le modifiche restano aperte.'));
      }, 120000);
      pending.set(id, { resolve, reject, timer });
      post('IUSENTRA_PDF_SAVE', { id, name, buffer }, [buffer]);
    });
  });

  window.addEventListener('message', async event => {
    if (event.source !== window.parent || event.data?.token !== token) return;
    const data = event.data;
    if (data.type === 'IUSENTRA_PDF_IMAGE' && data.buffer instanceof ArrayBuffer && data.buffer.byteLength <= 32 * 1024 * 1024) {
      try { await editor.addImageFromFile(new File([data.buffer], data.name || 'immagine', { type: data.mime })); }
      catch { post('IUSENTRA_PDF_STATUS', { message: 'Immagine non leggibile. Scegli un file PNG, JPEG o WebP valido.' }); }
    } else if (data.type === 'IUSENTRA_PDF_FONT_CATALOG' && Array.isArray(data.entries)) {
      fontCatalog = data.entries;
      editor.registerLocalFontCatalog(fontCatalog, readPcFont);
    } else if (data.type === 'IUSENTRA_PDF_VERIFY_FONTS' && !verifyingFonts) {
      verifyingFonts = true; cancelFonts = false;
      const results = [];
      try {
        for (const entry of fontCatalog) {
          if (cancelFonts) break;
          let result;
          try {
            const blob = await readPcFont(entry.id);
            const bytes = new Uint8Array(await blob.arrayBuffer());
            // The installed catalog renders through the platform's local font
            // resolver, exactly as the editor CSS does. PDFium independently
            // receives the actual font bytes for embedding and persistence.
            await new FontFace('iusentra-font-probe', 'local(' + JSON.stringify(entry.fullName || entry.family) + ')').load();
            result = verifyFontForPdf(editor.P().M, bytes);
          } catch (error) { result = { ok: false, reason: error.message }; }
          results.push({ family: entry.family, style: entry.style, ...result });
          post('IUSENTRA_PDF_FONT_VERIFY_PROGRESS', { tested: results.length, total: fontCatalog.length });
          await new Promise(resolve => setTimeout(resolve, 0));
        }
      } finally {
        verifyingFonts = false;
        post('IUSENTRA_PDF_FONT_VERIFY_RESULT', { results, total: fontCatalog.length, cancelled: cancelFonts });
      }
    } else if (data.type === 'IUSENTRA_PDF_CANCEL_FONT_VERIFY') {
      cancelFonts = true;
    } else if (data.type === 'IUSENTRA_PDF_FONT_BYTES_RESULT') {
      const pending = pendingFonts.get(data.id);
      if (!pending) return;
      clearTimeout(pending.timer); pendingFonts.delete(data.id);
      if (data.ok && data.buffer instanceof ArrayBuffer) pending.resolve(new Blob([data.buffer]));
      else pending.reject(new Error('Carattere del PC non disponibile.'));
    } else if (data.type === 'IUSENTRA_PDF_FONTS' && Array.isArray(data.fonts)) {
      const files = data.fonts.filter(font => typeof font.name === 'string'
        && font.buffer instanceof ArrayBuffer && font.buffer.byteLength <= 40 * 1024 * 1024)
        .map(font => new File([font.buffer], font.name));
      const imported = await editor.loadLocalFontFiles(files);
      post('IUSENTRA_PDF_FONTS_RESULT', { imported });
    } else if (data.type === 'IUSENTRA_PDF_SAVE_RESULT') {
      const request = pending.get(data.id);
      if (!request) return;
      pending.delete(data.id); clearTimeout(request.timer);
      if (data.ok) request.resolve();
      else request.reject(new Error(data.message || 'Salvataggio non confermato.'));
    } else if (data.type === 'IUSENTRA_PDF_LOAD') {
      if (!(data.buffer instanceof ArrayBuffer) || data.buffer.byteLength > 64 * 1024 * 1024) return;
      try {
        if (!await editor.engineReady) throw new Error('I comandi dell’editor non sono disponibili. Riprova l’apertura.');
        await editor.openFile(new File([data.buffer], data.name || 'documento.pdf', { type: 'application/pdf' }));
        post('IUSENTRA_PDF_LOADED');
      } catch {
        post('IUSENTRA_PDF_ERROR', { message: 'Il PDF non è stato aperto. L’originale è preservato.' });
      }
    }
  });

  document.addEventListener('click', event => {
    if (event.target.closest?.('#exitEditor')) {
      event.preventDefault(); event.stopImmediatePropagation(); post('IUSENTRA_PDF_EXIT');
    }
  }, true);
  post('IUSENTRA_PDF_READY');
}
