"""Sede del giudice amministrativo dal fascicolo, NRG letti solo se amministrativi, profilo PEC da fonti certe."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from pct import pec_profilo_ufficio as pec
from pct.pat_formweb import letture
from pct.pec_pipeline import build_pec_procedural_profile
from web.services.react_fascicoli_bridge import _deposit_office_payload


@pytest.mark.parametrize(
    ("ufficio", "sede", "codice"),
    [
        ("TAR di Reggio Calabria", "tar_rc", "T170001"),
        ("Tar della Calabria sede di Reggio Calabria", "tar_rc", "T170001"),
        ("TAR VENEZIA", "tar_ve", "T060000"),
        ("Tribunale amministrativo del Veneto", "tar_ve", "T060000"),
        ("Tar Lazio", "tar_rm", "T120000"),
        ("TAR Calabria", "tar_cz", "T170000"),
        ("TAR Friuli-V.G.", "tar_ts", "T070000"),
        ("Tar Catania", "tar_ct", "T180001"),
        ("TAR", "", ""),
        ("Tribunale di Reggio Calabria", "", ""),
        ("Taranto", "", ""),
    ],
)
def test_sede_del_giudice_amministrativo_scritta_a_mano(ufficio, sede, codice):
    assert letture.sede_da_testo(ufficio) == sede
    assert letture.codice_ufficio_da_testo(ufficio) == codice


def test_ogni_tar_del_registro_uffici_si_risolve_nel_proprio_codice():
    from pct.pat_formweb.catalogo import SEDI
    from pct.uffici_giudiziari import _build_bundle_completo

    for ufficio in _build_bundle_completo():
        if ufficio["codice"] in SEDI and ufficio["codice"] not in {"T010001", "T120001"}:  # sezioni interne della sede
            assert letture.codice_ufficio_da_testo(ufficio["nome"]) == ufficio["codice"], ufficio["nome"]


def _ruolo(valore: str, letto: str, contesto: str) -> SimpleNamespace:
    return SimpleNamespace(categoria="ruolo", campo="numero_ruolo", valore=valore, valore_letto=letto,
                           contesto=contesto, verifica="verificata", oggetto_id="d1")


def test_nrg_proposto_solo_se_del_giudice_amministrativo():
    ottemperanza = _ruolo("2914/2024", "R.G. 2914/2024", "per l'ottemperanza della sentenza n. 512/2025 del Tribunale di Palmi "
                                                           "in funzione di giudice del lavoro nel procedimento R.G. 2914/2024")
    tar = _ruolo("593/2024", "R.G. 593/2024", "Il Tribunale Amministrativo Regionale per la Calabria sezione staccata di "
                                              "Reggio Calabria sul ricorso R.G. 593/2024 proposto da")
    lavoro = _ruolo("2733/2023", "R.G.L. 2733/2023", "TAR Calabria ricorso per ottemperanza alla sentenza R.G.L. 2733/2023")
    assert not letture.ruolo_amministrativo(ottemperanza)
    assert letture.ruolo_amministrativo(tar)
    assert not letture.ruolo_amministrativo(lavoro)
    letti = letture.dati_letti([ottemperanza, lavoro, tar], {"d1": "Sentenza.pdf"})
    assert letti["nrg"]["valore"] == "202400593" and "altri" not in letti["nrg"]
    assert letti["sede"]["valore"] == "tar_rc"
    assert letture.dati_letti([ottemperanza]) == {}


def test_ufficio_del_deposito_per_il_tar_scritto_a_mano():
    payload = _deposit_office_payload(SimpleNamespace(tribunale="Tar della Calabria sede di Reggio Calabria"))
    assert payload["code"] == "T170001"
    veneto = _deposit_office_payload(SimpleNamespace(tribunale="Tribunale amministrativo del Veneto"))
    assert veneto["code"] == "T060000" and "Napoli" not in veneto["name"]
    generico = _deposit_office_payload(SimpleNamespace(tribunale="TAR"))
    assert generico["code"] == "" and "sede del giudice amministrativo" in generico["message"]


REGISTRO = [
    {"nome": "Tribunale di Vicenza", "pec": "tribunale.vicenza@civile.ptel.giustiziacert.it"},
    {"nome": "Tribunale di Brescia", "pec": "tribunale.brescia@civile.ptel.giustiziacert.it"},
]


def test_ufficio_da_pec_oggetto_e_avviso_della_giustizia_amministrativa():
    assert pec.ufficio_da_pec('Da: "Per conto di: tribunale.brescia@civile.ptel.giustiziacert.it"', REGISTRO) == "Tribunale di Brescia"
    assert pec.ufficio_da_pec("Da: posta-certificata@legalmail.it", REGISTRO) == ""
    assert pec.ufficio_da_oggetto("POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza") == "Tribunale di Vicenza"
    assert pec.ufficio_da_oggetto("POSTA CERTIFICATA: Tribunale di Palmi Notificazione ai sensi del D.L. 179/2012") == "Tribunale di Palmi"
    avviso = pec.avviso_giustizia_amministrativa(
        "Avviso FISSAZIONE UDIENZA per il ricorso 202500519 COD#tarrc202609175956_1 Da: invio_avvisi1@pec.ga-cert.it")
    assert avviso == {"numero_rg": "519/2025", "nrg": "202500519", "ufficio": "TAR CALABRIA - REGGIO CALABRIA"}
    assert pec.numero_ruolo("1263/2026/LAV") == "1263/2026"
    assert pec.e_ricevuta_di_deposito("CONSEGNA: DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza")
    assert not pec.e_ricevuta_di_deposito("POSTA CERTIFICATA: COMUNICAZIONE 1263/2026/LAV")
    assert pec.cliente_da_relata("difensore per mandato come in atti di: Valentina MARRA C.F: MRRVNT90B49I119X") == "Valentina MARRA"
    assert pec.parti_da_oggetto("Esecuzione sentenza del TAR n. 23823/2025. Scarfò Emanuela c/Ministero dell'istruzione e del merito.") == (
        "Scarfò Emanuela", "Ministero dell'istruzione e del merito")


def test_profilo_pec_senza_etichette_scambiate_per_uffici():
    ministero = build_pec_procedural_profile(
        subject="POSTA CERTIFICATA: Protocollo nr: 166683 - Esecuzione sentenza del TAR n. 23823/2025. Scarfò Emanuela c/Ministero dell'istruzione e del merito.",
        body_text="Da: dgosv@postacert.istruzione.it",
        semantic_context={"office_hint": "TAR o Consiglio di Stato"},
    )
    assert "ufficio" not in ministero
    assert ministero["cliente"] == "Scarfò Emanuela" and ministero["cliente_da_verificare"] is True
    consegna = build_pec_procedural_profile(
        subject="CONSEGNA: DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza",
        body_text="A: tribunale.vicenza@civile.ptel.giustiziacert.it\n- Sentenza_Tribunale_Vicenza_20-04-2023.PDF",
        semantic_context={"office_hint": "Ufficio giudiziario civile"},
    )
    assert consegna["ufficio"] == "Tribunale di Vicenza"
    assert consegna["fase_pratica"] == "deposito telematico da completare o monitorare"
    cancelleria = build_pec_procedural_profile(
        subject="POSTA CERTIFICATA: Tribunale di Palmi Notificazione ai sensi del D.L. 179/2012",
        body_text="Tribunale di Palmi.\nNumero di Ruolo generale: 1733/2026\nRicorr. principale: PUNTURIERO ROSA\n"
                  "Resist. principale: AVVOCATURA DISTRETTUALE DI STATO DI REGGIO CALABRIA Si da' atto che in data 10/09/2026",
    )
    assert cancelleria["convenuto_principale"] == "AVVOCATURA DISTRETTUALE DI STATO DI REGGIO CALABRIA"


def test_profilo_gia_salvato_riallineato_alla_lettura():
    profilo = pec.riallinea_profilo({
        "ufficio": "Ufficio giudiziario civile", "numero_ruolo_certificato": "1571/2026",
        "oggetto_evento": "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza",
        "fase_pratica": "provvedimento/sentenza da leggere e notificare o presidiare",
    })
    assert profilo["ufficio"] == "Tribunale di Vicenza" and profilo["numero_rg"] == "1571/2026"
    assert profilo["fase_pratica"] == "deposito telematico da completare o monitorare"
    assert "ufficio" not in pec.riallinea_profilo({"ufficio": "TAR o Consiglio di Stato", "oggetto_evento": "Protocollo nr: 1"})


def _pdf(testo: str) -> bytes:
    import io

    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pagina = canvas.Canvas(buffer)
    pagina.drawString(72, 720, testo)
    pagina.save()
    return buffer.getvalue()


def _p7m(contenuto: bytes) -> bytes:
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID

    chiave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Avvocato di prova")])
    adesso = datetime.now(UTC)
    certificato = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chiave.public_key())
                   .serial_number(1).not_valid_before(adesso - timedelta(days=1)).not_valid_after(adesso + timedelta(days=30))
                   .sign(chiave, hashes.SHA256()))
    return (pkcs7.PKCS7SignatureBuilder().set_data(contenuto).add_signer(certificato, chiave, hashes.SHA256())
            .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary]))


def test_pdf_p7m_letto_anche_cifrato_a_riposo_e_in_base64(monkeypatch):
    import base64

    from pct.document_crypto import encrypt_doc
    from pct.document_intelligence.extraction import extract_text_from_document

    busta = _p7m(_pdf("RICORSO EX ART. 414 C.P.C. TRIBUNALE DI PALMI"))
    for dati in (busta, base64.encodebytes(busta)):
        esito = extract_text_from_document(dati, "Ricorso.pdf.p7m", "pdf")
        assert esito.ok and "RICORSO EX ART. 414" in esito.text, esito.error_message
    monkeypatch.setenv("PCT_DOC_KEY", "chiave-di-prova")
    cifrato = encrypt_doc(busta)
    assert cifrato.startswith(b"PCTENC")
    esito = extract_text_from_document(cifrato, "Ricorso.pdf.p7m", "pdf")
    assert esito.ok and "RICORSO EX ART. 414" in esito.text and "PCTENC" not in esito.text
    monkeypatch.delenv("PCT_DOC_KEY")
    senza_chiave = extract_text_from_document(cifrato, "Ricorso.pdf.p7m", "pdf")
    assert not senza_chiave.ok and senza_chiave.error_code == "encrypted_document"


def test_testo_del_p7m_dalla_lettura_decifrata_se_l_indice_ha_letto_il_file_cifrato(monkeypatch):
    import web.services.archivio_letture_runtime as runtime
    import web.services.document_intelligence_runtime as di_runtime
    import web.services.registro_letture_runtime as registro_runtime

    record = lambda rid, sha, data: SimpleNamespace(id=rid, sha256=sha, status="ready", original_filename="Ricorso.pdf.p7m",
                                                     updated_at=data, current_version_id=f"v-{rid}")
    records = [record("vecchio", "sha-cifrato", "2026-07-01"), record("nuovo", "sha-chiaro", "2026-09-01")]
    testi = {"vecchio": "PCTENC\x01garbage", "nuovo": "RICORSO EX ART. 414 C.P.C."}
    repository = SimpleNamespace(list_documents=lambda tenant, fid: records,
                                 get_extracted_text=lambda tenant, fid, rid, vid: SimpleNamespace(text=testi[rid]))
    monkeypatch.setattr(di_runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=repository))
    monkeypatch.setattr(di_runtime, "document_ai_tenant_id", lambda: "t")
    monkeypatch.setattr(registro_runtime, "impronte_contenuto", lambda fid: None)
    documento = SimpleNamespace(id="D1", nome="Ricorso.pdf.p7m", nome_originale="", hash_sha256="sha-cifrato", hash_contenuto_sha256="")
    assert runtime.testi_indice_archivio(SimpleNamespace(id="F1", documenti=[documento])) == {"D1": "RICORSO EX ART. 414 C.P.C."}


def test_editor_lavora_sul_pdf_di_busta_firmata_ed_email_solo_in_copia():
    from web.services.pdf_modificabile import modificabile_come_pdf, pdf_di_lavoro

    pdf = _pdf("ATTO FIRMATO")
    busta = SimpleNamespace(nome="Ricorso.pdf.p7m", firmato_digitalmente=True, tags=[])
    lavoro = pdf_di_lavoro(busta, _p7m(pdf), originale_modificabile=False)
    assert lavoro.dati == pdf and lavoro.origine == "busta_firmata" and lavoro.solo_copia and lavoro.nome_copia == "Ricorso.pdf"
    email = SimpleNamespace(nome="ACCETTAZIONE: Notificazione [JQ329-L01] [Notifica_ID:Cc25btuS]", firmato_digitalmente=False, tags=["email"])
    grezza = b"From: a@pec.it\r\nTo: b@pec.it\r\nSubject: ACCETTAZIONE\r\nDate: Thu, 24 Sep 2026 10:14:52 +0200\r\nMIME-Version: 1.0\r\n\r\nRicevuta di accettazione\r\n"
    assert modificabile_come_pdf(email)
    convertita = pdf_di_lavoro(email, grezza, originale_modificabile=False)
    assert convertita.dati.startswith(b"%PDF") and convertita.origine == "convertito" and convertita.solo_copia
    studio = SimpleNamespace(nome="Nota.pdf", firmato_digitalmente=False, tags=[])
    assert not pdf_di_lavoro(studio, pdf, originale_modificabile=True).solo_copia
