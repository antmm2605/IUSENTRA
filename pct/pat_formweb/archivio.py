"""Archivio del procedimento amministrativo telematico di ogni fascicolo.

Un file JSON per studio con, per fascicolo, i dati del procedimento che il
Formweb chiede (sede, tipo di ricorso, NRG, posizione dell'assistito, ruolo
PAT di ogni parte) e lo storico dei depositi preparati e verificati. La
scrittura è atomica e serializzata: due richieste non si sovrascrivono.
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

CAMPI_PROCEDIMENTO = ("sede", "tipoRicorso", "nrg", "posizione", "materia", "pnrr", "anteCausam", "cuTipologia",
                      "esenzione", "valore", "oggetto", "attoImpugnato", "istanze", "cassazionista", "fax")
POSIZIONI = ("ricorrente", "resistente", "controinteressato", "interveniente")
RUOLI_PARTE = ("ricorrente", "resistente", "controinteressato", "escludi")
RUOLI_DOCUMENTO = ("atto", "procura", "allegato", "notifica", "contributo", "escludi")
STATI = ("in preparazione", "riepilogo verificato", "inviato", "depositato", "rifiutato")


def _adesso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class ArchivioPat:
    def __init__(self, percorso: str | os.PathLike[str]) -> None:
        self.percorso = Path(percorso)

    @contextmanager
    def _blocco(self) -> Iterator[dict[str, Any]]:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.percorso)):  # blocco condiviso di IUSENTRA: vale su Linux e su Windows
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
        return {"procedimento": dict(voce.get("procedimento") or {}), "ruoli": dict(voce.get("ruoli") or {}),
                "documenti": dict(voce.get("documenti") or {}), "depositi": list(voce.get("depositi") or [])}

    def aggiorna_procedimento(self, fid: str, dati: dict[str, Any]) -> dict[str, Any]:
        if dati.get("posizione") and dati["posizione"] not in POSIZIONI:
            raise ValueError("Posizione dell'assistito non prevista.")
        with self._blocco() as tutto:
            voce = tutto.setdefault(fid, {})
            procedimento = voce.setdefault("procedimento", {})
            for chiave in CAMPI_PROCEDIMENTO:
                if chiave in dati:
                    procedimento[chiave] = dati[chiave]
            procedimento["aggiornatoIl"] = _adesso()
            return dict(procedimento)

    def imposta_ruolo(self, fid: str, soggetto: str, ruolo: str) -> None:
        if ruolo not in RUOLI_PARTE:
            raise ValueError("Ruolo della parte non previsto dal Formweb.")
        with self._blocco() as tutto:
            tutto.setdefault(fid, {}).setdefault("ruoli", {})[soggetto] = ruolo

    def imposta_documento(self, fid: str, documento: str, ruolo: str, descrizione: str = "") -> None:
        if ruolo not in RUOLI_DOCUMENTO:
            raise ValueError("Ruolo del documento non previsto.")
        with self._blocco() as tutto:
            tutto.setdefault(fid, {}).setdefault("documenti", {})[documento] = {
                "ruolo": ruolo, "descrizione": str(descrizione or "").strip()[:150]}

    def registra_deposito(self, fid: str, dati: dict[str, Any]) -> dict[str, Any]:
        stato = dati.get("stato") or "in preparazione"
        if stato not in STATI:
            raise ValueError("Stato del deposito non previsto.")
        with self._blocco() as tutto:
            depositi = tutto.setdefault(fid, {}).setdefault("depositi", [])
            esistente = next((d for d in depositi if d["id"] == dati.get("id")), None)
            if esistente is None:
                esistente = {"id": uuid.uuid4().hex[:12], "creatoIl": _adesso()}
                depositi.insert(0, esistente)
            for chiave in ("tipo", "stato", "identificativo", "note", "riepilogo", "documenti"):
                if chiave in dati:
                    esistente[chiave] = dati[chiave]
            esistente.setdefault("stato", stato)
            esistente["aggiornatoIl"] = _adesso()
            return dict(esistente)


__all__ = ["ArchivioPat", "CAMPI_PROCEDIMENTO", "POSIZIONI", "RUOLI_DOCUMENTO", "RUOLI_PARTE", "STATI"]
