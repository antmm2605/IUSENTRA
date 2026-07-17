from __future__ import annotations

from lxml import etree

from pct.clienti import Cliente, Indirizzo, Recapiti, TipoCliente
from pct.fattura_pa import genera_xml_fattura_pa
from pct.fatturazione import Parcella, StatoParcella, VoceParcella


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
    root = etree.fromstring(xml_bytes)
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    assert root.xpath("string(.//f:DatiTrasmissione/f:ProgressivoInvio)", namespaces=ns) == "A1202"
    assert root.xpath(".//f:CessionarioCommittente/f:Sede/f:Nazione/text()", namespaces=ns) == ["FR"]
    assert root.xpath("string(.//f:DatiPagamento/f:DettaglioPagamento/f:IBAN)", namespaces=ns) == "IT60X0542811101000000123456"
    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:TipoCassa)", namespaces=ns) == "TC01"
    descriptions = root.xpath(".//f:DatiBeniServizi/f:DettaglioLinee/f:Descrizione/text()", namespaces=ns)
    assert "Spese generali 15%" in descriptions
    assert "Contributo Cassa Forense 4% (art. 11 L. 576/1980)" in descriptions
    assert len(root.xpath(".//f:DatiBeniServizi/f:DatiRiepilogo", namespaces=ns)) == 2


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
    root = etree.fromstring(xml_bytes)
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:TipoCassa)", namespaces=ns) == "TC01"
    assert root.xpath("string(.//f:DatiRiepilogo/f:AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//f:DatiRiepilogo/f:Imposta)", namespaces=ns) == "0.00"
    assert "franchigia IVA" in root.xpath("string(.//f:DatiRiepilogo/f:RiferimentoNormativo)", namespaces=ns)


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
    root = etree.fromstring(xml_bytes)
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    assert root.get("versione") == "FPR12"
    assert root.xpath("string(.//f:DatiTrasmissione/f:FormatoTrasmissione)", namespaces=ns) == "FPR12"
    assert root.xpath("string(.//f:DatiTrasmissione/f:CodiceDestinatario)", namespaces=ns) == "0000000"
    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:TipoCassa)", namespaces=ns) == "TC01"
    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:AlCassa)", namespaces=ns) == "4.00"
    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//f:DatiCassaPrevidenziale/f:Natura)", namespaces=ns) == "N2.2"
    assert root.xpath("string(.//f:DatiBeniServizi/f:DettaglioLinee[1]/f:AliquotaIVA)", namespaces=ns) == "0.00"
    assert root.xpath("string(.//f:DatiBeniServizi/f:DettaglioLinee[1]/f:Natura)", namespaces=ns) == "N2.2"
    assert root.xpath("string(.//f:DatiBeniServizi/f:DatiRiepilogo/f:ImponibileImporto)", namespaces=ns) == "308.57"


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

    root = etree.fromstring(genera_xml_fattura_pa(
        parcella=parcella,
        cliente=cliente,
        studio_nome="Studio Legale Montagnese",
        studio_piva="01301790802",
        studio_cf="MNTRRT64L01L063H",
        studio_indirizzo="Via Nino Bixio 4, 89029 Taurianova (RC)",
    ))
    ns = {"f": "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"}

    recipient_path = ".//f:CessionarioCommittente/f:DatiAnagrafici/f:Anagrafica"
    assert root.xpath(f"string({recipient_path}/f:Nome)", namespaces=ns) == "Robertino"
    assert root.xpath(f"string({recipient_path}/f:Cognome)", namespaces=ns) == "Alessi"
    assert root.xpath(f"string({recipient_path}/f:Denominazione)", namespaces=ns) == ""
    assert root.xpath("string(.//f:DatiPagamento/f:DettaglioPagamento/f:BIC)", namespaces=ns) == "BCITITMMXXX"
