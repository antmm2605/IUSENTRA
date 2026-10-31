"""Riconvalida delle bozze «termine lungo» nate dalle PEC di sentenza prima della correzione del 31/10/2026.

Base normativa: art. 133 c.p.c. (la sentenza è resa pubblica con il deposito) e art. 327 c.p.c.
(sei mesi dalla pubblicazione); la comunicazione di cancelleria non fa decorrere il termine.

Verifica sulle PEC reali del 31/10/2026: per 33 bozze su 40 la data di decorrenza era quella
della comunicazione, perché la PEC non riporta la data dell'evento e la sentenza allegata è
l'originale del giudice, senza timbro di pubblicazione. Il principio è quello delle fonti certe:

- il software cerca la data di deposito: prima la sentenza depositata nel fascicolo telematico
  (PST, data del portale), poi il timbro «pubbl. il» letto dall'archivio delle letture, solo se
  legato allo stesso numero della sentenza comunicata; se la trova, ricalcola il termine e
  dichiara la fonte. Sul campione reale due proposte su quattro con la sentenza dal portale
  partivano dal giorno dopo il deposito: la scadenza indicata sarebbe stata tardiva;
- se non la trova, decide l'avvocato: la bozza resta da confermare con l'avviso che la data non
  è certa, e si ricontrolla quando il fascicolo riceve la sentenza dal portale. Nulla si cancella
  e nulla si conferma al posto dell'avvocato.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from datetime import date

from pct.termine_lungo_sentenza import (
    data_deposito_dal_portale,
    data_pubblicazione_da_fatti,
    numero_sentenza,
    scadenza_termine_lungo,
)

MARCATORE_PEC = "PEC_TERMINE_PROPOSTO:"
CODICE_TERMINE_LUNGO = "CIV_APPELLO_LUNGO"
NON_CERTA = "DATA_DEPOSITO_NON_CERTA"
DAI_DOCUMENTI = "DATA_DEPOSITO_DAI_DOCUMENTI"
AVVISO = (
    "Data di deposito non certa: la data indicata è quella della comunicazione di cancelleria, che non fa "
    "decorrere il termine (artt. 133 e 327 c.p.c.). Verificare la data di pubblicazione della sentenza sul "
    "portale o sulla copia con il timbro di deposito e correggere prima di confermare."
)


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def da_riconvalidare(scadenza: Any) -> bool:
    """Bozza di termine lungo nata da una PEC, con decorrenza uguale alla data della comunicazione."""
    note = _valore(scadenza, "note")
    if _valore(scadenza, "stato") != "BOZZA" or MARCATORE_PEC not in note:
        return False
    if _valore(scadenza, "deadline_profile_code") != CODICE_TERMINE_LUNGO or DAI_DOCUMENTI in note:
        return False
    if NON_CERTA in note:
        return True  # già segnalata: si ricontrolla finché non compare la fonte certa
    decorrenza, comunicazione = _valore(scadenza, "data_decorrenza")[:10], _valore(scadenza, "source_event_at")[:10]
    return bool(decorrenza) and decorrenza == comunicazione


def _fatti_della_sentenza(fatti: Iterable[Any], numero: str) -> list[Any]:
    compatto = re.sub(r"\s+", "", numero)
    return [fatto for fatto in fatti if compatto in re.sub(r"\s+", "", _valore(fatto, "contesto"))]


def riconvalida_bozze(
    scadenziario: Any,
    fatti_del_fascicolo: Callable[[str], Iterable[Any]],
    documenti_del_fascicolo: Callable[[str], Iterable[Any]] | None = None,
) -> dict[str, int]:
    esito = {"dal_portale": 0, "dai_documenti": 0, "da_giudicare": 0}
    for scadenza in list(scadenziario.tutte(solo_aperte=False)):
        if not da_riconvalidare(scadenza):
            continue
        testo = f"{_valore(scadenza, 'titolo')} {_valore(scadenza, 'descrizione')}"
        numero = numero_sentenza(testo)
        fascicolo_id = _valore(scadenza, "id_fascicolo")
        note = _valore(scadenza, "note")
        deposito, fonte = None, ""
        try:
            comunicazione = date.fromisoformat(_valore(scadenza, "source_event_at")[:10])
        except ValueError:
            comunicazione = None
        if fascicolo_id and comunicazione and documenti_del_fascicolo is not None:
            deposito = data_deposito_dal_portale(documenti_del_fascicolo(fascicolo_id), comunicazione=comunicazione)
            fonte = "dal_portale" if deposito else ""
        if deposito is None and numero and fascicolo_id:
            deposito = data_pubblicazione_da_fatti(_fatti_della_sentenza(fatti_del_fascicolo(fascicolo_id), numero), numero=numero)
            fonte = "dai_documenti" if deposito else ""
        if deposito is not None:
            lavoro = "Sospensione feriale non applicata" in testo
            calcolo = scadenza_termine_lungo(deposito, lavoro=lavoro)
            origine = ("data di deposito della sentenza nel fascicolo telematico (portale)" if fonte == "dal_portale"
                       else f"data di pubblicazione della sentenza n. {numero} letta dai documenti del fascicolo")
            descrizione = _valore(scadenza, "descrizione").replace(AVVISO, "").strip()
            scadenziario.aggiorna(
                _valore(scadenza, "id"), data_scadenza=calcolo["deadline"], data_decorrenza=deposito.isoformat(),
                legal_due_at=calcolo["deadline"], raw_due_at=calcolo["rawDeadline"],
                descrizione=f"Termine lungo calcolato dal deposito del {deposito:%d/%m/%Y} ({origine}).\n{descrizione}".strip(),
                note=(f"{note.replace(NON_CERTA, '').strip()}\n{DAI_DOCUMENTI} deposito={deposito.isoformat()}: {origine}; "
                      "la data della comunicazione è stata sostituita.").strip(),
            )
            esito[fonte] += 1
        elif NON_CERTA not in note:
            scadenziario.aggiorna(
                _valore(scadenza, "id"),
                descrizione=f"{AVVISO}\n{_valore(scadenza, 'descrizione')}".strip(),
                note=f"{note}\n{NON_CERTA}".strip(),
            )
            esito["da_giudicare"] += 1
    return esito


__all__ = ["AVVISO", "DAI_DOCUMENTI", "NON_CERTA", "da_riconvalidare", "riconvalida_bozze"]
