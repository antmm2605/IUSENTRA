from __future__ import annotations

import json
import sqlite3

from pct.uffici_competenti import normalizza_codici_ufficio_telematico, ricerca_uffici_competenti
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
    assert result["uffici_unici"] == 1028
    assert result["codici_ufficio_presenti"] > 0
    assert result["codici_pst_presenti"] > 0
    assert result["codici_gl_presenti"] > 0
    assert result["uffici_solo_istat_sede"] > 0
    assert result["codici_istat_promossi_a_codice"] == []


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


def test_codici_nazionali_restano_separati_da_istat_sede() -> None:
    with sqlite3.connect(DEFAULT_UFFICI_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT office_json FROM offices ORDER BY office_id").fetchall()

    assert len(rows) == 1028
    for row in rows:
        office = normalizza_codici_ufficio_telematico(json.loads(row["office_json"]))
        istat = str(office.get("istatCode") or "")
        if not istat:
            continue
        assert str(office.get("codice") or "") != istat
        assert str(office.get("codiceMinistero") or "") != istat
        assert str(office.get("codiceGiustiziaLocale") or "") != istat


def test_ricerca_taurianova_separa_codici_pst_gl_e_istat_per_uffici_speciali() -> None:
    result = ricerca_uffici_competenti("Taurianova", includi_speciali=True)
    offices = {office["name"]: office for office in result["offices"]}

    tribunale = offices["Tribunale di PALMI"]
    assert tribunale["codice"] == "0910011"
    assert tribunale["codiceMinistero"] == "0800570094"
    assert tribunale["codiceGiustiziaLocale"] == "GLRC"
    assert tribunale["istatCode"] == "18080057"

    assise_appello = offices["Corte di Assise di Appello di REGGIO CALABRIA"]
    assert assise_appello["kind"] == "assise_appello"
    assert assise_appello["codice"] in ("", None)
    assert assise_appello["codiceMinistero"] in ("", None)
    assert assise_appello["codiceGiustiziaLocale"] in ("", None)
    assert assise_appello["istatCode"] == "18080063"

    unep = offices["Unep presso il Tribunale di PALMI"]
    assert unep["kind"] == "unep"
    assert unep["codice"] == "08005702237"
    assert unep["codiceMinistero"] == "08005702237"
    assert unep["codiceGiustiziaLocale"] == "UNRC"


def test_unep_distrettuale_non_prende_il_codice_della_corte_appello() -> None:
    result = ricerca_uffici_competenti("Reggio Calabria", includi_speciali=True)
    offices = {office["name"]: office for office in result["offices"]}
    unep_appello = offices["Unep presso la Corte d'Appello di REGGIO CALABRIA"]

    assert unep_appello["kind"] == "unep"
    assert unep_appello["codice"] == "08006300630"
    assert unep_appello["codiceMinistero"] == "08006300630"
    assert unep_appello["codiceGiustiziaLocale"] == "UNRC"


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
    assert any(office["codiceMinistero"] == "08005702237" for office in result["offices"])


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
