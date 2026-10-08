from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from lxml import etree

from pct.clienti import Cliente, Indirizzo, Recapiti, TipoCliente
from pct.fattura_pa import genera_xml_fattura_pa
from pct.fatturazione import Parcella, StatoParcella, VoceParcella


def test_bollo_studio_resta_dovuto_senza_riaddebito_e_preserva_default():
    parcella = Parcella(
        id="BOLLO-QA", numero="2026/003", id_cliente="CLI-QA", id_fascicolo=None,
        data_emissione="2026-10-08", data_scadenza="2026-11-07",
        stato=StatoParcella.BOZZA,
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=260, tipo="ONORARIO")],
        applica_iva=False, applica_cassa=True, applica_ritenuta=False,
        applica_bollo=True, percentuale_spese_generali=15,
        dati_personalizzati={"document": {"regime_fiscale": "RF19"}},
    )
    assert parcella.bollo == 2
    assert parcella.totale_documento == 312.96
    parcella.dati_personalizzati["document"]["bollo_a_carico_studio"] = True
    assert parcella.bollo == 2
    assert parcella.bollo_addebitato == 0
    assert parcella.totale_documento == 310.96
    parcella.dati_personalizzati["document"]["bollo_a_carico_studio"] = False
    assert parcella.totale_documento == 312.96


class _OfficialSchemaResolver(etree.Resolver):
    def resolve(self, url, public_id, context):
        if url.endswith("xmldsig-core-schema.xsd"):
            return self.resolve_filename(str(_SCHEMA_DIR / "xmldsig-core-schema.xsd"), context)
        return None


_SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs/specs/ministero/fonti_ufficiali/2026-10-08"


def _validated_root(xml_bytes):
    parser = etree.XMLParser(no_network=True, resolve_entities=False)
    parser.resolvers.add(_OfficialSchemaResolver())
    schema = etree.XMLSchema(etree.parse(str(_SCHEMA_DIR / "Schema_VFPR12_v1.2.3.xsd"), parser))
    root = etree.fromstring(xml_bytes, parser)
    schema.assertValid(root)
    # La cassa compare nel blocco previdenziale e nel riepilogo, senza una seconda riga.
    for summary in root.findall(".//DatiRiepilogo"):
        rate, nature = summary.findtext("AliquotaIVA"), summary.findtext("Natura")
        lines = sum((Decimal(line.findtext("PrezzoTotale")) for line in root.findall(".//DettaglioLinee")
                     if line.findtext("AliquotaIVA") == rate and line.findtext("Natura") == nature), Decimal(0))
        contributions = sum((Decimal(item.findtext("ImportoContributoCassa")) for item in root.findall(".//DatiCassaPrevidenziale")
                             if item.findtext("AliquotaIVA") == rate and item.findtext("Natura") == nature), Decimal(0))
        assert Decimal(summary.findtext("ImponibileImporto")) == lines + contributions
    return root


def test_xml_fattura_pa_usa_snapshot_personalizzato_e_destinatario_estero():
    cliente = Cliente(
        id="CLI-EST",
        tipo=TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Cliente Estero SARL",
        indirizzo_sede_legale=Indirizzo(via="Rue de Paris", civico="10", cap="75000", comune="Paris", provincia="", nazione="Francia"),
        recapiti=Recapiti(email="contact@client.example"),
    )
    parcella = Parcella(
        id="PAR-001",
        numero="2026/001",
        id_cliente=cliente.id,
        id_fascicolo=None,
        data_emissione="2026-05-10",
        data_scadenza="2026-06-09",
        stato=StatoParcella.BOZZA,
        voci=[
            VoceParcella(descrizione="Compenso professionale", quantita=1, prezzo_unitario=258.0, tipo="ONORARIO"),
            VoceParcella(descrizione="Anticipazione contributo unificato", quantita=1, prezzo_unitario=43.5, tipo="ANTICIPO"),
        ],
        applica_iva=True,
        applica_cassa=True,
        applica_ritenuta=False,
        percentuale_spese_generali=15.0,
        metodo_pagamento="Bonifico",
        dati_personalizzati={
            "transmission": {
                "identificativo_fiscale": "RSSMRA80A01H501Z",
                "codice_invio": "A1202",
                "telefono": "061234567",
                "email": "segreteria@studio-rossi.example",
            },
            "studio": {
                "nome_denominazione": "Studio Legale Rossi",
                "partita_iva": "09876543210",
                "codice_fiscale": "RSSMRA80A01H501Z",
                "indirizzo_completo": "Via Verdi 8, 00100 Roma (RM)",
            },
            "recipient": {
                "denominazione": "Cliente Estero SARL",
                "indirizzo_completo": "Rue de Paris 10, 75000 Paris",
                "cap": "00000",
                "citta": "Paris",
                "nazione": "FR",
                "codice_destinatario": "XXXXXXX",
            },
            "document": {
                "tipo_documento": "TD01",
                "data_documento": "2026-05-10",
                "causale_oggetto": "Parcella pratica internazionale",
                "regime_fiscale": "RF01",
                "esigibilita_iva": "I",
            },
            "payment": {
                "modalita_pagamento_label": "Bonifico",
                "modalita_pagamento_codice": "MP05",
                "beneficiario": "Studio Legale Rossi",
                "istituto_finanziario": "Banca Forense",
                "iban": "IT60X0542811101000000123456",
                "giorni_termini": "30",
            },
        },
    )

    xml_bytes = genera_xml_fattura_pa(
        parcella=parcella,
        cliente=cliente,
        studio_nome="Studio Legale Rossi",
        studio_piva="09876543210",
        studio_cf="RSSMRA80A01H501Z",
        studio_indirizzo="Via Verdi 8, 00100 Roma (RM)",
    )
    root = _validated_root(xml_bytes)
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    assert root.xpath("string(.//DatiTrasmissione/ProgressivoInvio)", namespaces=ns) == "A1202"
    assert root.xpath(".//CessionarioCommittente/Sede/Nazione/text()", namespaces=ns) == ["FR"]
    assert root.xpath("string(.//DatiPagamento/DettaglioPagamento/IBAN)", namespaces=ns) == "IT60X0542811101000000123456"
    assert root.xpath("string(.//DatiCassaPrevidenziale/TipoCassa)", namespaces=ns) == "TC01"
    descriptions = root.xpath(".//DatiBeniServizi/DettaglioLinee/Descrizione/text()", namespaces=ns)
    assert "Spese generali 15%" in descriptions
    assert not any("Cassa Forense" in text for text in descriptions)
    assert root.xpath("string(.//DatiCassaPrevidenziale/ImportoContributoCassa)") == "11.87"
    assert len(root.xpath(".//DatiBeniServizi/DatiRiepilogo", namespaces=ns)) == 2


def test_xml_fattura_pa_forfettaria_esclude_iva():
    cliente = Cliente(
        id="CLI-IT",
        tipo=TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Beta Srl",
        indirizzo_sede_legale=Indirizzo(via="Via Roma", civico="5", cap="20100", comune="Milano", provincia="MI", nazione="Italia"),
        recapiti=Recapiti(email="amministrazione@beta.example"),
    )
    parcella = Parcella(
        id="PAR-002",
        numero="2026/002",
        id_cliente=cliente.id,
        id_fascicolo=None,
        data_emissione="2026-05-10",
        data_scadenza="2026-06-09",
        stato=StatoParcella.BOZZA,
        voci=[VoceParcella(descrizione="Compenso professionale", quantita=1, prezzo_unitario=258.0, tipo="ONORARIO")],
        applica_iva=True,
        applica_cassa=True,
        applica_ritenuta=False,
        percentuale_spese_generali=15.0,
        dati_personalizzati={
            "document": {
                "regime_fiscale": "RF19",
                "esigibilita_iva": "I",
            },
        },
    )

    xml_bytes = genera_xml_fattura_pa(
        parcella=parcella,
        cliente=cliente,
        studio_nome="Studio Legale Rossi",
        studio_piva="09876543210",
        studio_cf="RSSMRA80A01H501Z",
        studio_indirizzo="Via Verdi 8, 00100 Roma (RM)",
    )
    root = _validated_root(xml_bytes)
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    assert root.xpath("string(.//DatiCassaPrevidenziale/AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//DatiCassaPrevidenziale/TipoCassa)", namespaces=ns) == "TC01"
    assert root.xpath("string(.//DatiRiepilogo/AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//DatiRiepilogo/Imposta)", namespaces=ns) == "0.00"
    assert "franchigia IVA" in root.xpath("string(.//DatiRiepilogo/RiferimentoNormativo)", namespaces=ns)


def test_xml_fattura_pa_allinea_cassa_forense_all_esempio_firmato_utente():
    cliente = Cliente(
        id="CLI-PF",
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Vittoria",
        cognome="Fraone",
        codice_fiscale="FRNVTR76R53M208Z",
        indirizzo_residenza=Indirizzo(via="via Michele Servello", civico="51", cap="89814", comune="Filadelfia", provincia="VV", nazione="Italia"),
    )
    parcella = Parcella(
        id="PAR-003",
        numero="FE 144",
        id_cliente=cliente.id,
        id_fascicolo=None,
        data_emissione="2025-10-14",
        data_scadenza=None,
        stato=StatoParcella.BOZZA,
        voci=[VoceParcella(descrizione="Assistenza legale", quantita=1, prezzo_unitario=296.70, tipo="ONORARIO")],
        applica_iva=False,
        applica_cassa=True,
        applica_ritenuta=False,
        applica_bollo=False,
        dati_personalizzati={
            "transmission": {
                "identificativo_fiscale": "MNTGPP94L01G791A",
                "codice_invio": "144",
                "email": "giuseppe.montagnese94@gmail.com",
            },
            "studio": {
                "nome": "Giuseppe",
                "cognome": "Montagnese",
                "partita_iva": "03256320809",
                "codice_fiscale": "MNTGPP94L01G791A",
                "indirizzo_completo": "Via Nino Bixio 4, 89029 Taurianova (RC)",
            },
            "recipient": {
                "nome": "Vittoria",
                "cognome": "Fraone",
                "codice_fiscale": "FRNVTR76R53M208Z",
                "indirizzo_completo": "via Michele Servello n.51, 89814 Filadelfia (VV)",
                "nazione": "IT",
            },
            "document": {
                "tipo_documento": "TD01",
                "regime_fiscale": "RF19",
                "data_documento": "2025-10-14",
                "causale_oggetto": "Assistenza legale",
                "cassa_previdenziale": "CAF",
            },
            "payment": {"modalita_pagamento_codice": "MP05"},
        },
    )

    xml_bytes = genera_xml_fattura_pa(
        parcella=parcella,
        cliente=cliente,
        studio_nome="Giuseppe Montagnese",
        studio_piva="03256320809",
        studio_cf="MNTGPP94L01G791A",
        studio_indirizzo="Via Nino Bixio 4, 89029 Taurianova (RC)",
    )
    root = _validated_root(xml_bytes)
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    assert root.get("versione") == "FPR12"
    assert root.xpath("string(.//DatiTrasmissione/FormatoTrasmissione)", namespaces=ns) == "FPR12"
    assert root.xpath("string(.//DatiTrasmissione/CodiceDestinatario)", namespaces=ns) == "0000000"
    assert root.xpath("string(.//DatiCassaPrevidenziale/TipoCassa)", namespaces=ns) == "TC01"
    assert root.xpath("string(.//DatiCassaPrevidenziale/AlCassa)", namespaces=ns) == "4.00"
    assert root.xpath("string(.//DatiCassaPrevidenziale/AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//DatiCassaPrevidenziale/Natura)", namespaces=ns) == "N2.2"
    assert root.xpath("string(.//DatiBeniServizi/DettaglioLinee[1]/AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//DatiBeniServizi/DettaglioLinee[1]/Natura)", namespaces=ns) == "N2.2"
    assert root.xpath("string(.//DatiBeniServizi/DatiRiepilogo/ImponibileImporto)", namespaces=ns) == "308.57"


def test_xml_fattura_pa_ripara_vecchia_denominazione_duplicata_della_persona_fisica():
    cliente = Cliente(
        id="CLI-ALESSI",
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Robertino",
        cognome="Alessi",
        codice_fiscale="LSSRRR80A01H501X",
        indirizzo_residenza=Indirizzo(
            via="Via Roma",
            civico="9",
            cap="89029",
            comune="Taurianova",
            provincia="RC",
            nazione="Italia",
        ),
    )
    parcella = Parcella(
        id="PAR-ALESSI",
        numero="2026/010",
        id_cliente=cliente.id,
        id_fascicolo=None,
        data_emissione="2026-07-13",
        data_scadenza="2026-08-12",
        stato=StatoParcella.BOZZA,
        voci=[VoceParcella(descrizione="Assistenza legale", prezzo_unitario=100.0)],
        dati_personalizzati={
            "studio": {
                "denominazione": "Studio Legale Montagnese",
                "nome_denominazione": "Studio Legale Montagnese",
                "partita_iva": "01301790802",
                "codice_fiscale": "MNTRRT64L01L063H",
                "indirizzo_completo": "Via Nino Bixio 4, 89029 Taurianova (RC)",
            },
            "recipient": {
                "denominazione": "Alessi Robertino",
                "nome_denominazione": "Alessi Robertino",
                "nome": "Robertino",
                "cognome": "Alessi",
                "codice_fiscale": "LSSRRR80A01H501X",
                "indirizzo_completo": "Via Roma 9, 89029 Taurianova (RC)",
            },
            "payment": {
                "modalita_pagamento_codice": "MP05",
                "iban": "IT60X0542811101000000123456",
                "bic_swift": "BCITITMMXXX",
            },
        },
    )

    root = _validated_root(genera_xml_fattura_pa(
        parcella=parcella,
        cliente=cliente,
        studio_nome="Studio Legale Montagnese",
        studio_piva="01301790802",
        studio_cf="MNTRRT64L01L063H",
        studio_indirizzo="Via Nino Bixio 4, 89029 Taurianova (RC)",
    ))
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    recipient_path = ".//CessionarioCommittente/DatiAnagrafici/Anagrafica"
    assert root.xpath(f"string({recipient_path}/Nome)", namespaces=ns) == "Robertino"
    assert root.xpath(f"string({recipient_path}/Cognome)", namespaces=ns) == "Alessi"
    assert root.xpath(f"string({recipient_path}/Denominazione)", namespaces=ns) == ""
    assert root.xpath("string(.//DatiPagamento/DettaglioPagamento/BIC)", namespaces=ns) == "BCITITMMXXX"


def test_nome_xml_preserva_codice_fiscale_e_non_duplica_numeri_diversi():
    from pct.fattura_pa import nome_file_fattura_pa
    sender = "MNTGPP94L01G791A"
    numbers = ["2000/001", "2026/003", "2026/004", "2026/1000", "2027/003", "2100/399999"]
    names = [nome_file_fattura_pa(sender, number) for number in numbers]
    assert len(set(names)) == len(numbers)
    assert all(name.startswith(f"IT{sender}_") and len(name.split("_")[1].removesuffix(".xml")) == 5 for name in names)
    assert nome_file_fattura_pa(sender, "2026/003") == names[1]


def test_nome_xml_non_tronca_progressivi_o_identita_non_validi():
    import pytest
    from pct.fattura_pa import FatturaPAValidationError, nome_file_fattura_pa
    for progress in ["2026/400000", "2099/000", "ABCDEF", "FE 251", ""]:
        with pytest.raises(FatturaPAValidationError):
            nome_file_fattura_pa("MNTGPP94L01G791A", progress)
    with pytest.raises(FatturaPAValidationError):
        nome_file_fattura_pa("", "00001")


def test_validazione_runtime_rifiuta_xml_incompleto_senza_accesso_rete():
    import pytest
    from pct.fattura_pa import FatturaPAValidationError, valida_xml_fattura_pa
    payload = b'<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2" versione="FPR12"/>'
    with pytest.raises(FatturaPAValidationError, match="XML FatturaPA non conforme"):
        valida_xml_fattura_pa(payload)
