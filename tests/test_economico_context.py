from pct.economico_context import (
    carica_log_calcolo,
    causale_documento_economico,
    costruisci_contesto_economico,
    dump_log_calcolo,
    riepilogo_contesto_economico,
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
