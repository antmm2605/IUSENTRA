"""
Timesheet operativo per fascicoli, clienti e utenti.

Il modulo usa la stessa strategia dei repository core:
- JSON come formato legacy locale
- SQLite/PostgreSQL tramite ``studio_db`` quando il runtime core e' attivo

Obiettivo:
- tracciare il tempo speso per pratica
- supportare fatturazione, KPI di produttivita' e workflow cliente -> incasso
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class StatoTimesheet(str, Enum):
    APERTO = "APERTO"
    VALIDATO = "VALIDATO"
    FATTURATO = "FATTURATO"
    ANNULLATO = "ANNULLATO"


@dataclass
class VoceTimesheet:
    id: str
    id_fascicolo: str = ""
    id_cliente: str = ""
    id_utente: str = ""
    username: str = ""
    data_attivita: str = field(default_factory=lambda: date.today().isoformat())
    descrizione: str = ""
    minuti: int = 0
    valore_unitario: float = 0.0
    fatturabile: bool = True
    stato: StatoTimesheet = StatoTimesheet.APERTO
    origine: str = ""
    note: str = ""
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat())
    dati_json: Dict[str, Any] = field(default_factory=dict)

    @property
    def ore(self) -> float:
        return round(self.minuti / 60.0, 2)

    @property
    def valore_totale(self) -> float:
        if not self.fatturabile:
            return 0.0
        return round(self.ore * float(self.valore_unitario or 0.0), 2)

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["stato"] = self.stato.value
        return row

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoceTimesheet":
        payload = dict(data or {})
        payload["stato"] = StatoTimesheet(payload.get("stato", StatoTimesheet.APERTO))
        payload["minuti"] = int(payload.get("minuti", 0) or 0)
        payload["valore_unitario"] = float(payload.get("valore_unitario", 0.0) or 0.0)
        payload["fatturabile"] = bool(payload.get("fatturabile", True))
        payload.setdefault("dati_json", {})
        valid_fields = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in payload.items() if key in valid_fields})


class GestioneTimesheet:
    """Repository timesheet compatibile con JSON legacy e storage core."""

    def __init__(self, db_path: str = "./timesheet/entries.json", studio_db=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._entries: Dict[str, VoceTimesheet] = {}
        self._carica()

    def _carica(self) -> None:
        if self._studio_db is not None:
            rows = self._studio_db.carica_tabella("timesheet_entries")
            self._entries = {}
            for row in rows:
                try:
                    voce = VoceTimesheet.from_dict(row)
                except Exception:
                    continue
                self._entries[voce.id] = voce
            return

        if not self.db_path.exists():
            self._entries = {}
            return

        with open(self.db_path, encoding="utf-8") as handle:
            raw = json.load(handle)
        if isinstance(raw, dict):
            payloads = raw.values()
        elif isinstance(raw, list):
            payloads = raw
        else:
            payloads = []
        self._entries = {}
        for payload in payloads:
            voce = VoceTimesheet.from_dict(payload)
            self._entries[voce.id] = voce

    def _salva(self) -> None:
        if self._studio_db is not None:
            def _insert(conn, voce: VoceTimesheet):
                payload = voce.to_dict()
                conn.execute(
                    """
                    INSERT INTO timesheet_entries
                    (id, id_fascicolo, id_cliente, id_utente, username, data_attivita,
                     descrizione, minuti, valore_unitario, fatturabile, stato, origine,
                     creato_il, modificato_il, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        voce.id,
                        voce.id_fascicolo or None,
                        voce.id_cliente or None,
                        voce.id_utente or None,
                        voce.username,
                        voce.data_attivita,
                        voce.descrizione,
                        int(voce.minuti or 0),
                        float(voce.valore_unitario or 0.0),
                        1 if voce.fatturabile else 0,
                        voce.stato.value,
                        voce.origine,
                        voce.creato_il,
                        voce.modificato_il,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("timesheet_entries", list(self._entries.values()), _insert)
            return

        from pct import cache as _cache

        _cache.save(self.db_path, {key: value.to_dict() for key, value in self._entries.items()})

    def crea(
        self,
        *,
        descrizione: str,
        minuti: int,
        id_fascicolo: str = "",
        id_cliente: str = "",
        id_utente: str = "",
        username: str = "",
        data_attivita: str = "",
        valore_unitario: float = 0.0,
        fatturabile: bool = True,
        stato: StatoTimesheet = StatoTimesheet.APERTO,
        origine: str = "",
        note: str = "",
        dati_json: Optional[Dict[str, Any]] = None,
    ) -> VoceTimesheet:
        if not str(descrizione or "").strip():
            raise ValueError("La descrizione del tempo lavorato e' obbligatoria.")
        if int(minuti or 0) <= 0:
            raise ValueError("I minuti devono essere maggiori di zero.")

        voce = VoceTimesheet(
            id=uuid.uuid4().hex,
            id_fascicolo=str(id_fascicolo or "").strip(),
            id_cliente=str(id_cliente or "").strip(),
            id_utente=str(id_utente or "").strip(),
            username=str(username or "").strip(),
            data_attivita=str(data_attivita or date.today().isoformat()).strip(),
            descrizione=str(descrizione).strip(),
            minuti=int(minuti or 0),
            valore_unitario=float(valore_unitario or 0.0),
            fatturabile=bool(fatturabile),
            stato=stato,
            origine=str(origine or "").strip(),
            note=str(note or "").strip(),
            dati_json=dict(dati_json or {}),
        )
        self._entries[voce.id] = voce
        self._salva()
        return voce

    def get(self, id_entry: str) -> Optional[VoceTimesheet]:
        return self._entries.get(id_entry)

    def tutte(self) -> List[VoceTimesheet]:
        return sorted(
            self._entries.values(),
            key=lambda item: (item.data_attivita, item.creato_il, item.id),
            reverse=True,
        )

    def per_cliente(self, id_cliente: str) -> List[VoceTimesheet]:
        return [item for item in self.tutte() if item.id_cliente == id_cliente]

    def per_fascicolo(self, id_fascicolo: str) -> List[VoceTimesheet]:
        return [item for item in self.tutte() if item.id_fascicolo == id_fascicolo]

    def per_utente(self, username: str = "", id_utente: str = "") -> List[VoceTimesheet]:
        if id_utente:
            return [item for item in self.tutte() if item.id_utente == id_utente]
        return [item for item in self.tutte() if item.username == username]

    def aggiorna(self, id_entry: str, **kwargs) -> VoceTimesheet:
        voce = self._entries[id_entry]
        for key, value in kwargs.items():
            if not hasattr(voce, key):
                continue
            if key == "stato":
                value = StatoTimesheet(value)
            if key == "minuti":
                value = int(value or 0)
            if key == "valore_unitario":
                value = float(value or 0.0)
            setattr(voce, key, value)
        voce.modificato_il = datetime.now().isoformat()
        self._salva()
        return voce

    def cambia_stato(self, id_entry: str, stato: StatoTimesheet) -> VoceTimesheet:
        return self.aggiorna(id_entry, stato=stato)

    def statistiche(self, entries: Optional[Iterable[VoceTimesheet]] = None) -> Dict[str, Any]:
        righe = list(entries if entries is not None else self.tutte())
        minuti_totali = sum(int(item.minuti or 0) for item in righe if item.stato != StatoTimesheet.ANNULLATO)
        fatturabili = [item for item in righe if item.fatturabile and item.stato != StatoTimesheet.ANNULLATO]
        non_fatturabili = [item for item in righe if not item.fatturabile and item.stato != StatoTimesheet.ANNULLATO]
        valore_totale = round(sum(item.valore_totale for item in fatturabili), 2)
        return {
            "totale_voci": len(righe),
            "totale_minuti": minuti_totali,
            "totale_ore": round(minuti_totali / 60.0, 2),
            "fatturabili": len(fatturabili),
            "non_fatturabili": len(non_fatturabili),
            "valore_totale": valore_totale,
            "aperte": sum(1 for item in righe if item.stato == StatoTimesheet.APERTO),
            "validate": sum(1 for item in righe if item.stato == StatoTimesheet.VALIDATO),
            "fatturate": sum(1 for item in righe if item.stato == StatoTimesheet.FATTURATO),
        }

    def riepilogo_cliente(self, id_cliente: str) -> Dict[str, Any]:
        righe = self.per_cliente(id_cliente)
        stats = self.statistiche(righe)
        ultimi = righe[:5]
        utenti: Dict[str, Dict[str, Any]] = {}
        for item in righe:
            key = item.username or item.id_utente or "Operatore"
            bucket = utenti.setdefault(
                key,
                {"username": key, "minuti": 0, "ore": 0.0, "voci": 0, "valore": 0.0},
            )
            bucket["minuti"] += int(item.minuti or 0)
            bucket["voci"] += 1
            bucket["valore"] = round(bucket["valore"] + item.valore_totale, 2)
        for bucket in utenti.values():
            bucket["ore"] = round(bucket["minuti"] / 60.0, 2)
        return {
            "stats": stats,
            "ultimi": ultimi,
            "per_utente": sorted(utenti.values(), key=lambda row: (row["minuti"], row["valore"]), reverse=True),
        }

    def riepilogo_fascicolo(self, id_fascicolo: str) -> Dict[str, Any]:
        righe = self.per_fascicolo(id_fascicolo)
        stats = self.statistiche(righe)
        ultimi = righe[:6]
        fatturabili_aperti = [
            item for item in righe if item.fatturabile and item.stato in {StatoTimesheet.APERTO, StatoTimesheet.VALIDATO}
        ]
        return {
            "stats": stats,
            "ultimi": ultimi,
            "fatturabili_aperti": fatturabili_aperti,
            "prossimo_passo": (
                "Trasforma le ore validate in parcella."
                if any(item.stato == StatoTimesheet.VALIDATO for item in righe)
                else "Registra tempo o valida le voci aperte."
            ),
        }
