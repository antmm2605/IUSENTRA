"""Vista in italiano della sequenza notturna per la console Pianificazioni."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pct.scheduler_notturno import finestra
from pct.scheduler_notturno.registro import ESITI_ITALIANI, RegistroNotte
from pct.scheduler_notturno.sequenza import FASI, passi_in_ordine


def stato_sequenza_notturna(db_path: str | Path, momento: datetime | None = None) -> dict[str, Any]:
    registro = RegistroNotte(db_path)
    ora = momento or finestra.adesso()
    sera = finestra.sera_della_notte(ora)
    stato = registro.avanzamento(sera.isoformat()) or registro.ultima_notte_prima(sera.isoformat())
    passi = registro.passi(stato["sera"]) if stato else []
    durate = registro.durate_medie()
    totale = len(passi_in_ordine())
    fatti = int(stato["indice"]) if stato else 0
    return {
        "inizio": finestra.inizio().strftime("%H:%M"),
        "fine": finestra.fine().strftime("%H:%M"),
        "notte": stato["sera"] if stato else "",
        "conclusa": bool(stato and stato["conclusa"]),
        "ripresa_da": (stato or {}).get("ripresa_da", ""),
        "avanzamento": f"{fatti} di {totale} passi",
        "fasi": [
            {
                "numero": fase.numero,
                "nome": fase.nome,
                "motivo": fase.motivo,
                "lavori": [p.lavoro for p in fase.passi],
                "durata_media_minuti": round(sum(durate.get(p.lavoro, 0.0) for p in fase.passi) / 60, 1),
            }
            for fase in FASI
        ],
        "passi": [
            {**p, "esito_italiano": ESITI_ITALIANI.get(p["esito"], p["esito"])} for p in passi
        ],
        "falliti": [p["lavoro"] for p in passi if p["esito"] == "fallito"],
        "ai_riserva": registro.esiti_ai(),
    }
