from pct.economico_context import (
    carica_log_calcolo,
    causale_documento_economico,
    costruisci_contesto_economico,
    dump_log_calcolo,
    riepilogo_contesto_economico,
    sincronizza_contesto_economico,
)


def test_contesto_economico_serializza_e_riassume_adr():
    raw = dump_log_calcolo(
        costruisci_contesto_economico(
            source="preventivo_guidato",
            source_label="Preventivo guidato",
            pratica_label="Negoziazione assistita",
            area_pratica="Stragiudiziale",
            tipo_compenso="Per fasi processuali (D.M. 55/2014)",
            tipo_procedimento="Negoziazione assistita — Procedura ADR",
            grado_sede="Procedura ADR",
            regola_tariffaria="negoziazione_assistita",
            complessita="media",
            valore_controversia=10000,
            adr_accordo=True,
            variazioni_fasi_pct={"attivazione": 50, "negoziazione": -50},
            risultato={"scaglione": "Da EUR 5.200 a EUR 26.000", "totale": 3626.24},
            riferimenti_normativi=["D.M. 10 marzo 2014, n. 55", "Art. 20, comma 1-bis, D.M. 55/2014"],
        )
    )

    loaded = carica_log_calcolo(raw)
    summary = riepilogo_contesto_economico(loaded)

    assert summary["source_label"] == "Preventivo guidato"
    assert summary["pratica_label"] == "Negoziazione assistita"
    assert summary["adr_enabled"] is True
    assert summary["adr_accordo"] is True
    assert [row["label"] for row in summary["variazioni_fasi"]] == [
        "attivazione: +50%",
        "negoziazione: -50%",
    ]


def test_causale_documento_economico_arricchisce_la_nota_con_contesto_adr():
    raw = dump_log_calcolo(
        costruisci_contesto_economico(
            source="tariffario_forense",
            source_label="Tariffario forense",
            pratica_label="Mediazione civile",
            regola_tariffaria="mediazione_obbligatoria",
            adr_accordo=True,
            variazioni_fasi_pct={"attivazione": 10},
        )
    )

    causale = causale_documento_economico("Compenso professionale", raw)

    assert "Compenso professionale" in causale
    assert "Mediazione civile" in causale
    assert "ADR con accordo" in causale


def test_sincronizza_contesto_economico_arricchisce_regola_e_audit_tariffario():
    raw = dump_log_calcolo(
        costruisci_contesto_economico(
            source="tariffario_forense",
            source_label="Tariffario forense",
            id_pratica="negoziazione_assistita",
            pratica_label="Negoziazione assistita",
            regola_tariffaria="negoziazione_adr",
            regola_tariffaria_code="negoziazione_adr",
        )
    )

    synced = sincronizza_contesto_economico(raw)
    summary = riepilogo_contesto_economico(synced)

    assert synced["regola_tariffaria_code"] == "negoziazione_adr"
    assert synced["regola_tariffaria_label"] == "Negoziazione assistita"
    assert summary["regola_tariffaria_label"] == "Negoziazione assistita"
    assert summary["audit_tariffario"]["table_code"] == "A27"
    assert summary["audit_tariffario"]["compliance_label"] == "Ricostruzione dichiarata"


def test_contesto_economico_arricchisce_procedura_operativa():
    raw = dump_log_calcolo(
        costruisci_contesto_economico(
            source="preventivo_guidato",
            source_label="Preventivo guidato",
            id_pratica="ricorso_tributario",
            pratica_label="Ricorso tributario",
            area_pratica="Tributario",
            tipo_compenso="Per fasi processuali (D.M. 55/2014)",
            tipo_procedimento="Ricorso tributario di primo grado",
        )
    )

    summary = riepilogo_contesto_economico(raw)

    assert summary["procedura_operativa_codice"] == "PROC_TRIB_RIC_002"
    assert summary["procedura_operativa_nome"] == "Ricorso tributario di primo grado"
    assert summary["canale_operativo"] == "PTT_TRIBUTARIO"
