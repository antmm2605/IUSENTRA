"""La sentenza chiude il grado? Lettura del solo testo, senza dominio né Flask.

Serve a proporre all'avvocato la definizione del fascicolo, mai ad applicarla:
la conferma resta un atto dello studio. Il testo dice soltanto se il
provvedimento è una sentenza che decide la causa nel grado (art. 132 c.p.c.;
art. 88 c.p.a. per il processo amministrativo). Non dice se è passata in
giudicato: l'impugnazione resta possibile nei termini degli artt. 325-327
c.p.c. (art. 92 c.p.a. per il processo amministrativo), e la proposta lo
ricorda nel motivo.

Non nasce alcuna proposta quando il testo indica una pronuncia che lascia
proseguire il giudizio: sentenza non definitiva o parziale (art. 279, secondo
comma, n. 4 c.p.c.), separata ordinanza per la prosecuzione, rimessione in
istruttoria o sul ruolo, riserva della decisione, cassazione con rinvio
(art. 384 c.p.c.).
"""

from __future__ import annotations

import re
from typing import Any

from pct.spese_liquidate_lettura import compatta_testo

VERSIONE = "sentenza-conclusiva.v2"

_PQM = re.compile(r"(?<![\w.])p\s*\.?\s*q\s*\.?\s*m\b\.?", re.IGNORECASE)
_PER_QUESTI_MOTIVI = re.compile(r"\bper\s+questi\s+motivi\b", re.IGNORECASE)
# Le intestazioni scrivono spesso il titolo con le lettere spaziate («S E N T E N Z A»): una sola spaziatura
# facoltativa fra le lettere, quantificatori limitati (sentenza del 08/10/2026 non riconosciuta).
_SENTENZA = re.compile(r"\bs ?e ?n ?t ?e ?n ?z ?a\b", re.IGNORECASE)

# Epigrafe: la pronuncia si dichiara non definitiva o parziale già nel titolo.
_INTESTAZIONE_NON_CONCLUSIVA = re.compile(r"\bsentenza\s+(?:non\s+definitiva|parziale)\b", re.IGNORECASE)

# Dispositivo: ogni formula con il motivo che l'avvocato legge.
_DISPOSITIVO_NON_CONCLUSIVO: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bnon\s+definitiv\w*", re.IGNORECASE), "sentenza non definitiva (art. 279 c.p.c.)"),
    (re.compile(r"\bsentenza\s+parziale\b", re.IGNORECASE), "sentenza parziale"),
    (re.compile(r"\bseparat[ao]\s+ordinanza\b", re.IGNORECASE), "prosecuzione disposta con separata ordinanza"),
    (re.compile(r"\bprosecuzione\s+del(?:l[ao]?)?\s*(?:giudizio|processo|causa|istruttoria)\b", re.IGNORECASE), "prosecuzione del giudizio"),
    (re.compile(r"\bprosieguo\b", re.IGNORECASE), "prosecuzione del giudizio"),
    (re.compile(r"\brimett\w*\s+(?:la\s+causa|il\s+giudizio|gli\s+atti|le\s+parti|il\s+processo)\b", re.IGNORECASE), "rimessione della causa"),
    (re.compile(r"\brimett\w*\s+(?:\w+\s+){0,3}(?:in\s+istruttoria|sul\s+ruolo)\b", re.IGNORECASE), "rimessione in istruttoria o sul ruolo"),
    (re.compile(r"\briserv\w*\s+(?:la\s+|ogni\s+(?:altra\s+|ulteriore\s+)?)?(?:decisione|statuizione|pronuncia)\b", re.IGNORECASE), "decisione riservata"),
    (re.compile(r"\bcon\s+rinvio\b", re.IGNORECASE), "cassazione con rinvio (art. 384 c.p.c.)"),
)

_DECISIONE = re.compile(
    r"\bdefinitivamente\s+pronunciando\b|\b(?:accoglie|rigetta|respinge|dichiara|condanna|annulla|accerta|revoca|"
    r"conferma|riforma|compensa|omologa|assolve|estingue|cassa)\b",
    re.IGNORECASE,
)
_COMPENSATE = re.compile(r"\bcompens\w*\s+(?:\w+\s+){0,4}spese\b|\bspese\s+(?:\w+\s+){0,4}compensat\w*", re.IGNORECASE)


def _grado(intestazione: str) -> str:
    testo = intestazione.casefold()
    if re.search(r"corte\s+(?:suprema\s+)?di\s+cassazione|suprema\s+corte", testo):
        return "cassazione"
    if re.search(r"tribunale\s+amministrativo|\bt\.?\s?a\.?\s?r\.?\b|consiglio\s+di\s+stato", testo):
        return "amministrativo"
    if re.search(r"corte\s+d['’]\s*appello|corte\s+di\s+appello|in\s+grado\s+d['’]\s*appello", testo):
        return "appello"
    return "merito"


def avvertenza_impugnazione(grado: str) -> str:
    """Il motivo ricorda che la conferma non attesta il giudicato."""
    if grado == "amministrativo":
        termini = "art. 92 c.p.a."
    elif grado == "cassazione":
        return "Pronuncia di legittimità senza rinvio: la conferma definisce il fascicolo."
    else:
        termini = "artt. 325-327 c.p.c."
    return ("Prima di confermare verificare che non sia stata proposta impugnazione o che ne siano decorsi i termini "
            f"({termini}): la definizione non attesta il passaggio in giudicato.")


def valuta_sentenza(testo: str) -> dict[str, Any]:
    """`conclusiva` vero solo per una sentenza con un unico dispositivo che decide la causa nel grado."""
    compatto = compatta_testo(testo)
    esito: dict[str, Any] = {"conclusiva": False, "versione": VERSIONE, "dispositivo": "", "compensate": False, "grado": ""}
    if not _SENTENZA.search(compatto[:6000]):
        return {**esito, "motivo": "Documento non riconosciuto come sentenza."}
    if _INTESTAZIONE_NON_CONCLUSIVA.search(compatto[:3000]):
        return {**esito, "motivo": "Sentenza non definitiva o parziale: il giudizio prosegue."}
    # Un solo dispositivo: due «P.Q.M.» indicano citazioni o più provvedimenti nello stesso file.
    marcatori = list(_PQM.finditer(compatto)) or list(_PER_QUESTI_MOTIVI.finditer(compatto))
    if len(marcatori) != 1:
        return {**esito, "motivo": "Dispositivo unico non individuato: verifica manuale."}
    intestazione = compatto[: marcatori[0].start()][:4000]
    dispositivo = compatto[marcatori[0].end():]
    grado = _grado(intestazione)
    esito.update(dispositivo=dispositivo, grado=grado, compensate=bool(_COMPENSATE.search(dispositivo)))
    for regola, motivo in _DISPOSITIVO_NON_CONCLUSIVO:
        if regola.search(dispositivo):
            return {**esito, "motivo": f"Il dispositivo non chiude il giudizio: {motivo}."}
    if not _DECISIONE.search(dispositivo[:1500]):
        return {**esito, "motivo": "Decisione della causa non dimostrata dal dispositivo."}
    return {**esito, "conclusiva": True, "motivo": "Sentenza che decide la causa nel grado. " + avvertenza_impugnazione(grado)}


__all__ = ["VERSIONE", "avvertenza_impugnazione", "valuta_sentenza"]
