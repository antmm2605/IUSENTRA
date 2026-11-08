"""Ricevute dei depositi lette dall'archivio PEC del software quando la casella non le ha più (08/11/2026).

Esempi fittizi: stessa struttura delle PEC reali del gestore (X-Ricevuta, X-Riferimento-Message-ID).
"""

from __future__ import annotations

import json
import sqlite3
from email import message_from_bytes
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from pct.fascicoli import EsitoDepositoPCT
from pct.polling_depositi import esegui_polling
from pct.ricevute_deposito_archivio import percorso_archivio_pec, ricevute_da_archivio, unisci_ricevute

MSGID = "178644507416.17784.3635212909859078282@pcstudio"
ROMA = ZoneInfo("Europe/Rome")


def _deposito(**extra) -> EsitoDepositoPCT:
    valori = dict(
        id="CD8044C6", timestamp="2026-10-12T10:00:00", stato="INVIATO", tipo_atto="RICORSO",
        pec_destinatario="tribunale.esempio@civile.ptel.giustiziacert.it",
        messaggio=f"Busta CD8044C6 inviata via PEC. Message-ID: <{MSGID}>", nome_atto_principale="Ricorso.pdf.p7m",
    )
    valori.update(extra)
    return EsitoDepositoPCT(**valori)


def _pec(oggetto: str, *, da: str = "posta-certificata@gestore.example", x: str = "avvenuta-consegna",
         rif: str = f"<{MSGID}>", data: str = "Mon, 12 Oct 2026 10:01:00 +0200", mid: str = "<ric-1@gestore.example>",
         corpo: str = "Ricevuta di avvenuta consegna") -> bytes:
    righe = [f"From: {da}", "To: studio@pec.example", f"Subject: {oggetto}", f"Date: {data}", f"Message-ID: {mid}",
             f"X-Ricevuta: {x}", f"X-Riferimento-Message-ID: {rif}", "Content-Type: text/plain; charset=utf-8", "", corpo]
    return "\r\n".join(righe).encode("utf-8")


def _archivio(tmp_path: Path, messaggi: list[tuple[str, bytes]], cartella: str = "INBOX") -> Path:
    # Le colonne usate di pct/pec_pipeline.py::pec_messages; metadata_json come lo scrive il presidio PEC.
    percorso = tmp_path / "pec_audit.sqlite"
    conn = sqlite3.connect(percorso)
    conn.execute("CREATE TABLE pec_messages (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL DEFAULT 'studio', folder TEXT NOT NULL, original_mime BLOB NOT NULL, "
                 "mime_size INTEGER NOT NULL, received_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}')")
    for numero, (ricevuta_il, grezzo) in enumerate(messaggi):
        intest = message_from_bytes(grezzo)
        metadati = json.dumps({"headers": {"from": str(intest["From"]), "subject": str(intest["Subject"])}})
        conn.execute("INSERT INTO pec_messages (id, folder, original_mime, mime_size, received_at, metadata_json) "
                     "VALUES (?,?,?,?,?,?)",
                     (f"pec-{numero}", cartella, grezzo, len(grezzo), ricevuta_il, metadati))
    conn.commit()
    conn.close()
    return percorso


class _GF:
    def __init__(self, fascicoli):
        self._fascicoli = {f.id: f for f in fascicoli}

    def _salva(self):
        pass


def test_rdac_cancellata_dalla_casella_trovata_nell_archivio(tmp_path):
    archivio = _archivio(tmp_path, [("2026-10-12T10:01:00", _pec("CONSEGNA: DEPOSITO TELEMATICO - RICORSO"))])
    dep = _deposito()

    report = esegui_polling(gf=_GF([SimpleNamespace(id="F1", depositi_pct=[dep])]), config_pec=None,
                            archivio_pec=archivio)

    assert report["aggiornati"] == 1
    assert dep.stato == "CONSEGNATO"


def test_ricevuta_falsa_nell_archivio_non_cambia_lo_stato(tmp_path):
    falsa = _pec("CONSEGNA: DEPOSITO TELEMATICO - RICORSO", da="truffatore@mail.example")
    archivio = _archivio(tmp_path, [("2026-10-12T10:01:00", falsa)])
    dep = _deposito()

    esegui_polling(gf=_GF([SimpleNamespace(id="F1", depositi_pct=[dep])]), config_pec=None, archivio_pec=archivio)

    assert dep.stato == "INVIATO"  # stessi controlli sul gestore delle PEC lette via IMAP


def test_pec_estranee_e_anteriori_al_deposito_escluse(tmp_path):
    archivio = _archivio(tmp_path, [
        ("2026-10-12T09:00:00", _pec("Appuntamento di lunedì", mid="<altra@x>")),
        ("2026-09-01T10:00:00", _pec("CONSEGNA: DEPOSITO TELEMATICO", mid="<vecchia@x>")),
    ])
    ricevute = ricevute_da_archivio(archivio, dal=datetime(2026, 10, 11, tzinfo=ROMA))
    assert ricevute == []


def test_pec_della_cartella_inviati_non_sono_ricevute(tmp_path):
    archivio = _archivio(tmp_path, [("2026-10-12T10:01:00", _pec("CONSEGNA: DEPOSITO TELEMATICO"))], cartella="INVIATI")
    assert ricevute_da_archivio(archivio, dal=datetime(2026, 10, 11, tzinfo=ROMA)) == []


def test_esito_del_ministero_letto_per_intero(tmp_path):
    esito = _pec("POSTA CERTIFICATA: ESITO CONTROLLI AUTOMATICI DEPOSITO", x="posta-certificata", rif="",
                 corpo=f"<EsitoAtto><IdMsgMitt>&lt;{MSGID}&gt;</IdMsgMitt></EsitoAtto>", mid="<esito@x>")
    archivio = _archivio(tmp_path, [("2026-10-12T10:05:00", esito)])
    [ricevuta] = ricevute_da_archivio(archivio, dal=datetime(2026, 10, 11, tzinfo=ROMA))
    assert MSGID in ricevuta["testo"] and ricevuta["fonte"] == "archivio_pec"


def test_archivio_assente_non_blocca(tmp_path):
    assert ricevute_da_archivio(tmp_path / "manca.sqlite", dal=datetime(2026, 10, 11, tzinfo=ROMA)) == []
    dep = _deposito()
    report = esegui_polling(gf=_GF([SimpleNamespace(id="F1", depositi_pct=[dep])]), config_pec=None,
                            archivio_pec=tmp_path / "manca.sqlite")
    assert report["controllati"] == 1 and dep.stato == "INVIATO"


def test_stessa_pec_in_casella_e_archivio_conta_una_volta():
    a = {"message_id": "<ric-1@gestore.example>", "fonte": "imap"}
    b = {"message_id": "ric-1@gestore.example", "fonte": "archivio_pec"}
    c = {"message_id": "<ric-2@gestore.example>"}
    assert unisci_ricevute([a], [b, c]) == [a, c]


def test_percorso_dell_archivio_accanto_alla_casella():
    assert percorso_archivio_pec({"EMAIL_CASELLA_DB": "/data/t/email/casella.json"}) == Path("/data/t/email/pec_audit.sqlite")
    assert percorso_archivio_pec({"PEC_AUDIT_DB": "/x/a.sqlite"}) == Path("/x/a.sqlite")
