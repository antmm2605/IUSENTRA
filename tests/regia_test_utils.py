from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pct.clienti import GestioneClienti, Indirizzo, Recapiti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.fatturazione import GestioneFatturazione, StatoParcella, VoceParcella
from pct.practice_engine import PracticeEngineRepository, get_profile
from pct.preventivi import GestionePreventivi, VocePreventivo
from pct.scadenziario import GestioneScadenziario


def pdfa_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"<x:xmpmeta><pdfaid:part>2</pdfaid:part><pdfaid:conformance>B</pdfaid:conformance></x:xmpmeta>\n"
        b"1 0 obj<<>>endobj\n%%EOF"
    )


def encrypted_pdf_bytes() -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<< /Encrypt 2 0 R >>endobj\n"
        b"<pdfaid:part>2</pdfaid:part><pdfaid:conformance>B</pdfaid:conformance>\n%%EOF"
    )


def make_simple_fascicolo(tmp_path: Path, *, procedure_code: str = "PROC_LIC_IMP_001"):
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    fascicolo = gf.nuovo(
        titolo="Licenziamento disciplinare",
        tipo=TipoFascicolo.LAVORO,
        id_cliente="cliente-1",
        nome_cliente="Cliente Regia",
        oggetto="Impugnazione licenziamento disciplinare",
        tribunale="Tribunale di Palmi",
        avvocato="Avv. Regia",
        codice_fiscale_cliente="RSSMRA80A01H501U",
        procedura_operativa_codice=procedure_code,
    )
    repo = PracticeEngineRepository(str(tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"))
    profile = get_profile(procedure_code)
    repo.apply_profile(fascicolo.id, profile, actor="test")
    return gf, repo, fascicolo, profile


def make_context_objects(tmp_path: Path, *, paid: bool = True):
    clienti = GestioneClienti(db_path=str(tmp_path / "clienti" / "clienti.json"))
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Cliente",
        cognome="Regia",
        codice_fiscale="RSSMRA80A01H501U",
    )
    cliente = clienti.aggiorna(
        cliente.id,
        recapiti=Recapiti(email="cliente.regia@example.test"),
        indirizzo_residenza=Indirizzo(via="Via Regia", civico="1", comune="Palmi", provincia="RC"),
    )
    preventivi = GestionePreventivi(db_path=str(tmp_path / "preventivi" / "preventivi.json"))
    preventivo = preventivi.crea_preventivo(
        id_cliente=cliente.id,
        oggetto="Impugnazione licenziamento disciplinare",
        voci=[VocePreventivo("Assistenza giudiziale", 1200.0)],
        procedura_operativa_codice="PROC_LIC_IMP_001",
        id_pratica="licenziamento_impugnazione",
        tipo_procedimento="lavoro",
        valore_controversia=25000.0,
    )
    preventivo, conferimento = preventivi.registra_accettazione_preventivo(
        preventivo.id,
        avvocato_referente="Avv. Regia",
    )
    conferimento = preventivi.registra_firma_conferimento(conferimento.id)
    fatture = GestioneFatturazione(db_path=str(tmp_path / "fatturazione" / "parcelle.json"))
    parcella = fatture.crea(
        id_cliente=cliente.id,
        id_preventivo=preventivo.id,
        voci=[VoceParcella("Acconto", prezzo_unitario=500.0)],
        procedura_operativa_codice="PROC_LIC_IMP_001",
    )
    if paid:
        fatture.cambia_stato(parcella.id, StatoParcella.PAGATA, data_pagamento="2026-05-04", metodo_pagamento="bonifico")
    gf = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli" / "fascicoli.json"),
        documents_dir=str(tmp_path / "fascicoli" / "documenti"),
        archive_dir=str(tmp_path / "fascicoli" / "archivio"),
    )
    gs = GestioneScadenziario(db_path=str(tmp_path / "scadenziario" / "scadenze.json"))
    repo = PracticeEngineRepository(str(tmp_path / "fascicoli" / "practice_engine" / "practice_engine.json"))
    return SimpleNamespace(
        clienti=clienti,
        cliente=cliente,
        preventivi=preventivi,
        preventivo=preventivo,
        conferimento=conferimento,
        fatture=fatture,
        parcella=parcella,
        fascicoli=gf,
        scadenziario=gs,
        repo=repo,
    )


def link_required_documents(gf: GestioneFascicoli, repo: PracticeEngineRepository, fascicolo, *, procura: bool = True, signed: bool = True):
    atto = gf.aggiungi_documento(
        fascicolo.id,
        "atto_principale.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdfa_bytes(),
        firmato=signed,
    )
    repo.link_slot(fascicolo.id, "ATTO_PRINCIPALE", atto.id, actor="test")
    procura_doc = None
    if procura:
        procura_doc = gf.aggiungi_documento(
            fascicolo.id,
            "procura.pdf",
            TipoDocumento.PROCURA,
            pdfa_bytes(),
            firmato=True,
        )
        repo.link_slot(fascicolo.id, "PROCURA", procura_doc.id, actor="test")
    return atto, procura_doc
