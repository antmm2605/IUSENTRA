"""Collegamento delle notizie ai fascicoli dello studio, con il motivo scritto per l'avvocato.

Si usano solo i dati anagrafici del fascicolo già nell'indice leggero (titolo,
oggetto, tipo, area della pratica): nessun documento viene riletto.
Una notizia è pertinente a un fascicolo quando:
1. cita per estremi lo stesso atto citato nel titolo o nell'oggetto del fascicolo, oppure
2. condivide con titolo, oggetto e descrizione ufficiale del codice oggetto PST
   almeno due parole significative e la materia è
   compatibile (materie del fascicolo da `pct.normativa_fascicolo.materie`).
La sola materia non basta: renderebbe pertinente quasi ogni notizia.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Iterable

from pct.normativa_fascicolo.materie import materie_del_fascicolo
from pct.notiziario.classifica import atti_citati, citazioni_atti

MASSIMO_FASCICOLI = 5
_PAROLA = re.compile(r"[a-zà-ÿ]{5,}", re.IGNORECASE)
_RADICE = 7
_SIGLE_ATTO = {"dlgs": "D.Lgs.", "dl": "D.L.", "dpr": "D.P.R.", "legge": "L.", "lcost": "L. cost.", "regue": "Reg. UE", "dirue": "Dir. UE"}

# Parole troppo generiche per dire che due testi parlano della stessa cosa (radici di 7 lettere).
_GENERICHE = frozenset(
    parola[:_RADICE] for parola in (
        "decreto", "decreti", "legge", "leggi", "legislativo", "sentenza", "sentenze", "ordinanza", "ordinanze",
        "ricorso", "ricorsi", "giudizio", "giudizi", "causa", "cause", "corte", "tribunale", "ministero", "ministro",
        "articolo", "articoli", "comma", "commi", "disposizioni", "disposizione", "materia", "nazionale", "nazionali",
        "regione", "regionale", "provincia", "comune", "pubblico", "pubblica", "pubblici", "generale", "generali",
        "italia", "italiana", "italiano", "repubblica", "presidente", "consiglio", "ufficio", "uffici", "procedimento",
        "procedura", "termine", "termini", "modifica", "modifiche", "relativo", "relativa", "relative", "materie",
        "nonche", "ovvero", "attuazione", "approvazione", "riconoscimento", "richiesta", "istanza", "domanda",
        "contro", "nell'ambito", "ambito", "seguito", "sensi", "previsto", "prevista", "previste", "misure",
        "servizi", "servizio", "soggetti", "documenti", "documento", "comunicazione", "comunicato", "avviso",
        "circolare", "messaggio", "numero", "altri", "altre", "della", "delle", "degli", "nella", "nelle", "sulla",
        "sulle", "dalla", "dalle", "questa", "questo", "quale", "quali", "essere", "sono", "anche", "presso",
        "giudice", "giudici", "parte", "parti", "atto", "atti", "pratica", "fascicolo", "cliente", "studio",
        "privato", "privata", "privati", "dipendente", "dipendenti", "settore", "lavoratori", "lavoratore",
        "sezione", "civile", "penale", "lavoro", "appello", "primo", "grado", "decisione", "provvedimento",
        "provvedimenti", "ordinario", "ordinaria", "speciale", "europea", "europeo", "unione", "commissione",
    )
)


# Catalogo ufficiale dei codici oggetto (XSD del PST): «222050» → «retribuzione · Pubblico impiego».
_CATALOGO_PST = Path(__file__).resolve().parents[1] / "data" / "cataloghi" / "codici_oggetto_pst_ui.json"


@lru_cache(maxsize=1)
def _descrizioni_pst() -> dict[str, str]:
    try:
        dati = json.loads(_CATALOGO_PST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {
        str(riga.get("codice") or ""): f"{riga.get('descrizione') or ''} {riga.get('descrizionePadre') or ''}".strip()
        for riga in dati.get("records") or []
        if riga.get("codice")
    }


def descrizione_oggetto_pst(codice: str) -> str:
    return _descrizioni_pst().get(str(codice or "").strip(), "")


def _normalizza(testo: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(testo or "").lower())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def parole_significative(testo: str) -> dict[str, str]:
    """Radice → prima forma incontrata nel testo, senza parole generiche."""
    risultato: dict[str, str] = {}
    for parola in _PAROLA.findall(_normalizza(testo)):
        radice = parola[:_RADICE]
        if radice in _GENERICHE or radice in risultato:
            continue
        risultato[radice] = parola
    return risultato


def etichetta_atto(chiave: str) -> str:
    tipo, numero, anno = (chiave.split(":") + ["", "", ""])[:3]
    sigla = _SIGLE_ATTO.get(tipo, tipo)
    return f"{sigla} {anno}/{numero}" if tipo in {"regue", "dirue"} else f"{sigla} {numero}/{anno}"


@dataclass
class _Fascicolo:
    id: str
    etichetta: str
    materie: tuple[str, ...]
    atti: frozenset[str]
    parole: frozenset[str]
    # atto → (articolo citato, documento) dalle norme citate negli atti (lettore «norme_citate»)
    nei_documenti: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class IndicePertinenza:
    fascicoli: list[_Fascicolo] = field(default_factory=list)
    per_parola: dict[str, list[int]] = field(default_factory=dict)
    per_atto: dict[str, list[int]] = field(default_factory=dict)
    diffusi: frozenset[str] = frozenset()


def costruisci_indice(
    fascicoli: Iterable[dict[str, Any]],
    atti_documenti: dict[str, list[dict[str, Any]]] | None = None,
) -> IndicePertinenza:
    """`fascicoli`: dict con id, etichetta, titolo, oggetto, tipo, area_pratica, codice_oggetto_pst.

    `atti_documenti`: per fascicolo, gli atti citati nei suoi documenti (riepilogo del
    lettore «norme_citate», già calcolato in sfondo).
    """
    indice = IndicePertinenza()
    atti_documenti = atti_documenti or {}
    for voce in fascicoli:
        testo = " ".join((
            str(voce.get("titolo") or ""), str(voce.get("oggetto") or ""),
            descrizione_oggetto_pst(str(voce.get("codice_oggetto_pst") or "")),
        ))
        fascicolo_id = str(voce.get("id") or "")
        if not fascicolo_id:
            continue
        nei_documenti = {
            str(atto.get("chiave")): (str(atto.get("articolo") or ""), str(atto.get("documento") or ""))
            for atto in atti_documenti.get(fascicolo_id, []) if atto.get("chiave")
        }
        fascicolo = _Fascicolo(
            id=fascicolo_id,
            etichetta=str(voce.get("etichetta") or voce.get("titolo") or "Fascicolo"),
            materie=tuple(materie_del_fascicolo(str(voce.get("tipo") or ""), str(voce.get("area_pratica") or ""))),
            atti=frozenset(atti_citati(testo)) | frozenset(nei_documenti),
            parole=frozenset(parole_significative(testo)),
            nei_documenti=nei_documenti,
        )
        posizione = len(indice.fascicoli)
        indice.fascicoli.append(fascicolo)
        for parola in fascicolo.parole:
            indice.per_parola.setdefault(parola, []).append(posizione)
        for atto in fascicolo.atti:
            indice.per_atto.setdefault(atto, []).append(posizione)
    indice.diffusi = atti_diffusi(indice)
    return indice


# Un atto citato in più di un quarto dei fascicoli (es. D.P.R. 115/2002 nei ricorsi, D.Lgs. 28/2010 nelle procure)
# descrive lo studio, non la pratica: collega solo per stesso articolo e comma (misura 08/11/2026: 98 su 308).
QUOTA_DIFFUSIONE = 0.25
MINIMO_FASCICOLI_DIFFUSIONE = 20


def atti_diffusi(indice: IndicePertinenza) -> frozenset[str]:
    """Atti citati in più di un quarto dei fascicoli (almeno 20): da soli non distinguono un fascicolo."""
    totale = len(indice.fascicoli)
    if totale < MINIMO_FASCICOLI_DIFFUSIONE:
        return frozenset()
    return frozenset(atto for atto, posizioni in indice.per_atto.items() if len(posizioni) > totale * QUOTA_DIFFUSIONE)


def _numero_articolo(articolo: str) -> str:
    """«art. 1 c. 121» → «1 c. 121»: articolo e comma, perché lo stesso articolo regola cose diverse
    (art. 4 D.Lgs. 28/2010: c. 1 competenza, c. 3 informativa nella procura)."""
    parti = str(articolo or "").lower().split()
    return " ".join(parti[1:]) if len(parti) > 1 and parti[0] == "art." else ""


def _nome_breve(fascicolo: _Fascicolo) -> str:
    """«RG 771/2025 - Rossi c. MIUR» → «RG 771/2025»; senza ruolo, il titolo."""
    return fascicolo.etichetta.split(" - ", 1)[0].strip() or fascicolo.etichetta


def _motivo_atti(fascicolo: _Fascicolo, atti: list[str]) -> str:
    atto = atti[0]
    articolo, documento = fascicolo.nei_documenti.get(atto, ("", ""))
    citato = f"l'{articolo} {etichetta_atto(atto)}" if articolo else etichetta_atto(atto)
    if documento:
        motivo = f"Il fascicolo {_nome_breve(fascicolo)} cita {citato} (documento «{documento}»)"
    else:
        motivo = f"Il fascicolo {_nome_breve(fascicolo)} cita {citato} nel titolo o nell'oggetto"
    if len(atti) > 1:
        motivo += " e anche " + ", ".join(etichetta_atto(a) for a in atti[1:3])
    return motivo


def fascicoli_pertinenti(notizia: dict[str, Any], indice: IndicePertinenza) -> list[dict[str, str]]:
    """Fino a cinque fascicoli, i più vicini per primi, ciascuno con il motivo."""
    return pertinenza(notizia, indice)[0]


def pertinenza(notizia: dict[str, Any], indice: IndicePertinenza) -> tuple[list[dict[str, str]], int]:
    """I fascicoli più vicini (fino a cinque), ciascuno con il motivo, e quanti sono in tutto."""
    parole = parole_significative(f"{notizia.get('titolo') or ''} {notizia.get('sintesi') or ''}")
    atti = [atto for atto in notizia.get("atti") or [] if atto in indice.per_atto]
    articoli_notizia = dict(citazioni_atti(f"{notizia.get('titolo') or ''} {notizia.get('sintesi') or ''}"))
    materia = str(notizia.get("materia") or "")
    candidati: dict[int, dict[str, list[str]]] = {}
    diffusi = indice.diffusi
    for atto in atti:
        articolo_notizia = _numero_articolo(articoli_notizia.get(atto, ""))
        for posizione in indice.per_atto[atto]:
            if atto in diffusi:
                # Atto citato in quasi tutti i fascicoli (clausole di procure, contratti, moduli): conta solo
                # se notizia e fascicolo citano lo stesso articolo.
                articolo_fascicolo = _numero_articolo(indice.fascicoli[posizione].nei_documenti.get(atto, ("", ""))[0])
                if not articolo_notizia or articolo_notizia != articolo_fascicolo:
                    continue
            candidati.setdefault(posizione, {"atti": [], "parole": []})["atti"].append(atto)
    for radice in parole:
        for posizione in indice.per_parola.get(radice, ()):
            candidati.setdefault(posizione, {"atti": [], "parole": []})["parole"].append(radice)
    scelti: list[tuple[int, dict[str, str]]] = []
    for posizione, segnali in candidati.items():
        fascicolo = indice.fascicoli[posizione]
        materia_compatibile = not materia or not fascicolo.materie or materia in fascicolo.materie
        if segnali["atti"]:
            motivo = _motivo_atti(fascicolo, segnali["atti"])
        elif len(segnali["parole"]) >= 2 and materia_compatibile:
            motivo = "Stesso tema dell'oggetto: " + ", ".join(f"«{parole[r]}»" for r in segnali["parole"][:4])
            if materia and materia in fascicolo.materie:
                motivo += f" · materia {materia}"
        else:
            continue
        # l'articolo citato in un documento pesa più del solo atto
        punteggio = sum(4 if fascicolo.nei_documenti.get(a, ("", ""))[0] else 3 for a in segnali["atti"]) + len(segnali["parole"])
        scelti.append((punteggio, {"id": fascicolo.id, "etichetta": fascicolo.etichetta, "motivo": motivo}))
    scelti.sort(key=lambda voce: (-voce[0], voce[1]["etichetta"]))
    return [voce for _, voce in scelti[:MASSIMO_FASCICOLI]], len(scelti)


__all__ = [
    "IndicePertinenza", "costruisci_indice", "etichetta_atto", "fascicoli_pertinenti", "parole_significative", "pertinenza",
]
