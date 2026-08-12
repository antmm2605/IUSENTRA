"""Lettura di eventi e scadenze di un fascicolo dai registri di cancelleria (PST).

Base normativa: consultazione dei registri di cancelleria tramite i servizi
ufficiali del Portale Servizi Telematici (D.M. 44/2011; specifiche DGSIA).
Le classi QBuilder ``InfoScadenze`` (udienze e scadenze prospettiche) e
``EventoFascicoloAgenda`` (storico eventi del fascicolo) sono definite nei
cataloghi ministeriali versionati (WSDL Catalog v1.52, SICID
``catalog_sicc_be.xml``).

Questo modulo si limita a modello + parsing + normalizzazione: nessuna
chiamata di rete (quella vive in ``pct/polisWeb.py``), cosi' resta testabile
da fixture XML. Le date lette qui non sono termini legali: alimentano
proposte in BOZZA da confermare (principio delle fonti certe: la fonte
primaria dei termini resta la comunicazione/notificazione ex art. 136 c.p.c.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class EventoRegistro:
    """Evento o scadenza letto dal registro di cancelleria."""

    tipo: str  # "scadenza" | "udienza" | "evento"
    descrizione: str
    data: str  # YYYY-MM-DD (vuoto se non parsabile)
    fonte_classe: str  # classe QBuilder di provenienza (InfoScadenze/EventoFascicoloAgenda)
    giudice: str = ""
    id_documento: str = ""
    data_registrazione: str = ""

    @property
    def is_futuro(self) -> bool:
        if not self.data:
            return False
        try:
            return date.fromisoformat(self.data) >= date.today()
        except ValueError:
            return False

    def chiave(self) -> str:
        """Chiave stabile per dedup idempotente tra giri di sincronizzazione."""

        base = f"{self.tipo}|{self.data}|{' '.join(self.descrizione.lower().split())}"
        return base[:200]


def _clean(value: Any, limit: int = 400) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def _parse_data(value: Any) -> str:
    raw = _clean(value, 40)
    if not raw:
        return ""
    # Formati osservati dai registri: ISO, gg/mm/aaaa, con eventuale orario.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw[: len(fmt) + 4], fmt).date().isoformat()
        except ValueError:
            continue
    # ISO con parte oraria: taglia ai primi 10 caratteri.
    head = raw[:10]
    try:
        return date.fromisoformat(head).isoformat()
    except ValueError:
        return ""


def _row_value(row: dict[str, Any], *names: str) -> str:
    wanted = {str(name or "").strip().upper() for name in names}
    for key, value in row.items():
        if str(key or "").strip().upper() in wanted and not isinstance(value, (dict, list)):
            text = _clean(value)
            if text:
                return text
    return ""


def evento_da_info_scadenza(row: dict[str, Any]) -> EventoRegistro | None:
    """Mappa una riga QBuilder ``InfoScadenze`` in un evento normalizzato."""

    data = _parse_data(_row_value(row, "DATASCADENZA", "DATA"))
    if not data:
        return None
    tipo_raw = _row_value(row, "TIPOSCADENZA", "TIPO").lower()
    tipo = "udienza" if "udienza" in tipo_raw else "scadenza"
    descrizione = _row_value(row, "DESCSCADENZA", "DESCRIZIONE", "DESC") or (
        "Udienza" if tipo == "udienza" else "Scadenza processuale"
    )
    return EventoRegistro(
        tipo=tipo,
        descrizione=descrizione,
        data=data,
        fonte_classe="InfoScadenze",
        giudice=_row_value(row, "GIUDICE"),
    )


def evento_da_agenda(row: dict[str, Any]) -> EventoRegistro | None:
    """Mappa una riga QBuilder ``EventoFascicoloAgenda`` in un evento storico."""

    data = _parse_data(_row_value(row, "DATA"))
    descrizione = _row_value(row, "DESC", "DESCRIZIONE", "TIPO")
    if not data and not descrizione:
        return None
    return EventoRegistro(
        tipo="evento",
        descrizione=descrizione or "Evento di fascicolo",
        data=data,
        fonte_classe="EventoFascicoloAgenda",
        id_documento=_row_value(row, "IDDOCUMENTO", "IDATTO"),
        data_registrazione=_parse_data(_row_value(row, "DATAREGISTRAZIONE")),
    )


def normalizza_eventi(
    righe_scadenze: list[dict[str, Any]],
    righe_agenda: list[dict[str, Any]] | None = None,
) -> list[EventoRegistro]:
    """Deduplica e ordina gli eventi letti dal registro (scadenze prima)."""

    eventi: list[EventoRegistro] = []
    for row in righe_scadenze or []:
        if isinstance(row, dict):
            evento = evento_da_info_scadenza(row)
            if evento:
                eventi.append(evento)
    for row in righe_agenda or []:
        if isinstance(row, dict):
            evento = evento_da_agenda(row)
            if evento:
                eventi.append(evento)
    visti: set[str] = set()
    unici: list[EventoRegistro] = []
    for evento in eventi:
        chiave = evento.chiave()
        if chiave in visti:
            continue
        visti.add(chiave)
        unici.append(evento)
    ordine_tipo = {"udienza": 0, "scadenza": 1, "evento": 2}
    unici.sort(key=lambda e: (ordine_tipo.get(e.tipo, 3), e.data or "9999-12-31"))
    return unici
