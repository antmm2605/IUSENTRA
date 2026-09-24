"""Formato del testo riconosciuto: com'era sul foglio, non come capita.

Un atto non e' testo semplice. Chi lo legge riconosce l'intestazione dal corpo
perche' e' piu' grande, la rubrica perche' e' in grassetto, la formula finale
perche' e' centrata, le conclusioni perche' sono rientrate. Restituire tutto
come capoversi identici significa consegnare all'avvocato un testo che deve
riformattare a mano prima di poterlo usare.

Il formato qui non viene indovinato: si misura su quello che la pagina mostra.

- **Dimensione**: altezza della riga rispetto all'altezza mediana della pagina.
  Una riga alta il 45% in piu' del corpo e' un titolo, non una frase.
- **Grassetto**: densita' d'inchiostro della parola rispetto alla mediana delle
  parole della stessa classe di dimensione. Il grassetto e' letteralmente piu'
  inchiostro sulla stessa area; e' una misura, non una congettura.
- **Allineamento**: posizione della riga rispetto ai margini del testo della
  pagina. Centrato e a destra si vedono dai margini, non dal contenuto.
- **Giustificato**: un capoverso le cui righe, tranne l'ultima, toccano
  entrambi i margini della colonna. E' la forma abituale del corpo di un atto.
- **Corsivo**: si dichiara solo quando il documento lo dice (PDF con carattere
  dichiarato). Dall'immagine non e' misurabile in modo affidabile e non viene
  inventato: meglio un corsivo mancante che un corsivo falso in un atto.

Quando il documento porta gia' il proprio formato — un PDF nativo dichiara
carattere, corpo e stile di ogni parola — quei valori prevalgono sulla misura:
il dato dichiarato e' sempre migliore di quello stimato. Solo da li' arrivano
anche il **carattere** e il **corpo in punti**: da una scansione non si leggono
con sicurezza, e un Garamond 13 inventato in un atto e' peggio del carattere
del documento.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .page_layout import Blocco

# Una riga piu' alta del corpo di questa proporzione e' un titolo del livello
# indicato. Le soglie sono quelle gia' usate dall'editor per i PDF nativi
# (pct/editor.py), cosi' lo stesso documento si formatta allo stesso modo
# qualunque strada abbia seguito.
SOGLIE_TITOLO: tuple[tuple[float, int], ...] = ((1.45, 1), (1.25, 2), (1.10, 3))

# Una riga in grassetto, corta e isolata e' una rubrica: titolo di quarto
# livello, come fa l'editor con i PDF nativi.
LUNGHEZZA_MASSIMA_RUBRICA = 120

# Sopra questa proporzione rispetto alla densita' mediana la parola e' scritta
# con un tratto piu' spesso: e' grassetto. Sotto, la differenza rientra nella
# variabilita' della scansione.
SOGLIA_GRASSETTO = 1.22

# Margine di tolleranza sui bordi del testo, in frazione della larghezza della
# colonna: sotto questa soglia la riga e' considerata a filo del margine.
TOLLERANZA_MARGINE = 0.06

# Due margini liberi sono un testo centrato solo se si somigliano: oltre questo
# scarto relativo la riga e' semplicemente rientrata.
SCARTO_CENTRATURA = 0.34

ALLINEAMENTO_SINISTRA = "sinistra"
ALLINEAMENTO_CENTRO = "centro"
ALLINEAMENTO_DESTRA = "destra"
ALLINEAMENTO_GIUSTIFICATO = "giustificato"
ALLINEAMENTI = (ALLINEAMENTO_SINISTRA, ALLINEAMENTO_CENTRO, ALLINEAMENTO_DESTRA, ALLINEAMENTO_GIUSTIFICATO)

# Un capoverso e' giustificato quando le sue righe, tranne l'ultima, arrivano
# a filo di entrambi i margini: sotto questa quota di righe piene e' un testo
# a sinistra con righe lunghe.
QUOTA_RIGHE_PIENE = 0.8


@dataclass(frozen=True)
class Misure:
    """Riferimenti della pagina su cui si misura il formato di ogni blocco."""

    altezza_corpo: float
    colonna_sinistra: float
    colonna_destra: float
    densita_corpo: float

    @property
    def larghezza_colonna(self) -> float:
        return max(1.0, self.colonna_destra - self.colonna_sinistra)


@dataclass(frozen=True)
class Formato:
    """Come il blocco era scritto sul foglio."""

    livello: int = 0
    grassetto: bool = False
    corsivo: bool = False
    allineamento: str = ALLINEAMENTO_SINISTRA
    scala: float = 1.0
    #: Colore del testo, `#rrggbb`. Vuoto quando non e' un colore: il nero di
    #: un atto non si dichiara, si lascia al documento.
    colore: str = ""
    #: Carattere, gia' ricondotto a una famiglia che l'editor offre. Vuoto
    #: quando il documento non lo dichiara: si usa quello del documento.
    famiglia: str = ""
    #: Corpo in punti tipografici, come lo dichiara il documento. Zero quando
    #: non e' dichiarato.
    corpo: float = 0.0
    #: Sottolineato e barrato: nel PDF sono linee disegnate sopra il testo, e
    #: si dichiarano solo quando sono state misurate.
    sottolineato: bool = False
    barrato: bool = False

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "livello": int(self.livello),
            "grassetto": bool(self.grassetto),
            "corsivo": bool(self.corsivo),
            "allineamento": self.allineamento,
            "scala": round(float(self.scala), 3),
            "colore": self.colore or "",
            "famiglia": self.famiglia or "",
            "corpo": float(self.corpo or 0.0),
            "sottolineato": bool(self.sottolineato),
            "barrato": bool(self.barrato),
        }


def _numero(valore: Any, predefinito: float = 0.0) -> float:
    try:
        return float(valore)
    except (TypeError, ValueError):
        return predefinito


def _mediana(valori: Iterable[float], predefinito: float) -> float:
    elenco = [valore for valore in valori if valore > 0]
    return statistics.median(elenco) if elenco else predefinito


def _percentile(valori: Sequence[float], quota: float, predefinito: float) -> float:
    if not valori:
        return predefinito
    ordinati = sorted(valori)
    indice = min(len(ordinati) - 1, max(0, round(quota * (len(ordinati) - 1))))
    return ordinati[indice]


def misure_pagina(parole: Sequence[dict[str, Any]]) -> Misure:
    """Corpo del testo e margini della colonna, da cui si misura tutto il resto.

    I margini non sono il minimo e il massimo assoluti: un numero di pagina o
    un timbro a bordo foglio sposterebbero la colonna e farebbero sembrare
    rientrato tutto il testo. Si usano i percentili.
    """
    altezze = [_numero(parola.get("height")) for parola in parole]
    sinistre = [_numero(parola.get("left")) for parola in parole]
    destre = [_numero(parola.get("left")) + _numero(parola.get("width")) for parola in parole]
    densita = [_numero(parola.get("densita")) for parola in parole]
    return Misure(
        altezza_corpo=_mediana(altezze, 1.0),
        colonna_sinistra=_percentile([valore for valore in sinistre if valore >= 0], 0.08, 0.0),
        colonna_destra=_percentile(destre, 0.92, 1.0),
        densita_corpo=_mediana(densita, 0.0),
    )


def _parole_del_blocco(blocco: Blocco, parole: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    sinistra, alto, destra, basso = blocco.riquadro
    dentro: list[dict[str, Any]] = []
    for parola in parole:
        x = _numero(parola.get("left")) + _numero(parola.get("width")) / 2
        y = _numero(parola.get("top")) + _numero(parola.get("height")) / 2
        if sinistra <= x <= destra and alto <= y <= basso:
            dentro.append(parola)
    return dentro


def _livello(scala: float) -> int:
    for soglia, livello in SOGLIE_TITOLO:
        if scala >= soglia:
            return livello
    return 0


def _grassetto(parole: Sequence[dict[str, Any]], misure: Misure) -> bool:
    dichiarati = [parola.get("grassetto") for parola in parole if "grassetto" in parola]
    if dichiarati:
        # Il documento dichiara il proprio carattere: nessuna stima.
        return sum(1 for valore in dichiarati if valore) > len(dichiarati) / 2
    if misure.densita_corpo <= 0:
        return False
    densita = [_numero(parola.get("densita")) for parola in parole]
    densita = [valore for valore in densita if valore > 0]
    if not densita:
        return False
    return statistics.median(densita) >= misure.densita_corpo * SOGLIA_GRASSETTO


def _dichiarato(parole: Sequence[dict[str, Any]], chiave: str) -> bool:
    """Vero se la maggioranza delle parole lo dichiara; falso se nessuna lo dice."""
    dichiarati = [parola.get(chiave) for parola in parole if chiave in parola]
    if not dichiarati:
        # Dall'immagine non si misura: non si dichiara.
        return False
    return sum(1 for valore in dichiarati if valore) > len(dichiarati) / 2


def _corsivo(parole: Sequence[dict[str, Any]]) -> bool:
    return _dichiarato(parole, "corsivo")


def _allineamento_riga(sinistra: float, destra: float, misure: Misure) -> str:
    tolleranza = misure.larghezza_colonna * TOLLERANZA_MARGINE
    margine_sinistro = max(0.0, sinistra - misure.colonna_sinistra)
    margine_destro = max(0.0, misure.colonna_destra - destra)
    libero_a_sinistra = margine_sinistro > tolleranza
    libero_a_destra = margine_destro > tolleranza
    if libero_a_sinistra and libero_a_destra:
        somma = margine_sinistro + margine_destro
        scarto = abs(margine_sinistro - margine_destro) / somma if somma else 1.0
        return ALLINEAMENTO_CENTRO if scarto <= SCARTO_CENTRATURA else ALLINEAMENTO_SINISTRA
    if libero_a_sinistra and not libero_a_destra:
        return ALLINEAMENTO_DESTRA
    return ALLINEAMENTO_SINISTRA


def _righe(parole: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    righe: dict[tuple[int, int, int], list[dict[str, Any]]] = {}
    for parola in parole:
        chiave = (int(_numero(parola.get("block"))), int(_numero(parola.get("par"))), int(_numero(parola.get("line"))))
        righe.setdefault(chiave, []).append(parola)
    return [righe[chiave] for chiave in sorted(righe)]


def _giustificato(righe: Sequence[Sequence[dict[str, Any]]], misure: Misure) -> bool:
    """Vero se le righe del capoverso, tranne l'ultima, riempiono la colonna.

    Il testo giustificato e' la norma negli atti: si riconosce perche' ogni
    riga tocca il margine destro entro la tolleranza, mentre un testo a
    sinistra lascia il bordo destro frastagliato.
    """
    if len(righe) < 3:
        return False
    tolleranza = misure.larghezza_colonna * TOLLERANZA_MARGINE
    piene = 0
    for gruppo in righe[:-1]:
        sinistra = min(_numero(parola.get("left")) for parola in gruppo)
        destra = max(_numero(parola.get("left")) + _numero(parola.get("width")) for parola in gruppo)
        a_sinistra = sinistra - misure.colonna_sinistra <= tolleranza
        a_destra = misure.colonna_destra - destra <= tolleranza
        if a_sinistra and a_destra:
            piene += 1
    return piene >= max(2, round(len(righe[:-1]) * QUOTA_RIGHE_PIENE))


def _allineamento(parole: Sequence[dict[str, Any]], misure: Misure) -> str:
    righe = _righe(parole)
    if not righe:
        return ALLINEAMENTO_SINISTRA
    if _giustificato(righe, misure):
        return ALLINEAMENTO_GIUSTIFICATO
    conteggio: dict[str, int] = {}
    for gruppo in righe:
        sinistra = min(_numero(parola.get("left")) for parola in gruppo)
        destra = max(_numero(parola.get("left")) + _numero(parola.get("width")) for parola in gruppo)
        scelta = _allineamento_riga(sinistra, destra, misure)
        conteggio[scelta] = conteggio.get(scelta, 0) + 1
    # A parita' vince il testo a sinistra: e' il caso normale di un atto.
    return max(ALLINEAMENTI[:3], key=lambda voce: (conteggio.get(voce, 0), voce == ALLINEAMENTO_SINISTRA))


#: Quanto un colore deve staccarsi dal grigio per essere un colore. Sotto
#: questa distanza fra la componente piu' alta e la piu' bassa siamo nel nero,
#: nel grigio o in una sfumatura dell'inchiostro: dichiararla come colore
#: vorrebbe dire scrivere «#1a1a1a» dove l'autore aveva scritto in nero.
SATURAZIONE_MINIMA = 26

#: Sopra questa luce non e' inchiostro, e' carta. Si guarda il canale piu'
#: **basso**: il bianco ha tutti e tre i canali alti, mentre un blu pieno ha il
#: rosso a zero. Guardando il canale piu' alto — come facevo — l'indirizzo PEC
#: scritto in blu pieno finiva scartato insieme allo sfondo.
LUMINOSITA_CARTA = 210


def _colore_leggibile(rosso: int, verde: int, blu: int) -> str:
    """Il colore in forma `#rrggbb`, ma solo se e' davvero un colore."""
    alto, basso = max(rosso, verde, blu), min(rosso, verde, blu)
    if alto - basso < SATURAZIONE_MINIMA or basso > LUMINOSITA_CARTA:
        return ""
    return f"#{rosso:02x}{verde:02x}{blu:02x}"


def _colore(parole: Sequence[dict[str, Any]]) -> str:
    """Il colore del blocco: quello che dichiara la maggioranza delle parole.

    Basta una parola colorata in mezzo a venti nere per non fare un blocco
    colorato — e una intestazione azzurra dichiara l'azzurro in tutte.
    """
    dichiarati = [str(parola.get("colore") or "") for parola in parole]
    colorate = [colore for colore in dichiarati if colore]
    if not colorate or len(colorate) * 2 < len(dichiarati):
        return ""
    conteggio: dict[str, int] = {}
    for colore in colorate:
        conteggio[colore] = conteggio.get(colore, 0) + 1
    return max(conteggio, key=lambda chiave: conteggio[chiave])


def _famiglia(parole: Sequence[dict[str, Any]]) -> str:
    """Il carattere del blocco: quello della maggioranza delle parole.

    Come per il colore, una sigla in Arial dentro un capoverso in Times non
    cambia il carattere del capoverso.
    """
    dichiarate = [str(parola.get("famiglia") or "") for parola in parole]
    presenti = [famiglia for famiglia in dichiarate if famiglia]
    if not presenti or len(presenti) * 2 < len(dichiarate):
        return ""
    conteggio: dict[str, int] = {}
    for famiglia in presenti:
        conteggio[famiglia] = conteggio.get(famiglia, 0) + 1
    return max(conteggio, key=lambda chiave: conteggio[chiave])


def _corpo(corpi: Sequence[float]) -> float:
    """Il corpo del blocco in punti, al mezzo punto come lo scrive Word."""
    if not corpi:
        return 0.0
    return round(statistics.median(corpi) * 2) / 2


def formato_blocco(blocco: Blocco, parole: Sequence[dict[str, Any]], misure: Misure) -> Formato:
    """Formato di un blocco, misurato sulle sue parole."""
    proprie = _parole_del_blocco(blocco, parole)
    if not proprie:
        return Formato()
    altezze = [_numero(parola.get("height")) for parola in proprie]
    corpi = [_numero(parola.get("corpo")) for parola in proprie if _numero(parola.get("corpo")) > 0]
    if corpi:
        # Il PDF dichiara il corpo in punti: si confronta con il corpo mediano
        # della pagina espresso nella stessa unita'.
        corpo_pagina = _mediana([_numero(parola.get("corpo")) for parola in parole], 0.0)
        scala = (statistics.median(corpi) / corpo_pagina) if corpo_pagina > 0 else 1.0
    else:
        scala = (_mediana(altezze, misure.altezza_corpo) / misure.altezza_corpo) if misure.altezza_corpo > 0 else 1.0
    grassetto = _grassetto(proprie, misure)
    livello = _livello(scala)
    testo = blocco.testo or ""
    if not livello and grassetto and blocco.tipo != "tabella" and 0 < len(testo) <= LUNGHEZZA_MASSIMA_RUBRICA:
        livello = 4
    return Formato(
        livello=livello,
        grassetto=grassetto,
        corsivo=_corsivo(proprie),
        allineamento=_allineamento(proprie, misure),
        scala=scala,
        colore=_colore(proprie),
        famiglia=_famiglia(proprie),
        corpo=_corpo(corpi),
        sottolineato=_dichiarato(proprie, "sottolineato"),
        barrato=_dichiarato(proprie, "barrato"),
    )


def blocchi_con_formato(
    blocchi: Sequence[Blocco],
    parole: Sequence[dict[str, Any]],
    *,
    misure: Misure | None = None,
) -> list[dict[str, Any]]:
    """Blocchi pronti per la pagina, ciascuno con il proprio formato misurato."""
    riferimenti = misure or misure_pagina(parole)
    voci: list[dict[str, Any]] = []
    for blocco in blocchi:
        voce = blocco.come_dizionario()
        voce["formato"] = formato_blocco(blocco, parole, riferimenti).come_dizionario()
        voci.append(voce)
    return voci


def densita_parole(immagine: Any, parole: Sequence[dict[str, Any]]) -> None:
    """Misura l'inchiostro di ogni parola sull'immagine della pagina.

    Serve solo a distinguere il grassetto: si conta la quota di pixel scuri nel
    riquadro della parola. Se l'immagine non e' leggibile la misura si salta e
    il grassetto semplicemente non viene dichiarato.
    """
    if immagine is None or not parole:
        return
    try:
        grigia = immagine.convert("L")
        larghezza, altezza = grigia.size
        pixel = grigia.load()
    except (AttributeError, OSError, ValueError):
        return
    for parola in parole:
        sinistra = int(max(0, _numero(parola.get("left"))))
        alto = int(max(0, _numero(parola.get("top"))))
        destra = int(min(larghezza, sinistra + _numero(parola.get("width"))))
        basso = int(min(altezza, alto + _numero(parola.get("height"))))
        if destra <= sinistra or basso <= alto:
            continue
        scuri = 0
        totale = 0
        # Un passo di campionamento tiene la misura leggera anche a 300 dpi
        # senza cambiarne il significato: la densita' e' una proporzione.
        passo = max(1, (destra - sinistra) // 40)
        for x in range(sinistra, destra, passo):
            for y in range(alto, basso, passo):
                totale += 1
                if pixel[x, y] < 128:
                    scuri += 1
        if totale:
            parola["densita"] = scuri / totale


def colori_parole(immagine: Any, parole: Sequence[dict[str, Any]]) -> None:
    """Misura il colore dell'inchiostro di ogni parola sull'immagine.

    Una scansione non dichiara niente: il colore va guardato. Si prende la
    media dei pixel scuri dentro il riquadro della parola — quelli chiari sono
    la carta — e si dichiara solo se e' un colore vero: l'intestazione azzurra
    di una carta intestata lo e', il nero del testo no.

    Se l'immagine non e' leggibile la misura si salta, e il colore
    semplicemente non viene dichiarato: meglio il nero del documento che un
    colore inventato.
    """
    if immagine is None or not parole:
        return
    try:
        colorata = immagine.convert("RGB")
        larghezza, altezza = colorata.size
        pixel = colorata.load()
    except (AttributeError, OSError, ValueError):
        return
    for parola in parole:
        sinistra = int(max(0, _numero(parola.get("left"))))
        alto = int(max(0, _numero(parola.get("top"))))
        destra = int(min(larghezza, sinistra + _numero(parola.get("width"))))
        basso = int(min(altezza, alto + _numero(parola.get("height"))))
        if destra <= sinistra or basso <= alto:
            continue
        somma = [0, 0, 0]
        quanti = 0
        passo = max(1, (destra - sinistra) // 40)
        for x in range(sinistra, destra, passo):
            for y in range(alto, basso, passo):
                rosso, verde, blu = pixel[x, y][:3]
                # solo l'inchiostro: la carta intorno falserebbe la media
                if (rosso + verde + blu) / 3 > LUMINOSITA_CARTA:
                    continue
                somma[0] += rosso
                somma[1] += verde
                somma[2] += blu
                quanti += 1
        if quanti:
            colore = _colore_leggibile(*(valore // quanti for valore in somma))
            if colore:
                parola["colore"] = colore


__all__ = [
    "ALLINEAMENTI",
    "ALLINEAMENTO_CENTRO",
    "ALLINEAMENTO_DESTRA",
    "ALLINEAMENTO_GIUSTIFICATO",
    "ALLINEAMENTO_SINISTRA",
    "Formato",
    "Misure",
    "blocchi_con_formato",
    "colori_parole",
    "densita_parole",
    "formato_blocco",
    "misure_pagina",
]
