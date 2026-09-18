"""Dal testo alle righe ai paragrafi: allineamenti, rientri, interlinea, elenchi.

Il documento che ne esce scorre — paragrafi e elenchi restano modificabili
nell'editor — e l'aspetto resta quello dell'originale."""

from __future__ import annotations

import re
import statistics
from html import escape
from typing import Optional

from .taratura import Taratura, _pt
from .modello import Elemento, Riga, Tratto
from .lettura import _RE_SEGNO, _unisci_segni_elenco


# ===========================================================================
# 2. Dal testo ai paragrafi
# ===========================================================================

def _html_tratti(tratti: list[Tratto], corpo_base: float, famiglia_base: str) -> str:
    """Accorpa i tratti con lo stesso stile e li rende in HTML."""
    pezzi: list[str] = []
    gruppo: list[str] = []
    chiave = None
    modello: Optional[Tratto] = None

    def _chiudi():
        if not gruppo or not modello:
            return
        testo = escape("".join(gruppo))
        stile = []
        if modello.famiglia != famiglia_base:
            stile.append(f"font-family:{modello.famiglia}")
        if abs(modello.corpo - corpo_base) >= 0.6:
            stile.append(f"font-size:{_pt(modello.corpo)}pt")
        if modello.colore.lower() not in ("#000000", "#000"):
            stile.append(f"color:{modello.colore}")
        if modello.evidenziato:
            stile.append(f"background-color:{modello.evidenziato}")

        apri, chiudi = "", ""
        if modello.grassetto:
            apri += "<strong>"; chiudi = "</strong>" + chiudi
        if modello.corsivo:
            apri += "<em>"; chiudi = "</em>" + chiudi
        if modello.sottolineato:
            apri += "<u>"; chiudi = "</u>" + chiudi
        if modello.barrato:
            apri += "<s>"; chiudi = "</s>" + chiudi
        if modello.apice:
            apri += "<sup>"; chiudi = "</sup>" + chiudi
        if modello.pedice:
            apri += "<sub>"; chiudi = "</sub>" + chiudi

        corpo = f"{apri}{testo}{chiudi}"
        if stile:
            corpo = f'<span style="{";".join(stile)}">{corpo}</span>'
        if modello.collegamento:
            corpo = f'<a href="{escape(modello.collegamento, quote=True)}">{corpo}</a>'
        pezzi.append(corpo)
        gruppo.clear()

    for t in tratti:
        if t.chiave() != chiave:
            _chiudi()
            chiave, modello = t.chiave(), t
        gruppo.append(t.testo)
    _chiudi()
    return "".join(pezzi)


def _classe_allineamento(riga: Riga, sinistra: float, destra: float) -> str:
    """
    Solo le differenze che contano davvero. Una riga a sinistra dopo una
    giustificata e' semplicemente l'ultima riga del paragrafo, non un nuovo
    blocco: le due classi vanno tenute insieme.
    """
    a = _allineamento(riga, sinistra, destra)
    return a if a in ("center", "right") else "scorre"


def _allineamento(riga: Riga, sinistra: float, destra: float) -> str:
    larghezza = destra - sinistra
    if larghezza <= 0:
        return "left"
    x0, x1 = riga.bbox[0], riga.bbox[2]
    sx, dx = x0 - sinistra, destra - x1
    centro_riga, centro_col = (x0 + x1) / 2, (sinistra + destra) / 2

    if sx > larghezza * 0.05 and abs(centro_riga - centro_col) < larghezza * 0.055:
        return "center"
    if sx > larghezza * 0.05 and dx < larghezza * 0.03:
        return "right"
    if sx < larghezza * 0.045 and dx < larghezza * 0.045:
        return "justify"
    return "left"


_RE_PUNTO_ELENCO = re.compile(r"^\s*([•·▪◦‣o§\-–—*])\s+")
_RE_NUMERO_ELENCO = re.compile(r"^\s*((?:\d{1,3}|[a-zA-Z]|[ivxlcIVXLC]{1,6})[.)])\s+")
#: numerazione senza punto ne' parentesi: si accetta solo dentro un blocco in
#: cui piu' righe la portano e i numeri crescono
_RE_NUMERO_NUDO = re.compile(r"^\s*(\d{1,3})\s+(?=\S)")


def _interlinea_mediana(righe: list[Riga]) -> float:
    salti = [righe[i + 1].bbox[1] - righe[i].bbox[1] for i in range(len(righe) - 1)]
    salti = [s for s in salti if s > 0.5]
    return statistics.median(salti) if salti else 14.0


def costruisci_paragrafi(
    righe: list[Riga], sinistra: float, destra: float,
    corpo_base: float, famiglia_base: str,
) -> list[Elemento]:
    if not righe:
        return []

    interlinea = _interlinea_mediana(righe)
    bordo_sx = min(r.bbox[0] for r in righe)
    bordo_dx = max(r.bbox[2] for r in righe)

    blocchi: list[list[Riga]] = [[righe[0]]]
    for prec, corr in zip(righe, righe[1:]):
        salto = corr.bbox[1] - prec.bbox[1]
        # capoverso con rientro di prima riga: la riga precedente arriva al
        # margine destro e questa ricomincia piu' dentro
        rientra = (
            corr.bbox[0] - bordo_sx > Taratura.RIENTRO_MINIMO
            and prec.bbox[0] - bordo_sx <= Taratura.RIENTRO_MINIMO * 0.6
            and _allineamento(corr, bordo_sx, bordo_dx) not in ("center", "right")
        )
        salto_sx = abs(corr.bbox[0] - prec.bbox[0])
        cambia = (
            rientra
            or salto_sx > (bordo_dx - bordo_sx) * 0.25   # colonna diversa
            or salto > interlinea * Taratura.SALTO_PARAGRAFO
            or abs(corr.corpo - prec.corpo) > 1.2
            or _classe_allineamento(corr, sinistra, destra)
            != _classe_allineamento(prec, sinistra, destra)
            or bool(_RE_PUNTO_ELENCO.match(corr.testo)) != bool(_RE_PUNTO_ELENCO.match(prec.testo))
            or bool(_RE_NUMERO_ELENCO.match(corr.testo)) != bool(_RE_NUMERO_ELENCO.match(prec.testo))
        )
        (blocchi.append([corr]) if cambia else blocchi[-1].append(corr))

    fuori: list[Elemento] = []
    indice = 0
    while indice < len(blocchi):
        blocco = blocchi[indice]
        testo = blocco[0].testo

        # elenco tutto dentro un blocco solo: piu' righe che iniziano col segno
        segnate = [r for r in blocco
                   if _RE_PUNTO_ELENCO.match(r.testo) or _RE_NUMERO_ELENCO.match(r.testo)]
        nudi = [r for r in blocco if _RE_NUMERO_NUDO.match(r.testo)]
        crescenti = (
            len(nudi) >= 2
            and len(nudi) >= len(blocco) * 0.7
            and all(
                int(_RE_NUMERO_NUDO.match(b.testo).group(1))
                < int(_RE_NUMERO_NUDO.match(a.testo).group(1))
                for b, a in zip(nudi, nudi[1:])
            )
        )
        if (len(segnate) >= 2 and len(segnate) >= len(blocco) * 0.7) or crescenti:
            numerato = crescenti or bool(_RE_NUMERO_ELENCO.match((segnate or nudi)[0].testo))
            fuori.append(_elenco([[r] for r in blocco], numerato, corpo_base,
                                 famiglia_base, sinistra, destra))
            indice += 1
            continue

        # elenco spalmato su blocchi consecutivi
        if _RE_PUNTO_ELENCO.match(testo) or _RE_NUMERO_ELENCO.match(testo):
            numerato = bool(_RE_NUMERO_ELENCO.match(testo))
            voci, fine = [], indice
            while fine < len(blocchi):
                t = blocchi[fine][0].testo
                if numerato and not _RE_NUMERO_ELENCO.match(t):
                    break
                if not numerato and not _RE_PUNTO_ELENCO.match(t):
                    break
                voci.append(blocchi[fine])
                fine += 1
            if len(voci) >= 2:
                fuori.append(_elenco(voci, numerato, corpo_base, famiglia_base,
                                     sinistra, destra))
                indice = fine
                continue

        fuori.append(_paragrafo(blocco, blocchi, indice, sinistra, destra,
                                corpo_base, famiglia_base, interlinea))
        indice += 1
    return fuori


def _allineamento_blocco(blocco: list[Riga], sinistra: float, destra: float) -> str:
    """Il paragrafo prende l'allineamento della maggioranza delle sue righe,
    escludendo l'ultima (che in un testo giustificato e' sempre corta)."""
    riferimento = blocco[:-1] if len(blocco) > 2 else blocco
    voti = [_allineamento(r, sinistra, destra) for r in riferimento]
    for candidato in ("justify", "center", "right"):
        if voti.count(candidato) >= max(1, len(voti) * 0.6):
            return candidato
    return "left"


def _stile_paragrafo(
    blocco: list[Riga], successivo: Optional[list[Riga]],
    sinistra: float, destra: float, corpo_base: float, interlinea: float,
) -> list[str]:
    allinea = _allineamento_blocco(blocco, sinistra, destra)
    corpo = statistics.median([r.corpo for r in blocco])
    stile = [f"text-align:{allinea}"]

    if len(blocco) > 1:
        interno = _interlinea_mediana(blocco)
        rapporto = max(0.9, min(3.0, interno / max(corpo, 1.0)))
        stile.append(f"line-height:{rapporto:.2f}")

    rientro_sx = (min(r.bbox[0] for r in blocco[1:]) if len(blocco) > 1
                  else blocco[0].bbox[0]) - sinistra
    rientro_dx = destra - max(r.bbox[2] for r in blocco)
    if rientro_sx > Taratura.RIENTRO_MINIMO and allinea in ("left", "justify"):
        if len(blocco) == 1 and rientro_sx < 42:
            stile.append(f"text-indent:{_pt(rientro_sx)}pt")   # capoverso breve
        else:
            stile.append(f"margin-left:{_pt(rientro_sx)}pt")
    if rientro_dx > Taratura.RIENTRO_MINIMO and allinea in ("right", "justify"):
        stile.append(f"margin-right:{_pt(rientro_dx)}pt")

    # rientro della prima riga
    if len(blocco) > 1:
        prima = blocco[0].bbox[0]
        altre = min(r.bbox[0] for r in blocco[1:])
        if prima - altre > Taratura.RIENTRO_MINIMO:
            stile.append(f"text-indent:{_pt(prima - altre)}pt")

    if successivo:
        salto = successivo[0].bbox[1] - blocco[-1].bbox[1]
        extra = salto - interlinea
        if extra > corpo_base * 0.3:
            # lo stacco si limita: un vuoto enorme e' quasi sempre dovuto a
            # una tabella o a un'immagine che sta in mezzo, non al paragrafo
            stile.append(f"margin-bottom:{_pt(min(extra * 0.75, corpo_base * 2.4))}pt")
    return stile


def _paragrafo(
    blocco: list[Riga], blocchi: list[list[Riga]], indice: int,
    sinistra: float, destra: float, corpo_base: float,
    famiglia_base: str, interlinea: float,
) -> Elemento:
    successivo = blocchi[indice + 1] if indice + 1 < len(blocchi) else None
    stile = _stile_paragrafo(blocco, successivo, sinistra, destra, corpo_base, interlinea)
    corpo = statistics.median([r.corpo for r in blocco])
    if abs(corpo - corpo_base) >= 0.6:
        stile.append(f"font-size:{_pt(corpo)}pt")

    grassetto_tutto = all(
        t.grassetto for r in blocco for t in r.tratti if t.testo.strip()
    )
    allinea_blocco = _allineamento_blocco(blocco, sinistra, destra)
    testo_blocco = " ".join(r.testo for r in blocco).strip()
    titolo = (
        len(blocco) <= 2
        and allinea_blocco != "justify"
        and (grassetto_tutto or testo_blocco.isupper())
        and 3 < len(testo_blocco) < 130
        and (
            corpo >= corpo_base + 0.4          # corpo piu' grande del testo
            or (allinea_blocco == "center" and len(blocco) == 1)
        )
    )
    livello = 2 if corpo >= corpo_base + 2 else 3
    tag = f"h{livello}" if titolo else "p"

    interno = "<br>".join(
        _html_tratti(r.tratti, corpo, famiglia_base) for r in blocco
    )
    return Elemento(
        tipo="titolo" if titolo else "paragrafo",
        html=f'<{tag} style="{";".join(stile)}">{interno}</{tag}>',
        top=blocco[0].bbox[1],
        bbox=(min(r.bbox[0] for r in blocco), blocco[0].bbox[1],
              max(r.bbox[2] for r in blocco), blocco[-1].bbox[3]),
    )


def _elenco(
    voci: list[list[Riga]], numerato: bool, corpo_base: float,
    famiglia_base: str, sinistra: float, destra: float,
) -> Elemento:
    tag = "ol" if numerato else "ul"
    pezzi = []
    for blocco in voci:
        righe = list(blocco)
        primo = righe[0]
        tratti = [Tratto(**{**t.__dict__}) for t in primo.tratti]
        if tratti:
            testa = tratti[0].testo
            if _RE_SEGNO.match(testa):
                # il segno e' un tratto a se' (ricucito da _unisci_segni_elenco)
                tratti = tratti[1:]
            else:
                for schema in (_RE_NUMERO_ELENCO, _RE_PUNTO_ELENCO, _RE_NUMERO_NUDO):
                    if schema.match(testa):
                        tratti[0].testo = schema.sub("", testa, count=1)
                        break
        interno = _html_tratti(tratti, corpo_base, famiglia_base)
        for r in righe[1:]:
            interno += "<br>" + _html_tratti(r.tratti, corpo_base, famiglia_base)
        pezzi.append(f"<li>{interno}</li>")

    rientro = min(b[0].bbox[0] for b in voci) - sinistra
    stile = f'style="margin-left:{_pt(max(0, rientro))}pt"' if rientro > Taratura.RIENTRO_MINIMO else ""
    return Elemento(
        tipo="elenco",
        html=f"<{tag} {stile}>{''.join(pezzi)}</{tag}>",
        top=voci[0][0].bbox[1],
        bbox=(min(b[0].bbox[0] for b in voci), voci[0][0].bbox[1],
              max(b[-1].bbox[2] for b in voci), voci[-1][-1].bbox[3]),
    )
