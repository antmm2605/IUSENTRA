"""Il registro delle letture dentro l'applicazione: inventario, eventi, endpoint, verifica delle date.

Un documento caricato entra nel registro e invalida la lettura in cache; il
pannello mostra per lettore che cosa manca; «Leggi i nuovi» accoda solo ciò
che non è letto; una data letta male diventa un'anomalia che l'avvocato
conferma o corregge dall'endpoint.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pct.fascicoli import TipoDocumento, TipoFascicolo
from pct.registro_letture import Oggetto
from tests.test_react_shell import _app

HEADERS = {"X-API-Key": "react-test-key"}
PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


def _seed(app) -> tuple[str, str]:
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("Bianchi / Delta S.r.l.", TipoFascicolo.CIVILE, nome_cliente="Anna Bianchi", tribunale="Tribunale di Torino", numero_rg="777", anno_rg=2026)
        documento = fascicoli.aggiungi_documento(fascicolo.id, nome_file="decreto.pdf", tipo=TipoDocumento.ALTRO, contenuto=PDF, hash_contenuto_sha256="a" * 64)
        return fascicolo.id, documento.id


def test_endpoint_letture_censisce_i_documenti_e_le_novita_per_utente(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, documento_id = _seed(app)
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture", headers=HEADERS)
        assert risposta.status_code == 200
        letture = risposta.get_json()["letture"]
        assert letture["oggetti"] == 1 and letture["tutto_letto"] is False
        per_lettore = {voce["lettore"]: voce for voce in letture["lettori"]}
        assert per_lettore["ocr"]["etichetta"] == "Testo e ricerca" and per_lettore["ocr"]["da_leggere"] == 1
        assert per_lettore["indice_documentale"]["da_leggere"] == 1
        oggetto = letture["per_oggetto"][0]
        assert oggetto["oggetto_id"] == documento_id and oggetto["etichetta"] == "decreto.pdf"
        assert oggetto["cliente"] == "Anna Bianchi" and oggetto["numero_rg"] == "777" and oggetto["anno_rg"] == "2026"
        assert oggetto["letture"]["ocr"] == "da_leggere"
        assert letture["novita"]["prima_vista"] is True
        assert letture["anomalie"] == []
        assert client.get("/api/v1/ui/fascicoli/NONESISTE/letture", headers=HEADERS).status_code == 404


def test_un_documento_caricato_entra_nel_registro_e_invalida_la_lettura(tmp_path: Path):
    from web.services.lettura_cache import LETTURA_CACHE, chiave_lettura

    app = _app(tmp_path)
    fascicolo_id, documento_id = _seed(app)
    with app.app_context():
        from web.services.registro_letture_runtime import documento_aggiornato, documento_rimosso, registro_corrente, tenant_corrente

        registro = registro_corrente()
        tenant = tenant_corrente()
        LETTURA_CACHE.set(chiave_lettura("", fascicolo_id), b"{}")
        documento_aggiornato(fascicolo_id)
        assert LETTURA_CACHE.get(chiave_lettura("", fascicolo_id)) is None
        oggetti = registro.oggetti(tenant, fascicolo_id)
        assert [o.oggetto_id for o in oggetti] == [documento_id]
        assert oggetti[0].sha256 == "a" * 64  # impronta in chiaro passata al caricamento
        documento_rimosso(fascicolo_id, documento_id)
        assert registro.oggetti(tenant, fascicolo_id) == []



def test_cache_lettura_persistente_nel_registro_sql_e_invalidata_da_eventi(tmp_path: Path):
    from web.services.lettura_cache import LETTURA_CACHE, chiave_lettura

    app = _app(tmp_path)
    fascicolo_id, documento_id = _seed(app)
    with app.app_context():
        from web.services.registro_letture_runtime import documento_aggiornato, registro_corrente, tenant_corrente

        registro = registro_corrente()
        tenant = tenant_corrente()
        key = chiave_lettura(tenant, fascicolo_id)
        LETTURA_CACHE.set(key, b'{"ok":true,"lettura":{"lacune":[]}}')
        LETTURA_CACHE._memory.clear()

        assert LETTURA_CACHE.get(key) == b'{"ok":true,"lettura":{"lacune":[]}}'
        rows = registro._seleziona("letture_payload_cache", "tenant_id = ? AND fascicolo_id = ?", (tenant, fascicolo_id))
        assert len(rows) == 1 and rows[0]["payload_json"].startswith('{"ok":true')

        documento_aggiornato(fascicolo_id)
        assert LETTURA_CACHE.get(key) is None
        assert registro._seleziona("letture_payload_cache", "tenant_id = ? AND fascicolo_id = ?", (tenant, fascicolo_id)) == []


def test_presidio_economico_scheduler_salta_tenant_fermo(tmp_path: Path, monkeypatch):
    app = _app(tmp_path)
    calls: list[str] = []

    def fake_presidio(**kwargs):
        calls.append("run")
        return {
            "ok": True,
            "source": "repository_reali",
            "created": [],
            "createdCount": 0,
            "existingCount": 0,
            "missingBasisCount": 0,
            "processedDefined": 0,
            "contributiCheckedCount": 7,
            "contributiUpdatedCount": 0,
            "contributiMissingCount": 0,
            "documentAnalysisUpdatedCount": 0,
            "documentAnalysisCandidateCount": 0,
            "documentAnalysisPendingCount": 0,
            "statusDefinedUpdatedCount": 0,
            "skippedCount": 0,
        }

    monkeypatch.setattr("web.services.react_fascicoli_bridge.run_react_fascicoli_economic_presidio", fake_presidio)
    with app.test_request_context("/__test/presidio"):
        from web.services.fascicoli_presidi_runtime import run_fascicoli_document_economic_presidio_for_current_context

        first = run_fascicoli_document_economic_presidio_for_current_context(limit=25)
        second = run_fascicoli_document_economic_presidio_for_current_context(limit=25)

    assert calls == ["run"]
    assert first["contributiCheckedCount"] == 7
    assert second["idle"] is True
    assert second["contributiCheckedCount"] == 0

def test_l_indice_documentale_non_decifra_i_documenti_gia_letti(tmp_path: Path):
    """La raccolta delle sorgenti usa l'impronta nota: niente lettura né decifratura del file."""
    from pct.document_intelligence.sources import source_from_fascicolo_document

    aperture: list[str] = []

    def decifra(dati: bytes) -> bytes:
        aperture.append("decifrato")
        return dati

    root = tmp_path / "docs"
    root.mkdir()
    (root / "atto.pdf").write_bytes(PDF)
    documento = SimpleNamespace(id="d1", nome="atto.pdf", percorso="atto.pdf", dimensione_bytes=len(PDF), hash_sha256="e" * 64, hash_contenuto_sha256="e" * 64, tipo=SimpleNamespace(value="ATTO"), fonte_documento="", data_caricamento="2026-09-15")

    class Impronte:
        def __init__(self):
            self.imparate = []
        def nota(self, doc):
            return "f" * 64 if self.imparate else ""
        def impara(self, doc, sha, size=0):
            self.imparate.append(sha)

    impronte = Impronte()
    prima = source_from_fascicolo_document(tenant_id="t", fascicolo_id="F", document=documento, documents_root=root, decrypt=decifra, impronte=impronte)
    assert aperture == ["decifrato"] and impronte.imparate and prima.sha256 == impronte.imparate[0]
    seconda = source_from_fascicolo_document(tenant_id="t", fascicolo_id="F", document=documento, documents_root=root, decrypt=decifra, impronte=impronte)
    assert aperture == ["decifrato"]  # nessuna nuova decifratura
    assert seconda.sha256 == "f" * 64 and seconda.content_bytes is None and seconda.content_path == root / "atto.pdf"
    assert seconda.read_bytes() == PDF  # il contenuto resta disponibile a chi deve indicizzare
    # Impronta in chiaro dichiarata dal caricamento: neanche la prima lettura apre il file.
    dichiarato = SimpleNamespace(**{**documento.__dict__, "hash_contenuto_sha256": "c" * 64})
    aperture.clear()
    terza = source_from_fascicolo_document(tenant_id="t", fascicolo_id="F", document=dichiarato, documents_root=root, decrypt=decifra, impronte=None)
    assert aperture == [] and terza.sha256 == "c" * 64


def test_la_coda_ocr_rifiuta_i_documenti_gia_letti(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, documento_id = _seed(app)
    with app.app_context():
        from web.services.registro_letture_runtime import aggiorna_inventario, registro_corrente, tenant_corrente

        registro = registro_corrente()
        tenant = tenant_corrente()
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        documento = next(d for d in fascicoli.get(fascicolo_id).documenti if d.id == documento_id)
        ocr_runtime = app.extensions["ocr_runtime"]
        prima = ocr_runtime.store.status_snapshot()["totale"]
        aggiorna_inventario(fascicoli.get(fascicolo_id), registro=registro, con_pec=False)
        oggetto = registro.oggetto(tenant, fascicolo_id, "documento", documento_id)
        assert oggetto is not None
        registro.segna_letto(tenant, fascicolo_id, oggetto, "ocr", esito={"caratteri": 10})
        ocr_runtime.enqueue(percorso=str(fascicoli.percorso_documento(fascicolo_id, documento_id)), hash_sha256=documento.hash_sha256, id_fasc=fascicolo_id, id_doc=documento_id, nome_doc="decreto.pdf", tipo_doc="ALTRO", index_path=app.config["SEARCH_INDEX"])
        assert ocr_runtime.store.status_snapshot()["totale"] == prima  # gia' letto: nessun job nuovo
        registro.registra_inventario(tenant, fascicolo_id, [Oggetto(tipo="documento", oggetto_id=documento_id, nome="decreto.pdf", sha256="b" * 64, sha256_archivio="nuovo")])
        ocr_runtime.enqueue(percorso="x", hash_sha256="nuovo", id_fasc=fascicolo_id, id_doc=documento_id, nome_doc="decreto.pdf", tipo_doc="ALTRO", index_path=app.config["SEARCH_INDEX"])
        assert ocr_runtime.store.status_snapshot()["totale"] == prima + 1  # contenuto cambiato: si rilegge


def test_anomalia_sulla_data_si_conferma_o_si_corregge_dall_endpoint(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, documento_id = _seed(app)
    with app.app_context():
        from web.services.registro_letture_runtime import aggiorna_inventario, registro_corrente, registra_lettura, tenant_corrente

        registro = registro_corrente()
        tenant = tenant_corrente()
        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fascicolo_id)
        aggiorna_inventario(fascicolo, registro=registro, con_pec=False)
        oggetto = registro.oggetto(tenant, fascicolo_id, "documento", documento_id)
        assert oggetto is not None
        esito = registra_lettura(fascicolo, oggetto, "ocr", esito={"date_processuali": [{"raw_date": "1O/O3/2O26", "label": "udienza", "context": "udienza del 1O/O3/2O26"}], "date": ["31/02/2026"]})
        assert [a["codice"] for a in esito["anomalie"]] == ["corretta_da_ocr", "giorno_inesistente"]
    with app.test_client() as client:
        letture = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture", headers=HEADERS).get_json()["letture"]
        assert letture["anomalie_aperte"] == 2
        anomalia = next(a for a in letture["anomalie"] if a["codice"] == "corretta_da_ocr")
        assert anomalia["oggetto"] == "decreto.pdf" and anomalia["lettore_etichetta"] == "Testo e ricerca" and anomalia["valore_proposto"] == "10/03/2026"
        corretta = client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture/anomalie/{anomalia['id']}", json={"esito": "corretta", "valore": "11/03/2026"}, headers=HEADERS).get_json()
        assert corretta["ok"] is True and corretta["anomalia"]["stato"] == "corretta" and corretta["anomalia"]["valore_confermato"] == "11/03/2026"
        altra = next(a for a in letture["anomalie"] if a["codice"] == "giorno_inesistente")
        assert client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture/anomalie/{altra['id']}", json={"esito": "ignorata"}, headers=HEADERS).get_json()["ok"] is True
        assert client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture/anomalie/{altra['id']}", json={"esito": "corretta", "valore": ""}, headers=HEADERS).get_json()["ok"] is False
        dopo = client.get(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture", headers=HEADERS).get_json()["letture"]
        assert dopo["anomalie_aperte"] == 0
    with app.app_context():
        assert registro.correzioni(tenant, fascicolo_id) == {(documento_id, "udienza", "1O/O3/2O26"): "11/03/2026"}




def test_leggi_i_nuovi_chiude_ocr_sui_formati_non_ocr(tmp_path: Path):
    app = _app(tmp_path)
    with app.app_context():
        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("PEC / EML", TipoFascicolo.CIVILE, nome_cliente="Anna Bianchi", tribunale="Tribunale di Torino", numero_rg="778", anno_rg=2026)
        documento = fascicoli.aggiungi_documento(
            fascicolo.id,
            nome_file="accettazione-deposito.eml",
            tipo=TipoDocumento.COMUNICAZIONE,
            contenuto=b"From: cancelleria@example.test\nSubject: ACCETTAZIONE DEPOSITO\n\nMessaggio PEC",
            hash_contenuto_sha256="e" * 64,
        )
    with app.test_client() as client:
        risposta = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/letture/aggiorna", json={}, headers=HEADERS)
        assert risposta.status_code == 200
        payload = risposta.get_json()
        assert payload["ok"] is True
    with app.app_context():
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        registro = registro_corrente()
        stato = registro.stato_fascicolo(tenant_corrente(), fascicolo.id, lettori=("ocr",))
        assert [(voce.letti, voce.da_leggere, voce.errori) for voce in stato.lettori] == [(1, 0, 0)]
        lettura = next(l for l in registro.letture(tenant_corrente(), fascicolo.id, lettore="ocr") if l.oggetto_id == documento.id)
        assert lettura.stato == "letto"
        assert "OCR non necessario" in lettura.esito.get("motivo", "")

def test_leggi_i_nuovi_accoda_solo_cio_che_manca(tmp_path: Path):
    app = _app(tmp_path)
    fascicolo_id, _documento_id = _seed(app)
    with app.test_client() as client:
        risposta = client.post(f"/api/v1/ui/fascicoli/{fascicolo_id}/letture/aggiorna", json={}, headers=HEADERS)
        assert risposta.status_code == 200
        payload = risposta.get_json()
        assert payload["ok"] is True
        assert payload["esito"]["da_leggere_prima"] == 1
        assert "messaggio" in payload["esito"] and "letture" in payload
        # Il presidio documentale legge le date con le lettere e le mette da confermare.
        assert isinstance(payload["letture"]["lettori"], list)
