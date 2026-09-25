"""Archivio del procedimento tributario telematico di ogni fascicolo.

Un file JSON per studio: per fascicolo i dati della nota di iscrizione a ruolo
(Corte, grado, atti impugnati, valore della lite, CUT), il ruolo PTT dei
documenti e lo storico dei depositi con lo stato della NIR che l'avvocato
riporta dal SIGIT. Scrittura atomica e serializzata con il blocco condiviso
di IUSENTRA (Linux e Windows).
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from pct.sync import FileLock

from .catalogo import STATI_NIR

CAMPI_PROCEDIMENTO = ("corte", "grado", "tipoDeposito", "atto", "posizione", "rg", "notificaRicorso", "pubblicaUdienza",
                      "sospensione", "prova", "atti", "cutModalita", "cutEstremi", "cutData", "cutEsenzione",
                      "sentenza", "note")
POSIZIONI = ("ricorrente", "resistente")
RUOLI_DOCUMENTO = ("atto", "allegato", "escludi")


def _adesso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ArchivioPtt:
    def __init__(self, percorso: str | os.PathLike[str]) -> None:
        self.percorso = Path(percorso)

    @contextmanager
    def _blocco(self) -> Iterator[dict[str, Any]]:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.percorso)):
            dati = self._leggi()
            yield dati
            fd, temporaneo = tempfile.mkstemp(dir=self.percorso.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(dati, out, ensure_ascii=False, indent=1)
            os.replace(temporaneo, self.percorso)

    def _leggi(self) -> dict[str, Any]:
        try:
            dati = json.loads(self.percorso.read_text(encoding="utf-8"))
            return dati if isinstance(dati, dict) else {}
        except (FileNotFoundError, ValueError):
            return {}

    def fascicolo(self, fid: str) -> dict[str, Any]:
        voce = self._leggi().get(fid) or {}
        return {"procedimento": dict(voce.get("procedimento") or {}), "documenti": dict(voce.get("documenti") or {}),
                "depositi": list(voce.get("depositi") or [])}

    def aggiorna_procedimento(self, fid: str, dati: dict[str, Any]) -> dict[str, Any]:
        if dati.get("posizione") and dati["posizione"] not in POSIZIONI:
            raise ValueError("Posizione della parte non prevista.")
        with self._blocco() as tutto:
            procedimento = tutto.setdefault(fid, {}).setdefault("procedimento", {})
            for chiave in CAMPI_PROCEDIMENTO:
                if chiave in dati:
                    procedimento[chiave] = dati[chiave]
            procedimento["aggiornatoIl"] = _adesso()
            return dict(procedimento)

    def imposta_documento(self, fid: str, documento: str, ruolo: str, tipologia: str = "", descrizione: str = "") -> None:
        if ruolo not in RUOLI_DOCUMENTO:
            raise ValueError("Ruolo del documento non previsto.")
        with self._blocco() as tutto:
            tutto.setdefault(fid, {}).setdefault("documenti", {})[documento] = {
                "ruolo": ruolo, "tipologia": tipologia[:120], "descrizione": descrizione[:70]}

    def registra_deposito(self, fid: str, dati: dict[str, Any]) -> dict[str, Any]:
        stato = dati.get("stato") or "in preparazione"
        if stato not in STATI_NIR:
            raise ValueError("Stato della NIR non previsto dal SIGIT.")
        with self._blocco() as tutto:
            depositi = tutto.setdefault(fid, {}).setdefault("depositi", [])
            esistente = next((d for d in depositi if d["id"] == dati.get("id")), None)
            if esistente is None:
                esistente = {"id": uuid.uuid4().hex[:12], "creatoIl": _adesso()}
                depositi.insert(0, esistente)
            for chiave in ("tipo", "stato", "ricevuta", "rg", "note", "controlli"):
                if chiave in dati:
                    esistente[chiave] = dati[chiave]
            esistente.setdefault("stato", stato)
            esistente["aggiornatoIl"] = _adesso()
            return dict(esistente)


__all__ = ["ArchivioPtt", "CAMPI_PROCEDIMENTO", "POSIZIONI", "RUOLI_DOCUMENTO"]
