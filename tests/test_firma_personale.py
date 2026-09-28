"""«La mia firma»: ogni avvocato dello studio sceglie il proprio gestore o dispositivo.

Due avvocati dello stesso studio con prestatori diversi firmano ciascuno con il proprio
servizio; chi non ha scelto usa la firma dello studio. Password e OTP non si salvano.
"""

from __future__ import annotations

import io
import json

import pytest

from pct.auth import RuoloUtente
from pct.config_studio import ConfigFirma
from pct.firma_profili import ArchivioProfiliFirma, firma_effettiva
from tests.firma_remota_simulata import ServizioSimulato

INTESTAZIONI = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


def test_archivio_e_firma_effettiva(tmp_path):
    archivio = ArchivioProfiliFirma.accanto_a(tmp_path / "config" / "studio.json")
    assert archivio.percorso == tmp_path / "config" / "firme_avvocati.json"
    assert archivio.leggi("u1") is None
    archivio.salva("u1", {"backend_preferito": "remota", "prestatore": "namirial", "remota_utente": "RHI123",
                          "campo_estraneo": "x"})
    profilo = archivio.leggi("u1")
    assert profilo["prestatore"] == "namirial" and "campo_estraneo" not in profilo and profilo["aggiornato_il"]
    with pytest.raises(ValueError):
        archivio.salva("u1", {"backend_preferito": "remota", "password": "segreta"})
    studio = ConfigFirma(backend_preferito="pkcs11", dispositivo_produttore="bit4id", p12_path="/x.p12")
    personale = firma_effettiva(studio, profilo)
    assert personale.backend_preferito_normalizzato == "remota" and personale.remota_utente == "RHI123"
    assert personale.p12_path == "/x.p12" and personale.dispositivo_produttore == ""
    assert firma_effettiva(studio, None) is studio
    assert firma_effettiva(studio, {"backend_preferito": "studio"}) is studio
    assert archivio.rimuovi("u1") and archivio.leggi("u1") is None and not archivio.rimuovi("u1")


def _pdf() -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    tela = canvas.Canvas(buffer)
    tela.drawString(72, 720, "Comparsa")
    tela.save()
    return buffer.getvalue()


@pytest.fixture()
def studio(tmp_path, monkeypatch):
    import requests

    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _create_user
    from web.helpers import get_fascicoli

    servizio = ServizioSimulato()
    monkeypatch.setattr(requests, "post", servizio.post)
    app = _app(tmp_path)
    _create_user(app, "avv.rossi", "Rossi12345!", ruolo=RuoloUtente.AVVOCATO)
    _create_user(app, "avv.verdi", "Verdi12345!", ruolo=RuoloUtente.AVVOCATO)
    _create_user(app, "segreteria", "Segreteria123!", ruolo=RuoloUtente.SEGRETERIA)
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE)
        pdf = get_fascicoli().aggiungi_documento(fascicolo.id, "Comparsa.pdf", TipoDocumento.RICORSO, _pdf())
    return app, fascicolo.id, pdf.id, tmp_path


def _entra(app, utente, password):
    client = app.test_client()
    risposta = client.post("/login", data={"username": utente, "password": password}, follow_redirects=True)
    assert risposta.status_code == 200
    return client


def _mia(client, **corpo):
    return client.post("/api/v1/ui/impostazioni/firma-personale", json=corpo, headers=INTESTAZIONI)


def test_ogni_avvocato_ha_il_suo_gestore(studio):
    app, id_fasc, id_pdf, tmp_path = studio
    # Lo studio firma con il dispositivo; Rossi usa Aruba, Verdi resta sulla firma dello studio.
    with _entra(app, "operatore", "Operatore123!") as admin:
        assert admin.post("/api/v1/ui/impostazioni/firma", json={"backend_preferito": "pkcs11", "dispositivo_produttore": "bit4id"},
                          headers=INTESTAZIONI).get_json()["ok"]
    with _entra(app, "avv.rossi", "Rossi12345!") as rossi:
        iniziale = rossi.get("/api/v1/ui/impostazioni/firma-personale", headers=INTESTAZIONI).get_json()
        assert iniziale["ok"] and iniziale["puo_modificare"] and iniziale["personale"] is False
        assert iniziale["valori"]["canale"] == "studio" and iniziale["studio"]["canale"] == "pkcs11"
        # Il prestatore decide cosa serve: Aruba non chiama il codice per notifica, InfoCert vuole l'indirizzo.
        errore = _mia(rossi, canale="remota", prestatore="aruba", remota_tipo_otp="notifica").get_json()
        assert errore["ok"] is False and "remota_tipo_otp" in errore["errors"]
        errore = _mia(rossi, canale="remota", prestatore="infocert").get_json()
        assert "remota_endpoint" in errore["errors"]
        errore = _mia(rossi, canale="remota", prestatore="infocert", remota_endpoint="https://firma.example.it/api").get_json()
        assert "/csc/v1" in errore["errors"]["remota_endpoint"]
        errore = _mia(rossi, canale="remota", prestatore="poste").get_json()
        assert "Firma esterna" in errore["errors"]["prestatore"]
        assert _mia(rossi, canale="p12").status_code == 400
        salvato = _mia(rossi, canale="remota", prestatore="aruba", remota_utente="avv.rossi", remota_dominio="firma",
                       remota_tipo_otp="sms").get_json()
        assert salvato["ok"], salvato
        assert salvato["profilo"]["personale"] and salvato["profilo"]["valori"]["prestatore"] == "aruba"
        assert salvato["profilo"]["prestatore_info"]["endpoint_predefinito"].startswith("https://arss.arubapec.it/")
        stato = rossi.get("/api/firma/remota/stato", headers=INTESTAZIONI).get_json()
        assert stato["attiva"] and stato["prestatore"].startswith("Aruba") and stato["utente"] == "avv.rossi"
        prova = rossi.post("/api/v1/ui/impostazioni/firma-personale/prova", json={"password": "Firma!2026"},
                           headers=INTESTAZIONI).get_json()
        assert prova["ok"] and prova["intestatario"] == "ROSSI MARIO"
        assert rossi.post("/api/firma/remota/otp", json={"password": "Firma!2026"}, headers=INTESTAZIONI).get_json()["ok"]
        firmato = rossi.post("/api/firma/remota/firma-documento", headers=INTESTAZIONI, json={
            "fascicolo_id": id_fasc, "documento_id": id_pdf, "password": "Firma!2026", "otp": "123456"}).get_json()
        assert firmato["ok"] and firmato["formato"] == "pades", firmato
    with _entra(app, "avv.verdi", "Verdi12345!") as verdi:
        stato = verdi.get("/api/firma/remota/stato", headers=INTESTAZIONI).get_json()
        assert stato["attiva"] is False and "La mia firma" in stato["messaggio"]
        assert _mia(verdi, canale="pkcs11", dispositivo_produttore="athena").get_json()["ok"]
        mia = verdi.get("/api/v1/ui/impostazioni/firma-personale", headers=INTESTAZIONI).get_json()
        assert mia["valori"]["canale"] == "pkcs11" and any(p.endswith("asepkcs.dll") for p in mia["librerie_dispositivo"]["windows"])
        assert _mia(verdi, canale="studio").get_json()["profilo"]["personale"] is False
    with _entra(app, "segreteria", "Segreteria123!") as segreteria:
        negato = _mia(segreteria, canale="remota", prestatore="aruba")
        assert negato.status_code == 403
        assert segreteria.get("/api/v1/ui/impostazioni/firma-personale", headers=INTESTAZIONI).get_json()["puo_modificare"] is False
    archivio = next(tmp_path.rglob("firme_avvocati.json"))
    dati = json.loads(archivio.read_text(encoding="utf-8"))
    assert len(dati["profili"]) == 1  # Rossi; Verdi è tornato alla firma dello studio
    for file in tmp_path.rglob("*"):
        if file.is_file() and file.suffix in {".json", ".db", ".sqlite", ".log"}:
            contenuto = file.read_bytes()
            assert b"Firma!2026" not in contenuto and b"123456" not in contenuto, file
