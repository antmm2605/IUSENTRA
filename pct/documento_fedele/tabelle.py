"""Tabelle del PDF, anche senza filetti, con celle unite e sfondi.

Una tabella riconosciuta come tale e' modificabile nell'editor; letta come
testo continuo diventa un blocco di righe che l'avvocato deve riscrivere."""

from __future__ import annotations

import statistics
from typing import Optional

from .geometria import Riquadro
from .modello import Elemento, Riga, Tratto
from .paragrafi import _allineamento, _html_tratti
from .sorgente import PaginaSorgente
from .taratura import Taratura, _colore_da_float, _pt

# ===========================================================================
# 3. Tabelle
# ===========================================================================

def _sfondo_cella(pagina: PaginaSorgente, riquadro: Riquadro) -> Optional[str]:
    """Il colore dietro una cella, se c'e' e non e' il bianco della pagina.

    Vale solo un rettangolo che copre quasi tutta la cella: un riquadro che la
    sfiora e' un'altra cosa — il bordo di quella accanto, un filetto spesso.
    """
    for rettangolo in pagina.rettangoli:
        if not rettangolo.get("fill"):
            continue
        r = Riquadro(rettangolo["x0"], rettangolo["top"],
                     rettangolo["x1"], rettangolo["bottom"])
        if not r.intersects(riquadro):
            continue
        if (r & riquadro).get_area() < riquadro.get_area() * 0.8:
            continue
        colore = _colore_da_float(rettangolo.get("non_stroking_color"))
        if colore and colore.lower() not in ("#ffffff", "#fefefe"):
            return colore
    return None


def estrai_tabelle(
    pagina: PaginaSorgente, righe: list[Riga],
    sinistra: Optional[float] = None, destra: Optional[float] = None,
) -> list[Elemento]:
    """Tabelle rigate e non, con celle unite, intestazioni e sfondi."""
    trovate = pagina.tabelle("lines_strict")
    dedotte = False
    if not trovate:
        # una tabella senza filetti resta una tabella: si guarda
        # l'incolonnamento del testo
        trovate = pagina.tabelle("text")
        dedotte = True
    if not trovate:
        return []

    fuori: list[Elemento] = []
    for tabella in trovate:
        if dedotte and not _tabella_plausibile(pagina, tabella, righe):
            continue
        riquadro = Riquadro(tabella.bbox)
        celle = [c for c in (tabella.cells or []) if c]
        if len(celle) < 4:
            continue

        xs = _accorpa(sorted({round(c[0], 1) for c in celle} | {round(c[2], 1) for c in celle}))
        ys = _accorpa(sorted({round(c[1], 1) for c in celle} | {round(c[3], 1) for c in celle}))
        if len(xs) < 2 or len(ys) < 2:
            continue
        n_col, n_rig = len(xs) - 1, len(ys) - 1
        griglia: list[list[Optional[dict]]] = [[None] * n_col for _ in range(n_rig)]

        for (x0, y0, x1, y1) in celle:
            c = _banda(xs, x0 + 0.5)
            r = _banda(ys, y0 + 0.5)
            if c is None or r is None or griglia[r][c] is not None:
                continue
            colspan = max(1, sum(1 for k in range(c, n_col) if xs[k + 1] <= x1 + Taratura.TOLLERANZA))
            rowspan = max(1, sum(1 for k in range(r, n_rig) if ys[k + 1] <= y1 + Taratura.TOLLERANZA))
            cella = Riquadro(x0, y0, x1, y1)
            griglia[r][c] = {
                "rect": cella,
                "colspan": colspan,
                "rowspan": rowspan,
                "sfondo": _sfondo_cella(pagina, cella),
                "righe": [g for g in righe if Riquadro(g.bbox).intersects(cella)
                          and (Riquadro(g.bbox) & cella).get_area()
                          > Riquadro(g.bbox).get_area() * 0.5],
            }
            for rr in range(r, min(n_rig, r + rowspan)):
                for cc in range(c, min(n_col, c + colspan)):
                    if (rr, cc) != (r, c) and griglia[rr][cc] is None:
                        griglia[rr][cc] = {"salta": True}

        fuori.append(Elemento(
            tipo="tabella",
            html=_html_tabella(griglia, xs, tabella, riquadro, sinistra, destra),
            top=riquadro.y0,
            bbox=tuple(riquadro),
        ))
    return fuori


#: Quota minima delle righe coperte dalla tabella che devono stare in una sua
#: cella perche' la griglia descriva davvero quel testo.
QUOTA_RIGHE_RACCOLTE = 0.70

#: E comunque almeno due righe: una sola non fa una tabella.
RIGHE_RACCOLTE_MINIME = 2

#: Quanta parte di una riga deve stare dentro una cella perche' si consideri
#: raccolta da quella cella.
DENTRO_LA_CELLA = 0.50

#: In quante righe, almeno, deve essere scritta la seconda colonna piu' piena
#: perche' la griglia sia una tabella e non un testo incolonnato.
QUOTA_SECONDA_COLONNA = 0.30

#: E comunque in almeno due righe.
RIGHE_SECONDA_COLONNA_MINIME = 2

#: Quante parole spezzate a meta' bastano a dire che quelle colonne non
#: esistono: due, perche' una potrebbe essere una sillabazione.
PAROLE_SPEZZATE_AMMESSE = 1


def _tabella_plausibile(pagina, tabella, righe: list[Riga]) -> bool:
    """Vero se una tabella dedotta dall'incolonnamento regge davvero.

    Senza filetti la ricerca «a testo» trova una griglia dappertutto: su un
    paragrafo giustificato lungo ne inventava una di seicento celle, e siccome
    le righe finite in tabella escono dai paragrafi, il testo dell'atto
    spariva — l'avvocato apriva l'editor su una griglia vuota.

    Quello che distingue i due casi e' se la griglia **raccoglie** il testo che
    copre: in una tabella ogni riga sta dentro una cella, in un paragrafo le
    righe sono piu' larghe di qualsiasi cella, perche' quelle colonne non
    esistono — le ha inventate la ricerca allineando parole di righe diverse.

    Basta che la meta' della riga stia in una cella sola: la ricerca «a testo»
    spezza anche dentro una cella vera (fra «EUR» e la cifra, per dire), e
    pretendere che la riga ci stia tutta boccerebbe tabelle buone.

    Non si applica alle tabelle con i filetti disegnati: li' il bordo e' una
    dichiarazione dell'autore, e un modulo da compilare e' fatto apposta di
    celle vuote.
    """
    celle = [Riquadro(c[0], c[1], c[2], c[3]) for c in (tabella.cells or []) if c]
    if len(celle) < 4:
        return False

    coperto = Riquadro(tabella.bbox)
    dentro = [
        r for r in righe
        if Riquadro(r.bbox).intersects(coperto)
        and (Riquadro(r.bbox) & coperto).get_area() > Riquadro(r.bbox).get_area() * 0.5
    ]
    if len(dentro) < RIGHE_RACCOLTE_MINIME:
        return False

    raccolte = 0
    for riga in dentro:
        riquadro = Riquadro(riga.bbox)
        if any(riquadro.sovrapposizione(cella) > DENTRO_LA_CELLA for cella in celle):
            raccolte += 1

    if raccolte < RIGHE_RACCOLTE_MINIME or raccolte < len(dentro) * QUOTA_RIGHE_RACCOLTE:
        return False
    if _spezza_le_parole(pagina, tabella):
        return False
    return _almeno_due_colonne_scritte(tabella)


def _spezza_le_parole(pagina, tabella) -> bool:
    """Vero se il bordo fra due colonne passa in mezzo a una parola.

    E' il segno che quelle colonne non ci sono. Una tabella vera ha le colonne
    separate da uno spazio bianco; la ricerca «a testo» invece allinea per caso
    parole di righe diverse e taglia dove capita — «Avvocato Roberto
    Montagnes | e», «Ufficio R | ecupero Crediti». Guardando le lettere una per
    una si vede subito: fra le due che stanno ai lati del bordo non c'e'
    nemmeno lo spazio di uno spazio.
    """
    celle = [c for c in (tabella.cells or []) if c]
    if not celle:
        return False
    bordi = sorted({round(float(c[0]), 1) for c in celle}
                   | {round(float(c[2]), 1) for c in celle})
    riquadro = Riquadro(tabella.bbox)
    interni = [b for b in bordi
               if riquadro.x0 + Taratura.TOLLERANZA < b < riquadro.x1 - Taratura.TOLLERANZA]
    if not interni:
        return False

    try:
        caratteri = [c for c in pagina.caratteri
                     if riquadro.y0 <= float(c["top"]) <= riquadro.y1]
    except Exception:
        return False
    if not caratteri:
        return False

    per_riga: dict[int, list[dict]] = {}
    for carattere in caratteri:
        per_riga.setdefault(int(round(float(carattere["top"]))), []).append(carattere)

    spezzate = 0
    for gruppo in per_riga.values():
        gruppo.sort(key=lambda c: float(c["x0"]))
        for prima, dopo in zip(gruppo, gruppo[1:]):
            if str(prima.get("text") or "").isspace() or str(dopo.get("text") or "").isspace():
                continue
            fine, inizio = float(prima["x1"]), float(dopo["x0"])
            corpo = float(dopo.get("size") or prima.get("size") or 11.0)
            if inizio - fine > corpo * 0.18:
                continue   # qui uno spazio c'e': il bordo puo' passare
            if any(fine - 0.2 <= b <= inizio + 0.2 for b in interni):
                spezzate += 1
                if spezzate > PAROLE_SPEZZATE_AMMESSE:
                    return True
    return False


def _almeno_due_colonne_scritte(tabella) -> bool:
    """Vero se la griglia ha davvero due colonne, non una sola e il vuoto.

    Una pagina di solo testo puo' superare la prova delle righe raccolte: se la
    griglia inventata e' larga quanto la pagina, ogni riga ci sta dentro. Ma in
    quella griglia una colonna sola porta il testo e le altre restano vuote —
    era il caso della carta intestata seguita dall'atto, cinquantanove righe e
    due colonne vuote — mentre in una tabella vera almeno due colonne sono
    scritte. Non si applica alle tabelle con i filetti: quelle le dichiara
    l'autore, e un modulo da compilare e' fatto apposta di celle vuote.
    """
    try:
        dati = tabella.extract() or []
    except Exception:
        return True   # non si riesce a leggerla: si lascia decidere al resto
    dati = [fila for fila in dati if fila]
    if len(dati) < RIGHE_RACCOLTE_MINIME:
        return False
    larghezza = max(len(fila) for fila in dati)
    if larghezza < 2:
        return False
    scritte = [
        sum(1 for fila in dati
            if colonna < len(fila) and (fila[colonna] or "").strip())
        for colonna in range(larghezza)
    ]
    scritte.sort(reverse=True)
    soglia = max(RIGHE_SECONDA_COLONNA_MINIME, len(dati) * QUOTA_SECONDA_COLONNA)
    return scritte[1] >= soglia


def _e_intestazione(griglia: list[list[Optional[dict]]]) -> bool:
    """Vero se la prima riga della griglia si comporta da intestazione."""
    prima = [c for c in griglia[0] if c and not c.get("salta")]
    if not prima:
        return False

    if any(c.get("sfondo") for c in prima):
        return True

    def _tutta_grassetto(fila) -> bool:
        tratti = [t for c in fila if c and not c.get("salta")
                  for r in c.get("righe", []) for t in r.tratti if t.testo.strip()]
        return bool(tratti) and all(t.grassetto for t in tratti)

    if not _tutta_grassetto(griglia[0]):
        return False
    return not any(_tutta_grassetto(fila) for fila in griglia[1:])


def _accorpa(valori: list[float], tol: float = Taratura.TOLLERANZA) -> list[float]:
    if not valori:
        return []
    fuso = [valori[0]]
    for v in valori[1:]:
        if v - fuso[-1] <= tol:
            fuso[-1] = (fuso[-1] + v) / 2
        else:
            fuso.append(v)
    return fuso


def _banda(valori: list[float], v: float) -> Optional[int]:
    if v < valori[0] - Taratura.TOLLERANZA or v > valori[-1] + Taratura.TOLLERANZA:
        return None
    for k in range(len(valori) - 1):
        if v < valori[k + 1] - Taratura.TOLLERANZA:
            return k
    return len(valori) - 2


def _html_tabella(griglia, xs: list[float], tabella, riquadro: Riquadro,
                  sinistra: Optional[float] = None,
                  destra: Optional[float] = None) -> str:
    totale = max(1.0, xs[-1] - xs[0])

    # larghezza e posizione rispetto alla colonna di testo: una tabella
    # stretta e centrata deve restare stretta e centrata
    stile_tabella = []
    if sinistra is not None and destra is not None and destra > sinistra:
        colonna = destra - sinistra
        quota = max(10.0, min(100.0, (riquadro.width / colonna) * 100))
        stile_tabella.append(f"width:{quota:.1f}%")
        scarto_sx = riquadro.x0 - sinistra
        scarto_dx = destra - riquadro.x1
        if quota < 98:
            if abs(scarto_sx - scarto_dx) < colonna * 0.06:
                stile_tabella.append("margin-left:auto;margin-right:auto")
            elif scarto_sx > Taratura.RIENTRO_MINIMO:
                stile_tabella.append(f"margin-left:{_pt(scarto_sx)}pt")
    # PyMuPDF dichiarava da solo quale fosse la riga di intestazione;
    # pdfplumber consegna solo la griglia. La regola che la ritrova e' quella
    # che usano gli atti: la prima riga e' intestazione quando ha uno sfondo
    # suo, oppure quando e' tutta in grassetto e le altre no.
    intestazione = set()
    if griglia and _e_intestazione(griglia):
        intestazione = {0}

    attributo = f' style="{";".join(stile_tabella)}"' if stile_tabella else ""
    fuori = [f'<table class="iu-doc-tabella"{attributo}><tbody>']
    for indice_riga, fila in enumerate(griglia):
        fuori.append("<tr>")
        for cella in fila:
            if not cella or cella.get("salta"):
                continue
            tag = "th" if indice_riga in intestazione else "td"
            attributi = ""
            if cella["colspan"] > 1:
                attributi += f' colspan="{cella["colspan"]}"'
            if cella["rowspan"] > 1:
                attributi += f' rowspan="{cella["rowspan"]}"'

            righe_cella = cella["righe"]
            corpo = statistics.median([r.corpo for r in righe_cella]) if righe_cella else 10.0
            larghezza = (cella["rect"].width / totale) * 100
            stile = [f"width:{larghezza:.1f}%"]
            if cella["sfondo"]:
                stile.append(f"background-color:{cella['sfondo']}")
            if righe_cella:
                allinea = _allineamento(
                    righe_cella[0], cella["rect"].x0 + 2, cella["rect"].x1 - 2
                )
                if allinea != "left":
                    stile.append(f"text-align:{allinea}")

            # lo sfondo e' gia' sulla cella: toglierlo dai tratti evita di
            # ridipingere il colore dietro ogni parola
            pulite = []
            for r in righe_cella:
                tratti = []
                for t in r.tratti:
                    if cella["sfondo"] and t.evidenziato == cella["sfondo"]:
                        t = Tratto(**{**t.__dict__, "evidenziato": None})
                    tratti.append(t)
                pulite.append(Riga(tratti=tratti, bbox=r.bbox, origine_y=r.origine_y))

            contenuto = "<br>".join(
                _html_tratti(r.tratti, corpo, "") for r in pulite
            ) or "&nbsp;"
            fuori.append(f'<{tag}{attributi} style="{";".join(stile)}">{contenuto}</{tag}>')
        fuori.append("</tr>")
    fuori.append("</tbody></table>")
    return "".join(fuori)
