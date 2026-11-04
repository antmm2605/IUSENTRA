"""Prova della catena notturna ADESSO, dentro il container scheduler-worker (richiesta dell'avvocato del 04/11/2026).

Esegue la catena vera (``pct.scheduler_notturno.catena.esegui_passo``), un passo alla volta, con i lavori veri
registrati come nello scheduler (senza avviarlo: nessun lavoro parte a orario da questo processo), il registro
della notte vero e il semaforo dei motori vero (SQLite condivisi). L'avanzamento si scrive sotto una chiave di sera
dedicata («prova-AAAA-MM-GG-HHMM»), così la notte vera non viene toccata: le chiavi «prova-…» non sono mai prese
come «notte precedente» dalla catena, che confronta solo date.

Il momento passato alla catena è le 22:00 di stasera più il tempo trascorso: la finestra notturna vale solo per
questa prova, nessuna variabile cambia il comportamento del worker in produzione.

Variabili:
- ``PROVA_MINUTI`` durata massima (predefinito 50, al più 540);
- ``PROVA_FASI`` fasi ammesse, es. «1-5» o «2,4,5» (vuoto = tutte); i passi delle altre fasi si segnano «saltato»;
- ``PROVA_CHIAVE`` chiave della prova (per riprendere una prova interrotta).

Si ferma al primo passo «fallito», a fine catena (o delle fasi ammesse) o allo scadere del tempo. Stampa una riga
JSON con i passi (fase, lavoro, esito, secondi, messaggio) e l'inventario delle letture prima e dopo, per studio:
solo conteggi, nessun dato di clienti.

Uso sul server:
    cd /opt/iusentra/repo
    docker compose --env-file /opt/iusentra/.env.hetzner -f deploy/hetzner/docker-compose.hetzner.yml \
        exec -T -e PROVA_MINUTI=50 -e PROVA_FASI=1-5 scheduler-worker python - < deploy/hetzner/prova_catena.py

Base normativa: art. 3 D.M. 44/2011 e art. 20 CAD (integrità delle letture dei documenti informatici).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from collections.abc import Callable
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

MARCATORE = "PROVA_CATENA_JSON:"
_ID = re.compile(r"\b[0-9A-Fa-f]{8,}\b|\b[\w.+-]+@[\w-]+\.[\w.]+\b|/[\w./-]{6,}")
PAUSA_ATTESA_SECONDI = 20.0
MINUTI_MASSIMI = 540


def _breve(testo: Any) -> str:
    riga = str(testo or "").strip().splitlines()[0] if str(testo or "").strip() else ""
    return _ID.sub("<ID>", riga)[:200]


def fasi_ammesse(testo: str) -> set[int] | None:
    """«1-5» → {1..5}; «2,4» → {2,4}; vuoto → None (tutte)."""
    numeri: set[int] = set()
    for parte in [p.strip() for p in str(testo or "").split(",") if p.strip()]:
        if "-" in parte:
            da, a = parte.split("-", 1)
            numeri.update(range(int(da), int(a) + 1))
        else:
            numeri.add(int(parte))
    return numeri or None


def registro_di_prova(db_path: str | Path, chiave: str) -> Any:
    """Il registro della notte vero, con ogni lettura e scrittura sotto la chiave della prova."""
    from pct.scheduler_notturno.registro import RegistroNotte

    class RegistroProva(RegistroNotte):
        def avanzamento(self, sera: str) -> dict[str, Any] | None:
            return super().avanzamento(chiave)

        def ultima_notte_prima(self, sera: str) -> dict[str, Any] | None:
            return None  # la prova parte sempre dal primo passo

        def apri_notte(self, sera: str, partenza: int, ripresa_da: str, adesso: str) -> dict[str, Any]:
            return super().apri_notte(chiave, 0, "Prova della catena avviata a mano.", adesso)

        def aggiorna(self, sera: str, adesso: str, **campi: Any) -> None:
            super().aggiorna(chiave, adesso, **campi)

        def scrivi_passo(self, sera: str, *args: Any, **kwargs: Any) -> None:
            super().scrivi_passo(chiave, *args, **kwargs)

        def passi(self, sera: str) -> list[dict[str, Any]]:
            return super().passi(chiave)

    registro = RegistroProva(db_path)
    registro.chiave = chiave  # type: ignore[attr-defined]
    return registro


def esegui_prova(registro: Any, ambiente: Any, *, minuti: float, fasi: set[int] | None = None,
                 adesso: Callable[[], datetime] | None = None, dormi: Callable[[float], None] = time.sleep,
                 pausa: float = PAUSA_ATTESA_SECONDI) -> dict[str, Any]:
    from pct.scheduler_notturno import catena, finestra
    from pct.scheduler_notturno.sequenza import passi_in_ordine

    orologio = adesso or finestra.adesso
    inizio = orologio()
    base = datetime.combine(inizio.astimezone(finestra.ROME_TZ).date(), datetime.min.time(),
                            tzinfo=finestra.ROME_TZ).replace(hour=22)
    limite = timedelta(minutes=min(float(minuti), MINUTI_MASSIMI))

    def notte() -> datetime:
        return base + (orologio() - inizio)

    elenco = passi_in_ordine()
    totale = len(elenco)
    passi: list[dict[str, Any]] = []
    attese: dict[str, Any] = {"giri": 0, "ultimo_messaggio": ""}
    motivo = ""
    while True:
        if orologio() - inizio >= limite:
            motivo = "tempo_scaduto"
            break
        stato = registro.avanzamento("") or {"indice": 0, "partenza": 0, "conclusa": 0}
        if int(stato["conclusa"] or 0):
            motivo = "catena_conclusa"
            break
        indice = int(stato["indice"])
        posizione = (int(stato["partenza"]) + indice) % totale
        fase, passo = elenco[posizione]
        if fasi is not None and fase.numero not in fasi:
            if not any(f.numero in fasi for f, _ in elenco[posizione:]):
                motivo = "fasi_richieste_concluse"
                break
            ora = notte().isoformat(timespec="seconds")
            if not registro.avanzamento(""):
                registro.apri_notte("", 0, "", ora)
            registro.scrivi_passo("", indice, fase.numero, passo.lavoro, "saltato", messaggio="Fase esclusa dalla prova.",
                                  avvio=ora, fine=ora)
            registro.aggiorna("", ora, indice=indice + 1, passo_avviato_alle="", conclusa=int(indice + 1 >= totale))
            continue
        t0 = time.monotonic()
        esito = catena.esegui_passo(registro, ambiente, momento=notte(), adesso=notte)
        if esito.get("lavoro"):
            passi.append({"fase": esito.get("fase"), "lavoro": esito["lavoro"], "esito": esito.get("esito"),
                          "secondi": round(time.monotonic() - t0, 1), "messaggio": _breve(esito.get("message"))})
            if esito.get("esito") == "fallito":
                motivo = "passo_fallito"
                break
            continue
        if "conclusa" in str(esito.get("message") or ""):
            motivo = "catena_conclusa"
            break
        attese["giri"] += 1
        attese["ultimo_messaggio"] = _breve(esito.get("message"))
        dormi(pausa)
    return {"chiave": getattr(registro, "chiave", ""), "motivo_fine": motivo, "passi": passi, "attese": attese,
            "minuti": round((orologio() - inizio).total_seconds() / 60, 1)}


# ---- inventario (stesso codice di collaudo_motori.py, fase INVENTARIO) -------------------------------------------

def _collaudo_motori() -> Any:
    candidati = [Path("/app/deploy/hetzner/collaudo_motori.py")]
    if "__file__" in globals():
        candidati.insert(0, Path(__file__).resolve().with_name("collaudo_motori.py"))
    for percorso in candidati:
        if percorso.is_file():
            spec = importlib.util.spec_from_file_location("collaudo_motori_prova", percorso)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)  # type: ignore[union-attr]
            return modulo
    raise FileNotFoundError("collaudo_motori.py")


def _piatto(valore: Any, prefisso: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    if isinstance(valore, dict):
        for k, v in valore.items():
            out.update(_piatto(v, f"{prefisso}.{k}" if prefisso else str(k)))
    elif isinstance(valore, (int, float)) and not isinstance(valore, bool):
        out[prefisso] = valore
    return out


def inventario(app: Any) -> dict[str, Any]:
    try:
        completo = _collaudo_motori().fase_inventario(app)
    except Exception as exc:
        return {"errore": _breve(f"{type(exc).__name__}: {exc}")}
    return {"istante": completo.get("istante"), "studi": completo.get("studi"), "coda_ocr": completo.get("coda_ocr")}


def confronto(prima: dict[str, Any], dopo: dict[str, Any]) -> dict[str, Any]:
    """Per studio, solo i numeri cambiati (prima → dopo)."""
    out: dict[str, Any] = {}
    studi_prima = {s.get("studio"): s for s in prima.get("studi") or []}
    for studio in dopo.get("studi") or []:
        a, b = _piatto(studi_prima.get(studio.get("studio"), {})), _piatto(studio)
        cambi = {k: [a.get(k, 0), b.get(k, 0)] for k in sorted(set(a) | set(b)) if a.get(k, 0) != b.get(k, 0)}
        out[str(studio.get("studio"))] = cambi
    out["coda_ocr"] = {k: v for k, v in {k: [_piatto(prima.get("coda_ocr")).get(k, 0), n]
                                          for k, n in _piatto(dopo.get("coda_ocr")).items()}.items() if v[0] != v[1]}
    return out


# ---- lavori dello scheduler senza avviarlo ----------------------------------------------------------------------

def lavori_dello_scheduler(app: Any) -> Any:
    """Registra i lavori come ``start_scheduler`` ma senza avviare lo scheduler, senza chiudere le esecuzioni
    aperte del worker vero e senza prendere le sue richieste manuali."""
    from unittest import mock

    from apscheduler.schedulers.background import BackgroundScheduler

    import pct.scheduler as scheduler_mod
    import pct.scheduler_registry as registro_mod

    app.config["PCT_SCHEDULER_WORKER"] = True
    nessuna = {"cancelled": 0}
    with ExitStack() as pila:
        pila.enter_context(mock.patch.object(BackgroundScheduler, "start", lambda self, *a, **k: None))
        pila.enter_context(mock.patch.object(registro_mod, "dispatch_requested_manual_runs", lambda *a, **k: None))
        pila.enter_context(mock.patch.object(registro_mod.SchedulerRegistryRepository, "cancel_manual_runs_started_before",
                                             lambda *a, **k: nessuna))
        pila.enter_context(mock.patch.object(registro_mod.SchedulerRegistryRepository, "cancel_scheduler_runs_started_before",
                                             lambda *a, **k: nessuna))
        pila.enter_context(mock.patch.dict(os.environ, {"PCT_SCHEDULER_RUNNING": ""}))
        os.environ.pop("PCT_SCHEDULER_RUNNING", None)
        scheduler = scheduler_mod.start_scheduler(app)
    if scheduler is None:
        raise RuntimeError("Lavori dello scheduler non registrati.")
    return scheduler


def main() -> int:
    sys.path.insert(0, "/app")
    from pct.scheduler_notturno import catena, finestra, risorse
    from pct.scheduler_registry import scheduler_registry_repository
    from pct.scheduler_worker import create_scheduler_app

    app = create_scheduler_app()
    chiave = os.getenv("PROVA_CHIAVE", "").strip() or "prova-" + finestra.adesso().strftime("%Y-%m-%d-%H%M")
    esito: dict[str, Any] = {"chiave": chiave}
    with app.app_context():
        esito["inventario_prima"] = inventario(app)
        try:
            scheduler = lavori_dello_scheduler(app)
            registro = registro_di_prova(scheduler_registry_repository(app.config).db_path, chiave)
            ambiente = catena.Ambiente(
                trova_lavoro=scheduler.get_job,
                memoria_libera_mb=risorse.memoria_libera_mb,
                ocr_in_coda=lambda: risorse.ocr_in_coda(dict(app.config)),
                scarica_ai_locale=risorse.scarica_ai_locale,
            )
            esito.update(esegui_prova(registro, ambiente, minuti=float(os.getenv("PROVA_MINUTI", "50") or 50),
                                      fasi=fasi_ammesse(os.getenv("PROVA_FASI", ""))))
        except Exception as exc:
            esito["errore"] = _breve(f"{type(exc).__name__}: {exc}")
        esito["inventario_dopo"] = inventario(app)
    esito["confronto"] = confronto(esito["inventario_prima"], esito["inventario_dopo"])
    print(MARCATORE + json.dumps(esito, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
