from pct.presidio_processuale_ruleset import (
    extract_money_amounts,
    extract_rg_references,
    has_presidio_rule,
    is_pagopa_rt_contributo_xml,
    presidio_rule_hits,
)


def test_presidio_ruleset_riconosce_varianti_rg():
    refs = extract_rg_references("N. R.G. 3950/2026 - ruolo generale n. 1100/2026 - fascicolo 77/2025")

    assert refs == [
        {"number": "3950", "year": "2026", "label": "RG 3950/2026"},
        {"number": "1100", "year": "2026", "label": "RG 1100/2026"},
        {"number": "77", "year": "2025", "label": "RG 77/2025"},
    ]


def test_presidio_ruleset_riconosce_rt_xml_contributo_e_importi():
    rt_xml = """<pay_j:RT xmlns:pay_j="http://www.digitpa.gov.it/schemas/2011/Pagamenti/">
      <pay_j:identificativoMessaggioRicevuta>30003967997109978</pay_j:identificativoMessaggioRicevuta>
      <pay_j:codiceEsitoPagamento>0</pay_j:codiceEsitoPagamento>
      <pay_j:datiPagamento>
        <pay_j:importoTotalePagato>49.00</pay_j:importoTotalePagato>
        <pay_j:datiSpecificiRiscossione>9/0702100TS/CONTRIB</pay_j:datiSpecificiRiscossione>
      </pay_j:datiPagamento>
    </pay_j:RT>"""

    assert is_pagopa_rt_contributo_xml(rt_xml) is True
    assert has_presidio_rule(rt_xml, "contributo_unificato_pagamento") is True
    assert extract_money_amounts("Contributo unificato pagato € 49,00, spese € 1.234,56") == [49.0, 1234.56]


def test_presidio_ruleset_sentenza_economica_spese_distrazione_compensazione():
    text = (
        "REPUBBLICA ITALIANA - SENTENZA. P.Q.M. definitivamente pronunciando, condanna alle spese, "
        "che liquida in euro 258,00 per compensi, oltre spese generali 15%, IVA e CPA. "
        "Dispone la distrazione in favore dell'avv. antistatario e compensa parzialmente le spese."
    )

    assert has_presidio_rule(text, "sentenza_strutturale") is True
    assert has_presidio_rule(text, "spese_liquidazione") is True
    assert has_presidio_rule(text, "spese_distrazione") is True
    assert has_presidio_rule(text, "spese_compensazione") is True


def test_presidio_ruleset_udienze_procedimenti_speciali_e_notifiche():
    text = (
        "Il giudice dispone ex art. 127-ter c.p.c. il deposito di note scritte. "
        "Segue intimazione di sfratto per morosita con citazione per la convalida. "
        "Nel pignoramento presso terzi il terzo deve rendere la dichiarazione ex art. 547. "
        "La mediazione e la negoziazione assistita costituiscono condizione di procedibilita. "
        "Avviso di avvenuta ricezione su piattaforma notificazione digitale SEND con perfezionamento al decimo giorno."
    )
    codes = {hit["code"] for hit in presidio_rule_hits(text)}

    assert "udienza_127_ter" in codes
    assert "sfratto_convalida" in codes
    assert "esecuzione_pignoramento" in codes
    assert "mediazione_negoziazione" in codes
    assert "notifica_digitale_pa" in codes


def test_presidio_ruleset_gratuito_patrocinio_e_pec():
    text = (
        "Istanza di liquidazione SIAMM per patrocinio a spese dello Stato. "
        "Messaggio postacert con daticert.xml, ricevuta di accettazione e avvenuta consegna. "
        "Relata di notifica ex Legge 53/1994 a mezzo PEC estratta da pubblico elenco INI-PEC."
    )

    assert has_presidio_rule(text, "gratuito_patrocinio") is True
    assert has_presidio_rule(text, "pec_ricevute") is True
    assert has_presidio_rule(text, "notifica_53_1994") is True


def test_presidio_ruleset_siamm_non_equivale_sempre_a_gratuito_patrocinio():
    text = "Istanza web SIAMM di liquidazione spese di giustizia per CTU e decreto di pagamento."

    assert has_presidio_rule(text, "siamm_lsg_liquidazione") is True
    assert has_presidio_rule(text, "gratuito_patrocinio") is False


def test_presidio_ruleset_impugnazioni_gdp_volontaria_e_minori():
    text = (
        "Ricorso per cassazione ex art. 369 c.p.c. con controricorso e adunanza camerale. "
        "Opposizione a sanzione amministrativa davanti al Giudice di Pace su SIGP. "
        "Volontaria giurisdizione: amministrazione di sostegno, rendiconto e reclamo ex art. 739. "
        "Procedimento persone minorenni e famiglie ex 473-bis con ascolto del minore e registrazione audiovisiva. "
        "Atto di appello con inibitoria e sospensione dell'efficacia esecutiva. "
        "Appello amministrativo al Consiglio di Stato e appello tributario con controdeduzioni dell'appellato."
    )
    codes = {hit["code"] for hit in presidio_rule_hits(text)}

    assert "cassazione_civile" in codes
    assert "giudice_pace_sigp" in codes
    assert "volontaria_giurisdizione" in codes
    assert "famiglia_minori_ascolto" in codes
    assert "appello_civile_lavoro" in codes
    assert "impugnazione_amministrativa" in codes
    assert "impugnazione_tributaria" in codes
