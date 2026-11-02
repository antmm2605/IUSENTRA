"""Indice Lex: la busta Atto.enc cifrata per l'ufficio non è mai un errore di lettura.

D.M. 44/2011 art. 14 e Specifiche tecniche DGSIA: la busta del deposito è
crittografata con la chiave pubblica dell'ufficio; gli atti in chiaro sono già
nel fascicolo. Il messaggio di deposito si indicizza con corpo e allegati, la
busta si annota; un documento che sia solo busta è «non applicabile»; gli
errori storici con quella causa si riclassificano senza rilettura; un vero
errore (PDF corrotto) resta errore.
"""
from email.message import EmailMessage
from pathlib import Path
from types import SimpleNamespace

from asn1crypto.cms import ContentInfo
from flask import Flask

from pct.document_intelligence.busta_cifrata import CODICE_BUSTA_CIFRATA, NOTA_BUSTA_CIFRATA
from pct.document_intelligence.extraction import ExtractionResult, extract_text_from_document
from pct.document_intelligence.indexer import DocumentAIIndexer
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.service import DocumentAIService
from pct.document_intelligence.sources import source_from_fascicolo_document, source_from_uploaded_document
from pct.registro_letture import Oggetto, RegistroLetture
from tests.test_document_intelligence_auto_indexing import FakeFascicoli, _context

STORICO = ("Lettura del messaggio incompleta: Atto.enc: Busta cifrata destinata all’ufficio giudiziario: "
           "per leggere gli atti occorrono gli originali in chiaro collegati al deposito.")


def _cms_cifrato() -> bytes:
    return ContentInfo({
        "content_type": "enveloped_data",
        "content": {"version": "v0", "recipient_infos": [],
                    "encrypted_content_info": {
                        "content_type": "data",
                        "content_encryption_algorithm": {"algorithm": "aes256_cbc", "parameters": bytes(16)},
                        "encrypted_content": b"CONTENUTO_RISERVATO_UFFICIO" * 20,
                    }},
    }).dump()


def _eml_deposito(busta: bytes) -> bytes:
    email = EmailMessage()
    email["From"] = "avvocato@pec.example.test"
    email["To"] = "tribunale.milano@civile.ptel.giustiziacert.it"
    email["Subject"] = "DEPOSITO TELEMATICO - Comparsa di costituzione - RG 123/2026"
    email.set_content("Si trasmette il deposito telematico della comparsa di costituzione.")
    email.add_attachment(busta, maintype="application", subtype="octet-stream", filename="Atto.enc")
    return email.as_bytes()


def _service(tmp_path: Path) -> DocumentAIService:
    return DocumentAIService(DocumentAIRepository.from_sqlite_db(tmp_path / "ai.db"), FakeFascicoli())


def _source_eml(content: bytes, document_id: str = "pec-deposito", filename: str = "DEPOSITO TELEMATICO.eml"):
    return source_from_uploaded_document(tenant_id="tenant-a", fascicolo_id="fas-1", document_id=document_id,
                                         filename=filename, content=content, mime_type="message/rfc822")


def _registra(service, registro, summary, sources):
    from web.services.document_intelligence_runtime import _registra_indice_documentale

    oggetti = [Oggetto(tipo="documento", oggetto_id=s.source_id, nome=s.filename, sha256=s.sha256) for s in sources]
    with Flask(__name__).app_context():
        _registra_indice_documentale({"registro": registro, "tenant": "tenant-a", "oggetti": oggetti, "impronta": "inv"},
                                     summary, sources, service=service, tenant_id="tenant-a", fascicolo_id="fas-1",
                                     user_context=_context())


def test_eml_di_deposito_con_busta_si_legge_con_corpo_e_nota_senza_avvisi():
    for busta in (_cms_cifrato(), b"\x30\x80 busta non analizzabile"):
        for nome, tipo in (("DEPOSITO TELEMATICO.eml", "eml"), ("copia PEC deposito.pdf", "pdf")):
            result = extract_text_from_document(_eml_deposito(busta), nome, tipo)
            assert result.ok
            assert "Si trasmette il deposito telematico" in result.text
            assert NOTA_BUSTA_CIFRATA in result.text
            assert "CONTENUTO_RISERVATO_UFFICIO" not in result.text
            assert not [w for w in result.warnings if "Atto.enc" in w]


def test_eml_di_deposito_indicizzato_senza_errori(tmp_path):
    service = _service(tmp_path)
    try:
        result = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
                                                    sources=[_source_eml(_eml_deposito(_cms_cifrato()))],
                                                    user_context=_context())
        assert result.summary.ready == 1 and result.summary.errors == 0
        assert result.summary.source_errors == [] and not result.errors
    finally:
        service.repository.structured_db.close()


def test_documento_solo_busta_e_non_applicabile(tmp_path):
    service = _service(tmp_path)
    registro = RegistroLetture(tmp_path / "registro.db")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "Atto.enc").write_bytes(_cms_cifrato())
    documento = SimpleNamespace(id="doc-busta", nome="Atto.enc", percorso="Atto.enc", dimensione_bytes=0,
                                hash_sha256="", fonte_documento="", tipo=None, data_caricamento="")
    source = source_from_fascicolo_document(tenant_id="tenant-a", fascicolo_id="fas-1", document=documento,
                                            documents_root=tmp_path / "docs")
    try:
        indexer = DocumentAIIndexer(service)
        for _giro in range(2):
            summary = indexer.process(tenant_id="tenant-a", fascicolo_id="fas-1", sources=[source],
                                      user_context=_context()).summary
            assert summary.errors == 0 and summary.not_applicable == 1
            assert summary.source_errors == [] and summary.warnings == []
            assert summary.source_notes[0]["message"] == NOTA_BUSTA_CIFRATA
            assert summary.status == "ready"
        _registra(service, registro, summary, [source])
        (lettura,) = registro.letture("tenant-a", "fas-1", lettore="indice_documentale")
        assert lettura.stato == "non_leggibile" and lettura.esito["error_code"] == CODICE_BUSTA_CIFRATA
    finally:
        service.repository.structured_db.close()


def test_errore_storico_per_busta_riclassificato_senza_rilettura(tmp_path, monkeypatch):
    from web.services import registro_letture_runtime
    from web.services.document_index_outcomes import summary_with_registered_outcomes

    service = _service(tmp_path)
    registro = RegistroLetture(tmp_path / "registro.db")
    source = _source_eml(_eml_deposito(_cms_cifrato()))
    letture = []

    def storico(*_args, **_kwargs):
        letture.append(1)
        return ExtractionResult(ok=False, text="", pages=[], extraction_engine="email.message.v1",
                                error_code="eml_attachment_unreadable", error_message=STORICO)

    try:
        with monkeypatch.context() as patch:
            patch.setattr("pct.document_intelligence.service.extract_text_from_document", storico)
            first = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
                                                       sources=[source], user_context=_context())
        _registra(service, registro, first.summary, [source])
        assert registro.letture("tenant-a", "fas-1", lettore="indice_documentale")[0].stato == "errore"
        monkeypatch.setattr("pct.document_intelligence.service.extract_text_from_document", storico)
        monkeypatch.setattr(registro_letture_runtime, "registro_corrente",
                            lambda **kwargs: RegistroLetture(tmp_path / "registro.db", read_only=bool(kwargs.get("sola_lettura"))))
        letture.clear()
        for _giro in range(2):  # idempotente
            summary = summary_with_registered_outcomes(service, "tenant-a", "fas-1", [source], _context())
            assert summary.errors == 0 and summary.not_applicable == 1 and summary.source_errors == []
            assert summary.source_notes[0]["message"] == NOTA_BUSTA_CIFRATA
            assert not [w for w in summary.warnings if "Atto.enc" in w]
        assert letture == []  # nessuna rilettura
        (lettura,) = registro.letture("tenant-a", "fas-1", lettore="indice_documentale")
        assert lettura.stato == "non_leggibile" and lettura.esito["causa_precedente"]
        (record,) = service.repository.list_documents("tenant-a", "fas-1")
        assert service.repository.latest_processing_error("tenant-a", "fas-1", record.id, record.current_version_id)["error_code"] == CODICE_BUSTA_CIFRATA
        events = service.repository._conn().execute(
            "SELECT COUNT(*) FROM fascicolo_documenti_ai_audit WHERE event_type = 'document_ai.extraction.reclassified'").fetchone()[0]
        assert events == 1
        # Alla prossima indicizzazione il messaggio si legge con le regole correnti.
        monkeypatch.undo()
        result = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
                                                    sources=[source], user_context=_context())
        assert result.summary.ready == 1 and result.summary.errors == 0 and result.summary.not_applicable == 0
    finally:
        service.repository.structured_db.close()


def test_pdf_corrotto_resta_errore(tmp_path, monkeypatch):
    from web.services import registro_letture_runtime
    from web.services.document_index_outcomes import summary_with_registered_outcomes

    service = _service(tmp_path)
    registro = RegistroLetture(tmp_path / "registro.db")
    source = source_from_uploaded_document(tenant_id="tenant-a", fascicolo_id="fas-1", document_id="pdf-rotto",
                                           filename="comparsa.pdf", content=b"%PDF-1.4\n%%corrotto senza oggetti",
                                           mime_type="application/pdf")
    try:
        result = DocumentAIIndexer(service).process(tenant_id="tenant-a", fascicolo_id="fas-1",
                                                    sources=[source], user_context=_context())
        assert result.summary.errors == 1 and result.summary.not_applicable == 0
        _registra(service, registro, result.summary, [source])
        monkeypatch.setattr(registro_letture_runtime, "registro_corrente",
                            lambda **kwargs: RegistroLetture(tmp_path / "registro.db", read_only=bool(kwargs.get("sola_lettura"))))
        summary = summary_with_registered_outcomes(service, "tenant-a", "fas-1", [source], _context())
        assert summary.errors == 1 and summary.not_applicable == 0 and summary.source_notes == []
        assert registro.letture("tenant-a", "fas-1", lettore="indice_documentale")[0].stato == "errore"
    finally:
        service.repository.structured_db.close()
