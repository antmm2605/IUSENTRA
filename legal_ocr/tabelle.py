"""Le tabelle dei documenti in due forme: come testo e come struttura.

L'estrazione lineare di un PDF restituisce una tabella come righe di parole:
«Fase di studio € 1.215,00» si legge ancora, ma in una tabella a più colonne
le celle di righe diverse si mescolano e chi legge dopo (indice, Lex, motori
dell'archivio) non sa più quale importo appartiene a quale voce. La rassegna
Reducto del 26/09/2026 («From Ingestion to Agents») lo dice in una riga: le
tabelle vanno conservate come testo *e* come struttura.

Qui una tabella ha:

- la **struttura**: righe e celle (`Tabella.righe`), con la pagina e l'origine
  (tabella disegnata nel PDF, oppure prospetto di voci e importi riconosciuto
  nelle righe del testo, nativo o letto dal riconoscimento ottico);
- la **forma testuale**: un blocco delimitato che viaggia con il testo della
  pagina nell'indice e nell'archivio, e da cui la struttura si ricostruisce
  identica (`blocco` / `leggi_blocchi`):

      [TABELLA 1 · pagina 2 · 5 righe × 2 colonne]
      Voce | Importo
      Fase di studio | € 1.215,00
      [/TABELLA]

Il blocco si aggiunge dopo il testo della pagina, che resta quello dell'autore.
Le tabelle si cercano solo nelle pagine con almeno tre importi o date: una
pagina di sola prosa non paga il costo della ricerca e non produce tabelle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

ORIGINE_PDF = "tabella del PDF"
ORIGINE_PROSPETTO = "prospetto di voci e importi"

RIGHE_MASSIME = 80
COLONNE_MASSIME = 8
CELLA_MASSIMA = 160

# Un importo come si scrive in un atto: «1.215,00», «854,55», «€ 300», «92,00 euro».
IMPORTO = r"(?:€\s*)?-?\d{1,3}(?:\.\d{3})*,\d{2}|(?:€|EUR)\s*-?\d+(?:[.,]\d{1,2})?|-?\d+(?:,\d{2})?\s*(?:€|euro|EUR)"
_IMPORTO = re.compile(IMPORTO, re.IGNORECASE)
_IMPORTO_IN_FONDO = re.compile(rf"^(?P<voce>.*?\D)\s*(?P<importo>{IMPORTO})\s*$", re.IGNORECASE)
_DATA = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b")
_INIZIO = re.compile(r"^\[TABELLA (\d+) · pagina (\d+) · (\d+) righe × (\d+) colonne(?: · ([^\]]+))?\]\s*$")
_FINE = "[/TABELLA]"


@dataclass(frozen=True)
class Tabella:
    pagina: int
    righe: tuple[tuple[str, ...], ...]
    origine: str = ORIGINE_PDF

    @property
    def colonne(self) -> int:
        return max((len(riga) for riga in self.righe), default=0)

    def testo(self) -> str:
        """Le righe come testo: celle separate da « | », una riga per riga."""
        return "\n".join(" | ".join(riga) for riga in self.righe)

    def to_dict(self) -> dict[str, Any]:
        return {"pagina": self.pagina, "origine": self.origine, "righe": [list(r) for r in self.righe],
                "colonne": self.colonne, "testo": self.testo()}


def _cella(valore: Any) -> str:
    testo = " ".join(str(valore or "").replace("|", "/").split())
    return testo[:CELLA_MASSIMA]


def pulisci(righe: Iterable[Iterable[Any]]) -> tuple[tuple[str, ...], ...]:
    """Celle su una riga, senza righe o colonne vuote."""
    pulite = [[_cella(c) for c in riga] for riga in righe]
    pulite = [riga for riga in pulite if any(riga)]
    if not pulite:
        return ()
    larghezza = max(len(riga) for riga in pulite)
    pulite = [riga + [""] * (larghezza - len(riga)) for riga in pulite]
    piene = [i for i in range(larghezza) if any(riga[i] for riga in pulite)]
    return tuple(tuple(riga[i] for i in piene) for riga in pulite)[:RIGHE_MASSIME]


def _numerica(cella: str) -> bool:
    return bool(_IMPORTO.fullmatch(cella.strip()) or _DATA.fullmatch(cella.strip()) or re.fullmatch(r"[\d.,%/\s€-]+", cella.strip()))


def tabella_valida(righe: tuple[tuple[str, ...], ...]) -> bool:
    """Una tabella vera: almeno 2 righe e 2 colonne, celle brevi, una colonna di numeri.

    Un riquadro disegnato attorno a un paragrafo (intestazioni, timbri) non è
    una tabella: senza una colonna in cui almeno metà delle celle sono importi,
    date o numeri non si conserva come struttura.
    """
    if len(righe) < 2:
        return False
    colonne = max(len(r) for r in righe)
    if colonne < 2 or colonne > COLONNE_MASSIME:
        return False
    celle = [c for r in righe for c in r if c]
    if not celle or sum(len(c) for c in celle) / len(celle) > 90:
        return False
    corpo = righe[1:] if len(righe) > 2 else righe
    for indice in range(colonne):
        colonna = [r[indice] for r in corpo if indice < len(r) and r[indice]]
        if colonna and sum(1 for c in colonna if _numerica(c)) / len(colonna) >= 0.5:
            return True
    return False


def pagina_con_numeri(testo: str) -> bool:
    """Una pagina merita la ricerca delle tabelle solo se ha almeno tre importi o date."""
    return len(_IMPORTO.findall(testo or "")) + len(_DATA.findall(testo or "")) >= 3


# ── Dal PDF ──────────────────────────────────────────────────────────────────

def da_pdfplumber(pagina: Any, numero: int) -> list[Tabella]:
    """Le tabelle disegnate di una pagina pdfplumber (celle delimitate da linee).

    Le colonne ricavate dal solo allineamento del testo spezzano le parole
    («Fase d | i studio»): per le tabelle senza linee vale il prospetto letto
    nelle righe (`prospetti_dal_testo`), che conserva voce e importo interi.
    """
    tabelle: list[Tabella] = []
    try:
        disegnate = pagina.extract_tables() or []
    except Exception:
        disegnate = []
    for grezza in disegnate:
        righe = pulisci(grezza)
        if tabella_valida(righe):
            tabelle.append(Tabella(numero, righe, ORIGINE_PDF))
    return tabelle


def da_pymupdf(pagina: Any, numero: int) -> list[Tabella]:
    """Le tabelle disegnate di una pagina PyMuPDF (motore di lettura unico)."""
    tabelle: list[Tabella] = []
    try:
        trovate = pagina.find_tables(strategy="lines")
        grezze = [t.extract() for t in getattr(trovate, "tables", []) or []]
    except Exception:
        grezze = []
    for grezza in grezze:
        righe = pulisci(grezza)
        if tabella_valida(righe):
            tabelle.append(Tabella(numero, righe, ORIGINE_PDF))
    return tabelle


# ── Dal testo: prospetti di voci e importi ─────────────────────────────────────

def prospetti_dal_testo(testo: str, *, pagina: int = 0) -> list[Tabella]:
    """Righe consecutive che finiscono con un importo: «Spese generali 15% € 854,55».

    È la forma in cui arrivano i prospetti (nota spese, liquidazione, proforma,
    precetto) sia dal testo nativo sia dal riconoscimento ottico. Servono almeno
    tre righe di fila; una riga di intestazione subito sopra si conserva.
    """
    prospetti: list[Tabella] = []
    righe = [" ".join(r.split()) for r in str(testo or "").splitlines()]
    corrente: list[tuple[str, str]] = []
    intestazione = ""

    def chiudi() -> None:
        if len(corrente) >= 3:
            corpo = [(voce, importo) for voce, importo in corrente]
            testa = [tuple(p.strip() for p in re.split(r"\s{2,}|\t| (?=Importo\b)", intestazione) if p.strip())] if intestazione else []
            testa = [t for t in testa if len(t) == 2]
            prospetti.append(Tabella(pagina, tuple(testa) + tuple(corpo), ORIGINE_PROSPETTO))
        corrente.clear()

    precedente = ""
    for riga in righe:
        if riga.startswith("[TABELLA") or riga == _FINE:
            chiudi()
            precedente = ""
            continue
        trovata = _IMPORTO_IN_FONDO.match(riga)
        if trovata and len(trovata.group("voce").strip(" .:-")) >= 2 and len(riga) <= 140:
            if not corrente:
                intestazione = precedente if precedente and not _IMPORTO.search(precedente) and len(precedente) <= 60 and re.search(r"importo|voce|descrizione", precedente, re.I) else ""
            corrente.append((trovata.group("voce").strip(" .:-"), trovata.group("importo").strip()))
        else:
            chiudi()
        precedente = riga
    chiudi()
    return prospetti


# ── La forma testuale che viaggia con il testo ────────────────────────────────

def blocco(tabella: Tabella, indice: int) -> str:
    return (
        f"[TABELLA {indice} · pagina {tabella.pagina} · {len(tabella.righe)} righe × {tabella.colonne} colonne · {tabella.origine}]\n"
        f"{tabella.testo()}\n{_FINE}"
    )


def con_blocchi(testo: str, tabelle: Iterable[Tabella], *, primo: int = 1) -> str:
    """Il testo della pagina seguito dai blocchi delle sue tabelle."""
    blocchi = [blocco(t, primo + i) for i, t in enumerate(tabelle)]
    if not blocchi:
        return testo
    return (str(testo or "").rstrip() + "\n\n" + "\n\n".join(blocchi)).strip()


def leggi_blocchi(testo: str) -> list[Tabella]:
    """Le tabelle scritte nel testo come blocchi: la struttura ricostruita identica."""
    tabelle: list[Tabella] = []
    corrente: list[tuple[str, ...]] | None = None
    pagina, origine = 0, ORIGINE_PDF
    for riga in str(testo or "").splitlines():
        inizio = _INIZIO.match(riga.strip())
        if inizio:
            corrente, pagina, origine = [], int(inizio.group(2)), (inizio.group(5) or ORIGINE_PDF).strip()
            continue
        if corrente is None:
            continue
        if riga.strip() == _FINE:
            if corrente:
                tabelle.append(Tabella(pagina, tuple(corrente), origine))
            corrente = None
            continue
        corrente.append(tuple(c.strip() for c in riga.split(" | ")))
    return tabelle


def senza_blocchi(testo: str) -> str:
    """Il testo dell'autore, senza i blocchi delle tabelle (per chi conta parole o date una volta sola)."""
    return re.sub(r"\n*\[TABELLA \d+ · [^\n]*\n.*?\n\[/TABELLA\]", "", str(testo or ""), flags=re.S).strip()


def tabelle_del_testo(testo: str) -> list[Tabella]:
    """Tutte le tabelle di un testo: i blocchi già scritti e i prospetti riconosciuti nelle righe."""
    dai_blocchi = leggi_blocchi(testo)
    importi_nei_blocchi = {c for t in dai_blocchi for r in t.righe for c in r if _IMPORTO.fullmatch(c)}
    prospetti = [
        p for p in prospetti_dal_testo(senza_blocchi(testo))
        if not {r[-1] for r in p.righe if _IMPORTO.fullmatch(r[-1])} <= importi_nei_blocchi
    ]
    return dai_blocchi + prospetti


__all__ = [
    "IMPORTO", "ORIGINE_PDF", "ORIGINE_PROSPETTO", "Tabella", "blocco", "con_blocchi",
    "da_pdfplumber", "da_pymupdf", "leggi_blocchi", "pagina_con_numeri", "prospetti_dal_testo", "pulisci",
    "senza_blocchi", "tabella_valida", "tabelle_del_testo",
]
