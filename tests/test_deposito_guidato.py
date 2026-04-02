import os
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.deposito_guidato import OrchestratoreDepositoGuidato
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from web.app import create_app


def _pdf_base(pdfa_part: str = "2", pdfa_conf: str = "B") -> bytes:
    xmp = (
        b"<?xpacket begin='' id='W5M0MpCehiHzreSzNTczkc9d'?>"
        b"<x:xmpmeta xmlns:x='adobe:ns:meta/'>"
        b"<rdf:RDF xmlns:rdf='http://www.w3.org/1999/02/22-rdf-syntax-ns#'>"
        b"<rdf:Description xmlns:pdfaid='http://www.aiim.org/pdfa/ns/id/'>"
        b"<pdfaid:part>" + pdfa_part.encode() + b"</pdfaid:part>"
        b"<pdfaid:conformance>" + pdfa_conf.encode() + b"</pdfaid:conformance>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
        b"<?xpacket end='w'?>"
    )
    return b"%PDF-1.4\n" + xmp + b"\n%%EOF"


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "VALIDATION_RUNS_DB": str(tmp_path / "validation_runs.json"),
    }


def test_orchestratore_blocca_comparsa_senza_procura(tmp_path):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "docs"),
        archive_dir=str(tmp_path / "arch"),
    )
    fasc = gf.nuovo(
        titolo="Comparsa Rossi c. Banca Alfa",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        controparte="Banca Alfa S.p.A.",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "comparsa.pdf",
        TipoDocumento.COMPARSA,
        _pdf_base(),
        firmato=True,
    )

    orchestratore = OrchestratoreDepositoGuidato(
        validation_db_path=str(tmp_path / "validation.json"),
        office_cache_path=str(tmp_path / "uffici.json"),
    )
    run = orchestratore.valida(
        fascicolo=fasc,
        context={
            "tipo_atto": "COMPARSA_RISPOSTA",
            "codice_registro": "RG",
            "oggetto": "Comparsa di costituzione e risposta",
            "numero_rg": "1025",
            "anno_rg": 2024,
            "atto_principale_id": atto.id,
            "allegati_ids": [],
            "operatore": "avv.rossi",
        },
        selected_documents=[
            {
                "id": atto.id,
                "nome": atto.nome,
                "tipo": atto.tipo.value,
                "percorso": str(gf.percorso_documento(fasc.id, atto.id)),
                "dimensione_bytes": atto.dimensione_bytes,
                "firmato_digitalmente": atto.firmato_digitalmente,
            }
        ],
        all_documents=[
            {
                "id": atto.id,
                "nome": atto.nome,
                "tipo": atto.tipo.value,
                "percorso": str(gf.percorso_documento(fasc.id, atto.id)),
                "dimensione_bytes": atto.dimensione_bytes,
                "firmato_digitalmente": atto.firmato_digitalmente,
            }
        ],
    )

    assert run.can_prepare_deposit is False
    assert run.semaforo["giuridico"] == "blocco"
    assert any(issue["code"] == "procura_mancante" for issue in run.issues)


def test_api_validazione_deposito_restituisce_semaforo_e_consente_con_warning(tmp_path):
    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fasc = gf.nuovo(
        titolo="Comparsa di risposta demo",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="204",
        anno_rg=2025,
        controparte="Alfa S.r.l.",
        id_cliente="cli-1",
    )
    atto = gf.aggiungi_documento(
        fasc.id,
        "comparsa.pdf",
        TipoDocumento.COMPARSA,
        _pdf_base(),
        firmato=True,
    )
    procura = gf.aggiungi_documento(
        fasc.id,
        "procura.pdf",
        TipoDocumento.PROCURA,
        _pdf_base(),
        firmato=False,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/api/fascicoli/{fasc.id}/deposito/valida",
            data={
                "tipo_atto": "COMPARSA_RISPOSTA",
                "codice_registro": "RG",
                "oggetto": "Comparsa di costituzione e risposta",
                "numero_rg": "204",
                "anno_rg": "2025",
                "atto_principale_id": atto.id,
                "allegati_ids": [procura.id],
            },
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["validation"]["can_prepare_deposit"] is True
    assert data["validation"]["semaforo"]["tecnico_pst"] == "ok"
    assert data["validation"]["semaforo"]["documentale"] == "ok"
    assert data["validation"]["semaforo"]["giuridico"] == "warning"
    assert any(issue["code"] == "indice_non_rilevato" for issue in data["validation"]["issues"])
