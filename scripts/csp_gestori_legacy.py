"""Toglie dai template legacy il codice JavaScript scritto negli attributi (``onclick=``…).

La politica di sicurezza dei contenuti (CSP) non ammette più ``'unsafe-inline'``
per gli script: il browser esegue solo i file dello studio e i blocchi
``<script>`` che portano il nonce della richiesta. Gli attributi evento dei
template (``onclick="…"``, ``onsubmit="return confirm(…)"``) sono codice in
linea e verrebbero bloccati.

Questo strumento li converte:

* ``onclick="CODICE"`` diventa ``data-iu-on="click:ID"``; il CODICE finisce, una
  volta sola per testo uguale, nel registro ``web/static/js/iu-gestori-registro.js``
  sotto la chiave ID (impronta del codice);
* le espressioni Jinja dentro il codice (``{{ fascicolo.id }}``) diventano
  attributi ``data-iu-v-click-0="{{ fascicolo.id }}"``: il valore arriva al codice
  come testo, non come codice, e un nome con un apice non può più rompere lo script;
* ai blocchi ``<script>`` in linea si aggiunge ``nonce="{{ csp_nonce() }}"``.

``web/static/js/iu-gestori.js`` collega i gestori agli elementi (anche a quelli
creati dopo il caricamento) con la stessa semantica dell'attributo: ``this`` è
l'elemento, ``event`` l'evento, ``return false`` annulla l'azione predefinita,
e il codice vede gli stessi nomi (elemento, modulo, documento).

Uso::

    python scripts/csp_gestori_legacy.py          # converte i template e aggiorna il registro
    python scripts/csp_gestori_legacy.py --check  # esce con 1 se resta codice in linea

Base: CSP Level 3 (W3C), raccomandazioni OWASP sulla prevenzione XSS.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "web" / "templates"
REGISTRO = ROOT / "web" / "static" / "js" / "iu-gestori-registro.js"

INTESTAZIONE_REGISTRO = """/*
 * Registro dei gestori evento dei template legacy.
 * Generato da scripts/csp_gestori_legacy.py: non modificare a mano l'elenco,
 * si rigenera dai template. Ogni voce e' il codice che stava in un attributo
 * on<evento>="..."; iu-gestori.js lo esegue con la stessa semantica.
 * Il file non e' in modalita' strict: serve lo scope dell'attributo (with).
 */
(function (R) {
"""
CHIUSURA_REGISTRO = "})(window.IU_GESTORI = window.IU_GESTORI || {});\n"

_TAG_BLOCCO = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", re.S | re.I)
_COMMENTO_JINJA = re.compile(r"\{#.*?#\}", re.S)
_APERTURA_TAG = re.compile(r"<([a-zA-Z][\w:-]*)")
_NOME_ATTRIBUTO = re.compile(r"[^\s=>/\"'{]+")
_EVENTO = re.compile(r"on([a-z]+)$")
_SCRIPT_APERTURA = re.compile(r"<script\b([^>]*)>", re.I)
_VOCE = re.compile(
    r'^R\["(g[0-9a-f]{10})"\] = function \(event, __v\) \{ with \(document\) with \(this\.form \|\| \{\}\) with \(this\) \{\n(.*?)\n\}\}; /\* fine \1 \*/$',
    re.S | re.M,
)
_TIPI_DATI = ("application/json", "application/ld+json", "text/template", "text/x-template")


class ConversioneImpossibile(Exception):
    pass


@dataclass
class Attributo:
    inizio: int
    fine: int
    nome: str
    valore: str | None  # testo grezzo fra le virgolette, Jinja compreso
    virgolette: str


def _salta_jinja(testo: str, i: int) -> int:
    """Se in ``i`` inizia un blocco Jinja, restituisce l'indice subito dopo la chiusura."""
    for apre, chiude in (("{{", "}}"), ("{%", "%}"), ("{#", "#}")):
        if testo.startswith(apre, i):
            fine = testo.find(chiude, i + 2)
            if fine < 0:
                raise ConversioneImpossibile("blocco Jinja non chiuso")
            return fine + 2
    return i


def _attributi_tag(testo: str, inizio_tag: int) -> tuple[list[Attributo], int, bool]:
    """Legge gli attributi di un tag che inizia in ``inizio_tag`` (su ``<``).

    Restituisce gli attributi, l'indice del ``>`` di chiusura e se nel tag ci sono
    blocchi ``{% %}`` fuori dai valori (un ``{% if %}`` può rendere condizionale un attributo).
    """
    m = _APERTURA_TAG.match(testo, inizio_tag)
    assert m
    i = m.end()
    attributi: list[Attributo] = []
    jinja_libero = False
    n = len(testo)
    while i < n:
        c = testo[i]
        if c.isspace():
            i += 1
            continue
        if c == ">":
            return attributi, i, jinja_libero
        if testo.startswith("/>", i):
            return attributi, i + 1, jinja_libero
        dopo = _salta_jinja(testo, i)
        if dopo != i:
            # Un {{ }} fra gli attributi non rende condizionale nulla; un {% %} sì.
            jinja_libero = jinja_libero or not testo.startswith("{{", i)
            i = dopo
            continue
        mn = _NOME_ATTRIBUTO.match(testo, i)
        if not mn:
            raise ConversioneImpossibile(f"attributo illeggibile vicino a {testo[i:i + 40]!r}")
        nome = mn.group(0)
        inizio_attr = i
        i = mn.end()
        j = i
        while j < n and testo[j].isspace():
            j += 1
        if j < n and testo[j] == "=":
            j += 1
            while j < n and testo[j].isspace():
                j += 1
            if j < n and testo[j] in "\"'":
                q = testo[j]
                k = j + 1
                while k < n and testo[k] != q:
                    dopo = _salta_jinja(testo, k)
                    k = dopo if dopo != k else k + 1
                if k >= n:
                    raise ConversioneImpossibile("valore di attributo non chiuso")
                attributi.append(Attributo(inizio_attr, k + 1, nome, testo[j + 1:k], q))
                i = k + 1
            else:
                k = j
                while k < n and not testo[k].isspace() and testo[k] != ">":
                    dopo = _salta_jinja(testo, k)
                    k = dopo if dopo != k else k + 1
                attributi.append(Attributo(inizio_attr, k, nome, testo[j:k], ""))
                i = k
        else:
            attributi.append(Attributo(inizio_attr, i, nome, None, ""))
    raise ConversioneImpossibile("tag non chiuso")


def _pezzi(valore: str) -> list[tuple[str, str]]:
    """Divide il valore in testo statico ("t") ed espressioni Jinja ("j")."""
    pezzi: list[tuple[str, str]] = []
    i = 0
    buf = []
    while i < len(valore):
        if valore.startswith("{%", i) or valore.startswith("{#", i):
            raise ConversioneImpossibile("blocco {% %} dentro un gestore evento: convertire a mano")
        if valore.startswith("{{", i):
            fine = valore.find("}}", i + 2)
            if fine < 0:
                raise ConversioneImpossibile("espressione Jinja non chiusa")
            if buf:
                pezzi.append(("t", "".join(buf)))
                buf = []
            pezzi.append(("j", valore[i:fine + 2]))
            i = fine + 2
            continue
        buf.append(valore[i])
        i += 1
    if buf:
        pezzi.append(("t", "".join(buf)))
    return pezzi


def _stato_virgolette(codice: str, stato: str) -> str:
    """Aggiorna lo stato (virgoletta aperta o "") leggendo ``codice``."""
    i = 0
    while i < len(codice):
        c = codice[i]
        if stato:
            if c == "\\":
                i += 2
                continue
            if c == stato:
                stato = ""
        elif c in "'\"`":
            stato = c
        i += 1
    return stato


def codice_e_valori(valore: str) -> tuple[str, list[str]]:
    """Codice JavaScript del registro e le espressioni Jinja che diventano valori."""
    codice: list[str] = []
    valori: list[str] = []
    stato = ""
    for tipo, pezzo in _pezzi(valore):
        if tipo == "t":
            testo = html.unescape(pezzo)
            codice.append(testo)
            stato = _stato_virgolette(testo, stato)
            continue
        indice = len(valori)
        if stato:
            valori.append(pezzo)
            codice.append(f"{stato} + __v[{indice}] + {stato}")
        else:
            # Valore usato come codice (numero, booleano, JSON di tojson): nel
            # template era testo JavaScript, nell'attributo va sempre escapato
            # (tojson lascia le virgolette doppie, che chiuderebbero l'attributo).
            valori.append("{{ (" + pezzo[2:-2].strip() + ") | forceescape }}")
            codice.append(f"JSON.parse(__v[{indice}])")
    return "".join(codice).strip(), valori


def identificativo(codice: str) -> str:
    return "g" + hashlib.sha256(codice.encode("utf-8")).hexdigest()[:10]


def _zone_escluse(testo: str) -> list[tuple[int, int]]:
    zone = [m.span() for m in _TAG_BLOCCO.finditer(testo)]
    zone += [m.span() for m in _COMMENTO_JINJA.finditer(testo)]
    zone += [m.span() for m in re.finditer(r"<!--.*?-->", testo, re.S)]
    return zone


def converti_testo(testo: str, registro: dict[str, str], origine: str) -> tuple[str, int, list[str]]:
    """Converte gli attributi evento di un template. Restituisce testo, conteggio, problemi."""
    problemi: list[str] = []
    zone = _zone_escluse(testo)
    sostituzioni: list[tuple[int, int, str]] = []
    convertiti = 0
    for m in re.finditer(r"<[a-zA-Z]", testo):
        pos = m.start()
        if any(a <= pos < b for a, b in zone):
            continue
        # Il tag di apertura di <script>/<style> sta dentro la zona: va controllato a parte.
        try:
            attributi, _chiusura, jinja_libero = _attributi_tag(testo, pos)
        except ConversioneImpossibile:
            continue
        eventi = [a for a in attributi if _EVENTO.match(a.nome.lower()) and a.valore is not None]
        if not eventi:
            continue
        riga = testo.count("\n", 0, pos) + 1
        # Con un solo attributo evento la sostituzione avviene sul posto e resta
        # dentro l'eventuale {% if %}; con più attributi e blocchi {% %} no.
        if jinja_libero and len(eventi) > 1:
            problemi.append(f"{origine}:{riga}: blocco Jinja fra gli attributi del tag: convertire a mano")
            continue
        if any(a.nome.lower() == "data-iu-on" for a in attributi):
            problemi.append(f"{origine}:{riga}: tag con data-iu-on e attributi evento insieme")
            continue
        try:
            coppie = []
            extra = []
            for attr in eventi:
                evento = _EVENTO.match(attr.nome.lower()).group(1)
                codice, valori = codice_e_valori(attr.valore)
                chiave = identificativo(codice)
                registro.setdefault(chiave, codice)
                coppie.append(f"{evento}:{chiave}")
                for n, espressione in enumerate(valori):
                    extra.append(f'data-iu-v-{evento}-{n}="{espressione}"')
        except ConversioneImpossibile as exc:
            problemi.append(f"{origine}:{riga}: {exc}")
            continue
        nuovo = " ".join([f'data-iu-on="{" ".join(coppie)}"', *extra])
        # Il primo attributo evento prende il posto del nuovo attributo, gli altri si tolgono.
        primo, *altri = sorted(eventi, key=lambda a: a.inizio)
        sostituzioni.append((primo.inizio, primo.fine, nuovo))
        for attr in altri:
            inizio = attr.inizio
            while inizio > 0 and testo[inizio - 1] in " \t":
                inizio -= 1
            sostituzioni.append((inizio, attr.fine, ""))
        convertiti += len(eventi)
    for inizio, fine, nuovo in sorted(sostituzioni, reverse=True):
        testo = testo[:inizio] + nuovo + testo[fine:]
    return testo, convertiti, problemi


def aggiungi_nonce(testo: str) -> tuple[str, int]:
    """Aggiunge il nonce ai blocchi <script> in linea eseguibili."""
    conteggio = 0

    def sostituisci(m: re.Match[str]) -> str:
        nonlocal conteggio
        attributi = m.group(1)
        basso = attributi.lower()
        if re.search(r"\bsrc\s*=", basso) or "nonce=" in basso:
            return m.group(0)
        tipo = re.search(r"\btype\s*=\s*[\"']([^\"']+)", basso)
        if tipo and tipo.group(1).strip() in _TIPI_DATI:
            return m.group(0)
        conteggio += 1
        return f'<script nonce="{{{{ csp_nonce() }}}}"{attributi}>'

    risultato = []
    ultimo = 0
    for blocco in re.finditer(r"<script\b[^>]*>.*?</script\b[^>]*>", testo, re.S | re.I):
        risultato.append(testo[ultimo:blocco.start()])
        apertura = _SCRIPT_APERTURA.match(blocco.group(0))
        risultato.append(_SCRIPT_APERTURA.sub(sostituisci, blocco.group(0)[:apertura.end()], count=1))
        risultato.append(blocco.group(0)[apertura.end():])
        ultimo = blocco.end()
    risultato.append(testo[ultimo:])
    return "".join(risultato), conteggio


def carica_registro() -> dict[str, str]:
    if not REGISTRO.exists():
        return {}
    testo = REGISTRO.read_text(encoding="utf-8")
    voci = {}
    for m in re.finditer(_VOCE, testo):
        voci[m.group(1)] = m.group(2)
    return voci


def scrivi_registro(registro: dict[str, str], usati: set[str]) -> str:
    righe = [INTESTAZIONE_REGISTRO]
    for chiave in sorted(k for k in registro if k in usati):
        righe.append(f'R["{chiave}"] = function (event, __v) {{ with (document) with (this.form || {{}}) with (this) {{\n{registro[chiave]}\n}}}}; /* fine {chiave} */\n')
    righe.append(CHIUSURA_REGISTRO)
    return "".join(righe)


def chiavi_usate(testi: list[str]) -> set[str]:
    usati: set[str] = set()
    for testo in testi:
        for m in re.finditer(r'data-iu-on="([^"]+)"', testo):
            for coppia in m.group(1).split():
                usati.add(coppia.split(":", 1)[1])
    return usati


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="non scrive: esce con 1 se resta codice in linea")
    args = parser.parse_args(argv)
    registro = carica_registro()
    problemi: list[str] = []
    da_scrivere: dict[Path, str] = {}
    totale_gestori = totale_nonce = 0
    testi_finali: list[str] = []
    for percorso in sorted(TEMPLATES.rglob("*.html")):
        originale = percorso.read_text(encoding="utf-8")
        origine = str(percorso.relative_to(ROOT))
        testo, gestori, errori = converti_testo(originale, registro, origine)
        testo, nonce = aggiungi_nonce(testo)
        problemi.extend(errori)
        totale_gestori += gestori
        totale_nonce += nonce
        testi_finali.append(testo)
        if testo != originale:
            da_scrivere[percorso] = testo
    contenuto_registro = scrivi_registro(registro, chiavi_usate(testi_finali))
    registro_cambiato = not REGISTRO.exists() or REGISTRO.read_text(encoding="utf-8") != contenuto_registro
    if args.check:
        for percorso in da_scrivere:
            print(f"Codice in linea da convertire: {percorso.relative_to(ROOT)}")
        if registro_cambiato and not da_scrivere:
            print("Registro dei gestori non allineato ai template: rigenerare.")
        for problema in problemi:
            print(problema)
        return 1 if (da_scrivere or registro_cambiato or problemi) else 0
    for percorso, testo in da_scrivere.items():
        percorso.write_text(testo, encoding="utf-8")
    REGISTRO.write_text(contenuto_registro, encoding="utf-8")
    print(f"Gestori convertiti: {totale_gestori}; script con nonce aggiunto: {totale_nonce}; file: {len(da_scrivere)}")
    for problema in problemi:
        print(problema)
    return 1 if problemi else 0


if __name__ == "__main__":
    sys.exit(main())
