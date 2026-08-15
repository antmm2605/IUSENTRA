"""Motore differenze dei registri di cancelleria (fase 1 del piano Polisweb).

Confronta lo snapshot precedente degli eventi di un fascicolo (udienze e
scadenze lette da ``InfoScadenze``) con la lettura corrente e produce
differenze leggibili: nuova udienza fissata, udienza spostata, scadenza
rimossa dal registro, nuovi depositi importati. Lo storico per fascicolo
alimenta il pannello «Registro di cancelleria» nel dettaglio.

Base normativa: consultazione registri PST (D.M. 44/2011, specifiche DGSIA).
Le differenze sono INFORMATIVE: non creano ne' modificano scadenze operative
(quello resta al circuito proposte in BOZZA con conferma dell'avvocato).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Storico massimo per fascicolo: le differenze piu' vecchie scivolano via.
MAX_DIFFERENZE_PER_FASCICOLO = 60

TIPI_DIFFERENZA = ("nuovo_evento", "evento_spostato", "evento_rimosso", "nuovo_deposito")

_LABEL_EVENTO = {
    "udienza": "Udienza",
    "scadenza": "Scadenza",
    "evento": "Evento",
    "comunicazione": "Comunicazione di cancelleria",
    "notifica_da_ritiro": "Notifica da ritirare",
}


@dataclass
class Differenza:
    """Una variazione rilevata tra due letture del registro."""

    tipo: str
    descrizione: str
    data_precedente: str = ""
    data_corrente: str = ""
    rilevata_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10].upper())

    def messaggio(self) -> str:
        if self.tipo == "nuovo_evento":
            return f"{self.descrizione}: nuova data {self.data_corrente} dal registro."
        if self.tipo == "evento_spostato":
            return f"{self.descrizione}: spostato dal {self.data_precedente} al {self.data_corrente}."
        if self.tipo == "evento_rimosso":
            return f"{self.descrizione}: non compare piu' nel registro (era {self.data_precedente})."
        if self.tipo == "nuovo_deposito":
            return self.descrizione
        return self.descrizione

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tipo": self.tipo,
            "descrizione": self.descrizione,
            "dataPrecedente": self.data_precedente,
            "dataCorrente": self.data_corrente,
            "rilevataIl": self.rilevata_il,
            "messaggio": self.messaggio(),
        }


def _chiave_identita(evento: Any) -> str:
    """Identita' di un evento SENZA la data: cosi' lo spostamento si vede.

    Un'udienza resta "quella" udienza anche se cambia giorno: l'identita' e'
    tipo + descrizione normalizzata.
    """

    tipo = str(getattr(evento, "tipo", "") or "")
    descrizione = " ".join(str(getattr(evento, "descrizione", "") or "").casefold().split())
    return f"{tipo}|{descrizione[:160]}"


def snapshot_eventi(eventi: list[Any]) -> dict[str, list[str]]:
    """Snapshot serializzabile: identita' evento → date lette dal registro."""

    stato: dict[str, list[str]] = {}
    for evento in eventi or []:
        data = str(getattr(evento, "data", "") or "")
        if not data:
            continue
        stato.setdefault(_chiave_identita(evento), []).append(data)
    for date_evento in stato.values():
        date_evento.sort()
    return stato


def _etichetta(chiave: str) -> str:
    tipo, _sep, descrizione = chiave.partition("|")
    label = _LABEL_EVENTO.get(tipo, "Evento")
    return f"{label}: {descrizione}" if descrizione else label


def confronta_snapshot(
    precedente: dict[str, list[str]] | None,
    corrente: dict[str, list[str]],
) -> list[Differenza]:
    """Differenze tra due snapshot. Prima lettura (precedente None) → nessuna.

    La prima lettura di un fascicolo non genera differenze: tutto sarebbe
    "nuovo" e lo storico nascerebbe pieno di rumore.
    """

    if precedente is None:
        return []
    differenze: list[Differenza] = []
    for chiave, date_correnti in corrente.items():
        date_precedenti = precedente.get(chiave)
        if date_precedenti is None:
            for data in date_correnti:
                differenze.append(
                    Differenza(tipo="nuovo_evento", descrizione=_etichetta(chiave), data_corrente=data)
                )
        elif date_precedenti != date_correnti:
            # Stessa identita', date diverse: spostamento (confronto per posizione,
            # gli eventi multipli omonimi sono rari e comunque segnalati).
            nuove = [d for d in date_correnti if d not in date_precedenti]
            perse = [d for d in date_precedenti if d not in date_correnti]
            for indice, data_nuova in enumerate(nuove):
                data_precedente = perse[indice] if indice < len(perse) else ""
                if data_precedente:
                    differenze.append(
                        Differenza(
                            tipo="evento_spostato",
                            descrizione=_etichetta(chiave),
                            data_precedente=data_precedente,
                            data_corrente=data_nuova,
                        )
                    )
                else:
                    differenze.append(
                        Differenza(tipo="nuovo_evento", descrizione=_etichetta(chiave), data_corrente=data_nuova)
                    )
    for chiave, date_precedenti in precedente.items():
        if chiave not in corrente:
            for data in date_precedenti:
                differenze.append(
                    Differenza(tipo="evento_rimosso", descrizione=_etichetta(chiave), data_precedente=data)
                )
    differenze.sort(key=lambda d: (d.data_corrente or d.data_precedente))
    return differenze


class GestioneDiffRegistro:
    """Snapshot e storico differenze per fascicolo (JSON tenant-aware)."""

    def __init__(self, db_path: str = "./fascicoli/polisweb_diff.json"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._dati: dict[str, Any] = {"snapshots": {}, "differenze": {}}
        self._carica()

    def _carica(self) -> None:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._dati = {
                    "snapshots": dict(raw.get("snapshots") or {}),
                    "differenze": dict(raw.get("differenze") or {}),
                }
        except (OSError, json.JSONDecodeError, ValueError):
            self._dati = {"snapshots": {}, "differenze": {}}

    def _salva(self) -> None:
        self.db_path.write_text(
            json.dumps(self._dati, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )

    def registra_lettura(
        self,
        fascicolo_id: str,
        eventi: list[Any],
        *,
        depositi_importati: int = 0,
        origine: str = "sync",
    ) -> list[Differenza]:
        """Confronta con lo snapshot precedente, aggiorna storico e snapshot."""

        corrente = snapshot_eventi(eventi)
        precedente_raw = self._dati["snapshots"].get(fascicolo_id)
        precedente = dict(precedente_raw) if isinstance(precedente_raw, dict) else None
        differenze = confronta_snapshot(precedente, corrente)
        if depositi_importati > 0:
            differenze.append(
                Differenza(
                    tipo="nuovo_deposito",
                    descrizione=(
                        f"{depositi_importati} nuovi depositi importati dal registro"
                        if depositi_importati > 1
                        else "1 nuovo deposito importato dal registro"
                    ),
                )
            )
        self._dati["snapshots"][fascicolo_id] = corrente
        if differenze:
            storico = list(self._dati["differenze"].get(fascicolo_id) or [])
            storico.extend({**d.to_dict(), "origine": origine} for d in differenze)
            self._dati["differenze"][fascicolo_id] = storico[-MAX_DIFFERENZE_PER_FASCICOLO:]
        self._salva()
        return differenze

    def storico(self, fascicolo_id: str, *, limite: int = 20) -> list[dict[str, Any]]:
        rows = list(self._dati["differenze"].get(fascicolo_id) or [])
        return list(reversed(rows))[: max(1, limite)]

    def ha_snapshot(self, fascicolo_id: str) -> bool:
        return fascicolo_id in self._dati["snapshots"]
