"""Lo stato reale del fascicolo: quando cambia da solo, perché e con quale prova.

Lo stato (aperto, in corso, sospeso, definito, archiviato) cambiava da punti
diversi e con regole diverse: la sincronizzazione dal portale lo sovrascriveva
senza lasciare traccia, una sentenza letta riportava a «definito» perfino un
fascicolo già archiviato, un deposito accettato dalla cancelleria non lo
spostava da «aperto». Qui c'è una regola sola:

- ogni cambio automatico nasce da una **prova certa** e la registra
  nell'avanzamento della pratica (fonte, motivo, data): la cronologia dice
  sempre perché il fascicolo è in quello stato;
- l'automatismo **va solo avanti** nel ciclo della causa, con l'unica eccezione
  del registro di cancelleria, che fa fede anche quando riporta la causa a
  pendente (per esempio dopo la riassunzione);
- **l'archiviazione resta un atto dello studio**: produce l'archivio ZIP con
  documenti e metadati (conservazione del fascicolo, art. 44 CAD) e nessun
  automatismo può archiviare né togliere dall'archivio.

Prove e transizioni:

| Prova | Stato | Fonte |
|---|---|---|
| iscrizione a ruolo (numero R.G. assegnato) | in corso | art. 168 c.p.c.; artt. 45 c.p.a. e 22 D.Lgs. 546/1992 |
| deposito accettato dalla cancelleria | in corso | art. 16-bis D.L. 179/2012; D.M. 44/2011 art. 13 |
| prima attività processuale registrata | in corso | cronologia del fascicolo |
| stato del registro di cancelleria (PST, portali) | quello del registro | registri di cancelleria (D.M. 264/2000) |
| sentenza del procedimento letta nel fascicolo | definito | art. 132 c.p.c.; art. 88 c.p.a. |
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pct.fascicoli import AvanzamentoPratica, StatoFascicolo

ORIGINE_REGISTRO = "registro"
ORIGINE_PROVA = "prova"

# Posizione nel ciclo della causa: sospeso sta allo stesso punto di «in corso».
_POSIZIONE = {
    StatoFascicolo.APERTO: 0,
    StatoFascicolo.IN_CORSO: 1,
    StatoFascicolo.SOSPESO: 1,
    StatoFascicolo.DEFINITO: 2,
    StatoFascicolo.ARCHIVIATO: 3,
}


@dataclass(frozen=True)
class Prova:
    """Perché lo stato cambia: la prova, la sua fonte e la data in cui è nata."""

    stato: StatoFascicolo
    motivo: str
    fonte: str
    origine: str = ORIGINE_PROVA
    data: str = ""

    def nota(self) -> str:
        quando = f" ({self.data})" if self.data else ""
        return f"{self.motivo}{quando}. Fonte: {self.fonte}."


def _stato(valore: Any) -> StatoFascicolo:
    if isinstance(valore, StatoFascicolo):
        return valore
    try:
        return StatoFascicolo(str(getattr(valore, "value", valore) or "").strip().upper())
    except ValueError:
        return StatoFascicolo.APERTO


def ammessa(attuale: Any, prova: Prova) -> bool:
    """La transizione automatica è ammessa? Mai dall'archivio né verso l'archivio."""
    corrente, nuovo = _stato(attuale), prova.stato
    if corrente == nuovo or StatoFascicolo.ARCHIVIATO in (corrente, nuovo):
        return False
    if prova.origine == ORIGINE_REGISTRO:
        return True
    return _POSIZIONE[nuovo] > _POSIZIONE[corrente] or (corrente == StatoFascicolo.SOSPESO and nuovo == StatoFascicolo.IN_CORSO)


def avanzamento(attuale: Any, prova: Prova, *, autore: str = "IUSENTRA") -> AvanzamentoPratica:
    precedente = _stato(attuale).value
    return AvanzamentoPratica(
        data=datetime.now().isoformat(),
        descrizione=f"Stato cambiato da {precedente} a {prova.stato.value} in automatico",
        stato_precedente=precedente,
        stato_nuovo=prova.stato.value,
        note=prova.nota(),
        avvocato=autore,
    )


def applica(gestore: Any, fascicolo: Any, prova: Prova, *, persist: bool = True, autore: str = "IUSENTRA") -> bool:
    """Cambia lo stato con `cambia_stato` (avanzamento e data di chiusura) se la prova lo consente."""
    if fascicolo is None or not ammessa(getattr(fascicolo, "stato", ""), prova):
        return False
    gestore.cambia_stato(str(fascicolo.id), prova.stato, note=prova.nota(), avvocato=autore, persist=persist)
    return True


def prova_iscrizione_a_ruolo(numero_rg: Any, anno_rg: Any = "") -> Prova | None:
    numero = str(numero_rg or "").strip()
    if not numero:
        return None
    anno = str(anno_rg or "").strip()
    return Prova(StatoFascicolo.IN_CORSO, f"Causa iscritta a ruolo: R.G. {numero}{'/' + anno if anno else ''}",
                 "numero di ruolo del fascicolo (art. 168 c.p.c.; art. 45 c.p.a.; art. 22 D.Lgs. 546/1992)")


def prova_deposito_accettato(tipo_atto: str = "", data: str = "") -> Prova:
    atto = f" ({tipo_atto})" if tipo_atto else ""
    return Prova(StatoFascicolo.IN_CORSO, f"Deposito telematico accettato dalla cancelleria{atto}",
                 "ricevuta di accettazione della cancelleria (art. 16-bis D.L. 179/2012; D.M. 44/2011 art. 13)", data=data)


def prova_registro(stato: StatoFascicolo, descrizione: str, portale: str = "registro di cancelleria") -> Prova:
    return Prova(stato, f"Stato del procedimento nel {portale}: «{descrizione}»",
                 f"{portale} (consultazione telematica dei registri)", origine=ORIGINE_REGISTRO)


def prova_sentenza(data: str = "", numero: str = "") -> Prova:
    estremi = f" n. {numero}" if numero else ""
    return Prova(StatoFascicolo.DEFINITO, f"Sentenza{estremi} del procedimento letta nel fascicolo",
                 "sentenza depositata (art. 132 c.p.c.; art. 88 c.p.a.)", data=data)


__all__ = [
    "ORIGINE_PROVA",
    "ORIGINE_REGISTRO",
    "Prova",
    "ammessa",
    "applica",
    "avanzamento",
    "prova_deposito_accettato",
    "prova_iscrizione_a_ruolo",
    "prova_registro",
    "prova_sentenza",
]
