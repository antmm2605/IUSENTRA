"""Chi ha ricevuto la notifica, per gli effetti giuridici verso la pubblica amministrazione.

Due effetti della stessa notifica della sentenza dipendono da destinatari diversi:

* **termine breve per impugnare**: decorre dalla notifica al procuratore costituito (artt. 285 e 170 c.p.c.); per
  l'amministrazione dello Stato difesa dall'Avvocatura dello Stato la sentenza si notifica presso l'ufficio
  dell'Avvocatura (art. 11 R.D. 1611/1933). Se l'amministrazione è stata in giudizio con propri dipendenti
  (art. 417-bis c.p.c.) il destinatario è l'amministrazione stessa: la relata non lo dice, quindi resta un dubbio;
* **120 giorni dell'art. 14 D.L. 669/1996**: decorrono dalla notifica del titolo esecutivo all'amministrazione
  debitrice, che deve predisporre il pagamento; la notifica alla sola Avvocatura non li fa decorrere.

Il ruolo di ogni destinatario si legge dalla relata (art. 3-bis, comma 5, L. 53/1994: nome, qualità, indirizzo e
pubblico elenco da cui è estratto) e dal dominio della casella. Modulo puro.
"""

from __future__ import annotations

import re

AVVOCATURA = "avvocatura_stato"
DIFENSORE = "difensore"
AMMINISTRAZIONE = "amministrazione"
ALTRO = "altro"
RUOLI = (AVVOCATURA, DIFENSORE, AMMINISTRAZIONE, ALTRO)

_VOCE = re.compile(r"(?m)^\s*\d+\)\s*-\s*")
_INDIRIZZO = re.compile(r"indirizzo\s+(?:pec|di\s+posta\s+elettronica\s+certificata)\s*:?\s*([^\s;,<>()]+@[^\s;,<>()]+)", re.I)
_AVVOCATURA = re.compile(r"\bavvocatura\s+(?:generale|distrettuale)?\s*(?:dello|di)\s+stato\b", re.I)
_DIFENSORE = re.compile(r"\b(?:difensore|procuratore\s+costituito|domiciliat[oa]\s+presso)\b", re.I)
_PA = re.compile(
    r"\b(?:minister[oi]|ufficio\s+scolastico|agenzia|regione|provincia|comune|universit|istituto|ente|azienda\s+sanitaria|"
    r"inps|inail|prefettura|questura|amministrazione)\b|pubblico\s+elenco\s*:?\s*IPA\b", re.I)


def voci_relata(blocco_destinatari: str) -> dict[str, str]:
    """Indirizzo → testo della voce del destinatario nella relata («1) - MINISTERO ... indirizzo pec: x ...»)."""
    voci: dict[str, str] = {}
    for parte in _VOCE.split(blocco_destinatari or "")[1:]:
        for indirizzo in _INDIRIZZO.findall(parte):
            voci[indirizzo.strip(".;,").casefold()] = " ".join(parte.split())
    return voci


def ruolo_destinatario(indirizzo: str, voce: str) -> str:
    """Avvocatura dello Stato, difensore costituito, amministrazione o altro."""
    dominio = str(indirizzo or "").rsplit("@", 1)[-1].casefold()
    if dominio.endswith("avvocaturastato.it") or _AVVOCATURA.search(voce or ""):
        return AVVOCATURA
    if _DIFENSORE.search(voce or ""):
        return DIFENSORE
    if _PA.search(voce or ""):
        return AMMINISTRAZIONE
    return ALTRO


def effetti_verso_pa(destinatari: list[dict] | None) -> tuple[str, str]:
    """(motivo per cui il termine breve non decorre, motivo per cui i 120 giorni non decorrono); vuoti se decorrono.

    ``destinatari``: le consegne provate, ciascuna con ``indirizzo`` e ``ruolo``.
    """
    ruoli = {str(d.get("ruolo") or ALTRO) for d in destinatari or ()}
    elenco = ", ".join(sorted(str(d.get("indirizzo") or "") for d in destinatari or ())) or "nessun destinatario"
    breve = "" if ruoli & {AVVOCATURA, DIFENSORE} else (
        f"La sentenza risulta consegnata a {elenco}, ma non al difensore costituito dell'amministrazione "
        "(Avvocatura dello Stato): il termine breve decorre dalla notifica al procuratore costituito (artt. 285 e 170 "
        "c.p.c.; art. 11 R.D. 1611/1933). Verificare se l'amministrazione è stata in giudizio con propri dipendenti "
        "(art. 417-bis c.p.c.).")
    centoventi = "" if AMMINISTRAZIONE in ruoli else (
        f"Il titolo risulta consegnato a {elenco}, ma non all'amministrazione debitrice: i 120 giorni decorrono dalla "
        "notifica del titolo esecutivo all'amministrazione obbligata, che deve completare le procedure di pagamento "
        "(art. 14, comma 1, D.L. 669/1996), non alla sola Avvocatura dello Stato, la cui rappresentanza e domiciliazione "
        "riguardano l'attività giudiziale (Cass. civ., sez. V, 19 dicembre 2003, n. 19512, sul precetto). Notificare il "
        "titolo all'amministrazione prima del precetto.")
    return breve, centoventi


_SEDE = re.compile(r"pro[\s-]*tempore\s+(?P<sede>.+?)\s+mediante\s+inoltro", re.I)


def descrizione_destinatario(destinatario: dict) -> dict[str, str]:
    """Denominazione, sede e PEC dalla voce della relata («MINISTERO ... C.F: ... in persona ... viale Trastevere,
    76 - Roma mediante inoltro all'indirizzo pec: ...»)."""
    voce = " ".join(str(destinatario.get("voce") or "").split())
    denominazione = re.split(r"\s+C\.?\s?F\.?\s*:|\s+in\s+persona\b|\s+mediante\s+inoltro", voce, maxsplit=1)[0].strip(" ,;")
    sede = _SEDE.search(voce)
    sede_letta = re.sub(r"\((?:difensore|domiciliatari)[^)]*\)", " ", sede.group("sede")) if sede else ""
    return {"denominazione": denominazione, "sede": " ".join(sede_letta.split()).strip(" ,;"),
            "pec": str(destinatario.get("indirizzo") or ""), "ruolo": str(destinatario.get("ruolo") or ALTRO)}


__all__ = ["ALTRO", "AMMINISTRAZIONE", "AVVOCATURA", "DIFENSORE", "RUOLI", "descrizione_destinatario", "effetti_verso_pa",
           "ruolo_destinatario", "voci_relata"]
