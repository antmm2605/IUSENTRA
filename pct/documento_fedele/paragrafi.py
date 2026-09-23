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
from .lettura import _RE_SEGNO


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


#: Quanto due righe devono sovrapporsi in verticale perche' siano la stessa
#: riga spezzata in colonne, e non due righe una sotto l'altra.
SOVRAPPOSIZIONE_FILA = 0.6


def _file_affiancate(righe: list[Riga]) -> list[list[Riga]]:
    """Raggruppa le righe che stanno sulla stessa fascia verticale.

    La lettura spezza una riga di testo dove il bianco fra due parole e' tanto
    largo da essere una colonna: serve a tenere ferma la x di ogni pezzo. Ma
    quei pezzi sono ancora **una riga sola**, e chi li rimette in colonna uno
    sotto l'altro allunga la pagina di una riga per ogni cella — un prospetto
    di sette colonne diventa sette righe, e la pagina ne diventa due.
    """
    if not righe:
        return []
    gruppi: list[list[Riga]] = [[righe[0]]]
    for corrente in righe[1:]:
        ultima = gruppi[-1][-1]
        alto = max(ultima.bbox[1], corrente.bbox[1])
        basso = min(ultima.bbox[3], corrente.bbox[3])
        altezza = min(ultima.bbox[3] - ultima.bbox[1],
                      corrente.bbox[3] - corrente.bbox[1])
        affiancata = (
            altezza > 0
            and (basso - alto) > altezza * SOVRAPPOSIZIONE_FILA
            and corrente.bbox[0] > ultima.bbox[2] - Taratura.TOLLERANZA
        )
        (gruppi[-1].append(corrente) if affiancata else gruppi.append([corrente]))

    # una fila vale solo se ogni pezzo ci sta nello spazio che occupava
    fuori: list[list[Riga]] = []
    for gruppo in gruppi:
        if len(gruppo) > 1 and any(_testo_compresso(r) for r in gruppo):
            fuori.extend([r] for r in gruppo)
        else:
            fuori.append(gruppo)
    return fuori


#: Quanto spazio serve, come quota del corpo, per un carattere: sotto questa
#: misura il PDF non sta scrivendo, sta comprimendo. Un carattere stretto sta
#: intorno a 0,40 del corpo, uno normale a 0,50.
LARGHEZZA_MINIMA_PER_CARATTERE = 0.25


def _testo_compresso(riga: Riga) -> bool:
    """Vero se quel testo e' schiacciato piu' di quanto un carattere permetta.

    Certi PDF firmano la pagina con una sigla disegnata in un centimetro di
    riga: trentadue lettere in sette punti, un ventesimo di quello che
    servirebbe. Non e' testo da leggere, e chi lo rimette in una colonna larga
    sette punti lo manda a capo otto volte — una pagina ne diventa tre.
    """
    caratteri = len(riga.testo.strip())
    if caratteri < 4 or riga.corpo <= 0:
        return False
    larghezza = riga.bbox[2] - riga.bbox[0]
    return larghezza / caratteri < riga.corpo * LARGHEZZA_MINIMA_PER_CARATTERE


def _fila_affiancata(
    gruppo: list[Riga], sinistra: float, destra: float,
    successivo: Optional[Riga], interlinea: float, corpo_base: float,
    famiglia_base: str,
) -> Elemento:
    """Le celle di una stessa riga, rese come una tabella di una riga sola.

    Senza filetti e senza margini interni: serve solo a tenere insieme i pezzi
    e a dare a ognuno la sua colonna. L'altezza della riga e' il passo fino
    alla riga dopo, come per un paragrafo di una riga sola.
    """
    colonna = max(1.0, destra - sinistra)
    corpo = statistics.median([r.corpo for r in gruppo])

    passo = interlinea
    if successivo is not None:
        salto = successivo.bbox[1] - gruppo[0].bbox[1]
        salto -= Taratura.DISCESA_CARATTERE * (successivo.corpo - corpo)
        if salto > 0.5:
            passo = min(salto, _stacco_massimo(interlinea, corpo_base))
    passo = max(passo, corpo * 0.55)

    # ogni cella va dal suo inizio all'inizio di quella dopo: il testo ricade
    # dove stava, e l'ultima arriva al margine perche' un numero allineato a
    # destra ci si appoggia
    bordi = [max(sinistra, gruppo[0].bbox[0])]
    for prossima in gruppo[1:]:
        bordi.append(max(bordi[-1], prossima.bbox[0]))
    bordi.append(max(bordi[-1], destra))

    pezzi = ['<table class="iu-doc-tabella" data-bordi="0" data-fila="1"'
             ' style="width:100%">']
    pezzi.append("<tbody><tr>")

    vuoto = bordi[0] - sinistra
    if vuoto > Taratura.TOLLERANZA:
        pezzi.append(f'<td style="width:{vuoto / colonna * 100:.1f}%"></td>')

    for posto, riga in enumerate(gruppo):
        larga = bordi[posto + 1] - bordi[posto]
        stile = [f"width:{larga / colonna * 100:.1f}%",
                 f"line-height:{_pt(passo)}pt"]
        allinea = _allineamento(riga, bordi[posto], bordi[posto + 1])
        if allinea in ("center", "right"):
            stile.append(f"text-align:{allinea}")
        pezzi.append(f'<td style="{";".join(stile)}">'
                     f'{_html_tratti(riga.tratti, corpo_base, famiglia_base)}</td>')

    pezzi.append("</tr></tbody></table>")
    return Elemento(
        tipo="tabella",
        html="".join(pezzi),
        top=gruppo[0].bbox[1],
        bbox=(bordi[0], gruppo[0].bbox[1],
              max(r.bbox[2] for r in gruppo), max(r.bbox[3] for r in gruppo)),
    )


def _con_file_affiancate(
    gruppi: list[list[Riga]], sinistra: float, destra: float,
    corpo_base: float, famiglia_base: str, seguito: Optional[Riga],
) -> list[Elemento]:
    """Il documento ha righe spezzate in colonne: si alternano i due modi.

    I tratti di testo che scendono uno sotto l'altro restano paragrafi — e
    passano dalla stessa costruzione di sempre, che sa di capoversi, elenchi e
    rientri. Le righe affiancate diventano una fila. Ognuno dei due sa quale
    riga viene dopo, cosi' il passo verticale non si perde al passaggio.
    """
    interlinea = _interlinea_mediana([r for g in gruppi for r in g])
    fuori: list[Elemento] = []
    segmento: list[Riga] = []

    def _dopo(posto: int) -> Optional[Riga]:
        for gruppo in gruppi[posto + 1:]:
            return gruppo[0]
        return seguito

    for posto, gruppo in enumerate(gruppi):
        if len(gruppo) == 1:
            segmento.append(gruppo[0])
            continue
        if segmento:
            fuori += costruisci_paragrafi(segmento, sinistra, destra, corpo_base,
                                          famiglia_base, gruppo[0], interlinea)
            segmento = []
        fuori.append(_fila_affiancata(gruppo, sinistra, destra, _dopo(posto),
                                      interlinea, corpo_base, famiglia_base))
    if segmento:
        fuori += costruisci_paragrafi(segmento, sinistra, destra, corpo_base,
                                      famiglia_base, seguito, interlinea)
    fuori.sort(key=lambda e: e.top)
    return fuori


def costruisci_paragrafi(
    righe: list[Riga], sinistra: float, destra: float,
    corpo_base: float, famiglia_base: str,
    seguito: Optional[Riga] = None,
    interlinea_pagina: Optional[float] = None,
) -> list[Elemento]:
    """`seguito` e' la prima riga che viene dopo queste, quando non ne fa parte.

    Serve alla testata: le sue righe si costruiscono a parte, ma l'ultima deve
    sapere quanto dista dalla prima riga del corpo, altrimenti il corpo parte
    dove capita e tutta la pagina scivola con lui.
    """
    if not righe:
        return []

    gruppi = _file_affiancate(righe)
    if any(len(g) > 1 for g in gruppi):
        return _con_file_affiancate(gruppi, sinistra, destra, corpo_base,
                                    famiglia_base, seguito)

    # L'interlinea si misura sulla pagina, non sul pezzo: quando una riga
    # spezzata in colonne taglia il testo in segmenti corti, la mediana di
    # tre righe non e' l'interlinea dell'atto — e un paragrafo di una riga
    # sola, che prende il passo da li', casca dodici punti piu' in basso.
    interlinea = interlinea_pagina or _interlinea_mediana(righe)
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
                                corpo_base, famiglia_base, interlinea, seguito))
        indice += 1
    return fuori


def _allineamento_blocco(blocco: list[Riga], sinistra: float, destra: float) -> str:
    """Il paragrafo prende l'allineamento della maggioranza delle sue righe,
    escludendo l'ultima (che in un testo giustificato e' sempre corta)."""
    # l'ultima riga si esclude sempre, anche quando le righe sono due: in un
    # capoverso giustificato e' sempre corta, e su due righe il suo voto
    # pareggiava quello della riga piena e il capoverso finiva a sinistra
    riferimento = blocco[:-1] if len(blocco) > 1 else blocco
    voti = [_allineamento(r, sinistra, destra) for r in riferimento]
    for candidato in ("justify", "center", "right"):
        if voti.count(candidato) >= max(1, len(voti) * 0.6):
            return candidato
    return "left"


def _stacco_massimo(interlinea: float, corpo_base: float) -> float:
    """Oltre questo vuoto fra due capoversi c'e' qualcosa in mezzo, non uno stacco.

    Il limite si misura sul passo della pagina, non su quello del blocco. Una
    carta intestata ha righe fitte — nove punti e mezzo — e prendendo quelle
    come scala il vuoto fra la testata e il corpo, che e' cinquantacinque
    punti, veniva tagliato a trentatre: il corpo saliva di due centimetri e
    l'ultima riga della pagina scivolava a quella dopo.
    """
    scala = max(interlinea, corpo_base * 2.0)
    return scala * Taratura.STACCO_MASSIMO


def _centrato_su(blocco: list[Riga], sinistra: float, destra: float):
    """Il punto su cui le righe di questo blocco sono centrate, se lo sono.

    Una carta intestata e' centrata, ma non sulla colonna del testo: sta in una
    sua colonna piu' stretta, piu' a sinistra. Riga per riga non si vede — ogni
    riga sembra solo rientrata di un po' — e il blocco finiva allineato a
    sinistra con un rientro solo, che e' giusto per una riga e sbagliato per le
    altre.

    Il segno che le righe sono centrate fra loro e' che i loro centri stanno
    fermi mentre le lunghezze cambiano: in un blocco allineato a sinistra il
    centro si sposta della meta' di quanto si accorcia la riga.
    """
    if len(blocco) < 2:
        return None
    centri = [(r.bbox[0] + r.bbox[2]) / 2 for r in blocco]
    larghezze = [r.bbox[2] - r.bbox[0] for r in blocco]
    scarto_centri = max(centri) - min(centri)
    scarto_larghezze = max(larghezze) - min(larghezze)
    if scarto_larghezze <= Taratura.RIENTRO_MINIMO * 2:
        return None                      # righe tutte lunghe uguale: non si sa
    if scarto_centri > Taratura.CENTRI_FERMI:
        return None
    if scarto_centri > scarto_larghezze * 0.25:
        return None                      # i centri seguono le lunghezze: e' a sinistra
    centro = statistics.median(centri)
    # dev'essere un centro suo, non quello della colonna: altrimenti basta
    # dire "centrato" e non serve stringere la colonna
    if abs(centro - (sinistra + destra) / 2) < Taratura.RIENTRO_MINIMO:
        return None
    return centro


def _stile_paragrafo(
    blocco: list[Riga], successivo: Optional[list[Riga]],
    sinistra: float, destra: float, corpo_base: float, interlinea: float,
    cappa: Optional[float] = None,
) -> list[str]:
    allinea = _allineamento_blocco(blocco, sinistra, destra)
    corpo = statistics.median([r.corpo for r in blocco])
    centro_proprio = _centrato_su(blocco, sinistra, destra) if allinea == "left" else None
    if centro_proprio is not None:
        allinea = "center"
    stile = [f"text-align:{allinea}"]

    # Quanto scende ogni riga, in punti e non in proporzione al corpo: un
    # titolo di diciotto punti in un atto con righe a ventiquattro scende di
    # ventiquattro, non di trentasei. Chi riscrive il PDF fa un passo di
    # interlinea per ogni riga del paragrafo e uno stacco fra un paragrafo e
    # l'altro, quindi qui si dichiarano tutti e due.
    # Il salto si misura sul bordo alto delle righe, ma chi riscrive il PDF
    # lavora sulla linea di base: se il paragrafo dopo ha un corpo diverso, il
    # bordo alto si sposta anche senza che la riga si muova. Si toglie quella
    # differenza, altrimenti ogni cambio di corpo lascia un punto di scarto
    # che si somma riga dopo riga.
    salto_dopo = 0.0
    if successivo:
        salto_dopo = successivo[0].bbox[1] - blocco[-1].bbox[1]
        corpo_dopo = statistics.median([r.corpo for r in successivo])
        salto_dopo -= Taratura.DISCESA_CARATTERE * (corpo_dopo - corpo)
    if len(blocco) > 1:
        passo = _interlinea_mediana(blocco)
    elif salto_dopo > 0.5:
        # riga sola: il passo e' esattamente la distanza dalla riga dopo
        passo = min(salto_dopo, cappa or _stacco_massimo(interlinea, corpo_base))
    else:
        passo = interlinea
    # il pavimento serve solo contro una misura degenere: una carta intestata
    # sta stretta, nove punti e mezzo con un corpo da dodici, e alzarla al
    # corpo le fa guadagnare un punto per riga che poi la pagina si porta
    # dietro fino in fondo
    stile.append(f"line-height:{_pt(max(passo, corpo * 0.55))}pt")

    # Una riga che nell'originale arriva al margine destro era giustificata,
    # anche se e' l'ultima del capoverso — o l'unica. Senza dirlo resta corta,
    # le parole si stringono a sinistra e l'ultima finisce anche a due
    # centimetri da dove stava.
    if allinea == "justify" and destra - blocco[-1].bbox[2] <= Taratura.TOLLERANZA:
        stile.append("text-align-last:justify")

    if centro_proprio is not None:
        # si stringe la colonna a destra finche' il suo centro non e' quello
        # delle righe: cosi' ogni riga, lunga o corta, casca dov'era
        stretta = destra - (2 * centro_proprio - sinistra)
        if stretta > Taratura.RIENTRO_MINIMO:
            stile.append(f"margin-right:{_pt(stretta)}pt")
        elif stretta < -Taratura.RIENTRO_MINIMO:
            stile.append(f"margin-left:{_pt(-stretta)}pt")
        if successivo:
            extra = min(salto_dopo, cappa or _stacco_massimo(interlinea, corpo_base)) - passo
            if extra > 0.5:
                stile.append(f"margin-bottom:{_pt(extra)}pt")
        return stile

    rientro_sx = (min(r.bbox[0] for r in blocco[1:]) if len(blocco) > 1
                  else blocco[0].bbox[0]) - sinistra
    rientro_dx = destra - max(r.bbox[2] for r in blocco)
    if rientro_sx > Taratura.RIENTRO_DICHIARATO and allinea in ("left", "justify"):
        if len(blocco) == 1 and rientro_sx < 42:
            stile.append(f"text-indent:{_pt(rientro_sx)}pt")   # capoverso breve
        else:
            stile.append(f"margin-left:{_pt(rientro_sx)}pt")
    if rientro_dx > Taratura.RIENTRO_DICHIARATO and allinea in ("right", "justify"):
        stile.append(f"margin-right:{_pt(rientro_dx)}pt")

    # rientro della prima riga
    if len(blocco) > 1:
        prima = blocco[0].bbox[0]
        altre = min(r.bbox[0] for r in blocco[1:])
        if prima - altre > Taratura.RIENTRO_MINIMO:
            stile.append(f"text-indent:{_pt(prima - altre)}pt")

    if successivo:
        # un vuoto enorme e' quasi sempre una tabella o un'immagine in mezzo,
        # non lo stacco del paragrafo: oltre quel limite non si segue
        extra = min(salto_dopo, cappa or _stacco_massimo(interlinea, corpo_base)) - passo
        if extra > 0.5:
            stile.append(f"margin-bottom:{_pt(extra)}pt")
    return stile


def _paragrafo(
    blocco: list[Riga], blocchi: list[list[Riga]], indice: int,
    sinistra: float, destra: float, corpo_base: float,
    famiglia_base: str, interlinea: float, seguito: Optional[Riga] = None,
) -> Elemento:
    if indice + 1 < len(blocchi):
        successivo = blocchi[indice + 1]
        cappa = None
    else:
        successivo = [seguito] if seguito is not None else None
        # fra la testata e il corpo, o fra il corpo e il piede di pagina, il
        # vuoto e' grande per costruzione: mezza pagina fra l'ultima riga e il
        # numero in fondo. Il limite che protegge dai vuoti fasulli dentro il
        # testo, li', taglierebbe quello vero
        cappa = _stacco_massimo(interlinea, corpo_base) * 2.0 if successivo else None
    stile = _stile_paragrafo(blocco, successivo, sinistra, destra,
                             corpo_base, interlinea, cappa)
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
    # Quanto era larga la riga nell'originale. Chi riesporta ha solo i
    # caratteri base del PDF: quando quello dichiarato non c'e' — un
    # calligrafico, un titolo condensato — ripiega su Times, e una riga da
    # sedici punti in Times e' larga il doppio di com'era. Sapendo la misura
    # vera si sceglie il corpo che la riproduce.
    misura = ""
    if len(blocco) == 1 and allinea_blocco != "justify":
        larga = blocco[0].bbox[2] - blocco[0].bbox[0]
        if larga > 1:
            misura = f' data-larghezza="{_pt(larga)}"'

    return Elemento(
        tipo="titolo" if titolo else "paragrafo",
        html=f'<{tag} style="{";".join(stile)}"{misura}>{interno}</{tag}>',
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
