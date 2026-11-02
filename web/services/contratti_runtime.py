"""Orchestrazione delle pratiche contrattuali: archivio di studio, fascicoli, documenti.

Base normativa: art. 1322 c.c.; il salvataggio della bozza nel fascicolo passa
dall'archivio documenti (``aggiungi_documento``), quindi dal registro delle
letture (art. 3 D.M. 44/2011, art. 20 CAD) come ogni altro documento.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from flask import current_app, g

from pct.contratti.archivio import ArchivioContratti
from pct.contratti.bozza import componi
from pct.contratti.esporta_docx import bozza_docx
from web.services.tenant_paths import tenant_data_path


def _runtime(nome: str) -> Any:
    return current_app.extensions["core_runtime"][nome]()


def archivio() -> ArchivioContratti:
    base = Path(tenant_data_path("TELEMATICO_DB", require_tenant=True)).parent
    return ArchivioContratti(base / "contratti" / "pratiche.json")


def autore() -> str:
    utente = g.get("utente_corrente")
    return str(getattr(utente, "username", "") or getattr(utente, "nome", "") or "")


def fascicoli(testo: str = "", limite: int = 30) -> list[dict[str, str]]:
    archivio_fascicoli = _runtime("get_fascicoli")
    elenco = archivio_fascicoli.cerca(testo) if testo else archivio_fascicoli.tutti()
    return [{"id": f.id, "numero": f.numero, "titolo": f.titolo, "cliente": f.nome_cliente}
            for f in elenco[:limite]]


def _fascicolo(fid: str):
    fascicolo = _runtime("get_fascicoli").get(fid) if fid else None
    if fascicolo is None:
        raise LookupError("Fascicolo non trovato.")
    return fascicolo


def bozza_pratica(pratica: dict[str, Any]) -> dict[str, Any]:
    return componi(pratica["contratto_id"], pratica.get("dati") or {}, pratica.get("fatti") or {})


def nome_file(pratica: dict[str, Any], suffisso: str = "") -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "_", pratica.get("titolo") or pratica["contratto_id"]).strip("_")[:60]
    return f"{base or 'contratto'}{suffisso}.docx"


def salva_nel_fascicolo(pid: str) -> dict[str, Any]:
    from pct.fascicoli import TipoDocumento

    pratica = archivio().pratica(pid)
    fascicolo = _fascicolo(pratica.get("fascicolo_id", ""))
    contenuto = bozza_docx(bozza_pratica(pratica))
    nome = nome_file(pratica, f"_{pratica['stato']}")
    documento = _runtime("get_fascicoli").aggiungi_documento(
        fascicolo.id, nome, TipoDocumento.CONTRATTO, contenuto,
        note=f"Bozza dal catalogo contratti ({pratica['contratto_nome']}), stato: {pratica['stato']}.",
        tags=["contratti", pratica["contratto_id"]], caricato_da=autore(),
    )
    voce = {"documento_id": getattr(documento, "id", ""), "nome": nome, "fascicolo_id": fascicolo.id,
            "stato": pratica["stato"]}
    archivio().registra_documento(pid, voce)
    return voce
