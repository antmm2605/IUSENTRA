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
    descriptions = root.xpath(".//f:DatiBeniServizi/f:DettaglioLinee/f:Descrizione/text()", namespaces=ns)
    assert "Spese generali 15%" in descriptions
    assert "Contributo Cassa Forense 4% (art. 11 L. 576/1980)" in descriptions
    assert len(root.xpath(".//f:DatiBeniServizi/f:DatiRiepilogo", namespaces=ns)) == 2
