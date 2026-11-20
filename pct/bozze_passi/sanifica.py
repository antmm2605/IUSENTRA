"""Il testo di una bozza salvato dall'editor, ripulito con una lista di tag ammessi.

Il testo torna nell'editor e finisce nel PDF del fascicolo: tutto ciò che non serve a un atto si toglie, così
nessuno script salvato può eseguirsi alla riapertura (XSS memorizzato). Ammessi: paragrafi, a capo, grassetto,
corsivo, sottolineato, elenchi, titoli h1-h4, span e mark (i segnaposti gialli) e la sezione di pagina dell'editor
(``section``/``div`` con i soli attributi di impaginazione). Script, stili, iframe e oggetti si tolgono con il loro
contenuto; gli altri tag (immagini, collegamenti, moduli) si tolgono lasciando il testo. Si tolgono gli attributi
``on*``, ogni ``href``/``src``, gli stili con ``url(``, ``expression(`` o ``javascript:``.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

TAG_AMMESSI = frozenset({"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "h1", "h2", "h3", "h4",
                         "span", "mark", "section", "div"})
_SENZA_CHIUSURA = frozenset({"br"})
# Tag tolti insieme a tutto il loro contenuto.
_DA_SVUOTARE = frozenset({"script", "style", "iframe", "object", "embed", "template", "noscript", "svg", "math",
                          "textarea", "select", "head", "title"})
_ATTRIBUTI = frozenset({"class", "style", "data-pagina", "data-margine-alto", "data-margine-destro", "data-margine-basso",
                        "data-margine-sinistro", "data-allineamento", "data-interlinea", "data-layout-sezione"})
_STILE_PERICOLOSO = re.compile(r"url\s*\(|expression\s*\(|javascript\s*:|@import|behavior\s*:|-moz-binding", re.IGNORECASE)


class _Sanificatore(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parti: list[str] = []
        self._svuota = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        nome = tag.lower()
        if nome in _DA_SVUOTARE:
            self._svuota += 1
            return
        if self._svuota or nome not in TAG_AMMESSI:
            return
        tenuti = []
        for attributo, valore in attrs:
            chiave, testo = (attributo or "").lower(), str(valore or "")
            if chiave not in _ATTRIBUTI or (chiave == "style" and _STILE_PERICOLOSO.search(html.unescape(testo))):
                continue
            tenuti.append(f'{chiave}="{html.escape(testo, quote=True)}"')
        self.parti.append(f"<{nome}{' ' + ' '.join(tenuti) if tenuti else ''}>")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in _SENZA_CHIUSURA and tag.lower() not in _DA_SVUOTARE:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        nome = tag.lower()
        if nome in _DA_SVUOTARE:
            self._svuota = max(0, self._svuota - 1)
            return
        if not self._svuota and nome in TAG_AMMESSI and nome not in _SENZA_CHIUSURA:
            self.parti.append(f"</{nome}>")

    def handle_data(self, data: str) -> None:
        if not self._svuota:
            self.parti.append(html.escape(data, quote=False))


def sanifica_testo_bozza(testo_html: str) -> str:
    """Il testo dell'editor con i soli tag e attributi ammessi; il testo resta, il codice no."""
    sanificatore = _Sanificatore()
    sanificatore.feed(str(testo_html or ""))
    sanificatore.close()
    return "".join(sanificatore.parti).strip() or "<p></p>"


__all__ = ["TAG_AMMESSI", "sanifica_testo_bozza"]
