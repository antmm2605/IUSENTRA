"""Gli eventi che rendono «fatto» un adempimento: depositi con la loro ricevuta, comunicazioni di cancelleria.

- deposito: la busta telematica ha oggetto «DEPOSITO TELEMATICO: <atto>» (art. 14 D.M. 44/2011) e si perfeziona
  con la ricevuta di avvenuta consegna (art. 196-sexies disp. att. c.p.c.); vale anche il deposito registrato
  nel fascicolo con l'accettazione della cancelleria;
- comunicazione: il biglietto di cancelleria (art. 136 c.p.c.) dice quale provvedimento comunica e quando
  («Notificato alla PEC il …»): da lì decorrono i termini assegnati «dalla comunicazione».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from pct.ricevute_deposito_pct import data_consegna_deposito
from pct.notifica_atto_l53 import chiave_nome

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
    prova_da_registro: bool = False
    copia_in_chiaro_id: str = ""
    udienza_note: str = ""
    ricevute_notifiche: dict[str, tuple[int, int]] = field(default_factory=dict)
    busta_inviata_id: str = ""
    copia_prova_notifica_id: str = ""


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
            da_registro = False
            if not ricevute and stato == "accettato_cancelleria" and deposito.get("ricevuta_cancelleria"):
                momento = data_consegna_deposito(deposito.get("ricevuta_consegna"))
                if momento and deposito.get("id"):
                    consegna, prova = momento.isoformat(), pulito(deposito["id"])
                    da_registro = True
            esito.append(DepositoEseguito(
                pulito(deposito.get("nome_atto_principale") or deposito.get("tipo_atto")), data, pulito(deposito.get("id")),
                accettato=stato == "accettato_cancelleria", stato_registro=stato,
                data_esito=pulito(deposito.get("data_accettazione")) if stato == "accettato_cancelleria" else "",
                documenti_ids=tuple(deposito.get("documenti_ids") or ()), consegna=consegna, prova_consegna=prova,
                nome_atto=pulito(deposito.get("nome_atto_principale")),
                busta=pulito(deposito.get("id_deposito_esterno")),
                prova_da_registro=da_registro,
            ))
    invii: dict[str, list[tuple[DepositoEseguito, Atto]]] = {}
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
            titolo = m.group(1)
            voce = DepositoEseguito(titolo, data, atto.id)
            riferimento = re.search(r"\[(refid_[^\]\s]+)\]", titolo)
            if riferimento:
                invii.setdefault(riferimento.group(1), []).append((voce, atto))
            else:
                esito.append(voce)
    for copie in invii.values():
        date = {copia.data for copia, _ in copie if copia.data}
        if len(date) > 1:
            # Il riferimento non autorizza a scegliere fra intestazioni discordanti.
            esito.extend(copia for copia, _ in copie)
            continue
        voce = next((copia for copia, _ in copie if copia.data), copie[0][0])
        if voce.data and len(copie) > 1:
            riscontri = {(atto.id, udienza) for copia, atto in copie
                         if copia.titolo == voce.titolo and (udienza := _udienza_note_in_busta(atto, voce.titolo))}
            if len(riscontri) == 1:
                voce.copia_in_chiaro_id, voce.udienza_note = riscontri.pop()
            inviate = [atto.id for copia, atto in copie if copia.titolo == voce.titolo and copia.data == voce.data
                       and re.match(r"(?i)Oggetto:\s*DEPOSITO TELEMATICO\s*:", atto.testo)
                       and re.search(r"(?im)^Destinatari:[^\r\n]*@civile\.ptel\.giustiziacert\.it\b", atto.testo[:1500])
                       and re.search(r"(?im)^\[Allegato:\s*Atto\.enc(?:;[^\]]*)?\]$", atto.testo)]
            prove = [(atto.id, ricevute) for copia, atto in copie if copia.titolo == voce.titolo
                     and (ricevute := _ricevute_notifica_in_busta(atto.testo))]
            if len(inviate) == len(prove) == 1 and inviate[0] != prove[0][0]:
                voce.busta_inviata_id = inviate[0]
                voce.copia_prova_notifica_id, voce.ricevute_notifiche = prove[0]
        esito.append(voce)
    return esito


def _ricevute_notifica_in_busta(testo: str) -> dict[str, tuple[int, int]]:
    """Conta RAC e RdAC allegate direttamente alla busta, per identificativo di notifica."""
    allegati = re.findall(r"(?im)^\[Allegato:[ \t]*([^;\r\n]+); parte 1\.\d+\]$", testo)
    if not any(chiave_nome(nome) == "datiatto" for nome in allegati):
        return {}
    ricevute: dict[str, tuple[int, int]] = {}
    for nome in set(allegati):
        m = re.match(r"(ACCETTAZIONE|CONSEGNA)[:_ ]+Notificazione .+?\[Notifica_ID[:_]([A-Za-z0-9]+)\](?:\[\d+\])?\.eml$", nome, re.I)
        if m:
            accettazioni, consegne = ricevute.get(m[2], (0, 0))
            ricevute[m[2]] = (accettazioni + (m[1].upper() == "ACCETTAZIONE"),
                              consegne + (m[1].upper() == "CONSEGNA"))
    return ricevute


def _udienza_note_in_busta(atto: Atto, titolo: str) -> str:
    nome_principale = re.split(r"\s+rg\s*:|\s+\[", titolo, maxsplit=1)[0]
    if not chiave_nome(nome_principale).startswith("note scritte"):
        return ""
    blocchi = re.split(r"(?m)^\[Allegato:\s*([^;\]\r\n]+)(?:[^\]\r\n]*)\][ \t]*$", atto.testo)
    if not any(chiave_nome(nome) == "datiatto" for nome in blocchi[1::2]):
        return ""
    date = set()
    for nome, testo in zip(blocchi[1::2], blocchi[2::2]):
        if chiave_nome(nome) != chiave_nome(nome_principale):
            continue
        intestazione = re.search(r"(?i)\budienza(?:\s+del|\s+di)?\s+(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b", testo[:1200])
        if intestazione:
            date.update(data.isoformat() for _, _, data in date_nel_testo(intestazione.group(1)))
    return next(iter(date)) if len(date) == 1 else ""


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
