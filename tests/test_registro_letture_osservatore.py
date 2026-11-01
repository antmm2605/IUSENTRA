"""Ogni via che cambia i documenti di un fascicolo arriva al registro delle letture (01/11/2026)."""

from __future__ import annotations

from pathlib import Path


def test_il_decoratore_avvisa_dopo_il_salvataggio_e_non_su_errore():
    from pct.fascicoli_osservatori import documenti_cambiati, registra_osservatore, rimuovi_osservatore

    visti: list[tuple[str, str]] = []

    def osserva(fid, evento):
        visti.append((fid, evento))

    class Archivio:
        @documenti_cambiati("aggiunto")
        def aggiungi_documento(self, id_fasc, nome):
            return nome

        @documenti_cambiati("copiato")
        def copia(self, primary, doc):
            raise RuntimeError("salvataggio fallito")

    registra_osservatore(osserva)
    try:
        assert Archivio().aggiungi_documento("F1", "atto.pdf") == "atto.pdf"
        assert Archivio().aggiungi_documento(id_fasc="F2", nome="x") == "x"
        try:
            Archivio().copia(type("P", (), {"id": "F3"})(), None)
        except RuntimeError:
            pass
    finally:
        rimuovi_osservatore(osserva)
    assert visti == [("F1", "aggiunto"), ("F2", "aggiunto")]


def test_nella_richiesta_un_solo_evento_per_fascicolo_e_mai_doppio(tmp_path: Path, monkeypatch):
    from tests.test_archivio_letture_runtime import _app

    app = _app(tmp_path)
    inviati: list[str] = []
    monkeypatch.setattr("web.services.registro_letture_runtime.documento_aggiornato", lambda fid, *a, **k: inviati.append(fid))
    from web.services import registro_letture_osservatore as osservatore

    with app.test_request_context("/prova"):
        osservatore.osservatore_documenti("F1", "aggiunto")
        osservatore.osservatore_documenti("F1", "sostituito")
        osservatore.osservatore_documenti("F2", "rimosso")
        osservatore.segna_evento_inviato("F2")  # la rotta l'ha già inviato
        osservatore.invia_eventi_in_attesa(None)
    assert inviati == ["F1"]


def test_fuori_dalla_richiesta_il_fascicolo_si_accoda(tmp_path: Path, monkeypatch):
    from tests.test_archivio_letture_runtime import _app

    app = _app(tmp_path)
    accodati: list[str] = []

    class Registro:
        def accoda_evento(self, tenant, fid):
            accodati.append(fid)

    monkeypatch.setattr("web.services.registro_letture_runtime.registro_corrente", lambda: Registro())
    from web.services.registro_letture_osservatore import osservatore_documenti

    with app.app_context():
        osservatore_documenti("F9", "aggiunto")
    assert accodati == ["F9"]


def test_i_metodi_dell_archivio_sono_osservati():
    from pct.fascicoli import GestioneFascicoli

    for nome in ("aggiungi_documento", "sostituisci_documento", "rimuovi_documento", "ripristina_documento",
                 "elimina_documento_definitivamente", "_copia_documento_su_fascicolo_principale"):
        assert getattr(GestioneFascicoli, nome).__wrapped__, nome


def test_un_documento_aggiunto_fuori_dalla_richiesta_mette_il_fascicolo_in_coda(tmp_path: Path):
    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from tests.test_archivio_letture_runtime import DECRETO, _app

    app = _app(tmp_path)
    with app.app_context():
        from web.services.registro_letture_runtime import registro_corrente

        fascicoli = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = fascicoli.nuovo("Import / Prova", TipoFascicolo.CIVILE, nome_cliente="Anna Bianchi")
        fascicoli.aggiungi_documento(fascicolo.id, nome_file="decreto.pdf", tipo=TipoDocumento.ALTRO, contenuto=DECRETO)
        assert fascicolo.id in {e["fascicolo_id"] for e in registro_corrente().eventi_da_riprendere()}


def test_chi_indicizza_pochi_documenti_li_segna_nel_registro_senza_chiudere_il_fascicolo(monkeypatch):
    from types import SimpleNamespace

    from web.services import document_intelligence_runtime as runtime

    registrati = []
    monkeypatch.setattr(runtime, "_registro_indice_documentale", lambda fid, sources: {"registro": object(), "oggetti": ["x"]})
    monkeypatch.setattr(runtime, "_registra_indice_documentale", lambda registro, summary, sources, **kw: registrati.append(kw))
    service = SimpleNamespace(process_lex_indexing_sources=lambda *a, **k: SimpleNamespace(summary="riepilogo", errors=[]))
    esito = runtime.indicizza_e_registra(service, "studio", "F1", ["fonte"], object(), retry_errors=False)
    assert esito.summary == "riepilogo"
    assert registrati and registrati[0]["chiudi_fascicolo"] is False and registrati[0]["fascicolo_id"] == "F1"


def test_nessuna_via_web_indicizza_senza_registrare():
    from pathlib import Path

    radice = Path(__file__).resolve().parents[1] / "web"
    dirette = [
        str(percorso.relative_to(radice)) for percorso in radice.rglob("*.py")
        if "process_lex_indexing_sources(" in percorso.read_text(encoding="utf-8")
    ]
    assert dirette == ["services/document_intelligence_runtime.py"]


def test_il_rag_legacy_non_riscrive_le_letture_dei_documenti_invariati(tmp_path: Path):
    from types import SimpleNamespace

    from pct.local_ai import LocalAIService
    from pct.registro_letture import Oggetto, RegistroLetture

    registro = RegistroLetture(tmp_path / "registro-rag.db")
    oggetto = Oggetto(tipo="documento", oggetto_id="D1", nome="atto.pdf", sha256="a" * 64)
    registro.registra_inventario("studio", "F1", [oggetto])
    registro.segna_letto("studio", "F1", oggetto, "rag_locale")
    servizio = LocalAIService.__new__(LocalAIService)
    servizio.registro_letture = lambda: (registro, "studio")
    scritture = []
    originale = registro.segna_letto
    registro.segna_letto = lambda *a, **k: scritture.append(a) or originale(*a, **k)
    fascicolo, doc = SimpleNamespace(id="F1"), SimpleNamespace(id="D1")
    stato = servizio._stato_registro_rag(fascicolo)
    servizio._registra_lettura_rag(fascicolo, doc, {"status": "skipped"}, stato)
    assert scritture == []
    servizio._registra_lettura_rag(fascicolo, doc, {"status": "indexed", "chunk_count": 3}, stato)
    assert len(scritture) == 1
