"""I caratteri che il PDF si porta dentro, riusati per riscriverlo.

Un atto scritto in *French Script MT* o in *Monotype Corsiva* non si puo'
riprodurre con i quattordici caratteri base del PDF, e un equivalente metrico
aperto quei due non ce l'hanno. Il carattere pero' sta **dentro il documento**:
il PDF se lo porta incorporato, altrimenti non si vedrebbe nemmeno sul
computer di chi lo riceve. Qui si tira fuori e si riusa.

C'e' una trappola, ed e' la ragione per cui questo modulo esiste invece di
essere tre righe. **Il carattere incorporato e' un sottoinsieme**: contiene
solo le lettere che quel documento usa, non l'alfabeto. Scrivendoci una parola
nuova, le lettere che mancano non danno errore — escono **bianche**. Su un atto
che poi si deposita e' il difetto peggiore che ci sia, perche' non si vede.

Per questo il carattere estratto si usa solo dopo aver controllato, lettera per
lettera, che il testo da scrivere ci stia tutto dentro (`copre`). Quando non ci
sta, quel capoverso torna al carattere sostitutivo: cambia l'aspetto di una
riga, ma il testo c'e' tutto. Un guasto che si vede e' sempre meglio di uno che
non si vede.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import threading
from typing import Optional

_LOG = logging.getLogger(__name__)

#: Oltre questa taglia il carattere non si porta dietro: incorporarlo
#: gonfierebbe il documento piu' di quanto valga la resa. I calligrafici, che
#: sono quelli che servono, stanno tutti sotto i cento kilobyte.
TAGLIA_MASSIMA = 320_000

#: I nomi che un convertitore da' ai caratteri che rinomina: non dicono niente.
_SENZA_NOME = re.compile(r"^(?:cidfont\+)?[a-z]{1,3}\d{1,3}$", re.I)

_serratura = threading.Lock()
_registrati: dict[str, str] = {}


def _programma(descrittore: dict, risolvi) -> Optional[bytes]:
    for chiave in ("FontFile2", "FontFile3", "FontFile"):
        flusso = descrittore.get(chiave)
        if flusso is None:
            continue
        try:
            dati = risolvi(flusso).get_data()
        except Exception:
            return None
        if not dati or len(dati) > TAGLIA_MASSIMA:
            return None
        # solo TrueType: il resto reportlab non lo sa leggere
        if dati[:4] not in (b"\x00\x01\x00\x00", b"true", b"ttcf", b"OTTO"):
            return None
        return dati
    return None


def caratteri_della_pagina(pagina) -> dict:
    """I caratteri incorporati della pagina: nome nel PDF -> {alias, dati}.

    L'alias e' un nome stabile ricavato dai byte, cosi' lo stesso carattere su
    pagine diverse resta lo stesso e si registra una volta sola.
    """
    try:
        from pdfminer.pdftypes import resolve1
    except Exception:
        return {}
    fuori: dict = {}
    try:
        risorse = resolve1(pagina._pagina.page_obj.resources) or {}
        caratteri = resolve1(risorse.get("Font")) or {}
    except Exception:
        return {}
    for riferimento in list(caratteri.values()):
        try:
            voce = resolve1(riferimento) or {}
            descrittore = resolve1(voce.get("FontDescriptor")) or {}
            if not descrittore and voce.get("DescendantFonts"):
                discendenti = resolve1(voce["DescendantFonts"]) or []
                if discendenti:
                    descrittore = resolve1(
                        (resolve1(discendenti[0]) or {}).get("FontDescriptor")
                    ) or {}
            nome = voce.get("BaseFont")
            nome = getattr(nome, "name", None) or str(nome or "")
            if not nome:
                continue
            dati = _programma(descrittore, resolve1)
            if not dati:
                continue
            impronta = hashlib.sha1(dati).hexdigest()[:12]
            fuori[nome.split("+")[-1]] = {
                "alias": f"iu-{impronta}",
                "dati": dati,
            }
        except Exception:
            continue
    return fuori


def da_incorporare(caratteri: dict, serve: set) -> dict:
    """Quelli che vale la pena portarsi dietro: usati, e senza equivalente.

    Se la famiglia ha un equivalente metrico aperto — Times New Roman, Arial,
    Calibri, Cambria — non si incorpora niente: quello e' un carattere intero,
    non un sottoinsieme, e lo si puo' usare anche sul testo che l'avvocato
    riscrive.
    """
    try:
        from pct.caratteri_reali import tagli_per
    except Exception:
        def tagli_per(_):
            return None

    fuori = {}
    for nome, voce in caratteri.items():
        if voce["alias"] not in serve:
            continue
        if any(tagli_per(forma) for forma in _forme_del_nome(nome)):
            continue
        if _SENZA_NOME.match(nome.strip()):
            # nome senza significato: l'equivalente non si puo' cercare, ma il
            # carattere incorporato c'e' ed e' l'unico modo di renderlo
            fuori[nome] = voce
            continue
        fuori[nome] = voce
    return fuori


#: I suffissi con cui un PDF scrive il taglio dopo il nome della famiglia.
#: «roman» resta fuori apposta: in «Times New Roman» e «Nimbus Roman» e' parte
#: del nome della famiglia, non il taglio.
_TAGLI = (
    "bolditalic", "boldoblique", "bold_italic", "italic", "oblique", "bold",
    "regular", "normal", "light", "medium", "semibold", "black",
)


def _forme_del_nome(nome: str) -> tuple[str, ...]:
    """I modi in cui questo carattere puo' essere scritto nel catalogo.

    Un PDF scrive «Times New Roman,Bold», «TimesNewRoman-Bold» o
    «LiberationSerif-normal»: sotto c'e' sempre la stessa famiglia, e il
    catalogo degli equivalenti la conosce con un nome solo.
    """
    pulito = nome.split("+")[-1].split(",")[0].strip()
    forme = {pulito}
    minuscolo = pulito.lower()
    for taglio in _TAGLI:
        for separatore in ("-", "_", " "):
            fine = separatore + taglio
            if minuscolo.endswith(fine):
                forme.add(pulito[: -len(fine)])
                minuscolo = minuscolo[: -len(fine)]
                break
    # «LiberationSerif» e' «Liberation Serif»
    for forma in list(forme):
        forme.add(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", forma))
    return tuple(f.strip() for f in forme if f.strip())


def blocco_stile(incorporati: dict) -> str:
    """La dichiarazione `@font-face` da mettere in cima alla pagina."""
    if not incorporati:
        return ""
    pezzi = []
    visti = set()
    for voce in incorporati.values():
        if voce["alias"] in visti:
            continue
        visti.add(voce["alias"])
        dati = base64.b64encode(voce["dati"]).decode()
        pezzi.append(
            f'@font-face{{font-family:"{voce["alias"]}";'
            f'src:url(data:font/ttf;base64,{dati}) format("truetype")}}'
        )
    return f'<style class="iu-doc-caratteri">{"".join(pezzi)}</style>'


# ---------------------------------------------------------------------------
# Dall'altra parte: chi riscrive il PDF
# ---------------------------------------------------------------------------

def leggi_blocco_stile(html: str) -> dict:
    """I caratteri incorporati nell'HTML: alias -> byte."""
    fuori: dict = {}
    for pezzo in re.finditer(
        r'@font-face\{font-family:"(iu-[0-9a-f]+)";'
        r'src:url\(data:font/[^;]+;base64,([A-Za-z0-9+/=]+)\)',
        html or "",
    ):
        try:
            fuori[pezzo.group(1)] = base64.b64decode(pezzo.group(2))
        except Exception:
            continue
    return fuori


def registra(alias: str, dati: bytes) -> Optional[str]:
    """Registra il carattere e restituisce il nome con cui chiamarlo."""
    if alias in _registrati:
        return _registrati[alias]
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return None
    with _serratura:
        if alias in _registrati:
            return _registrati[alias]
        try:
            pdfmetrics.registerFont(TTFont(alias, io.BytesIO(dati)))
            # il carattere incorporato *e' gia'* il taglio giusto — il corsivo
            # di Monotype Corsiva e' un file a se' — quindi grassetto e
            # corsivo non devono cercarne un altro: portano tutti qui
            from reportlab.lib.fonts import addMapping
            for grassetto in (0, 1):
                for corsivo in (0, 1):
                    addMapping(alias, grassetto, corsivo, alias)
        except Exception as errore:
            _LOG.debug("carattere incorporato non registrabile: %s (%s)", alias, errore)
            _registrati[alias] = ""
            return None
        _registrati[alias] = alias
        return alias


def copre(alias: str, testo: str) -> bool:
    """Vero se ogni lettera del testo esiste in questo carattere.

    E' il controllo che rende sicuro riusare un sottoinsieme: senza, le lettere
    che l'avvocato aggiunge escono bianche e nessuno se ne accorge.
    """
    if not testo:
        return True
    try:
        from reportlab.pdfbase import pdfmetrics
        faccia = pdfmetrics.getFont(alias).face
    except Exception:
        return False
    mappa = getattr(faccia, "charToGlyph", None)
    if not mappa:
        return False
    for lettera in set(testo):
        if lettera in ("\n", "\r", "\t"):
            continue
        if not mappa.get(ord(lettera)):
            return False
    return True


def azzera_per_prova() -> None:
    """Svuota il registro: serve solo ai test."""
    _registrati.clear()
