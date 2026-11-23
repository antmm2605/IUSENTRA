"""Lavori pianificati orari dei testi della Giustizia amministrativa e della prassi (Agenzia delle Entrate, INPS).

L'app (8080) è l'unico scrittore degli archivi ``ga_testi.sqlite`` e ``prassi.sqlite``, accanto a
``LEGAL_INTELLIGENCE_DB`` (come la Gazzetta Ufficiale): due scrittori in WAL fra container e host danno conflitti di
permessi sul file ``-shm``. Ogni giro legge per al più ``PCT_GA_TEMPO_GIRO`` / ``PCT_PRASSI_TEMPO_GIRO`` secondi
(predefinito 1200, massimo 3300, così un giro orario non si somma al successivo) e riprende da dove si era fermato.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Mapping

ID_LAVORO_GA = "giustizia_amministrativa_testi"
ID_LAVORO_PRASSI = "prassi_agenzia_entrate_inps"
TEMPO_GIRO = 1200.0
TEMPO_MASSIMO = 3300.0
PAUSA = 2.0


def _valore(config: Mapping[str, Any], nome: str) -> str:
    return str(config.get(nome) or os.environ.get(nome) or "").strip()


def _accanto_agli_archivi(config: Mapping[str, Any], nome: str) -> Path:
    ancora = str(config.get("LEGAL_INTELLIGENCE_DB") or os.environ.get("PCT_LEGAL_INTELLIGENCE_DB")
                 or "./intelligence/motori.json")
    return Path(ancora).resolve().parent / nome


def percorso_ga(config: Mapping[str, Any]) -> Path:
    esplicito = _valore(config, "PCT_GA_TESTI_DB")
    return Path(esplicito) if esplicito else _accanto_agli_archivi(config, "ga_testi.sqlite")


def percorso_prassi(config: Mapping[str, Any]) -> Path:
    esplicito = _valore(config, "PCT_PRASSI_DB")
    return Path(esplicito) if esplicito else _accanto_agli_archivi(config, "prassi.sqlite")


def catalogo_openga(config: Mapping[str, Any]) -> Path | None:
    """Il catalogo OpenGA locale (sola lettura), se configurato."""
    for nome in ("OPENGA_CATALOGO_DB", "IUSENTRA_OPENGA_CATALOGO_DB"):
        valore = _valore(config, nome)
        if valore and Path(valore).is_file():
            return Path(valore)
    return None


def tempo_giro(config: Mapping[str, Any], nome: str) -> float:
    try:
        secondi = float(_valore(config, nome) or TEMPO_GIRO)
    except ValueError:
        secondi = TEMPO_GIRO
    return max(30.0, min(TEMPO_MASSIMO, secondi))


def uffici_dei_fascicoli(config: Mapping[str, Any]) -> list[str]:
    """Gli uffici dei fascicoli di tutti gli studi, letti in sola lettura (per l'ordine della coda dei TAR)."""
    radice = _valore(config, "PCT_TENANTS_DIR")
    cartella = Path(radice) if radice else _accanto_agli_archivi(config, "x").parent.parent / "tenants"
    uffici: set[str] = set()
    for studio in sorted(cartella.glob("*/studio.db")) if cartella.is_dir() else ():
        try:
            conn = sqlite3.connect(f"file:{studio}?mode=ro", uri=True, timeout=30)
            try:
                uffici |= {str(r[0]) for r in conn.execute(
                    "SELECT DISTINCT tribunale FROM fascicoli WHERE COALESCE(tribunale, '') <> ''")}
            finally:
                conn.close()
        except sqlite3.Error:
            continue
    return sorted(uffici)


def _estremi_del_catalogo(catalogo: Path):
    conn = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True, timeout=60)
    conn.row_factory = sqlite3.Row
    try:
        for riga in conn.execute("SELECT sede, nome_sede, tipo, numero, anno, ricorso, oggetto, esito_originale AS esito "
                                 "FROM righe WHERE tipo LIKE 'SENTENZA%'"):
            yield dict(riga)
    finally:
        conn.close()


def _sessione(agente: str):
    import requests

    sessione = requests.Session()
    sessione.headers["User-Agent"] = agente
    return sessione


def giro_testi_ga(config: Mapping[str, Any], *, scarica: Any = None, dormi: Any = None) -> dict[str, Any]:
    """Un giro: estremi nuovi dal catalogo (se cambiato), ordine della coda con le sedi dello studio, lettura testi."""
    import time

    from pct.giustizia_amministrativa_testi import ArchivioTestiGA, leggi, sedi_dai_fascicoli

    archivio = ArchivioTestiGA(percorso_ga(config))
    esito: dict[str, Any] = {"archivio": str(archivio.percorso)}
    catalogo = catalogo_openga(config)
    if catalogo is not None:
        impronta = f"{catalogo.stat().st_size}:{int(catalogo.stat().st_mtime)}"
        if archivio.valore("catalogo_impronta") != impronta:
            esito["estremi_nuovi"] = archivio.carica_estremi(_estremi_del_catalogo(catalogo))
            archivio.imposta_valore("catalogo_impronta", impronta)
    sedi = sedi_dai_fascicoli(uffici_dei_fascicoli(config))
    if sedi != archivio.sedi_studio():
        archivio.imposta_sedi_studio(sedi, da="fascicoli degli studi")
        esito["riordinati"] = archivio.riordina()
    esito["sedi_studio"] = sorted(sedi)
    if scarica is None:
        sessione = _sessione("IUSENTRA archivio giurisprudenza (consultazione professionale)")
        scarica = lambda url: sessione.get(url, timeout=60)  # noqa: E731
    esito.update(leggi(archivio, scarica=scarica, tempo_massimo=tempo_giro(config, "PCT_GA_TEMPO_GIRO"), pausa=PAUSA,
                       dormi=dormi or time.sleep))
    esito["stati"] = archivio.conteggi()
    return esito


def giro_prassi(config: Mapping[str, Any], *, scarica: Any = None) -> dict[str, Any]:
    from pct.prassi.archivio import ArchivioPrassi
    from pct.prassi.recupero import esegui_tratto

    archivio = ArchivioPrassi(percorso_prassi(config))
    if scarica is None:
        sessione = _sessione("IUSENTRA archivio prassi (consultazione professionale)")
        scarica = lambda url: sessione.get(url, timeout=120)  # noqa: E731
    return esegui_tratto(archivio, scarica, tempo_massimo=tempo_giro(config, "PCT_PRASSI_TEMPO_GIRO"), pausa=PAUSA)


__all__ = ["ID_LAVORO_GA", "ID_LAVORO_PRASSI", "catalogo_openga", "giro_prassi", "giro_testi_ga", "percorso_ga",
           "percorso_prassi", "tempo_giro", "uffici_dei_fascicoli"]
