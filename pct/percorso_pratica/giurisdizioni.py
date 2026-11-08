"""Giurisdizione e grado della sentenza, e i rimedi che ne seguono fuori dal processo civile di primo grado.

Il rimedio dipende da chi ha deciso e in che grado: la sentenza d'appello civile si impugna con ricorso per cassazione
(artt. 360 e 325 c.p.c.), quella del TAR con appello al Consiglio di Stato (artt. 92, 94 e 100 c.p.a.), quella della
corte di giustizia tributaria di primo grado con appello al secondo grado (artt. 51 e 52 D.Lgs. 546/1992), quella penale
con i termini dell'art. 585 c.p.p. Testi vigenti letti l'08/11/2026 nell'archivio Normattiva del software; il testo unico
della giustizia tributaria (D.Lgs. 175/2024) si applica dal 1° gennaio 2027 (art. 131), quindi oggi vale il D.Lgs. 546/1992.
"""

from __future__ import annotations

import re
from typing import Any

CIVILE, AMMINISTRATIVO, TRIBUTARIO, PENALE = "civile", "amministrativo", "tributario", "penale"
PRIMO, APPELLO, CASSAZIONE = "primo", "appello", "cassazione"

_TRIBUTARIO = re.compile(r"corte\s+di\s+giustizia\s+tributaria|commissione\s+tributaria|\bc\.?\s?t\.?\s?[pr]\.?(?=\s|$)")
_TRIBUTARIO_SECONDO = re.compile(r"giustizia\s+tributaria\s+di\s+(?:secondo|ii)\s+grado|commissione\s+tributaria\s+regionale|\bc\.?\s?t\.?\s?r\.?(?=\s|$)")
_AMMINISTRATIVO = re.compile(r"tribunale\s+amministrativo|\bt\.?\s?a\.?\s?r\.?(?=\s|$)|consiglio\s+di\s+stato|consiglio\s+di\s+giustizia\s+amministrativa")
_AMMINISTRATIVO_APPELLO = re.compile(r"consiglio\s+di\s+stato|consiglio\s+di\s+giustizia\s+amministrativa")
_PENALE = re.compile(r"corte\s+d['’]\s*assise|giudice\s+per\s+le\s+indagini|giudice\s+dell['’]\s*udienza\s+preliminare|\bg\.?\s?[iu]\.?\s?p\.?(?=\s|$)"
                     r"|tribunale\s+di\s+sorveglianza|\bimputat[oaie]\b")
_CASSAZIONE = re.compile(r"corte\s+(?:suprema\s+)?di\s+cassazione|\bcassazione\b")
_APPELLO = re.compile(r"corte\s+d['’]\s*appello|corte\s+di\s+appello|corte\s+d['’]\s*assise\s+d['’]\s*appello|in\s+grado\s+d['’i]\s*appello"
                      r"|giudizio\s+d['’i]\s*appello|sentenza\s+d['’]\s*appello|\bsezione\s+(?:lavoro\s+)?(?:della\s+)?corte\s+d['’]\s*appello")


def _testo(*valori: Any) -> str:
    return " ".join(" ".join(str(v or "").split()) for v in valori).lower()


def giurisdizione_e_grado(*, tipo: str = "", ufficio: str = "", rito: str = "", sentenza: str = "") -> tuple[str, str]:
    """Dal tipo di fascicolo, dall'ufficio, dal rito dichiarato e dall'intestazione della sentenza.

    L'ufficio e l'intestazione della sentenza prevalgono sul tipo: un fascicolo «civile» con sentenza della corte
    d'appello è in grado d'appello. Senza indizi si resta al primo grado civile, come prima.
    """
    tipo_l = _testo(tipo)
    giudice = _testo(ufficio, sentenza)
    tutto = _testo(ufficio, sentenza, rito)
    if _TRIBUTARIO.search(giudice) or "tribut" in tipo_l:
        if _CASSAZIONE.search(giudice):
            return TRIBUTARIO, CASSAZIONE
        return TRIBUTARIO, APPELLO if _TRIBUTARIO_SECONDO.search(giudice) else PRIMO
    if _AMMINISTRATIVO.search(giudice) or "amministrativ" in tipo_l:
        return AMMINISTRATIVO, APPELLO if _AMMINISTRATIVO_APPELLO.search(giudice) else PRIMO
    giurisdizione = PENALE if ("penal" in tipo_l or re.search(r"\bpenal", _testo(rito)) or _PENALE.search(giudice)) else CIVILE
    if _CASSAZIONE.search(_testo(ufficio)) or re.match(r"\s*(?:la\s+)?corte\s+(?:suprema\s+)?di\s+cassazione", _testo(sentenza)):
        return giurisdizione, CASSAZIONE
    return giurisdizione, APPELLO if _APPELLO.search(tutto) else PRIMO


def _rimedio(nome: str, termine: str, norme: list[str], quando: str, template: str = "") -> dict[str, Any]:
    return {"rimedio": nome, "termine": termine, "norme": norme, "quando": quando, "template": template}


_TERMINE_CPA = ("60 giorni dalla notificazione della sentenza; senza notifica sei mesi dalla pubblicazione; deposito entro 30 giorni "
                "dall'ultima notificazione (art. 94 c.p.a.); nei riti abbreviati dell'art. 119 c.p.a. i termini sono dimezzati")
_TERMINE_TRIB = ("60 giorni dalla notificazione della sentenza (art. 51 D.Lgs. 546/1992); senza notifica sei mesi dalla pubblicazione "
                 "(art. 38, comma 3, D.Lgs. 546/1992, che rinvia all'art. 327 c.p.c.)")
_TERMINE_CPP = ("15 giorni se la motivazione è contestuale, 30 se depositata entro 15 giorni, 45 se il giudice ha indicato un termine più "
                "lungo (art. 585, comma 1, c.p.p., con art. 544 c.p.p.), decorrenti come dispone l'art. 585, comma 2; più 15 giorni per "
                "il difensore dell'imputato giudicato in assenza (comma 1-bis)")

IMPUGNAZIONI_PER_GRADO: dict[tuple[str, str], list[dict[str, Any]]] = {
    (CIVILE, CASSAZIONE): [
        _rimedio("Revocazione o correzione della pronuncia della Corte di cassazione",
                 "revocazione per errore di fatto entro 60 giorni dalla notificazione o sei mesi dalla pubblicazione; correzione in qualsiasi tempo",
                 ["art. 391-bis c.p.c."], "pronuncia della Corte di cassazione: non ci sono altri gradi di impugnazione ordinaria"),
    ],
    (AMMINISTRATIVO, PRIMO): [
        _rimedio("Appello al Consiglio di Stato (al Consiglio di giustizia amministrativa per le sentenze del TAR Sicilia)", _TERMINE_CPA,
                 ["art. 100 c.p.a.", "art. 92 c.p.a.", "art. 94 c.p.a.", "art. 119 c.p.a."], "sentenza del TAR sfavorevole in tutto o in parte"),
    ],
    (AMMINISTRATIVO, APPELLO): [
        _rimedio("Ricorso per cassazione per i soli motivi inerenti alla giurisdizione",
                 "60 giorni dalla notificazione della sentenza; senza notifica sei mesi dalla pubblicazione",
                 ["art. 110 c.p.a.", "art. 92 c.p.a."], "sentenza del Consiglio di Stato: solo per difetto di giurisdizione"),
    ],
    (TRIBUTARIO, PRIMO): [
        _rimedio("Appello alla corte di giustizia tributaria di secondo grado", _TERMINE_TRIB,
                 ["art. 52 D.Lgs. 546/1992", "art. 51 D.Lgs. 546/1992", "art. 38 D.Lgs. 546/1992", "art. 327 c.p.c."],
                 "sentenza della corte di giustizia tributaria di primo grado sfavorevole in tutto o in parte"),
    ],
    (TRIBUTARIO, APPELLO): [
        _rimedio("Ricorso per cassazione", _TERMINE_TRIB,
                 ["art. 62 D.Lgs. 546/1992", "art. 360 c.p.c.", "art. 51 D.Lgs. 546/1992", "art. 38 D.Lgs. 546/1992"],
                 "sentenza della corte di giustizia tributaria di secondo grado: solo per i motivi dei nn. 1-5 dell'art. 360 c.p.c."),
    ],
    (TRIBUTARIO, CASSAZIONE): [
        _rimedio("Revocazione o correzione della pronuncia della Corte di cassazione",
                 "revocazione per errore di fatto entro 60 giorni dalla notificazione o sei mesi dalla pubblicazione; correzione in qualsiasi tempo",
                 ["art. 391-bis c.p.c."], "pronuncia della Corte di cassazione: non ci sono altri gradi di impugnazione ordinaria"),
    ],
    (PENALE, PRIMO): [
        _rimedio("Appello", _TERMINE_CPP, ["art. 593 c.p.p.", "art. 585 c.p.p.", "art. 581 c.p.p."],
                 "sentenza di primo grado, nei limiti dell'art. 593 c.p.p. (sono inappellabili, fra le altre, le condanne alla sola ammenda)"),
    ],
    (PENALE, APPELLO): [
        _rimedio("Ricorso per cassazione", _TERMINE_CPP, ["art. 606 c.p.p.", "art. 585 c.p.p.", "art. 581 c.p.p."],
                 "sentenza d'appello o inappellabile: solo per i motivi dell'art. 606 c.p.p."),
    ],
    (PENALE, CASSAZIONE): [],
}

# Rimedi davanti allo stesso giudice, diversi da quelli del codice di procedura civile.
ALTRI_RIMEDI: dict[str, list[dict[str, Any]]] = {
    AMMINISTRATIVO: [
        _rimedio("Revocazione", "60 giorni dalla notificazione (art. 92 c.p.a.); per i nn. 1, 2, 3 e 6 dell'art. 395 c.p.c. dalla scoperta",
                 ["art. 106 c.p.a.", "art. 92 c.p.a."], "contro le sentenze del TAR solo se i motivi non possono essere dedotti con l'appello"),
        _rimedio("Correzione dell'errore materiale", "domanda allo stesso giudice che ha emesso il provvedimento", ["art. 86 c.p.a."],
                 "omissioni o errori materiali nel testo della sentenza"),
    ],
    TRIBUTARIO: [
        _rimedio("Revocazione", "60 giorni dalla notificazione; per i nn. 1, 2, 3 e 6 dell'art. 395 c.p.c. dalla scoperta (art. 51, comma 2)",
                 ["art. 64 D.Lgs. 546/1992", "art. 51 D.Lgs. 546/1992"],
                 "sentenze d'appello o di unico grado; per quelle non più appellabili solo per i nn. 1, 2, 3 e 6 dell'art. 395 c.p.c."),
    ],
    PENALE: [],
}

# Se la causa è vinta, fuori dal processo civile: i passi propri del rito.
REALIZZAZIONE_PER_GIURISDIZIONE: dict[str, list[dict[str, Any]]] = {
    AMMINISTRATIVO: [
        {"passo": "Notificare la sentenza alla controparte: fa decorrere il termine di sessanta giorni per impugnarla", "norme": ["art. 92 c.p.a."]},
        {"passo": "Se l'amministrazione non esegue: giudizio di ottemperanza", "urgenza": 2, "norme": ["art. 112 c.p.a.", "art. 114 c.p.a."]},
    ],
    TRIBUTARIO: [
        {"passo": "Notificare la sentenza alle altre parti e depositare l'originale notificato entro trenta giorni", "norme": ["art. 38 D.Lgs. 546/1992"]},
        {"passo": "Se l'ente non esegue la sentenza passata in giudicato: giudizio di ottemperanza", "urgenza": 2, "norme": ["art. 70 D.Lgs. 546/1992"]},
    ],
    PENALE: [],
}

__all__ = ["ALTRI_RIMEDI", "IMPUGNAZIONI_PER_GRADO", "REALIZZAZIONE_PER_GIURISDIZIONE", "giurisdizione_e_grado"]
