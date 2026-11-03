"""Correzioni nate dal collaudo dei motori del 03/11/2026 (registro scratchpad COLLAUDO_MOTORI.md, D1–D5)."""

from __future__ import annotations

import time
from pathlib import Path

from tests.test_archivio_letture_runtime import _app


def _attendi_thread(runtime, secondi: float = 20) -> None:
    limite = time.monotonic() + secondi
    while runtime.letture_attive() and time.monotonic() < limite:
        time.sleep(0.1)


def test_d1_evento_di_fascicolo_inesistente_si_chiude_senza_errore(tmp_path: Path):
    from pct.registro_letture import Oggetto
    from web.services import archivio_letture_runtime as runtime
    from web.services.registro_letture_runtime import CHIAVE_PERCORSO, registro_per_percorsi

    app = _app(tmp_path)
    paths = {CHIAVE_PERCORSO: str(tmp_path / "registro-d1.db")}
    registro = registro_per_percorsi(paths)
    registro.registra_inventario("studio", "DEADBEEF", [Oggetto(tipo="documento", oggetto_id="d1", sha256="a" * 64)])
    registro.accoda_evento("studio", "DEADBEEF")
    with app.app_context():
        assert runtime.avvia_lettura_in_background(app, "DEADBEEF", paths=paths, tenant_slug="studio", _accoda_evento=False)
        _attendi_thread(runtime)
    esito = registro.esito_evento("studio", "DEADBEEF")
    assert esito["stato"] == "idle" and not esito["last_error"]
    assert registro.oggetti("studio", "DEADBEEF") == []  # nessun oggetto resta «da leggere»
    assert registro.reclama_evento("studio", "DEADBEEF", "altro") is None


def test_d2_la_prenotazione_si_proroga_durante_i_passi_finali(tmp_path: Path, monkeypatch):
    from pct.registro_letture.repository import RegistroLetture
    from tests.test_archivio_letture_runtime import _seed
    from web.services import archivio_letture_runtime as runtime
    from web.services.registro_letture_runtime import CHIAVE_PERCORSO, registro_per_percorsi

    app = _app(tmp_path)
    fascicolo_id, _d, _r = _seed(app)
    paths = {CHIAVE_PERCORSO: str(tmp_path / "registro-d2.db")}
    registro_per_percorsi(paths).accoda_evento("studio", fascicolo_id)
    proroghe: list[str] = []
    originale = RegistroLetture.rinnova_evento
    passi: list[str] = []

    def rinnova(self, *args, **kwargs):
        proroghe.append(passi[-1] if passi else "inizio")
        return originale(self, *args, **kwargs)

    monkeypatch.setattr(RegistroLetture, "rinnova_evento", rinnova)
    monkeypatch.setattr(runtime, "_prepara_lettura", lambda fid: passi.append("lettura") or True)
    monkeypatch.setattr(runtime, "_registra_esiti_udienze", lambda f: passi.append("esiti"))
    monkeypatch.setattr("web.services.discordanze_letture_runtime.verifica_discordanze_fascicolo", lambda f: passi.append("discordanze"))
    with app.app_context():
        assert runtime.avvia_lettura_in_background(app, fascicolo_id, paths=paths, tenant_slug="studio", _accoda_evento=False)
        _attendi_thread(runtime, 60)
    assert "esiti" in proroghe  # dopo gli esiti delle udienze e prima della Lettura la prenotazione è prorogata
    assert len(proroghe) >= 4


def test_d3_lettori_doppioni_non_censiti_e_lettori_su_richiesta_senza_arretrato(tmp_path: Path):
    from pct.registro_letture import LETTORI, Oggetto, RegistroLetture

    assert "presidio_pec" not in LETTORI and "sentenza_da_archiviare" not in LETTORI
    registro = RegistroLetture(tmp_path / "registro-d3.db")
    oggetti = [Oggetto(tipo="documento", oggetto_id=f"d{i}", sha256=str(i) * 64) for i in range(3)]
    registro.registra_inventario("studio", "F1", oggetti)
    stato = {v.lettore: v for v in registro.stato_fascicolo("studio", "F1").lettori}
    assert stato["scadenze_pdf"].da_leggere == 0 and stato["scadenze_pdf"].completa
    assert stato["proforma_automatica"].da_leggere == 0 and stato["proforma_automatica"].completa
    assert stato["motore_documenti"].da_leggere == 3  # un motore che deve leggere tutto conta ancora l'arretrato
    registro.segna_fascicolo("studio", "F1", "proforma_automatica", impronta="vecchia", oggetti_totali=3, oggetti_letti=3)
    stato = {v.lettore: v for v in registro.stato_fascicolo("studio", "F1").lettori}
    assert stato["proforma_automatica"].da_leggere == 3  # letto con un inventario diverso: ora è da rileggere


def test_d4_ocr_chiuso_dove_c_e_testo_e_accodato_una_volta_dove_manca(tmp_path: Path, monkeypatch):
    from pct.registro_letture import Oggetto, RegistroLetture
    from web.services.ocr_da_archivio import allinea_ocr_fascicolo

    class Coda:
        def __init__(self):
            self.lavori: list[str] = []

        def enqueue(self, **kw):
            self.lavori.append(kw["id_doc"])
            return len(self.lavori)

    class Doc:
        def __init__(self, ident):
            self.id, self.nome, self.hash_sha256, self.tipo = ident, f"{ident}.pdf", "", "ALTRO"

    class Fasc:
        id = "F4"
        documenti = [Doc("nativo"), Doc("scansione"), Doc("nuovo")]

    app = _app(tmp_path)
    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: type("G", (), {"percorso_documento": lambda self, f, d: tmp_path / f"{d}.pdf"})())
    coda = Coda()
    app.extensions["ocr_runtime"] = coda
    registro = RegistroLetture(tmp_path / "registro-d4.db")
    oggetti = {n: Oggetto(tipo="documento", oggetto_id=n, sha256=c * 64) for n, c in (("nativo", "a"), ("scansione", "b"), ("nuovo", "c"))}
    registro.registra_inventario("studio", "F4", list(oggetti.values()))
    registro.segna_letto("studio", "F4", oggetti["nativo"], "motore_documenti", esito={"origine": "nativo"})
    registro.segna_letto("studio", "F4", oggetti["scansione"], "motore_documenti", stato="non_leggibile",
                         esito={"motivo": "Il file è leggibile ma non contiene testo estraibile."})
    with app.test_request_context("/"):
        primo = allinea_ocr_fascicolo(registro, "studio", Fasc())
    assert primo == {"non_necessari": 1, "accodati": 1} and coda.lavori == ["scansione"]
    letture_ocr = {lt.oggetto_id: lt.stato for lt in registro.letture("studio", "F4", lettore="ocr")}
    assert letture_ocr == {"nativo": "letto"}  # il documento nuovo aspetta il motore documenti
    registro.segna_letto("studio", "F4", oggetti["scansione"], "ocr", stato="errore", esito={"errore": "OCR non riuscito"})
    with app.test_request_context("/"):
        secondo = allinea_ocr_fascicolo(registro, "studio", Fasc())
    assert secondo == {"non_necessari": 0, "accodati": 0} and coda.lavori == ["scansione"]  # una sola volta


def test_d5_impronta_della_casella_sql_cambia_con_i_messaggi_anche_se_il_json_e_fermo(tmp_path: Path, monkeypatch):
    import sqlite3
    from types import SimpleNamespace

    from web.services import pec_pipeline_runtime as runtime

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE email_mailbox_records (tenant_key TEXT, mailbox_kind TEXT, message_key TEXT, updated_at TEXT)")
    casella = SimpleNamespace(repository=SimpleNamespace(db=SimpleNamespace(conn=conn), tenant="studio-2", kind="pec"), _carica=lambda: {})
    monkeypatch.setattr(runtime, "create_email_mailbox", lambda **kw: casella)
    archivio = tmp_path / "email" / "casella.json"  # con la casella nel database il file non esiste più
    conn.execute("INSERT INTO email_mailbox_records VALUES ('studio-2','pec','m1','2026-11-01T10:00:00')")
    prima = runtime._archive_fingerprint(archivio)
    conn.execute("INSERT INTO email_mailbox_records VALUES ('studio-2','pec','m2','2026-11-03T09:00:00')")
    dopo = runtime._archive_fingerprint(archivio)
    assert prima.startswith("sql:1:") and dopo.startswith("sql:2:") and prima != dopo
    report = runtime.acquire_local_pec_for_paths({"EMAIL_CASELLA_DB": str(archivio)}, tenant_label="studio-2")
    assert report.get("reason") != "archivio email assente"
