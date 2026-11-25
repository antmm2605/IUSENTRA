"""Riconvalida notturna delle schede di istituto (lavoro «conoscenza_schede_riconvalida» dello scheduler).

Ogni notte, dopo l'aggiornamento degli archivi ufficiali, si confronta la versione di ogni fonte delle schede con
quella che il software legge oggi (``consultazione.stato_attuale``) e si rigenerano SOLO le schede con una fonte
cambiata o non più leggibile; le altre restano alla loro revisione con la data dell'ultimo controllo aggiornata.
Ogni passaggio entra nel registro della conoscenza (eventi append-only), insieme al rapporto del controllo della
wiki (``lint``).

Il codice del prodotto non si scrive di notte: i record riconvalidati stanno nella cartella dei dati
(``IUSENTRA_CONOSCENZA_DIR`` o ``PCT_DATA_DIR/conoscenza``). Sono la stessa raccolta del prodotto, ripresa dalla sua
copia: la cartella ricorda l'impronta dei record del prodotto da cui parte e, se un rilascio porta record nuovi,
riparte da quelli invece di nasconderli.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from . import deposito

BASE = "base_prodotto"


def cartella_runtime() -> Path | None:
    esplicita = os.environ.get("IUSENTRA_CONOSCENZA_DIR", "").strip()
    if esplicita:
        return Path(esplicita)
    dati = os.environ.get("PCT_DATA_DIR", "").strip()
    return Path(dati) / "conoscenza" if dati else None


def _impronta_prodotto() -> str:
    try:
        return hashlib.sha256(deposito.ARCHIVIO.read_bytes()).hexdigest()[:16]
    except OSError:
        return ""


def percorsi_attivi(cartella: Path | None = None) -> tuple[Path, Path]:
    """Archivio e registro da leggere: la copia riconvalidata se parte dai record del prodotto installati, altrimenti
    quelli del prodotto."""
    cartella = cartella or cartella_runtime()
    if cartella is not None:
        archivio = cartella / deposito.ARCHIVIO.name
        try:
            if json.loads(archivio.read_text(encoding="utf-8")).get(BASE) == _impronta_prodotto():
                return archivio, cartella / deposito.REGISTRO.name
        except (OSError, ValueError):
            pass
    return deposito.ARCHIVIO, deposito.REGISTRO


def _prepara(cartella: Path) -> tuple[Path, Path, bool]:
    archivio, registro = cartella / deposito.ARCHIVIO.name, cartella / deposito.REGISTRO.name
    if percorsi_attivi(cartella)[0] == archivio:
        return archivio, registro, False
    cartella.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(deposito.ARCHIVIO, archivio)
    shutil.copyfile(deposito.REGISTRO, registro)
    return archivio, registro, True


def riconvalida_notturna(cartella: Path | None = None, *, ora: str | None = None) -> dict[str, Any]:
    from .consultazione import stato_attuale
    from .generatore import genera_scheda
    from .istituti import carica
    from .lint import controlla, registra

    cartella = cartella or cartella_runtime()
    if cartella is None:
        return {"ok": False, "job": "conoscenza_schede_riconvalida",
                "error": "cartella dei dati non configurata (IUSENTRA_CONOSCENZA_DIR o PCT_DATA_DIR)"}
    archivio, registro, ripartita = _prepara(cartella)
    _, istituti = carica()
    per_id = {i.id_scheda: i for i in istituti}
    attuali = deposito.leggi_archivio(archivio)["schede"]
    nuove, rigenerate, motivi = [], [], {}
    for ident, rec in attuali.items():
        if rec.get("stato_ciclo") == "ritirata":
            continue
        st = stato_attuale(rec)
        if (st["fonti_cambiate"] or st["fonti_non_leggibili"]) and ident in per_id:
            nuove.append(genera_scheda(per_id[ident]))
            rigenerate.append(ident)
            motivi[ident] = st["motivi"]
        else:
            nuove.append(rec)
    esito = deposito.aggiorna(nuove, ora=ora, archivio=archivio, registro=registro)
    dati = deposito.leggi_archivio(archivio)
    momento = ora or deposito.adesso()
    for rec in dati["schede"].values():
        # Da quando una scheda è da riesaminare: serve al controllo dei 30 giorni; si toglie quando torna a posto.
        if stato_attuale(rec)["stato"] == "da_riesaminare":
            rec.setdefault("da_riesaminare_dal", momento)
        else:
            rec.pop("da_riesaminare_dal", None)
    dati[BASE] = _impronta_prodotto()
    deposito._scrivi_atomico(archivio, json.dumps(dati, ensure_ascii=False, indent=1) + "\n")
    rapporto = controlla(archivio=archivio)
    registra(rapporto, registro=registro, ora=ora)
    return {"ok": True, "job": "conoscenza_schede_riconvalida", "cartella": str(cartella), "ripartita_dal_prodotto": ripartita,
            "schede": len(nuove), "rigenerate": rigenerate, "motivi": motivi, **esito["conteggi"],
            "eventi": esito["eventi"], "lint": rapporto["conteggi"]}
