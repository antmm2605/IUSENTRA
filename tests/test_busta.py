"""Test per la creazione della busta telematica."""

import os
import tempfile
import pytest
from dataclasses import replace
from email import policy
from email.parser import BytesParser
from pathlib import Path

from pct.busta import (
    BustaTelematica,
    DatiBusta,
    Allegato,
    ATTO_MSG_FILENAME,
    DATI_ATTO_FILENAME,
    DATI_ATTO_FIRMATO_FILENAME,
    INDICE_BUSTA_FILENAME,
    INDICE_DOCUMENTI_FILENAME,
    CASSAZIONE_PARTE_NS,
    MINISTERIAL_ALLEGATI_NS,
    MINISTERIAL_ATTI_NS,
    SICID_SISTEMA_NS,
    SIECIC_PARTE_ESECUZIONI_NS,
)
from pct.firma import estrai_contenuto_cades
from pct.pst_cifratura import PSTCifraturaError


@pytest.fixture
def tmp_pdf(tmp_path):
    """Crea un PDF di test."""
    pdf = tmp_path / "atto.pdf"
    # PDF minimo valido
    pdf.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF"
    )
    return str(pdf)


@pytest.fixture
def dati_busta(tmp_pdf):
    """Dati di test per la busta."""
    return DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Memoria difensiva - RG 1234/2024",
        tipo_atto="MEMORIA",
        atto_principale=tmp_pdf,
        allegati=[],
        numero_rg="1234",
        anno_rg=2024,
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
    )


def test_crea_busta(dati_busta, tmp_path):
    """Verifica che la busta venga creata correttamente."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    assert Path(busta_path).exists()
    assert busta_path.endswith(".enc")


def _atto_msg_attachments(busta_path: str | Path) -> dict[str, bytes]:
    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
    attachments = {}
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = Path(part.get_filename() or part.get_param("name", header="Content-Type") or "").name
        if filename:
            attachments[filename] = part.get_payload(decode=True) or b""
    return attachments


def _atto_msg_named_parts(busta_path: str | Path) -> dict[str, object]:
    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
    parts = {}
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = Path(part.get_filename() or part.get_param("name", header="Content-Type") or "").name
        if filename:
            parts[filename] = part
    return parts


def _cades_signed_payload(payload: bytes) -> bytes:
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    from pct.firma_pkcs11 import _build_cades_bes
    from tools import local_signer as local_signer_mod

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Firma DatiAtto")]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    cert_der = cert.public_bytes(serialization.Encoding.DER)
    signed_attrs = local_signer_mod._build_signed_attrs_der_inline(payload, cert_der=cert_der)
    signature = key.sign(signed_attrs, padding.PKCS1v15(), hashes.SHA256())
    return _build_cades_bes(
        documento=payload,
        signature_bytes=signature,
        cert_der=cert_der,
        signed_attrs_der=signed_attrs,
        detached=False,
    )


def _anagrafica_ministeriale_test(
    atti: str = "http://schemi.processotelematico.giustizia.it/tipi/atti/v6",
    ana: str = "http://schemi.processotelematico.giustizia.it/tipi/anagrafiche/v4",
) -> bytes:
    from lxml import etree

    country_field = "nazione" if "cassazione" in ana else "stato"
    root = etree.Element(f"{{{atti}}}AnagraficaProcedimento", nsmap={None: atti, "at": ana})
    partecipanti = etree.SubElement(root, f"{{{atti}}}Partecipanti")
    parte = etree.SubElement(partecipanti, f"{{{atti}}}Parte", naturaGiuridica="PFI", ID="parte_ricorrente_1")
    etree.SubElement(parte, f"{{{ana}}}denominazione").text = "Rossi"
    etree.SubElement(parte, f"{{{ana}}}nome").text = "Mario"
    etree.SubElement(parte, f"{{{ana}}}codiceFiscale").text = "RSSMRA80A01H501Z"
    indirizzo = etree.SubElement(parte, f"{{{ana}}}indirizzo")
    etree.SubElement(indirizzo, f"{{{ana}}}via").text = "Via Roma 1"
    etree.SubElement(indirizzo, f"{{{ana}}}cap").text = "00100"
    etree.SubElement(indirizzo, f"{{{ana}}}localita").text = "Roma"
    etree.SubElement(indirizzo, f"{{{ana}}}provincia").text = "RM"
    etree.SubElement(indirizzo, f"{{{ana}}}{country_field}").text = "IT"
    controparte = etree.SubElement(partecipanti, f"{{{atti}}}ControParte", naturaGiuridica="ENP", ID="controparte_1")
    etree.SubElement(controparte, f"{{{ana}}}denominazione").text = "Ministero dell'Istruzione e del Merito"
    etree.SubElement(controparte, f"{{{ana}}}codiceFiscale").text = "80185250588"
    indirizzo = etree.SubElement(controparte, f"{{{ana}}}indirizzo")
    etree.SubElement(indirizzo, f"{{{ana}}}via").text = "Viale Trastevere 76 A"
    etree.SubElement(indirizzo, f"{{{ana}}}cap").text = "00153"
    etree.SubElement(indirizzo, f"{{{ana}}}localita").text = "Roma"
    etree.SubElement(indirizzo, f"{{{ana}}}provincia").text = "RM"
    etree.SubElement(indirizzo, f"{{{ana}}}{country_field}").text = "IT"
    soggetti = etree.SubElement(root, f"{{{atti}}}Soggetti")
    avvocato = etree.SubElement(soggetti, f"{{{atti}}}Avvocato")
    etree.SubElement(avvocato, f"{{{ana}}}cognome").text = "Rossi"
    etree.SubElement(avvocato, f"{{{ana}}}nome").text = "Mario"
    etree.SubElement(avvocato, f"{{{ana}}}codiceFiscale").text = "RSSMRA80A01H501Z"
    domicilio = etree.SubElement(avvocato, f"{{{ana}}}indirizzo")
    etree.SubElement(domicilio, f"{{{ana}}}via").text = "Via Studio 2"
    etree.SubElement(domicilio, f"{{{ana}}}cap").text = "00100"
    etree.SubElement(domicilio, f"{{{ana}}}localita").text = "Roma"
    etree.SubElement(domicilio, f"{{{ana}}}provincia").text = "RM"
    etree.SubElement(domicilio, f"{{{ana}}}{country_field}").text = "IT"
    etree.SubElement(avvocato, f"{{{ana}}}parteRappresentata", ref="parte_ricorrente_1")
    return etree.tostring(root, encoding="UTF-8")


def test_dati_atto_ministeriale_catalogo_citazione_usa_root_e_data(tmp_pdf):
    from lxml import etree

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="110001",
        tipo_atto="ATTO_DI_CITAZIONE",
        atto_principale=tmp_pdf,
        valore_causa=1000.0,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
        datiatto_generator_class="IntroduttiviSicid",
        datiatto_root_name="Citazione",
        datiatto_studio_variable="citazione",
        datiatto_generator_mode="introduttivo_citazione",
        data_notifica_citazione="30/06/2026",
    )

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())

    assert etree.QName(root).localname == "Citazione"
    assert root.get("Datacitazione") == "2026-06-30"
    assert root.xpath("//*[local-name()='destinazione']")
    assert root.xpath("//*[local-name()='Oggetto']")
    assert root.xpath("//*[local-name()='AnagraficaProcedimento']")


def test_dati_atto_introduttivo_gestisce_contributo_pagato_esente_e_prenotato_a_debito(tmp_pdf):
    from lxml import etree

    base = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="110001",
        tipo_atto="RICORSO",
        atto_principale=tmp_pdf,
        valore_causa=1000.0,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
        datiatto_generator_class="IntroduttiviSicid",
        datiatto_root_name="Ricorso",
        datiatto_required_data=["ContributoUnificato", "valore causa quando presente"],
        contributo_unificato_richiesto=True,
        contributo_unificato_xml_mode="atto_introduttivo",
    )

    with pytest.raises(ValueError, match="Contributo unificato non definito"):
        BustaTelematica(base).crea_dati_atto_xml_per_firma()

    with pytest.raises(ValueError, match="Mancano gli estremi di pagamento"):
        BustaTelematica(replace(
            base,
            contributo_unificato={
                "resolved": False,
                "mode": "pagato",
                "importo": 259.0,
                "blocking_message": "Mancano gli estremi di pagamento del Contributo Unificato.",
            },
        )).crea_dati_atto_xml_per_firma()

    paid = etree.fromstring(BustaTelematica(replace(
        base,
        contributo_unificato={"resolved": True, "mode": "pagato", "importo": 259.0},
    )).crea_dati_atto_xml_per_firma())
    paid_amount = paid.find(".//{*}ContributoUnificato/{*}Importo")
    assert paid_amount is not None
    assert paid_amount.text == "259.00"
    assert paid_amount.get("debito") == "false"

    exempt = etree.fromstring(BustaTelematica(replace(
        base,
        valore_causa=None,
        contributo_unificato={"resolved": True, "mode": "esente", "importo": None},
    )).crea_dati_atto_xml_per_firma())
    assert exempt.find(".//{*}ContributoUnificato") is None
    assert exempt.find(".//{*}ValoreCausa").text == "0.00"

    debt = etree.fromstring(BustaTelematica(replace(
        base,
        contributo_unificato={"resolved": True, "mode": "prenotato_a_debito", "importo": 259.0},
    )).crea_dati_atto_xml_per_firma())
    debt_amount = debt.find(".//{*}ContributoUnificato/{*}Importo")
    assert debt_amount is not None
    assert debt_amount.get("debito") == "true"

    debt_without_amount = etree.fromstring(BustaTelematica(replace(
        base,
        contributo_unificato={"resolved": True, "mode": "prenotato_a_debito", "importo": None},
    )).crea_dati_atto_xml_per_firma())
    debt_without_amount_node = debt_without_amount.find(".//{*}ContributoUnificato/{*}Importo")
    assert debt_without_amount_node is not None
    assert debt_without_amount_node.text == "0.00"
    assert debt_without_amount_node.get("debito") == "true"


def test_dati_atto_ministeriale_catalogo_citazione_appello_usa_root_specifica(tmp_pdf):
    from lxml import etree

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="110002",
        tipo_atto="ATTO_DI_CITAZIONE",
        atto_principale=tmp_pdf,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
        datiatto_generator_class="IntroduttiviSicid",
        datiatto_root_name="CitazioneAppello",
        datiatto_studio_variable="citazioneAppello",
        datiatto_generator_mode="introduttivo_citazione",
        datiatto_extra={
            "precedente_provvedimento_numero": "321",
            "precedente_provvedimento_anno": "2025",
        },
        data_notifica_citazione="30/06/2026",
    )

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())

    assert etree.QName(root).localname == "CitazioneAppello"
    assert root.get("Datacitazione") == "2026-06-30"
    assert root.xpath("//*[local-name()='AnagraficaProcedimento']")


def test_dati_atto_ministeriale_catalogo_produzione_documenti_usa_procedimento(tmp_pdf):
    from lxml import etree

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Memoria documentale",
        tipo_atto="ATTO_GENERICO",
        atto_principale=tmp_pdf,
        numero_rg="1234",
        anno_rg=2026,
        datiatto_generator_class="Parte",
        datiatto_root_name="ProduzioneDocumentiRichiesti",
        datiatto_studio_variable="produzioneDocumentiRichiesti",
        datiatto_generator_mode="procedimento_base",
    )

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())
    procedimento = root.xpath("//*[local-name()='procedimento']")[0]

    assert etree.QName(root).localname == "ProduzioneDocumentiRichiesti"
    assert procedimento.get("ufficio") == "0580010"
    assert procedimento.xpath("./*[local-name()='numero']/text()") == ["1234"]
    assert procedimento.xpath("./*[local-name()='anno']/text()") == ["2026"]
    assert not root.xpath("//*[local-name()='AnagraficaProcedimento']")


def test_dati_atto_ministeriale_catalogo_siecic_esecuzioni_usa_procedimento(tmp_pdf):
    from lxml import etree

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="SIECIC_ESECUZIONI",
        oggetto="Atto di intervento",
        tipo_atto="ATTO_GENERICO",
        atto_principale=tmp_pdf,
        numero_rg="55",
        anno_rg=2026,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(
            "http://schemi.processotelematico.giustizia.it/tipi/atti/v7"
        ),
        datiatto_generator_class="ParteSiecicEsecuzioni",
        datiatto_root_name="AttoIntervento",
        datiatto_studio_variable="attoIntervento",
        datiatto_generator_mode="procedimento_base",
        datiatto_extra={
            "credito_capitale": "1.000,00",
            "credito_data_decorrenza": "01/07/2026",
        },
    )

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())
    procedimento = root.xpath("//*[local-name()='procedimento']")[0]

    assert etree.QName(root).localname == "AttoIntervento"
    assert etree.QName(root).namespace == SIECIC_PARTE_ESECUZIONI_NS
    assert procedimento.xpath("./*[local-name()='numero']/text()") == ["55"]
    assert procedimento.xpath("./*[local-name()='anno']/text()") == ["2026"]


def test_dati_atto_ministeriale_atto_sistema_usa_destinazione_senza_rg(tmp_pdf):
    from lxml import etree

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Deposito complementare",
        tipo_atto="DEPOSITO_COMPLEMENTARE",
        atto_principale=tmp_pdf,
        datiatto_generator_class="AttoSistemaSicid",
        datiatto_root_name="DepositoComplementare",
        datiatto_studio_variable="depositoComplementare",
        datiatto_generator_mode="sistema_destinazione",
    )

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())

    assert etree.QName(root).localname == "DepositoComplementare"
    assert etree.QName(root).namespace == SICID_SISTEMA_NS
    assert root.xpath("//*[local-name()='destinazione']")
    assert not root.xpath("//*[local-name()='Oggetto']")
    assert root.xpath("/*[local-name()='DepositoComplementare']/*[local-name()='RefId']/text()")
    assert not root.xpath("//*[local-name()='procedimento']")


def test_dati_atto_ministeriale_catalogo_cassazione_usa_root_e_anagrafica(tmp_pdf):
    from lxml import etree

    dati = DatiBusta(
        codice_ufficio="80417740588",
        codice_registro="CASSCI",
        oggetto="Ricorso per cassazione",
        tipo_atto="RICORSO",
        atto_principale=tmp_pdf,
        valore_causa=1000.0,
        contributo_unificato={"resolved": True, "mode": "pagato", "importo": 259.0, "debito": False},
        contributo_unificato_richiesto=True,
        contributo_unificato_xml_mode="cassazione_spese_giustizia",
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(
            "http://schemi.processotelematico.giustizia.it/cassazione/tipi/atti/v13",
            "http://schemi.processotelematico.giustizia.it/cassazione/tipi/anagrafiche/v13",
        ),
        datiatto_generator_class="ParteCassazione",
        datiatto_root_name="Ricorso",
        datiatto_studio_variable="ricorso",
        datiatto_generator_mode="cassazione_parte",
        datiatto_extra={
            "tipo_ricorso_cassazione": "RicorsoOrdinario",
            "data_richiesta_notifica_cassazione": "30/06/2026",
            "data_effettiva_notifica_cassazione": "01/07/2026",
            "provvedimento_impugnato": {
                "ufficio": "0580010",
                "ruolo": "Contenzioso",
                "numero_fascicolo": "123",
                "anno_fascicolo": "2025",
            },
            "inizio_primo_grado_anno": "2024",
            "inizio_primo_grado_ufficio": "0580010",
            "materia_ricorso_cassazione": "001",
            "motivi_cassazione": [{"numero": "1", "numero_art_360": "3", "pagina": "1"}],
        },
    )

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())

    assert etree.QName(root).localname == "Ricorso"
    assert etree.QName(root).namespace == CASSAZIONE_PARTE_NS
    assert root.xpath("//*[local-name()='destinazione']")
    assert root.xpath("//*[local-name()='AnagraficaProcedimento']")


def test_dati_atto_ministeriale_citazione_blocca_data_mancante(tmp_pdf):
    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="110001",
        tipo_atto="ATTO_DI_CITAZIONE",
        atto_principale=tmp_pdf,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
        datiatto_generator_class="IntroduttiviSicid",
        datiatto_root_name="Citazione",
    )

    with pytest.raises(ValueError, match="Data notificazione citazione mancante"):
        BustaTelematica(dati).crea_dati_atto_xml_per_firma()


def test_busta_contiene_xml(dati_busta, tmp_path):
    """Verifica che la busta contenga il file DatiAtto.xml."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    assert DATI_ATTO_FILENAME in attachments
    assert INDICE_BUSTA_FILENAME in attachments
    assert INDICE_DOCUMENTI_FILENAME in attachments


def test_busta_contiene_indice_busta_ministeriale(dati_busta, tmp_path):
    """Verifica che Atto.msg contenga IndiceBusta.xml, distinto dal PDF indice."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    root = etree.fromstring(attachments[INDICE_BUSTA_FILENAME])
    assert root.tag == "IndiceBusta"
    atto = root.find("Atto")
    assert atto is not None
    assert atto.get("Nome") == "atto.pdf"
    dati = [node for node in root.findall("Allegato") if node.get("Tipo") == "DA"]
    assert dati
    assert dati[0].get("Nome") == DATI_ATTO_FILENAME


def test_atto_msg_usa_mime_file_parts_compatibili_con_parser_pst(dati_busta, tmp_path):
    """Le parti MIME seguono la disposizione attachment usata da Studio Telematico."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))
    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())

    assert message.get_content_type() == "multipart/related"
    leaf_parts = [part for part in message.walk() if not part.is_multipart()]
    assert leaf_parts
    assert all(part.get_filename() or part.get_param("name", header="Content-Type") for part in leaf_parts)
    assert "text/plain" not in {part.get_content_type() for part in leaf_parts}

    indice_part = next(
        part
        for part in leaf_parts
        if Path(part.get_filename() or part.get_param("name", header="Content-Type") or "").name
        == INDICE_BUSTA_FILENAME
    )
    assert indice_part.get_content_type() == "text/xml"
    assert indice_part.get_param("name", header="Content-Type") == INDICE_BUSTA_FILENAME
    assert indice_part.get_content_disposition() == "attachment"
    assert indice_part.get("Content-ID") == f"<{INDICE_BUSTA_FILENAME}>"
    assert indice_part.get("Content-Transfer-Encoding", "").lower() != "base64"
    assert etree.fromstring(indice_part.get_payload(decode=True)).tag == "IndiceBusta"


def test_indice_busta_esterno_usa_content_id_mime_per_tutte_le_parti(dati_busta, tmp_path):
    """La simulazione deve verificare lo stesso contratto Nome/ID che il PST controlla su Atto.msg."""
    from lxml import etree

    procura = tmp_path / "procura alle liti.pdf"
    procura.write_bytes(b"%PDF-1.4\n%%EOF")
    dati_busta.allegati = [Allegato(str(procura), "Procura alle liti", "PROCURA")]

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path / "out"))
    parts = _atto_msg_named_parts(busta_path)
    root = etree.fromstring(parts[INDICE_BUSTA_FILENAME].get_payload(decode=True))

    indexed_ids = {}
    atto = root.find("Atto")
    assert atto is not None
    indexed_ids[str(atto.get("Nome") or "")] = str(atto.get("ID") or "")
    for node in root.findall("Allegato"):
        indexed_ids[str(node.get("Nome") or "")] = str(node.get("ID") or "")

    mime_ids = {
        name: str(part.get("Content-ID") or "").strip("<> ")
        for name, part in parts.items()
        if name != INDICE_BUSTA_FILENAME
    }
    assert indexed_ids == mime_ids
    assert DATI_ATTO_FILENAME in indexed_ids
    assert INDICE_DOCUMENTI_FILENAME in indexed_ids
    assert "procura alle liti.pdf" in indexed_ids


def test_indice_busta_classifica_rt_solo_per_ricevute_telematiche_pagamento(dati_busta, tmp_path):
    """RT e' riservato alla ricevuta telematica di pagamento, non a qualunque ricevuta PEC."""
    from lxml import etree

    ricevuta_pagamento = tmp_path / "Ricevuta telematica pagamento PagoPA.pdf"
    ricevuta_pagamento.write_bytes(b"%PDF-1.4\nrt\n%%EOF")
    richiesta_pagamento = tmp_path / "Richiesta pagamento annualita CARTA DEL DOCENTE.pdf"
    richiesta_pagamento.write_bytes(b"%PDF-1.4\nrichiesta\n%%EOF")
    accettazione = tmp_path / "ACCETTAZIONE_ Notificazione ai sensi della legge n. 53.eml"
    accettazione.write_bytes(b"Subject: Accettazione notifica\r\n\r\nok")
    consegna = tmp_path / "CONSEGNA_ Notificazione ai sensi della legge n. 53.eml"
    consegna.write_bytes(b"Subject: Avvenuta consegna notifica\r\n\r\nok")
    dati_busta.allegati = [
        Allegato(str(ricevuta_pagamento), "Ricevuta telematica pagamento", "ALLEGATO"),
        Allegato(str(richiesta_pagamento), "Richiesta pagamento carta docente", "ALLEGATO"),
        Allegato(str(accettazione), "Messaggio PEC notifica", "ALLEGATO"),
        Allegato(str(consegna), "Ricevuta avvenuta consegna notifica", "ALLEGATO"),
    ]

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path / "out"))
    root = etree.fromstring(_atto_msg_attachments(busta_path)[INDICE_BUSTA_FILENAME])
    tipi = {
        str(node.get("Nome") or ""): str(node.get("Tipo") or "")
        for node in root.findall("Allegato")
    }

    assert tipi["Ricevuta telematica pagamento PagoPA.pdf"] == "RT"
    assert tipi["Richiesta pagamento annualita CARTA DEL DOCENTE.pdf"] == "SM"
    assert tipi["ACCETTAZIONE_ Notificazione ai sensi della legge n. 53.eml"] == "PA"
    assert tipi["CONSEGNA_ Notificazione ai sensi della legge n. 53.eml"] == "RA"
    assert busta.verifica_busta(busta_path)["valida"] is True


def test_atto_msg_tratta_eml_come_file_opaco_senza_parti_annidate(dati_busta, tmp_path):
    """Le ricevute PEC .eml nella busta non devono diventare email annidate dentro Atto.msg."""
    eml_path = tmp_path / "ricevuta deposito.eml"
    eml_path.write_bytes(
        b"From: posta-certificata@example.test\r\n"
        b"To: studio@example.test\r\n"
        b"Subject: Ricevuta deposito\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Ricevuta PEC di prova.\r\n"
    )
    dati_busta.allegati = [Allegato(str(eml_path), "Ricevuta PEC", "ALLEGATO")]
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))
    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())

    eml_part = next(part for part in message.iter_parts() if part.get_filename() == eml_path.name)
    assert eml_part.get_content_type() == "application/pkcs7-mime"
    assert eml_part.get_param("name", header="Content-Type") == eml_path.name
    assert eml_part.get_payload(decode=True) == eml_path.read_bytes()
    assert all(part.get_content_type() != "message/rfc822" for part in message.walk())
    assert all(
        part.get_filename() or part.get_param("name", header="Content-Type")
        for part in message.walk()
        if not part.is_multipart()
    )


def test_busta_reale_usa_dati_atto_firmato_nell_indice_busta(dati_busta, tmp_path):
    """Quando DatiAtto.xml è firmato, Atto.msg usa il .p7m e l'indice ministeriale lo richiama."""
    from lxml import etree

    dati_busta.tipo_atto = "RICORSO"
    dati_busta.codice_registro = "RGL"
    dati_busta.oggetto = "222050"
    dati_busta.valore_causa = 500.0
    dati_busta.anagrafica_procedimento_xml = _anagrafica_ministeriale_test()
    busta = BustaTelematica(
        dati_busta,
        id_busta="D78E4A75-B17D-428B-9DE7-DCFFD20959CD",
        timestamp="2026-06-23T09:10:00",
    )
    dati_atto_xml = busta.crea_dati_atto_xml_per_firma()
    dati_atto_firmato = _cades_signed_payload(dati_atto_xml)
    busta_path = busta.crea_busta(
        str(tmp_path),
        dati_atto_firmato=dati_atto_firmato,
        require_dati_atto_firmato=True,
    )

    attachments = _atto_msg_attachments(busta_path)
    assert DATI_ATTO_FIRMATO_FILENAME in attachments
    assert DATI_ATTO_FILENAME not in attachments
    assert INDICE_BUSTA_FILENAME not in attachments
    assert estrai_contenuto_cades(attachments[DATI_ATTO_FIRMATO_FILENAME]) == dati_atto_xml
    signed_root = etree.fromstring(dati_atto_xml)
    assert etree.QName(signed_root).localname == "Ricorso"
    indice_nodes = signed_root.xpath("//*[local-name()='IndiceBusta']")
    assert len(indice_nodes) == 1
    assert len(indice_nodes[0].xpath("./*[local-name()='AttoPrincipale']")) == 1
    assert signed_root.xpath("//*[local-name()='AnagraficaProcedimento']")
    audit = busta.audit_conformita_pst()
    assert audit["dati_atto_signed"] is True
    assert audit["indice_busta_mode"] == "interno_dati_atto"
    assert audit["indice_busta_external_included"] is False
    assert audit["dati_atto_indice_busta_interno"] is True
    assert audit["indice_busta_ambiguous"] is False
    assert not any(issue["code"] == "DATI-ATTO-SIGNATURE-MISSING" for issue in audit["issues"])
    assert audit["atto_msg_indice_busta_valid"] is True
    assert audit["busta_verifica_valida"] is True
    assert audit["atto_enc_cms_valid"] is True
    assert audit["atto_enc_sha256"]
    assert audit["indice_busta_dati_atto_filename"] == DATI_ATTO_FIRMATO_FILENAME
    assert audit["formal_checks"]["T002"]["status"] == "ok"


def test_busta_reale_mantiene_nomi_fisici_cades_in_atto_msg(tmp_path):
    """I documenti CAdES devono restare in Atto.msg con il nome fisico .p7m."""
    from lxml import etree

    ricorso = tmp_path / "Ricorso.pdf.p7m"
    procura = tmp_path / "Procura.PDF.p7m"
    ricorso.write_bytes(_cades_signed_payload(b"%PDF-1.4\nRICORSO\n%%EOF"))
    procura.write_bytes(_cades_signed_payload(b"%PDF-1.4\nPROCURA\n%%EOF"))
    dati = DatiBusta(
        codice_ufficio="0241160092",
        codice_registro="RGL",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(ricorso),
        allegati=[Allegato(str(procura), "Procura alle liti", "PROCURA")],
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
        valore_causa=500.0,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
    )
    busta = BustaTelematica(dati, id_busta="D78E4A75-B17D-428B-9DE7-DCFFD20959CD")
    dati_atto_xml = busta.crea_dati_atto_xml_per_firma()
    busta_path = busta.crea_busta(
        str(tmp_path / "out"),
        dati_atto_firmato=_cades_signed_payload(dati_atto_xml),
        require_dati_atto_firmato=True,
    )

    atto_msg_path = Path(busta_path).with_name(ATTO_MSG_FILENAME)
    message = BytesParser(policy=policy.default).parsebytes(atto_msg_path.read_bytes())
    parts = {
        Path(part.get_filename() or part.get_param("name", header="Content-Type") or "").name: part
        for part in message.walk()
        if not part.is_multipart()
    }
    assert INDICE_BUSTA_FILENAME not in parts
    assert "Ricorso.pdf.p7m" in parts
    assert "Ricorso.pdf" not in parts
    assert "Procura.PDF.p7m" in parts
    assert "Procura.PDF" not in parts
    assert parts["Ricorso.pdf.p7m"].get_content_type() == "application/pkcs7-mime"
    assert parts["Procura.PDF.p7m"].get_content_type() == "application/pkcs7-mime"

    signed_root = etree.fromstring(dati_atto_xml)
    indice_root = signed_root.xpath("//*[local-name()='IndiceBusta']")[0]
    internal_ids = {
        str(node.get("id") or "")
        for node in indice_root
        if isinstance(node.tag, str)
    }
    mime_ids = {str(part.get("Content-ID") or "").strip("<> ") for part in parts.values()}
    assert internal_ids <= mime_ids
    assert parts[DATI_ATTO_FIRMATO_FILENAME].get("Content-ID") == f"<{DATI_ATTO_FILENAME}>"
    assert all(part.get_content_disposition() == "attachment" for part in parts.values())


def test_busta_reale_decripta_documenti_cades_prima_di_atto_msg(tmp_path, monkeypatch):
    from pct.document_crypto import ENC_MAGIC, encrypt_doc

    monkeypatch.setenv("PCT_DOC_KEY", "chiave-test-busta-pctenc")
    ricorso_payload = _cades_signed_payload(b"%PDF-1.4\nRICORSO CIFRATO\n%%EOF")
    procura_payload = _cades_signed_payload(b"%PDF-1.4\nPROCURA CIFRATA\n%%EOF")
    ricorso = tmp_path / "Ricorso.pdf.p7m"
    procura = tmp_path / "Procura.pdf.p7m"
    ricorso.write_bytes(encrypt_doc(ricorso_payload))
    procura.write_bytes(encrypt_doc(procura_payload))
    dati = DatiBusta(
        codice_ufficio="0241160092",
        codice_registro="RGL",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(ricorso),
        allegati=[Allegato(str(procura), "Procura alle liti", "PROCURA")],
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
        valore_causa=500.0,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
    )
    busta = BustaTelematica(dati)
    dati_atto = busta.crea_dati_atto_xml_per_firma()
    busta_path = busta.crea_busta(
        str(tmp_path / "out-cifrato"),
        dati_atto_firmato=_cades_signed_payload(dati_atto),
        require_dati_atto_firmato=True,
    )

    attachments = _atto_msg_attachments(busta_path)
    assert attachments[ricorso.name] == ricorso_payload
    assert attachments[procura.name] == procura_payload
    assert not attachments[ricorso.name].startswith(ENC_MAGIC)
    assert not attachments[procura.name].startswith(ENC_MAGIC)


def test_busta_reale_blocca_p7m_non_cades(tmp_path):
    ricorso = tmp_path / "Ricorso.pdf.p7m"
    ricorso.write_bytes(b"payload che non e' una firma CAdES")
    dati = DatiBusta(
        codice_ufficio="0241160092",
        codice_registro="RGL",
        oggetto="222050",
        tipo_atto="RICORSO",
        atto_principale=str(ricorso),
        allegati=[],
        cf_mittente="RSSMRA80A01H501Z",
        operatore="Avv. Mario Rossi",
        valore_causa=500.0,
        anagrafica_procedimento_xml=_anagrafica_ministeriale_test(),
    )
    busta = BustaTelematica(dati)
    dati_atto = busta.crea_dati_atto_xml_per_firma()

    with pytest.raises(ValueError, match="non e' un contenitore CAdES"):
        busta.crea_busta(
            str(tmp_path / "out-non-cades"),
            dati_atto_firmato=_cades_signed_payload(dati_atto),
            require_dati_atto_firmato=True,
        )


def test_busta_reale_accetta_dati_atto_firmato_con_indice_busta_xml(dati_busta, tmp_path):
    dati_busta.tipo_atto = "RICORSO"
    busta = BustaTelematica(dati_busta)
    dati_atto_xml = busta.crea_dati_atto_xml_per_firma()

    busta_path = busta.crea_busta(
        str(tmp_path),
        dati_atto_firmato=_cades_signed_payload(dati_atto_xml),
        require_dati_atto_firmato=True,
    )

    attachments = _atto_msg_attachments(busta_path)
    assert INDICE_BUSTA_FILENAME in attachments
    assert DATI_ATTO_FIRMATO_FILENAME in attachments


def test_busta_reale_blocca_indice_busta_ambiguo(dati_busta, tmp_path, monkeypatch):
    """IndiceBusta.xml esterno e IndiceBusta interno nel DatiAtto non possono coesistere."""
    from lxml import etree

    dati_busta.tipo_atto = "RICORSO"
    dati_busta.codice_registro = "RGL"
    dati_busta.oggetto = "222050"
    dati_busta.anagrafica_procedimento_xml = _anagrafica_ministeriale_test()
    busta = BustaTelematica(dati_busta)
    originale = busta._crea_xml_dati_atto_ministeriale

    def con_indice_interno(document_parts):
        root = etree.fromstring(originale(document_parts))
        indice = etree.SubElement(root, f"{{{MINISTERIAL_ATTI_NS}}}IndiceBusta")
        main_part = next(part for part in document_parts if part.is_main)
        etree.SubElement(indice, f"{{{MINISTERIAL_ALLEGATI_NS}}}AttoPrincipale", id=main_part.content_id)
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    monkeypatch.setattr(busta, "_crea_xml_dati_atto_ministeriale", con_indice_interno)
    dati_atto_xml = busta.crea_dati_atto_xml_per_firma()

    with pytest.raises(ValueError, match="un solo IndiceBusta"):
        busta.crea_busta(
            str(tmp_path),
            dati_atto_firmato=_cades_signed_payload(dati_atto_xml),
            require_dati_atto_firmato=True,
        )


def test_dati_atto_per_firma_e_deterministico_con_stessa_busta(dati_busta):
    id_busta = "D78E4A75-B17D-428B-9DE7-DCFFD20959CD"
    timestamp = "2026-06-23T09:10:00"
    busta_a = BustaTelematica(dati_busta, id_busta=id_busta, timestamp=timestamp)
    busta_b = BustaTelematica(dati_busta, id_busta=id_busta, timestamp=timestamp)

    assert busta_a.crea_dati_atto_xml_per_firma() == busta_b.crea_dati_atto_xml_per_firma()


def test_datiatto_contiene_indice_documenti_generato(dati_busta, tmp_path):
    """Verifica che l'indice generato sia richiamato nei metadati della busta."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    xml_bytes = attachments[DATI_ATTO_FILENAME]
    indice_bytes = attachments[INDICE_DOCUMENTI_FILENAME]

    root = etree.fromstring(xml_bytes)
    ns = {"p": "http://www.giustizia.it/processo_telematico"}
    indice_node = root.find(f".//p:Documenti/p:Allegato[p:NomeFile='{INDICE_DOCUMENTI_FILENAME}']", ns)
    assert indice_node is not None
    assert indice_node.findtext("p:Tipo", namespaces=ns) == "INDICE_DOCUMENTI"
    assert indice_node.findtext("p:Hash", namespaces=ns) == BustaTelematica._hash_bytes(indice_bytes)


def test_indice_documenti_pdf_disponibile_per_anteprima(dati_busta):
    """Verifica che l'indice documenti possa essere mostrato prima dell'invio."""
    busta = BustaTelematica(dati_busta)
    indice_pdf = busta.crea_indice_documenti_pdf()

    assert indice_pdf.startswith(b"%PDF")
    assert b"%%EOF" in indice_pdf
    assert len(indice_pdf) > 250


def test_busta_contiene_atto(dati_busta, tmp_path):
    """Verifica che la busta contenga l'atto principale."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))

    attachments = _atto_msg_attachments(busta_path)
    assert "atto.pdf" in attachments


def test_verifica_busta_valida(dati_busta, tmp_path):
    """Verifica che la verifica della busta funzioni."""
    busta = BustaTelematica(dati_busta)
    busta_path = busta.crea_busta(str(tmp_path))
    risultato = busta.verifica_busta(busta_path)

    assert risultato["valida"] is True
    assert risultato["id_busta"] is not None
    assert risultato["audit_tecnico"]["transport_mode"] == "atto_enc_da_atto_msg_cifrato_aes256"
    assert risultato["audit_tecnico"]["uses_real_encryption"] is True
    assert risultato["audit_tecnico"]["formal_checks"]["T001"]["status"] == "ok"
    assert risultato["audit_tecnico"]["indice_busta_generated"] is True
    assert risultato["audit_tecnico"]["atto_msg_indice_busta_valid"] is True
    assert risultato["audit_tecnico"]["busta_verifica_valida"] is True
    assert risultato["audit_tecnico"]["atto_enc_sha256"]
    assert INDICE_BUSTA_FILENAME in _atto_msg_attachments(busta_path)
    assert INDICE_DOCUMENTI_FILENAME in risultato["documenti"]


def test_busta_blocca_indice_busta_non_coerente_con_atto_msg(dati_busta, tmp_path, monkeypatch):
    """La busta non deve arrivare ad Atto.enc se IndiceBusta.xml richiama file assenti."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)

    def indice_corrotto(*, dati_atto_filename=DATI_ATTO_FILENAME, **_kwargs):
        root = etree.Element("IndiceBusta")
        etree.SubElement(root, "Atto", Nome="atto_sbagliato.pdf", ID="ATTO_1")
        etree.SubElement(root, "Allegato", Nome=dati_atto_filename, ID="DATI_1", Tipo="DA")
        etree.SubElement(root, "Allegato", Nome=INDICE_DOCUMENTI_FILENAME, ID="INDICE_1", Tipo="SM")
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    monkeypatch.setattr(busta, "_crea_indice_busta_xml", indice_corrotto)

    with pytest.raises(ValueError, match="IndiceBusta.xml"):
        busta.crea_busta(str(tmp_path))


def test_busta_blocca_indice_busta_con_id_diversi_dai_content_id(dati_busta, tmp_path, monkeypatch):
    """Simula invio PEC non deve dichiarare 100% se IndiceBusta.xml usa ID non presenti nel MIME."""
    from lxml import etree

    busta = BustaTelematica(dati_busta)
    originale = busta._crea_indice_busta_xml

    def indice_con_id_corrotto(*args, **kwargs):
        root = etree.fromstring(originale(*args, **kwargs))
        dati = next(node for node in root.findall("Allegato") if node.get("Tipo") == "DA")
        dati.set("ID", "ALLEGATO_1_DatiAtto_xml_p7m")
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    monkeypatch.setattr(busta, "_crea_indice_busta_xml", indice_con_id_corrotto)

    with pytest.raises(ValueError, match="Content-ID MIME"):
        busta.crea_busta(str(tmp_path))


def test_busta_blocca_ricevuta_telematica_senza_tipo_rt(dati_busta, tmp_path, monkeypatch):
    """La simulazione deve bloccare ricevute pagamento RT classificate come allegati semplici."""
    from lxml import etree

    ricevuta = tmp_path / "Ricevuta telematica pagamento PagoPA.pdf"
    ricevuta.write_bytes(b"%PDF-1.4\nrt\n%%EOF")
    dati_busta.allegati = [Allegato(str(ricevuta), "Ricevuta telematica pagamento", "ALLEGATO")]
    busta = BustaTelematica(dati_busta)
    originale = busta._crea_indice_busta_xml

    def indice_con_rt_errato(*args, **kwargs):
        root = etree.fromstring(originale(*args, **kwargs))
        node = next(item for item in root.findall("Allegato") if item.get("Nome") == ricevuta.name)
        node.set("Tipo", "SM")
        return etree.tostring(root, xml_declaration=True, encoding="UTF-8")

    monkeypatch.setattr(busta, "_crea_indice_busta_xml", indice_con_rt_errato)

    with pytest.raises(ValueError, match="Tipo=RT"):
        busta.crea_busta(str(tmp_path))


def test_audit_busta_blocca_prima_della_generazione_reale(dati_busta):
    busta = BustaTelematica(dati_busta)
    audit = busta.audit_conformita_pst()

    assert audit["uses_real_encryption"] is False
    assert audit["atto_msg_generated"] is False
    assert audit["required_encryption_algorithm"] == "AES256"
    assert audit["expected_transport_mode"] == "atto_enc_da_atto_msg_cifrato_aes256"
    assert audit["blocks_direct_send"] is True
    assert audit["guided_completion_required"] is True
    assert audit["indice_busta_generated"] is True
    assert audit["indice_busta_filename"] == INDICE_BUSTA_FILENAME
    assert audit["dati_atto_signed"] is False
    assert any(issue["code"] == "DATI-ATTO-SIGNATURE-MISSING" for issue in audit["issues"])
    assert any("Atto.enc" in action and "AES256" in action for action in audit["guided_next_actions"])
    assert audit["formal_checks"]["T002"]["status"] == "warning"
    issue = next(issue for issue in audit["issues"] if issue["code"] == "ATTO-ENC-MISSING")
    assert "Atto.msg" in issue["detail"]
    assert "AES256" in issue["detail"]


def test_busta_con_certificato_pst_non_disponibile_conserva_atto_msg(dati_busta, tmp_path, monkeypatch):
    def resolver_non_disponibile(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError(
            "Download PST non riuscito: https://servizipst.giustizia.it/PST/it/pst_2_4.wp"
        )

    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        resolver_non_disponibile,
    )
    busta = BustaTelematica(dati_busta)

    with pytest.raises(PSTCifraturaError):
        busta.crea_busta(str(tmp_path))

    audit = busta.audit_conformita_pst()
    assert audit["uses_real_encryption"] is False
    assert audit["transport_mode"] == "atto_msg_generato_cifratura_pst_non_completata"
    assert audit["atto_msg_generated"] is True
    assert audit["atto_enc_path"] == ""
    assert Path(audit["atto_msg_path"]).name == ATTO_MSG_FILENAME
    assert Path(audit["atto_msg_path"]).exists()
    assert audit["blocks_direct_send"] is True
    assert audit["guided_completion_required"] is True
    assert ".cer" in audit["certificate_error"]
    assert "https://" not in audit["certificate_error"]
    assert any(".cer" in action for action in audit["guided_next_actions"])
    assert any("Atto.enc" in action and "AES256" in action for action in audit["guided_next_actions"])
    assert not any("https://" in action for action in audit["guided_next_actions"])


def test_busta_con_certificato_pst_non_pubblicato_spiega_blocco(dati_busta, tmp_path, monkeypatch):
    def resolver_non_pubblicato(codice_ufficio, *, cache_dir=None, force_refresh=False):
        raise PSTCifraturaError(
            f"Certificato di cifratura PST non trovato per l'ufficio {codice_ufficio}."
        )

    monkeypatch.setattr(
        "pct.busta.risolvi_certificato_cifratura_ufficio",
        resolver_non_pubblicato,
    )
    busta = BustaTelematica(dati_busta)

    with pytest.raises(PSTCifraturaError):
        busta.crea_busta(str(tmp_path))

    audit = busta.audit_conformita_pst()
    assert audit["certificate_error_code"] == "certificato_cifratura_non_pubblicato"
    assert "non pubblica" in audit["certificate_error"]
    assert "PST" in audit["certificate_error"]
    assert "Atto.enc" in " ".join(audit["guided_next_actions"])
    assert "diverso ufficio/canale ufficiale" in " ".join(audit["guided_next_actions"])


def test_busta_con_allegati(tmp_path, tmp_pdf):
    """Verifica che gli allegati vengano inclusi nella busta."""
    allegato_path = tmp_path / "allegato.pdf"
    allegato_path.write_bytes(b"%PDF-1.4\n%%EOF")

    dati = DatiBusta(
        codice_ufficio="0580010",
        codice_registro="CIVILE",
        oggetto="Test con allegati",
        tipo_atto="RICORSO",
        atto_principale=tmp_pdf,
        allegati=[
            Allegato(
                percorso=str(allegato_path),
                descrizione="Documento allegato",
                tipo="ALLEGATO",
            )
        ],
    )

    busta = BustaTelematica(dati)
    busta_path = busta.crea_busta(str(tmp_path / "output"))

    attachments = _atto_msg_attachments(busta_path)
    assert "allegato.pdf" in attachments


def test_id_busta_univoco(dati_busta, tmp_path):
    """Verifica che ogni busta abbia un ID univoco."""
    busta1 = BustaTelematica(dati_busta)
    busta2 = BustaTelematica(dati_busta)
    assert busta1.id_busta != busta2.id_busta


def test_hash_file(dati_busta):
    """Verifica che l'hash del file sia calcolato correttamente."""
    busta = BustaTelematica(dati_busta)
    hash_val = busta._hash_file(dati_busta.atto_principale)
    assert len(hash_val) == 64  # SHA-256 hex = 64 caratteri
    assert hash_val == hash_val.upper()
