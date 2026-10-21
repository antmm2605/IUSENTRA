/* IUSENTRA modification 2026-10-21. SPDX-License-Identifier: AGPL-3.0-only */
const level = value => value === 2 || value === '2' ? '2' : value === true || value === 1 || value === '1' ? '1' : '0';

export function embeddedFontIdentity(originalRun) {
  return { docfontFor: originalRun.family, docfontB: level(originalRun.bold), docfontI: level(originalRun.italic) };
}

export function canUseEmbeddedFont(current) {
  return Boolean(current.docfont && current.docfontFor === current.family
    && (current.docfontB ?? '0') === level(current.bold)
    && (current.docfontI ?? '0') === level(current.italic));
}
