"""Acquisizione di riserva dei soli sommari pubblici della Gazzetta Ufficiale."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from pct.gazzetta.acquisizione import esegui_giro
from pct.gazzetta.archivio import ArchivioGazzetta
from pct.gazzetta.serie import SERIE


def percorso_archivio() -> Path:
    if esplicito := os.environ.get("PCT_GAZZETTA_UFFICIALE_DB"):
        return Path(esplicito)
    return Path(os.environ.get("PCT_LEGAL_INTELLIGENCE_DB", "intelligence/motori.json")).parent / "gazzetta_ufficiale.sqlite"


def stato(percorso: Path) -> dict:
    archivio = ArchivioGazzetta.in_lettura(percorso)
    if archivio is None:
        return {"da_verificare": [serie.codice for serie in SERIE], "letti": {}}
    stati = archivio.stato_serie()
    limite = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat(timespec="seconds").replace("+00:00", "Z")
    da_verificare = [
        serie.codice for serie in SERIE
        if stati.get(serie.codice, {}).get("ultimo_successo", "") < limite
    ]
    return {"da_verificare": da_verificare, "letti": {codice: sorted(archivio.fascicoli_letti(codice)) for codice in da_verificare}}


class ArchivioAcquisizione(ArchivioGazzetta):
    def __init__(self, percorso: Path, letti: dict[str, list[str]]):
        super().__init__(percorso)
        self.letti = letti

    def fascicoli_letti(self, serie: str) -> set[str]:
        return super().fascicoli_letti(serie).union(self.letti.get(serie, ()))


def acquisisci(checkpoint: dict, destinazione: Path) -> bool:
    serie = [voce for voce in SERIE if voce.codice in checkpoint["da_verificare"]]
    if not serie:
        return False
    with TemporaryDirectory() as directory:
        percorso = Path(directory) / "gazzetta.sqlite"
        esiti = esegui_giro(ArchivioAcquisizione(percorso, checkpoint["letti"]), serie=serie)
        with closing(sqlite3.connect(percorso)) as conn:
            conn.row_factory = sqlite3.Row
            fascicoli = [dict(riga) for riga in conn.execute("SELECT * FROM fascicoli")]
            atti = [dict(riga) for riga in conn.execute("SELECT * FROM atti")]
        # I fascicoli completi restano utili anche se un'altra serie ha fallito.
        verifiche = [
            codice for codice, esito in esiti["esiti"].items()
            if esito["ok"] and not esito["rimasti"]
        ]
        if not verifiche and not fascicoli:
            raise RuntimeError("La rete di riserva non ha acquisito alcuna serie o fascicolo ufficiale.")
        destinazione.write_text(json.dumps({
            "verifiche": verifiche, "acquisito_il": esiti["eseguito_il"],
            "fascicoli": fascicoli, "atti": atti,
        }, ensure_ascii=False), encoding="utf-8")
        print(f"Verifiche complete: {len(verifiche)}/{len(serie)}, fascicoli: {len(fascicoli)}")
    return True


def importa(percorso: Path, dati: dict) -> None:
    quando = dati["acquisito_il"]
    istante = datetime.fromisoformat(quando.replace("Z", "+00:00"))
    if abs(datetime.now(timezone.utc) - istante) > timedelta(minutes=30):
        raise ValueError("Acquisizione di riserva fuori dalla finestra di importazione.")
    archivio = ArchivioGazzetta(percorso)
    serie = {voce.codice: voce for voce in SERIE}
    atti: dict[tuple[str, str, str], list[dict]] = {}
    for atto in dati["atti"]:
        chiave = (atto["serie"], atto["data_gu"], atto["numero_gu"])
        atti.setdefault(chiave, []).append(atto)
    for fascicolo in dati["fascicoli"]:
        codice, giorno, numero = fascicolo["serie"], fascicolo["data"], fascicolo["numero"]
        righe = atti[(codice, giorno, numero)]
        if (
            len(righe) != fascicolo["atti"]
            or fascicolo["url_sommario"] != serie[codice].url_sommario(giorno, numero)
        ):
            raise ValueError("Fascicolo della Gazzetta non coerente con i suoi atti.")
        archivio.salva_fascicolo(fascicolo, righe, solo_se_nuovo=True)
    for codice in dati["verifiche"]:
        if codice not in serie:
            raise ValueError("Serie sconosciuta.")
        archivio.registra_esito(codice, ok=True, quando=quando)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("azione", choices=("stato", "acquisisci", "importa"))
    parser.add_argument("--output", type=Path)
    argomenti = parser.parse_args()
    if argomenti.azione == "stato":
        print(json.dumps(stato(percorso_archivio())))
    elif argomenti.azione == "acquisisci":
        if argomenti.output is None:
            parser.error("--output richiesto per acquisisci")
        acquisisci(json.load(sys.stdin), argomenti.output)
    else:
        importa(percorso_archivio(), json.load(sys.stdin))


if __name__ == "__main__":
    main()

