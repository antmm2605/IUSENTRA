"""Il decreto di trattazione scritta arrivato con la comunicazione di cancelleria (art. 127-ter c.p.c.).

La PEC è collegata al fascicolo dal collegamento automatico per numero di ruolo e ufficio
(certificati da Comunicazione.xml, art. 16 D.M. 44/2011). Se il decreto sostituisce «l'udienza
già fissata» senza scriverne la data:

* con **una** udienza futura nel fascicolo si propone in bozza il termine per le note a quella
  data (09:30 se il decreto invita al deposito entro quell'ora, altrimenti fine giornata);
* senza udienze future, con più candidate o con la PEC non ancora collegata, si chiede
  all'avvocato quale udienza il decreto sostituisce («da verificare»): nessuna data indovinata;
* se il fascicolo ha già un termine equivalente (un'altra copia dello stesso decreto, o un
  termine per note inserito a mano) non si propone un doppione.

Nessuna scrittura avviene qui: l'esito torna alla pipeline, che crea la bozza con il
meccanismo di conferma dei termini proposti dai provvedimenti.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from .adempimenti import Adempimento, adempimenti_note
from .decreto import DecretoNoteScritte, riconosci_decreto
from .proposta import PropostaNote, proposta_note, termine_equivalente
from .udienza_riferita import UdienzaRiferita, udienza_riferita

#: riga della ricezione in agenda che chiede all'avvocato quale udienza il decreto sostituisce
DA_VERIFICARE_PREFISSO = "Da verificare (art. 127-ter c.p.c.):"


@dataclass
class EsitoDecretoNote:
    decreto: DecretoNoteScritte
    udienza: UdienzaRiferita | None = None
    proposte: list[PropostaNote] = field(default_factory=list)
    da_verificare: str = ""
    equivalente_id: str = ""
    adempimenti: list[Adempimento] = field(default_factory=list)

    def righe_descrizione(self) -> list[str]:
        righe: list[str] = []
        if self.udienza is not None and self.udienza.giorno is not None:
            righe.append(
                f"Decreto ex art. 127-ter c.p.c.: l'udienza del {self.udienza.giorno:%d/%m/%Y} è sostituita "
                "da note scritte (udienza cartolare, senza comparizione)."
            )
        if self.equivalente_id:
            righe.append("Termine per le note già presente nello scadenziario: nessuna nuova proposta.")
        if self.da_verificare:
            righe.append(f"{DA_VERIFICARE_PREFISSO} {self.da_verificare}")
        righe.extend(f"Per le note: {voce.riga()}" for voce in self.adempimenti)
        return righe

    def come_dizionario(self) -> dict[str, Any]:
        giorno = self.udienza.giorno if self.udienza is not None else None
        return {
            "udienza": giorno.isoformat() if giorno else "",
            "esito_udienza": self.udienza.esito if self.udienza is not None else "",
            "candidate": [d.isoformat() for d in (self.udienza.candidate if self.udienza else ())],
            "ora_limite": self.decreto.ora_limite,
            "da_verificare": self.da_verificare,
            "equivalente_id": self.equivalente_id,
            "proposte": [p.code for p in self.proposte],
            "adempimenti": [voce.codice for voce in self.adempimenti],
        }


def _da_verificare(udienza: UdienzaRiferita, fascicolo_id: str) -> str:
    if not fascicolo_id:
        return ("il decreto sostituisce l'udienza già fissata senza indicarne la data e la PEC non è ancora "
                "collegata a un fascicolo: collegarla e indicare quale udienza è sostituita.")
    if udienza.esito == "ambigua":
        elenco = ", ".join(f"{d:%d/%m/%Y}" for d in udienza.candidate)
        return (f"il decreto sostituisce l'udienza già fissata senza indicarne la data e il fascicolo ha più "
                f"udienze future ({elenco}): indicare quale è sostituita, il termine per le note scade quel giorno.")
    return ("il decreto sostituisce l'udienza già fissata senza indicarne la data e nel fascicolo non c'è "
            "un'udienza futura: indicare la data dell'udienza, il termine per le note scade quel giorno.")


def esamina_decreto_pec(
    testo: str,
    *,
    oggi: date,
    comunicata_il: date | None = None,
    fascicolo_id: str = "",
    rg: str = "",
    ufficio: str = "",
    giudice: str = "",
    prossima_udienza: Any = "",
    appuntamenti: Iterable[Any] = (),
    scadenze: Iterable[Any] = (),
    opposizione_proposta: bool = False,
) -> EsitoDecretoNote | None:
    """L'esame del decreto, o None se il testo non è un decreto che rinvia all'udienza già fissata."""
    decreto = riconosci_decreto(testo)
    if decreto is None or not decreto.senza_data:
        return None
    scadenze = list(scadenze or [])
    esito = EsitoDecretoNote(decreto=decreto)
    if not fascicolo_id:
        esito.da_verificare = _da_verificare(UdienzaRiferita(giorno=None), fascicolo_id)
        return esito
    udienza = udienza_riferita(
        appuntamenti=appuntamenti, scadenze=scadenze, fascicolo_id=fascicolo_id, rg=rg,
        prossima_udienza=prossima_udienza, oggi=oggi,
    )
    esito.udienza = udienza
    if udienza.giorno is None:
        esito.da_verificare = _da_verificare(udienza, fascicolo_id)
        return esito
    esito.adempimenti = adempimenti_note(
        decreto, udienza.giorno, rg=rg, giudice=giudice, ufficio=ufficio, opposizione_proposta=opposizione_proposta,
    )
    equivalente = termine_equivalente(scadenze, fascicolo_id=fascicolo_id, giorno=udienza.giorno)
    if equivalente is not None:
        esito.equivalente_id = str(getattr(equivalente, "id", "") or "")
        return esito
    esito.proposte.append(proposta_note(decreto, udienza.giorno, comunicata_il=comunicata_il, id_appuntamento=udienza.id_appuntamento,
                                        fonte="decreto ex art. 127-ter c.p.c. comunicato via PEC"))
    return esito


__all__ = ["DA_VERIFICARE_PREFISSO", "EsitoDecretoNote", "esamina_decreto_pec"]
