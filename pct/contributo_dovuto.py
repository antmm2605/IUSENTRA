"""Il contributo unificato dovuto per il procedimento e il confronto con l'importo versato.

Norme (testo vigente nell'archivio Normattiva del software, aggiornamento del 15/10/2026):

- art. 13, comma 1, D.P.R. 115/2002: importi per scaglioni di valore (lett. a-g); € 98 per i processi di
  volontaria giurisdizione (lett. b); € 43 per le controversie di previdenza e assistenza (lett. a); € 518
  per i processi di valore indeterminabile (lett. d), € 237 se di competenza esclusiva del giudice di pace (lett. c);
- art. 13, comma 3: metà per i processi speciali del libro IV, titolo I, c.p.c. (procedimento monitorio e sua
  opposizione, cautelari, possessori, convalida di sfratto) e per le controversie individuali di lavoro o di
  pubblico impiego, salvo l'art. 9, comma 1-bis;
- art. 30: l'anticipazione forfettaria di € 27 non è contributo unificato;
- art. 10 D.P.R. 115/2002 e art. 46-bis disp. att. c.c.: nella volontaria giurisdizione l'importo della lett. b) vale solo
  per i processi non esenti (tutela, prole, misure di protezione, assenza e morte presunta sono esenti): la verifica è in
  ``pct/contributo_esenzioni``, che chi calcola il dovuto chiama prima.

Gli scaglioni sono la tabella versionata ``contributo_unificato_civile`` di ``pct.normative_tables``; la natura
del procedimento viene dal codice oggetto PST del fascicolo (area e voce padre del catalogo ministeriale XSD,
``pct/data/cataloghi/codici_oggetto_pst.json``). Esiti del confronto (collaudo 10/11/2026, G-16):

- ``coincide``: l'importo versato è quello dovuto → versamento certo, nessuna conferma;
- ``insufficiente``: versato meno del dovuto (o solo l'anticipazione forfettaria) → dubbio vero: «contributo forse non
  versato o versato in misura insufficiente», con dovuto e versato;
- ``eccedente`` / ``indeterminato``: altro dubbio dichiarato, o dati mancanti per decidere.
Modulo puro.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

ANTICIPAZIONE_FORFETTARIA = 27.0
NORMA_ANTICIPAZIONE = "art. 30 D.P.R. 115/2002"

VOLONTARIA = "volontaria_giurisdizione"
LAVORO = "lavoro"
PREVIDENZA = "previdenza"
MONITORIO = "processo_speciale_libro_iv"
CIVILE = "civile_ordinario"
ESECUZIONE_IMMOBILIARE = "esecuzione_immobiliare"
ESECUZIONE_ALTRA = "altri_processi_esecutivi"
OPPOSIZIONE_ATTI_ESECUTIVI = "opposizione_atti_esecutivi"


@dataclass(frozen=True)
class Dovuto:
    importo: float
    norma: str
    spiegazione: str


def _euro(valore: float) -> str:
    testo = f"{valore:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"€ {testo}"


def categoria(*, area: str = "", padre: str = "", tipo_fascicolo: str = "") -> str:
    """La categoria del contributo dalla voce del catalogo PST (area e voce padre) o dal tipo del fascicolo."""
    area, padre = str(area or "").casefold(), str(padre or "").casefold()
    tipo = str(getattr(tipo_fascicolo, "value", tipo_fascicolo) or "").upper()
    if "volontaria" in area:
        return VOLONTARIA
    if "opposizione agli atti esecutivi" in padre:
        return OPPOSIZIONE_ATTI_ESECUTIVI
    if "esecuzioni immobiliari" in area:
        return ESECUZIONE_IMMOBILIARE
    if "esecuzioni mobiliari" in area:
        return ESECUZIONE_ALTRA
    if "lavoro e previdenza" in area or tipo in {"LAVORO", "PREVIDENZA"}:
        return PREVIDENZA if ("previdenz" in padre or "assistenz" in padre or tipo == "PREVIDENZA") else LAVORO
    if "procedimenti speciali sommari" in area:
        return MONITORIO
    if "contenzioso civile" in area:
        return CIVILE
    return ""


def _scaglioni() -> list[tuple[float | None, float]]:
    from pct.normative_tables import canonical_table_definitions

    return [(r["max_value"], float(r["amount"])) for r in canonical_table_definitions()["contributo_unificato_civile"]["rows"]]


def _speciale(categoria_tabella: str) -> float:
    from pct.normative_tables import canonical_table_definitions

    righe = canonical_table_definitions()["contributo_unificato_speciali"]["rows"]
    return float(next(r["amount"] for r in righe if r.get("category") == categoria_tabella))


def _scaglione(valore: float) -> tuple[float, str]:
    righe = _scaglioni()
    lettere = "abcdefg"
    for indice, (limite, importo) in enumerate(righe):
        if limite is None or valore <= limite:
            return importo, f"art. 13, comma 1, lett. {lettere[indice]}), D.P.R. 115/2002"
    return righe[-1][1], "art. 13, comma 1, lett. g), D.P.R. 115/2002"


def contributo_dovuto(cat: str, valore: float | None, *, giudice_pace: bool = False) -> Dovuto | None:
    """Il contributo dovuto per la categoria e il valore dichiarato; None se non si può dire con certezza."""
    if cat == VOLONTARIA:
        # Solo se il processo non è esente: le esenzioni (art. 10, commi 1-3, D.P.R. 115/2002; art. 46-bis disp. att.
        # c.c.: tutela, prole, misure di protezione, assenza) si verificano prima con pct/contributo_esenzioni.
        return Dovuto(98.0, "art. 13, comma 1, lett. b), D.P.R. 115/2002", "processo di volontaria giurisdizione")
    if cat == PREVIDENZA:
        return Dovuto(43.0, "art. 13, comma 1, lett. a), D.P.R. 115/2002", "controversia di previdenza e assistenza obbligatorie")
    # Art. 13, comma 2: processi esecutivi (tabella versionata «contributo_unificato_speciali»).
    if cat == ESECUZIONE_IMMOBILIARE:
        return Dovuto(_speciale("esecuzione_immobiliare"), "art. 13, comma 2, D.P.R. 115/2002", "processo esecutivo immobiliare")
    if cat == OPPOSIZIONE_ATTI_ESECUTIVI:
        return Dovuto(_speciale("opposizione_atti_esecutivi"), "art. 13, comma 2, D.P.R. 115/2002", "opposizione agli atti esecutivi")
    if cat == ESECUZIONE_ALTRA:
        if valore and 0 < valore < 2500:
            return Dovuto(_speciale("esecuzione_mobiliare_sotto_2500"), "art. 13, comma 2, D.P.R. 115/2002",
                          f"processo esecutivo mobiliare di valore inferiore a € 2.500 (valore {_euro(float(valore))})")
        if not valore or valore <= 0:
            return None  # sotto o sopra € 2.500 cambia l'importo: senza valore non si sceglie
        return Dovuto(_speciale("altri_processi_esecutivi"), "art. 13, comma 2, D.P.R. 115/2002",
                      f"processo esecutivo diverso dall'immobiliare (valore {_euro(float(valore))}, metà di € 278)")
    if cat not in {CIVILE, LAVORO, MONITORIO} or not valore or valore <= 0:
        return None  # valore non dichiarato: lo scaglione non si sceglie a caso
    importo, norma = _scaglione(float(valore))
    descrizione = f"valore {_euro(float(valore))}"
    if cat == CIVILE:
        return Dovuto(importo, norma, descrizione)
    riduzione = ("controversia di lavoro o di pubblico impiego" if cat == LAVORO
                 else "processo speciale del libro IV, titolo I, c.p.c. (procedimento monitorio)")
    return Dovuto(round(importo / 2, 2), f"{norma} e comma 3", f"{descrizione}, metà per {riduzione} ({_euro(importo)} / 2)")


def dovuti_possibili(cat: str) -> list[Dovuto]:
    """Senza valore dichiarato nel fascicolo: gli importi che il rito ammette, uno per scaglione (art. 13, commi 1 e 3)."""
    if cat in {VOLONTARIA, PREVIDENZA, ESECUZIONE_IMMOBILIARE, OPPOSIZIONE_ATTI_ESECUTIVI}:
        return [d for d in [contributo_dovuto(cat, None)] if d]
    if cat == ESECUZIONE_ALTRA:
        return [d for d in (contributo_dovuto(cat, 1000.0), contributo_dovuto(cat, 3000.0)) if d]
    if cat not in {CIVILE, LAVORO, MONITORIO}:
        return []
    possibili = []
    limite_precedente = 0.0
    for limite, _importo in _scaglioni():
        valore = (limite if limite is not None else limite_precedente + 1)
        dovuto = contributo_dovuto(cat, valore)
        if dovuto:
            fascia = f"scaglione fino a {_euro(limite)}" if limite is not None else f"scaglione oltre {_euro(limite_precedente)}"
            possibili.append(Dovuto(dovuto.importo, dovuto.norma, dovuto.spiegazione.replace(f"valore {_euro(valore)}", fascia)))
        limite_precedente = limite or limite_precedente
    return possibili


def confronta(versati: Iterable[Any], dovuto: Dovuto | None, *, cat: str = "") -> dict[str, Any]:
    """Il confronto fra gli importi letti nelle ricevute e il dovuto, con il dubbio da sollevare se c'è.

    Senza valore dichiarato (``dovuto`` None) l'importo versato è certo se coincide con uno degli importi che il rito
    ammette (``dovuti_possibili``): è il contributo di quello scaglione; altrimenti resta indeterminato.
    """
    letti = sorted({round(float(v), 2) for v in versati if v not in (None, "") and float(v) > 0})
    contributi = [v for v in letti if v != ANTICIPAZIONE_FORFETTARIA]
    if dovuto is None:
        dovuto = next((d for d in dovuti_possibili(cat) if d.importo in letti), None)
        if dovuto is None:
            return {"esito": "indeterminato", "versato": None, "dovuto": None, "dettaglio": ""}
    if dovuto.importo in letti:
        altri = [v for v in letti if v != dovuto.importo]
        nota = ""
        if ANTICIPAZIONE_FORFETTARIA in altri:
            nota = f" {_euro(ANTICIPAZIONE_FORFETTARIA)} è l'anticipazione forfettaria ({NORMA_ANTICIPAZIONE})."
        return {"esito": "coincide", "versato": dovuto.importo, "dovuto": dovuto.importo, "norma": dovuto.norma,
                "dettaglio": f"Versato {_euro(dovuto.importo)}, pari al dovuto: {dovuto.spiegazione} ({dovuto.norma}).{nota}"}
    if not contributi or max(contributi) < dovuto.importo:
        versato = max(contributi) if contributi else 0.0
        solo27 = ANTICIPAZIONE_FORFETTARIA in letti and not contributi
        return {"esito": "insufficiente", "versato": versato, "dovuto": dovuto.importo, "norma": dovuto.norma,
                "dettaglio": ("Contributo forse non versato o versato in misura insufficiente: "
                              + (f"la ricevuta riporta {_euro(ANTICIPAZIONE_FORFETTARIA)}, che è l'anticipazione forfettaria "
                                 f"({NORMA_ANTICIPAZIONE}), non il contributo; " if solo27 else f"versati {_euro(versato)}; ")
                              + f"dovuti {_euro(dovuto.importo)} per {dovuto.spiegazione} ({dovuto.norma}). "
                              "Verificare l'integrazione del versamento, salvo un'esenzione dichiarata nelle conclusioni "
                              "dell'atto introduttivo (art. 10, comma 6, D.P.R. 115/2002).")}
    return {"esito": "eccedente", "versato": max(contributi), "dovuto": dovuto.importo, "norma": dovuto.norma,
            "dettaglio": (f"Versati {_euro(max(contributi))}, più del dovuto ({_euro(dovuto.importo)} per {dovuto.spiegazione}, "
                          f"{dovuto.norma}): verificare il valore dichiarato o il rito.")}


__all__ = ["ANTICIPAZIONE_FORFETTARIA", "CIVILE", "ESECUZIONE_ALTRA", "ESECUZIONE_IMMOBILIARE", "OPPOSIZIONE_ATTI_ESECUTIVI", "Dovuto", "dovuti_possibili", "LAVORO", "MONITORIO", "PREVIDENZA", "VOLONTARIA",
           "categoria", "confronta", "contributo_dovuto"]
