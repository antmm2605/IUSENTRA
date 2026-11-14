"""Il deposito e il numero di ruolo che risultano dagli atti, quando la scheda del fascicolo non li porta.

Il deposito telematico si esegue con la PEC dell'avvocato all'ufficio (art. 13 D.M. 44/2011; art. 196-quater disp.
att. c.p.c.): la «copia non crittografata» del messaggio di deposito, conservata nel fascicolo, prova che l'atto è
stato inviato in quella data e quale atto conteneva (si perfeziona con la ricevuta di avvenuta consegna). Un
deposito successivo nella stessa causa (deposito integrativo, produzione di documenti) porta nell'oggetto e nel
DatiAtto.xml il numero di ruolo assegnato dalla cancelleria («RG: 14848/2025»): quel numero è certo quanto
l'iscrizione stessa.

Collaudo 10/11/2026 (Tribunale di Firenze, volontaria giurisdizione): «N. REGISTRO n.d.» e «nessun atto giudiziario
risulta ancora notificato o depositato», mentre il ricorso era stato depositato il 26/08/2025 e il deposito
integrativo del 02/09/2025 indicava RG 14848/2025.

Funzioni pure: ricevono i documenti catalogati e i fatti dell'archivio (dizionari).
"""

from __future__ import annotations

import re
from typing import Any, Iterable

UTILI = {"verificata", "corretta"}
_RE_COPIA_DEPOSITO = re.compile(r"^\s*(?:copia\s+non\s+crittografata\s+)?deposito\s+telematico\s*:", re.I)
_RE_RUOLO = re.compile(r"^\d{1,7}/\d{4}$")
_RE_DEPOSITO_NEL_CONTESTO = re.compile(r"deposito\s+telematico", re.I)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def ruolo_dagli_atti(fonti: Iterable[dict[str, Any]]) -> str:
    """Il numero di ruolo «numero/anno» se tutti i fatti verificati dell'archivio indicano lo stesso; altrimenti vuoto.

    Si usano solo i fatti ``ruolo`` verificati o corretti dall'avvocato: un numero solo plausibile (per esempio il
    numero del decreto «n. 1109/2024» accanto al ruolo) non basta, e due numeri verificati diversi non si scelgono.
    Vale solo il numero letto nel messaggio di deposito telematico dello studio all'ufficio: il ruolo di una sentenza
    prodotta come precedente o citata in un atto è di un'altra causa.
    """
    valori = {_testo(f.get("valore")) for f in fonti or () if f.get("categoria") == "ruolo" and f.get("verifica") in UTILI
              and _RE_RUOLO.match(_testo(f.get("valore"))) and _RE_DEPOSITO_NEL_CONTESTO.search(_testo(f.get("contesto")))}
    return next(iter(valori)) if len(valori) == 1 else ""


def depositi_dalle_copie_pec(documenti: Iterable[dict[str, Any]], fonti: Iterable[dict[str, Any]] = ()) -> list[dict[str, str]]:
    """I depositi telematici inviati che risultano dalle copie dei messaggi di deposito conservate nel fascicolo.

    Una voce per messaggio di deposito (la copia «non crittografata» e la busta dello stesso invio sono lo stesso
    deposito): atto depositato (dall'oggetto), data (dal fatto «deposito» letto nel messaggio o, in mancanza, dalla
    data del documento), numero di ruolo indicato nell'oggetto. Stato: inviato, non accettato (manca la ricevuta).
    """
    fonti = list(fonti or ())
    esito: dict[str, dict[str, str]] = {}
    for documento in documenti or ():
        nome = _testo(documento.get("nome"))
        if not _RE_COPIA_DEPOSITO.search(nome) and _testo(documento.get("etichetta")).lower() != "pec di deposito telematico":
            continue
        oggetto = _RE_COPIA_DEPOSITO.sub("", nome)
        ruolo = re.search(r"\bRG\s*:?\s*(\d{1,7})\s*[-/]\s*(\d{4})", oggetto)
        atto = _testo(re.sub(r"\[[^\]]*\]|\bRG\s*:?\s*\d{1,7}\s*[-/]\s*\d{4}|\.(?:eml|EML)$", "", oggetto)).strip(" -")
        identificativo = re.search(r"\[RefID_[^\]]+\]", nome)
        chiave = identificativo.group(0) if identificativo else atto
        date = sorted(_testo(f.get("valore"))[:10] for f in fonti
                      if f.get("oggetto_id") == documento.get("id") and f.get("campo") == "deposito" and _testo(f.get("valore")))
        giorno = date[0] if date else _testo(documento.get("data"))[:10]
        voce = esito.setdefault(chiave, {"atto": atto, "data": giorno, "rg": "", "documento_id": _testo(documento.get("id")), "stato": "inviato"})
        if ruolo:
            voce["rg"] = f"{int(ruolo.group(1))}/{ruolo.group(2)}"
        if date and (not voce["data"] or date[0] < voce["data"]):
            voce["data"] = date[0]
    return sorted(esito.values(), key=lambda voce: voce["data"])


__all__ = ["depositi_dalle_copie_pec", "ruolo_dagli_atti"]
