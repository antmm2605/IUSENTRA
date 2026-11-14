from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib

from pct.pec_ricevute_archivio import Ricevuta, riscontra_invio_storico


def test_riscontro_storico_richiede_stesso_invio_e_allegato_per_ogni_destinatario():
    a, b = "primo@example.test", "secondo@example.test"
    sender = "studio@example.test"
    allegato = b"sentenza"
    digest = hashlib.sha256(allegato).hexdigest()
    invio = EmailMessage()
    invio["From"] = sender
    invio["To"] = f"{a}, {b}"
    invio["Subject"] = "Notificazione ai sensi della legge n. 53/1994"
    invio["Message-ID"] = "<originale@example.test>"
    invio.set_content("Notificazione")
    invio.add_attachment(allegato, maintype="application", subtype="pdf", filename="sentenza.pdf")
    raw = invio.as_bytes()

    rac = Ricevuta("accettazione", "gestore@example.test", "originale@example.test",
                   datetime(2026, 4, 20, 8, 17, tzinfo=timezone.utc), frozenset({sender}),
                   frozenset({a, b}), "", frozenset())
    rdac_a = replace(rac, tipo="avvenuta-consegna", consegna=a, impronte=frozenset({digest}),
                     data=rac.data + timedelta(seconds=10))
    rdac_b = replace(rdac_a, consegna=b)
    assert riscontra_invio_storico(raw, [("RAC", rac), ("A", rdac_a), ("B", rdac_b)]) == {
        "accettazione_id": "RAC",
        "accettazione_data": "2026-04-20T10:17:00+02:00",
        "consegne": [{"documento_id": "A", "data": "2026-04-20T10:17:10+02:00"},
                     {"documento_id": "B", "data": "2026-04-20T10:17:10+02:00"}],
        "impronte_allegati": [digest],
    }
    for errata in (replace(rdac_b, identificativo="estraneo@example.test"),
                   replace(rdac_b, impronte=frozenset({"0" * 64})),
                   replace(rdac_b, consegna=a)):
        assert not riscontra_invio_storico(raw, [("RAC", rac), ("A", rdac_a), ("B", errata)])


def test_il_reimport_delle_stesse_ricevute_conserva_il_riscontro_sql(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from pct.registro_letture import Oggetto, RegistroLetture
    from web.services import archivio_letture_runtime, notifiche_storiche_archivio

    mittente, destinatario = "studio@example.test", "destinatario@example.test"
    allegato = b"sentenza"
    messaggio = EmailMessage()
    messaggio["From"] = mittente
    messaggio["To"] = destinatario
    messaggio["Message-ID"] = "<invio@example.test>"
    messaggio["Subject"] = "Notificazione ai sensi della legge n. 53/1994"
    messaggio.set_content("Notificazione")
    messaggio.add_attachment(allegato, maintype="application", subtype="pdf", filename="sentenza.pdf")
    rac_bytes = b"Content-Type: multipart/signed\r\nX-Ricevuta: accettazione\r\n\r\n"
    rdac_bytes = b"Content-Type: multipart/signed\r\nX-Ricevuta: avvenuta-consegna\r\n\r\n"
    rac = Ricevuta("accettazione", "gestore@example.test", "invio@example.test",
                   datetime(2026, 4, 20, 8, 17, tzinfo=timezone.utc),
                   frozenset({mittente}), frozenset({destinatario}), "", frozenset())
    rdac = replace(rac, tipo="avvenuta-consegna", consegna=destinatario,
                   impronte=frozenset({hashlib.sha256(allegato).hexdigest()}))
    contenuti = {"invio": messaggio.as_bytes(), "rac": rac_bytes, "rdac": rdac_bytes}
    fascicolo = SimpleNamespace(id="F", documenti=[])
    registro = RegistroLetture(tmp_path / "letture.sqlite")
    monkeypatch.setattr(archivio_letture_runtime, "_bytes_documento", lambda _, doc: contenuti[doc.id])
    monkeypatch.setattr(archivio_letture_runtime, "_formato_documento", lambda _: ".eml")
    monkeypatch.setattr(notifiche_storiche_archivio, "verifica_ricevuta_storica",
                        {rac_bytes: rac, rdac_bytes: rdac}.__getitem__)

    def aggiorna_inventario():
        fascicolo.documenti = [SimpleNamespace(id=oid) for oid in reversed(contenuti)]
        registro.registra_inventario("studio", fascicolo.id, [
            Oggetto("documento", oid, sha256=hashlib.sha256(raw).hexdigest())
            for oid, raw in contenuti.items()
        ])

    aggiorna_inventario()
    assert notifiche_storiche_archivio.registra_riscontri_notifiche(fascicolo, registro, "studio") == 1

    contenuti.update({"rac-copia": rac_bytes, "rdac-copia": rdac_bytes})
    aggiorna_inventario()
    assert notifiche_storiche_archivio.registra_riscontri_notifiche(fascicolo, registro, "studio") == 0
    [fatto] = registro.fatti("studio", fascicolo.id, campo="riscontro_notifica_pec_storica")
    assert set(fatto.prove[0]["impronte_eml"]) == {"invio", "rac", "rdac"}
