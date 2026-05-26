from __future__ import annotations

import sqlite3

from pct.uffici_competenti import ricerca_uffici_competenti
from scripts.audit_uffici_giudiziari_comuni_db import audit
from scripts.build_uffici_giudiziari_comuni_db import DEFAULT_UFFICI_DB, REQUESTED_KINDS
from pct.territorio_italia import DEFAULT_TERRITORIO_DB
from web.blueprints.api_v1_react import _uffici_competenti_result
from werkzeug.datastructures import MultiDict


def test_audit_associazioni_uffici_giudiziari_100_percento() -> None:
    result = audit(DEFAULT_UFFICI_DB, DEFAULT_TERRITORIO_DB)

    assert result["ok"] is True
    assert result["expected_comuni"] == 7894
    assert result["comuni_ok"] == result["expected_comuni"]
    assert result["comuni_con_associazioni"] == result["expected_comuni"]
    assert result["coverage_comuni_pct"] == 100.0
    assert result["coverage_associazioni_pct"] == 100.0
    assert set(result["tipologie_richieste_presenti"]) == REQUESTED_KINDS


def test_associazioni_contengono_tutte_le_tipologie_richieste_con_pec_dove_ufficiale() -> None:
    with sqlite3.connect(DEFAULT_UFFICI_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT o.kind AS kind,
                   COUNT(*) AS total,
                   SUM(CASE WHEN o.pec <> '' THEN 1 ELSE 0 END) AS with_pec
            FROM office_associations a
            JOIN offices o ON o.office_id = a.office_id
            GROUP BY o.kind
            """
        ).fetchall()

    by_kind = {row["kind"]: row for row in rows}
    assert set(by_kind) == REQUESTED_KINDS
    for kind in REQUESTED_KINDS:
        assert int(by_kind[kind]["total"]) > 0
        assert int(by_kind[kind]["with_pec"]) > 0


def test_ricerca_setteville_usa_comuni_predecessori_e_restituisce_pec_procura_generale() -> None:
    result = ricerca_uffici_competenti(
        "Setteville",
        includi_speciali=True,
        tipi_ufficio=["procura_generale"],
        solo_pec=True,
    )

    names = [office["name"] for office in result["offices"]]
    assert "Procura Generale della Repubblica presso la Corte d'Appello di VENEZIA" in names
    assert all("Cassazione" not in name for name in names)
    assert any("giustiziacert.it" in office["pec"] for office in result["offices"])
    assert any(office.get("derivedFromComuni") == ["Alano di Piave", "Quero Vas"] for office in result["offices"])


def test_ricerca_palmi_filtra_unep_e_inserisce_solo_recapiti_pec() -> None:
    result = ricerca_uffici_competenti(
        "Palmi",
        includi_speciali=True,
        tipi_ufficio=["unep"],
        solo_pec=True,
    )

    assert result["offices"]
    assert all(office["kind"] == "unep" for office in result["offices"])
    assert all("giustiziacert.it" in office["pec"] for office in result["offices"])


def test_endpoint_uffici_competenti_usa_codice_istat_del_comune_selezionato() -> None:
    payload = MultiDict(
        [
            ("comune", "Setteville"),
            ("comune_istat", "025075"),
            ("includi_speciali", "1"),
            ("solo_pec", "1"),
            ("tipo_ufficio", "procura_generale"),
        ]
    )

    result = _uffici_competenti_result(payload, {"title": "Uffici competenti per Comune"})

    assert result["ok"] is True
    assert result["comuneRecord"]["codiceIstat"] == "025075"
    assert result["metrics"][0]["value"] == "Setteville (BL)"
    assert result["offices"][0]["kind"] == "procura_generale"
    assert "giustiziacert.it" in result["offices"][0]["pec"]
