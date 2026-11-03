"""Crediti dalla sentenza: un credito una volta sola e registrazione automatica solo se certa.

Modulo puro (nessun Flask, nessun repository). Due regole decise dall'avvocato
titolare il 02/11/2026:

1. **Niente doppioni.** La stessa sentenza può arrivare nel fascicolo da più vie
   (documento del fascicolo, allegato PEC, analisi ripetuta): ogni via produce un
   controllo economico con i suoi eventi. Un credito è lo stesso quando coincidono
   natura (art. 91 o art. 93 c.p.c.), beneficiario e importo e la fonte è la stessa
   (impronta SHA-256 del documento, art. 20 CAD) oppure lo stesso capo spese letto.
   Il gruppo si mostra una volta; la decisione dell'avvocato prevale sempre.

2. **Automatico solo quando certo.** Definizione e credito hanno ciascuno la
   propria certezza (decisione dell'avvocato del 03/11/2026: il processo deve
   essere automatico). Il fascicolo si definisce senza conferma quando la
   sentenza decide la causa nel grado (art. 132 c.p.c.; art. 88 c.p.a.; regole
   di `pct.sentenza_conclusiva`) e l'identità del procedimento coincide (R.G.,
   cliente, ufficio, codice fiscale: `pct.fascicolo_sentenza_archiviazione`),
   anche con spese compensate (art. 92 c.p.c.). Il credito si registra senza
   conferma solo se importo e beneficiario si leggono senza ambiguità nel
   dispositivo (`valuta_certezza`): un solo credito, un solo importo liquidato,
   uguale in due letture indipendenti, parte condannata nominata ed estranea al
   cliente. Mai automatico con sentenza non definitiva o parziale, identità non
   coincidente, fascicolo sospeso o una decisione contraria dell'avvocato; il
   credito mai con importo ambiguo, più dispositivi, compensazione parziale o
   gratuito patrocinio. Tutto si annulla con «Annulla».
"""

from __future__ import annotations

import re
from typing import Any

from pct.spese_liquidate_lettura import MONEY_AMOUNT_PATTERN, compatta_testo, parse_importo

VERSIONE = "sentenza-automatica.v2"
AUTORE = "automatico dalla sentenza"
STATO_DOPPIONE = "duplicato"
CREDITI: dict[str, tuple[str, str]] = {
    "apri_credito_cliente": ("Spese liquidate a favore del cliente", "art. 91 c.p.c."),
    "apri_credito_avvocato_antistatario": ("Spese distratte al difensore antistatario", "art. 93 c.p.c."),
}
_PRIORITA_STATO = {"confirmed": 0, "rejected": 1, "to_review": 2}

_CONDANNA = re.compile(r"\bcondann\w*\b", re.IGNORECASE)
_VERSO_PAGAMENTO = re.compile(
    r"\b(?:al\s+pagamento|alla\s+rifusione|a\s+rifondere|a\s+rimborsare|al\s+rimborso|a\s+pagare|alle\s+spese|in\s+solido)\b",
    re.IGNORECASE,
)
_SPESE = re.compile(r"\bspese\b", re.IGNORECASE)
_DISTRAZIONE = re.compile(r"\bdistra(?:e|tte|zione|endo)\w*|\bantistatari\w*", re.IGNORECASE)
_PARZIALE = re.compile(r"\bparzialmente\s+compensat\w*|\bcompens\w*\s+(?:per\s+(?:la\s+)?(?:met[aà]|un\s+terzo|\w+\s+quart\w*)|parzialmente)",
                       re.IGNORECASE)
_GRATUITO = re.compile(r"\bgratuito\s+patrocinio\b|\bpatrocinio\s+a\s+spese\s+dello\s+stato\b", re.IGNORECASE)
_VALUTA = r"(?:€|eur\b|euro\b)"
_LIQUIDA_IMPORTO = re.compile(
    r"\bliquid\w*\b.{0,80}?(?:" + _VALUTA + r"\s*(?P<prima>" + MONEY_AMOUNT_PATTERN + r")|(?<![\d.,])(?P<dopo>"
    + MONEY_AMOUNT_PATTERN + r")\s*" + _VALUTA + r")",
    re.IGNORECASE | re.DOTALL,
)
_PAROLE_VUOTE = frozenset({"srl", "spa", "sas", "snc", "societa", "della", "delle", "dello", "degli", "del", "con", "per",
                           "sig", "sigra", "signor", "signora", "dott", "avv", "parte", "nonche"})


def _testo(valore: Any) -> str:
    return str(getattr(valore, "value", valore) or "").strip()


def _parole(testo: str) -> set[str]:
    from pct.email_client import _tokenizza_email_match

    return {p for p in _tokenizza_email_match(testo or "") if p not in _PAROLE_VUOTE}


def _importo(valore: Any) -> float | None:
    try:
        return round(float(valore), 2) if valore is not None else None
    except (TypeError, ValueError):
        return None


def _capo(audit: dict[str, Any]) -> str:
    spese = ((audit.get("audit") or {}).get("sentenza") or {}).get("spese_liquidate") or {}
    return re.sub(r"\s+", " ", _testo(spese.get("testo_capo_spese"))).casefold()


# --------------------------------------------------------------------------- #
# 1. Niente doppioni                                                           #
# --------------------------------------------------------------------------- #


def gruppi_crediti(eventi: list[dict[str, Any]], audits: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Raggruppa gli eventi di credito che sono lo stesso credito (fonte o capo spese, natura, beneficiario, importo)."""
    per_audit = {_testo(a.get("id")): a for a in audits}
    crediti = [e for e in eventi if _testo(e.get("event_type")) in CREDITI and _testo(e.get("status")) != STATO_DOPPIONE]
    genitore = list(range(len(crediti)))

    def radice(i: int) -> int:
        while genitore[i] != i:
            genitore[i] = genitore[genitore[i]]
            i = genitore[i]
        return i

    viste: dict[tuple[Any, ...], int] = {}
    for indice, evento in enumerate(crediti):
        audit = per_audit.get(_testo(evento.get("source_id"))) or {}
        natura = (_testo(evento.get("event_type")), _testo(evento.get("beneficiary_type")), _importo(evento.get("amount")))
        chiavi = [("evento", _testo(evento.get("id")))]
        sha = _testo(audit.get("document_hash_sha256")).lower()
        if sha:
            chiavi.append(("sha256", sha, *natura))
        if _capo(audit) and natura[2] is not None:
            chiavi.append(("capo", _capo(audit), *natura))
        for chiave in chiavi:
            if chiave in viste:
                genitore[radice(indice)] = radice(viste[chiave])
            else:
                viste[chiave] = indice
    gruppi: dict[int, list[dict[str, Any]]] = {}
    for indice, evento in enumerate(crediti):
        gruppi.setdefault(radice(indice), []).append(evento)
    return [sorted(g, key=_ordine_rappresentante) for g in gruppi.values()]


def _ordine_rappresentante(evento: dict[str, Any]) -> tuple[Any, ...]:
    # La decisione dell'avvocato prevale; a parità, l'evento nato per primo.
    return (_PRIORITA_STATO.get(_testo(evento.get("status")), 3), _testo(evento.get("created_at")), _testo(evento.get("id")))


def fondi_doppioni(eventi: list[dict[str, Any]], audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Gli eventi con un solo rappresentante per credito; gli altri eventi restano come sono."""
    gruppi = gruppi_crediti(eventi, audits)
    rappresentanti = {}
    for gruppo in gruppi:
        primo = dict(gruppo[0])
        primo["duplicati"] = [_testo(e.get("id")) for e in gruppo[1:]]
        rappresentanti[_testo(primo.get("id"))] = primo
    fusi = {_testo(e.get("id")) for g in gruppi for e in g[1:]}
    esito = []
    for evento in eventi:
        chiave = _testo(evento.get("id"))
        if chiave in fusi or (_testo(evento.get("event_type")) in CREDITI and _testo(evento.get("status")) == STATO_DOPPIONE):
            continue
        esito.append(rappresentanti.get(chiave, evento))
    return esito


def doppioni_da_chiudere(eventi: list[dict[str, Any]], audits: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Riconvalida: (doppione, rappresentante) per i soli doppioni ancora da confermare; le decisioni restano."""
    coppie = []
    for gruppo in gruppi_crediti(eventi, audits):
        rappresentante = _testo(gruppo[0].get("id"))
        coppie.extend((_testo(e.get("id")), rappresentante) for e in gruppo[1:] if _testo(e.get("status")) == "to_review")
    return coppie


# --------------------------------------------------------------------------- #
# 2. Automatico solo quando certo                                              #
# --------------------------------------------------------------------------- #


def parte_condannata(dispositivo: str) -> str:
    """Il tratto tra «condanna» e «al pagamento / alla rifusione» nel capo che parla di spese."""
    testo = compatta_testo(dispositivo)
    for condanna in _CONDANNA.finditer(testo):
        finestra = testo[condanna.end(): condanna.end() + 260]
        verso = _VERSO_PAGAMENTO.search(finestra)
        if verso and _SPESE.search(finestra[verso.start(): verso.start() + 160]):
            return finestra[: verso.start()].strip(" ,;:")
    return ""


def importi_liquidati(dispositivo: str) -> set[float]:
    """Gli importi che seguono ogni «liquida/liquidate» del dispositivo: più di uno è ambiguo."""
    importi = set()
    for trovato in _LIQUIDA_IMPORTO.finditer(compatta_testo(dispositivo)):
        valore = parse_importo(trovato.group("prima") or trovato.group("dopo"))
        if valore is not None:
            importi.add(round(valore, 2))
    return importi


def valuta_certezza(*, dispositivo: str, importo_dispositivo: Any, fascicolo: Any, audits: list[dict[str, Any]],
                    eventi: list[dict[str, Any]]) -> dict[str, Any]:
    """`certo` vero solo se credito e beneficiario si leggono senza ambiguità; `motivi` spiega il contrario.

    Presuppone una verifica della sentenza già superata (conclusiva, identità, codice fiscale):
    qui si controllano il controllo economico e il dispositivo.
    """
    motivi: list[str] = []
    stato = _testo(getattr(fascicolo, "stato", "")).upper()
    if stato == "SOSPESO":
        motivi.append("Fascicolo sospeso: la decisione resta dell'avvocato.")
    if not audits or not all(a.get("safe_to_attach") for a in audits):
        motivi.append("Controllo d'identità economico (R.G., cliente, ufficio, codice fiscale) non coincidente.")
    gruppi = [g for g in gruppi_crediti(eventi, audits)]
    if len(gruppi) != 1:
        motivi.append("Nessun credito letto nel capo spese." if not gruppi else "Più crediti letti nella stessa sentenza.")
        return {"certo": False, "motivi": motivi}
    gruppo = gruppi[0]
    rappresentante = gruppo[0]
    tipo = _testo(rappresentante.get("event_type"))
    importo = _importo(rappresentante.get("amount"))
    if any(_testo(e.get("status")) == "rejected" for e in gruppo):
        motivi.append("Credito già respinto dall'avvocato.")
    if importo is None or importo <= 0:
        motivi.append("Importo del credito non determinato.")
    elif _importo(importo_dispositivo) != importo:
        motivi.append("Importo del dispositivo diverso da quello del controllo economico.")
    liquidati = importi_liquidati(dispositivo)
    if len(liquidati) > 1:
        motivi.append("Più importi liquidati nel dispositivo.")
    if _PARZIALE.search(dispositivo):
        motivi.append("Spese compensate in parte.")
    if _GRATUITO.search(dispositivo):
        motivi.append("Gratuito patrocinio: compenso liquidato con decreto separato.")
    distratte = bool(_DISTRAZIONE.search(dispositivo))
    if (tipo == "apri_credito_avvocato_antistatario") != distratte:
        motivi.append("Beneficiario del credito non coerente con il dispositivo.")
    condannata = _parole(parte_condannata(dispositivo))
    cliente = _parole(_testo(getattr(fascicolo, "nome_cliente", "")))
    controparte = _parole(_testo(getattr(fascicolo, "controparte", "")))
    if not condannata or not controparte or not (condannata & controparte) or (condannata & cliente):
        motivi.append("Parte condannata alle spese non riconosciuta con certezza come controparte del cliente.")
    if motivi:
        return {"certo": False, "motivi": motivi}
    etichetta, norma = CREDITI[tipo]
    return {"certo": True, "motivi": [], "gruppo": gruppo, "evento": rappresentante, "tipo": tipo,
            "importo": importo, "etichetta": etichetta, "norma": norma}


__all__ = ["AUTORE", "CREDITI", "STATO_DOPPIONE", "VERSIONE", "doppioni_da_chiudere", "fondi_doppioni",
           "gruppi_crediti", "importi_liquidati", "parte_condannata", "valuta_certezza"]
