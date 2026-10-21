/* IUSENTRA modification 2026-10-21. SPDX-License-Identifier: AGPL-3.0-only
 * PDFium public/fpdf_edit.h: FPDFText_LoadFont, FPDFPageObj_CreateTextObj.
 * All probes use a separate in-memory document, never the user's PDF.
 */
function render(M, page) {
  const bitmap = M._FPDFBitmap_CreateEx(600, 100, 4, 0, 0);
  if (!bitmap) throw new Error('Memoria per il campione non disponibile.');
  try {
    M._FPDFBitmap_FillRect(bitmap, 0, 0, 600, 100, 0xffffffff);
    M._FPDF_RenderPageBitmap(bitmap, page, 0, 0, 600, 100, 0, 0);
    const address = M._FPDFBitmap_GetBuffer(bitmap);
    const size = M._FPDFBitmap_GetStride(bitmap) * 100;
    return M.HEAPU8.slice(address, address + size);
  } finally { M._FPDFBitmap_Destroy(bitmap); }
}

export function verifyFontForPdf(M, bytes) {
  let doc = 0, page = 0, font = 0, object = 0, data = 0, text = 0;
  let savedDoc = 0, savedPage = 0, savedData = 0, savedSize = 0, savedPtr = 0;
  try {
    doc = M._FPDF_CreateNewDocument();
    if (!doc) throw new Error('Documento di prova non disponibile.');
    data = M._malloc(bytes.length);
    M.HEAPU8.set(bytes, data);
    const firstType = bytes[0] === 0x4f && bytes[1] === 0x54 ? 1 : 2;
    font = M._FPDFText_LoadFont(doc, data, bytes.length, firstType, 1);
    if (!font) font = M._FPDFText_LoadFont(doc, data, bytes.length, firstType === 1 ? 2 : 1, 1);
    if (!font) throw new Error('Il motore PDF non accetta questo file di carattere.');
    page = M._FPDFPage_New(doc, 0, 600, 100);
    object = M._FPDFPageObj_CreateTextObj(doc, font, 18);
    if (!page || !object) throw new Error('Impossibile creare il campione PDF.');
    const sample = 'Abc 0123456789';
    text = M._malloc((sample.length + 1) * 2);
    for (let i = 0; i <= sample.length; i++) M.HEAPU16[(text >> 1) + i] = sample.charCodeAt(i) || 0;
    if (!M._FPDFText_SetText(object, text)) throw new Error('Il campione di testo non è accettato.');
    M._FPDFPageObj_Transform(object, 1, 0, 0, 1, 12, 50);
    M._FPDFPage_InsertObject(page, object); object = 0;
    if (!M._FPDFPage_GenerateContent(page)) throw new Error('Contenuto PDF non generato.');
    const before = render(M, page);
    if (!before.some((value, index) => index % 4 !== 3 && value < 240)) throw new Error('Il campione non produce segni visibili.');
    savedSize = M._malloc(4);
    savedPtr = M._ec_save_document(doc, 2, savedSize);
    const size = M.HEAPU32[savedSize >> 2];
    if (!savedPtr || !size) throw new Error('Il campione non può essere salvato.');
    savedData = M._malloc(size);
    M.HEAPU8.copyWithin(savedData, savedPtr, savedPtr + size);
    savedDoc = M._FPDF_LoadMemDocument64(savedData, size, 0);
    if (!savedDoc) throw new Error('Il campione salvato non si riapre.');
    savedPage = M._FPDF_LoadPage(savedDoc, 0);
    if (!savedPage) throw new Error('La pagina salvata non si riapre.');
    const after = render(M, savedPage);
    if (before.length !== after.length || before.some((value, index) => value !== after[index]))
      throw new Error('La resa del campione cambia dopo il salvataggio.');
    return { ok: true };
  } catch (error) {
    return { ok: false, reason: error.message || 'Verifica del carattere non riuscita.' };
  } finally {
    if (savedPage) M._FPDF_ClosePage(savedPage);
    if (savedDoc) M._FPDF_CloseDocument(savedDoc);
    if (savedData) M._free(savedData);
    if (savedPtr) M._ec_string_free(savedPtr);
    if (savedSize) M._free(savedSize);
    if (object) M._FPDFPageObj_Destroy(object);
    if (page) M._FPDF_ClosePage(page);
    if (font) M._FPDFFont_Close(font);
    if (doc) M._FPDF_CloseDocument(doc);
    if (text) M._free(text);
    if (data) M._free(data);
  }
}
