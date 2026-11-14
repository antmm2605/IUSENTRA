"""Gli eventi che rendono «fatto» un adempimento: depositi con la loro ricevuta, comunicazioni di cancelleria.

- deposito: la busta telematica ha oggetto «DEPOSITO TELEMATICO: <atto>» (art. 14 D.M. 44/2011) e si perfeziona
  con la ricevuta di avvenuta consegna (art. 196-sexies disp. att. c.p.c.); vale anche il deposito registrato
  nel fascicolo con l'accettazione della cancelleria;
- comunicazione: il biglietto di cancelleria (art. 136 c.p.c.) dice quale provvedimento comunica e quando
  («Notificato alla PEC il …»): da lì decorrono i termini assegnati «dalla comunicazione».
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .modello import Atto
from .testo import date_nel_testo, giorno, pulito, semplice


def _intestazione(testo: str) -> tuple[str, str]:
    """(oggetto, data ISO) dall'intestazione del messaggio PEC esportato."""
    oggetto = re.search(r"(?im)^Oggetto:\s*(.+)$", testo[:1500])
    data = re.search(r"(?im)^Data:\s*(.+)$", testo[:1500])
    trovate = date_nel_testo(data.group(1)) if data else []
    giorno_iso = trovate[0][2].isoformat() if trovate else ""
    m = re.search(r"(\d{1,2}) (jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w* (\d{4})", data.group(1), re.I) if data and not trovate else None
    if m:
        mesi = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        giorno_iso = f"{m.group(3)}-{mesi.index(m.group(2).lower()) + 1:02d}-{int(m.group(1)):02d}"
    return (pulito(oggetto.group(1)) if oggetto else ""), giorno_iso


@dataclass
class DepositoEseguito:
    titolo: str
    data: str
    fonte_id: str
    accettato: bool = False
    stato_registro: str = ""
    data_esito: str = ""
    documenti_ids: tuple[str, ...] = ()
    consegna: str = ""
    prova_consegna: str = ""
    nome_atto: str = ""
    busta: str = ""


@dataclass
class Comunicazione:
    data: str
    fonte_id: str
    nomi_allegati: list[str]
    testo: str


def depositi_eseguiti(atti: Iterable[Atto], depositi: Iterable[dict[str, Any]]) -> list[DepositoEseguito]:
    esito: list[DepositoEseguito] = []
    for deposito in depositi:
        data = pulito(deposito.get("data") or deposito.get("timestamp"))[:10]
        if giorno(data):
            stato = semplice(deposito.get("stato"))
            ricevute = {(pulito(r[0]), pulito(r[1])) for r in deposito.get("consegne_archivio") or ()
                        if isinstance(r, (tuple, list)) and len(r) == 2 and giorno(r[0]) and pulito(r[1])}
            consegna, prova = next(iter(ricevute)) if len(ricevute) == 1 else ("", "")
            esito.append(DepositoEseguito(
                pulito(deposito.get("tipo_atto")), data, pulito(deposito.get("id")),
                accettato=stato == "accettato_cancelleria", stato_registro=stato,
                data_esito=pulito(deposito.get("data_accettazione")) if stato == "accettato_cancelleria" else "",
                documenti_ids=tuple(deposito.get("documenti_ids") or ()), consegna=consegna, prova_consegna=prova,
                nome_atto=pulito(deposito.get("nome_atto_principale")),
                busta=pulito(deposito.get("id_deposito_esterno")),
            ))
    for atto in atti:
        oggetto, data = _intestazione(atto.testo)
        # Il nome dell'EML consente di chiedere il riscontro anche se manca la lettura
        # dell'intestazione. In quel caso l'evento non porta una data di deposito.
        pattern = r"(?:(?:posta certificata|copia non crittografata|consegna)(?:\s*:)?\s+)*deposito telematico\s*[:-]\s*(.+)"
        m = re.match(pattern, semplice(oggetto))
        if not m and atto.nome.lower().endswith((".eml", ".msg")):
            m = re.match(pattern, semplice(atto.nome.rsplit(".", 1)[0]))
            data = ""
        if m:
            esito.append(DepositoEseguito(m.group(1), data, atto.id))
    return esito


def comunicazioni(atti: Iterable[Atto]) -> list[Comunicazione]:
    esito = []
    for atto in atti:
        if atto.autore != "cancelleria":
            continue
        m = re.search(r"notificato alla pec[^0-9]{0,30}(\d{1,2}/\d{1,2}/\d{4})", semplice(atto.testo))
        data = date_nel_testo(m.group(1))[0][2].isoformat() if m else _intestazione(atto.testo)[1]
        if data:
            nomi = [semplice(n) for n in re.findall(r"\[Allegato:\s*([^;\]]+?)\s*;", atto.testo)]
            nomi += [semplice(n) for n in re.findall(r'Nome="([^"]+)"', atto.testo)]
            esito.append(Comunicazione(data, atto.id, nomi, atto.testo))
    return esito


def comunicazione_di(provvedimento: Atto, tutte: Iterable[Comunicazione]) -> Comunicazione | None:
    """La comunicazione che porta in allegato il provvedimento (stesso nome di file), la prima in data."""
    nome = semplice(provvedimento.nome)
    radice = re.sub(r"\.(pdf|p7m)$", "", nome)
    candidate = [c for c in tutte if any(radice and radice in n for n in c.nomi_allegati)]
    return min(candidate, key=lambda c: c.data) if candidate else None


__all__ = ["Comunicazione", "DepositoEseguito", "comunicazione_di", "comunicazioni", "depositi_eseguiti"]
