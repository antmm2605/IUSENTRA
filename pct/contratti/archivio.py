"""Archivio delle pratiche contrattuali dello studio (un file JSON per studio).

Base normativa: art. 2220 c.c. per analogia sulla conservazione e art. 32 GDPR
sulla sicurezza del trattamento; ogni salvataggio conserva la versione
precedente nello storico, così la redazione resta ricostruibile.
Scrittura atomica e serializzata con il blocco condiviso di IUSENTRA.
"""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pct.contratti.catalogo import famiglia
from pct.sync import FileLock

STATI = ("bozza", "in_revisione", "approvato", "firmato", "archiviato")
CAMPI = ("titolo", "fascicolo_id", "cliente", "fatti", "dati", "note", "stato", "decisioni")
MAX_STORICO = 30


def _adesso() -> str:
    return datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")


class ArchivioContratti:
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

    def elenco(self, fascicolo_id: str = "") -> list[dict[str, Any]]:
        pratiche = [p for p in self._leggi().get("pratiche", {}).values()
                    if not fascicolo_id or p.get("fascicolo_id") == fascicolo_id]
        sintesi = [{k: p.get(k) for k in ("id", "titolo", "contratto_id", "contratto_nome", "stato",
                                          "fascicolo_id", "cliente", "aggiornata_il", "creata_il")}
                   for p in pratiche]
        return sorted(sintesi, key=lambda p: p.get("aggiornata_il") or "", reverse=True)

    def pratica(self, pid: str) -> dict[str, Any]:
        pratica = self._leggi().get("pratiche", {}).get(pid)
        if not pratica:
            raise LookupError("Pratica contrattuale non trovata.")
        return pratica

    @staticmethod
    def _valida(dati: dict[str, Any]) -> None:
        if "stato" in dati and dati["stato"] not in STATI:
            raise ValueError("Stato della pratica non previsto.")
        for chiave in ("fatti", "dati", "decisioni"):
            if chiave in dati and not isinstance(dati[chiave], dict):
                raise ValueError(f"Il campo {chiave} deve essere un oggetto.")

    def crea(self, contratto_id: str, dati: dict[str, Any], autore: str = "") -> dict[str, Any]:
        contratto = famiglia(contratto_id)
        self._valida(dati)
        ora = _adesso()
        pratica = {"id": uuid.uuid4().hex[:12], "contratto_id": contratto.id, "contratto_nome": contratto.nome,
                   "titolo": (dati.get("titolo") or contratto.nome)[:200], "fascicolo_id": dati.get("fascicolo_id", ""),
                   "cliente": dati.get("cliente", ""), "fatti": dati.get("fatti", {}), "dati": dati.get("dati", {}),
                   "decisioni": dati.get("decisioni", {}), "note": dati.get("note", ""), "stato": "bozza",
                   "creata_il": ora, "aggiornata_il": ora, "autore": autore, "storico": [], "documenti": []}
        with self._blocco() as tutto:
            tutto.setdefault("pratiche", {})[pratica["id"]] = pratica
        return pratica

    def aggiorna(self, pid: str, dati: dict[str, Any], autore: str = "") -> dict[str, Any]:
        self._valida(dati)
        with self._blocco() as tutto:
            pratica = tutto.get("pratiche", {}).get(pid)
            if not pratica:
                raise LookupError("Pratica contrattuale non trovata.")
            if dati.get("stato") == "approvato" and not dati.get("forza_approvazione"):
                self._verifica_approvabile(pratica, dati)
            precedente = {k: pratica.get(k) for k in CAMPI}
            pratica["storico"] = ([{"il": pratica["aggiornata_il"], "autore": pratica.get("autore_modifica", ""),
                                    "versione": precedente}] + pratica.get("storico", []))[:MAX_STORICO]
            for chiave in CAMPI:
                if chiave in dati:
                    pratica[chiave] = dati[chiave]
            pratica["aggiornata_il"] = _adesso()
            pratica["autore_modifica"] = autore
            return pratica

    @staticmethod
    def _verifica_approvabile(pratica: dict[str, Any], dati: dict[str, Any]) -> None:
        from pct.contratti.selezione import valuta

        fatti = dati.get("fatti", pratica.get("fatti", {}))
        decisioni = dati.get("decisioni", pratica.get("decisioni", {}))
        esito = valuta(pratica["contratto_id"], fatti)
        if esito["bloccanti"]:
            raise ValueError("Approvazione impossibile: restano controlli bloccanti da risolvere.")
        aperti = [p["id"] for p in esito["punti_avvocato"] if not (decisioni.get(p["id"]) or {}).get("valutato")]
        if aperti:
            raise ValueError("Approvazione impossibile: registrare la valutazione dell'avvocato su tutti i punti aperti.")
        if esito["domande_aperte"] or esito["controlli_sospesi"]:
            raise ValueError("Approvazione impossibile: rispondere a tutte le domande del questionario.")
        from pct.contratti.bozza import componi

        bozza = componi(pratica["contratto_id"], dati.get("dati", pratica.get("dati", {})), fatti)
        if bozza["da_completare"]:
            raise ValueError("Approvazione impossibile: completare gli elementi evidenziati nella bozza.")

    def registra_documento(self, pid: str, voce: dict[str, Any]) -> dict[str, Any]:
        with self._blocco() as tutto:
            pratica = tutto.get("pratiche", {}).get(pid)
            if not pratica:
                raise LookupError("Pratica contrattuale non trovata.")
            pratica.setdefault("documenti", []).insert(0, {**voce, "il": _adesso()})
            return pratica

    def elimina(self, pid: str) -> None:
        with self._blocco() as tutto:
            if not tutto.get("pratiche", {}).pop(pid, None):
                raise LookupError("Pratica contrattuale non trovata.")
