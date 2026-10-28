"""Prova in sola lettura delle norme dei modelli nel container applicativo."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import os

from web.services import schede_fonti_runtime as runtime


def main():
    from lex.retrieval.normativa_catalog import library_path
    db = library_path(Path(os.environ.get("PCT_NORMATTIVA_DB") or "/data/normativa/normattiva.sqlite"))
    if not db.is_file():
        raise RuntimeError("Biblioteca pubblica assente nel container applicativo")
    modelli = runtime._modelli()
    assert len(modelli) >= 190, "Catalogo dei modelli incompleto"
    scheda = runtime.scheda(db, "CIV_ORD_023", studio_db=None)
    assert scheda and scheda["norme"] and scheda["impronta"]
    presenti = [n for n in scheda["norme"] if n["stato"] == "presente"]
    assert presenti, "Nessun testo disponibile per il modello campione"
    for n in presenti:
        assert n["testo"] and n["url"] and n["aggiornato_al"]
        assert hashlib.sha256(n["testo"].encode()).hexdigest() == n["sha256"]
        assert not n["approvata"], "Una lettura senza studio non puo' ereditare approvazioni"
    riepilogo = runtime.riepilogo(db, studio_db=None)
    print("SCHEDE_FONTI_SERVER_JSON=" + json.dumps({
        "modelli": len(modelli), "scheda": scheda["id"], "testi_presenti": len(presenti),
        "impronta": scheda["impronta"], "ultimo_controllo": riepilogo["eseguito_il"],
        "scritture": False, "approvazioni_automatiche": False,
    }))


if __name__ == "__main__":
    main()
