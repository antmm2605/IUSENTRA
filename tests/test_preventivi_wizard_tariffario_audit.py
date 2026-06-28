import json

from pct.preventivi import Preventivo
from pct.tariffario_catalogo import tariffario_audit_rows, tariffario_reference_rows
from web.services.react_preventivo_wizard_bridge import (
    build_react_preventivo_wizard_calculation_payload,
    build_react_preventivo_wizard_payload,
)


class _EmptyManager:
    def tutti(self):
        return []


class _NormativeTables:
    def tariffario_riferimenti(self):
        return tariffario_reference_rows()

    def tariffario_audit(self):
        return tariffario_audit_rows()


def _empty_manager():
    return _EmptyManager()


def _normative_tables():
    return _NormativeTables()


def test_wizard_espone_complessita_molto_alta_dalle_opzioni_backend():
    payload = build_react_preventivo_wizard_payload(
        get_clienti=_empty_manager,
        get_fascicoli=_empty_manager,
        get_normative_tables=_normative_tables,
        query={},
    )

    values = {row["value"]: row for row in payload["options"]["complexity"]}
    assert "molto_alta" in values
    assert "Molto alta" in values["molto_alta"]["label"]


def test_wizard_calcola_fascia_alta_e_conserva_audit_tariffario():
    payload = build_react_preventivo_wizard_calculation_payload(
        {
            "id_pratica": "atto_citazione",
            "regola_tariffaria": "civile_cognizione_primo_grado",
            "valore": "1000000",
            "grado": "Tribunale",
            "complessita": "molto_alta",
            "fasi": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "spese_generali": True,
            "applica_cpa": True,
            "applica_iva": True,
        }
    )

    assert payload["ok"] is True
    assert payload["scaglione"] == "Oltre € 520.000"
    assert payload["compenso_base"] > 0
    assert any(row["source"] == "motore" and row["importo"] > 0 for row in payload["rows"])
    audit = payload["audit"]
    assert audit["log_calcolo"]
    assert audit["audit_tariffario"]["scaglione"] == "Oltre € 520.000"
    assert audit["audit_tariffario"]["fascia_alta"] is True
    assert audit["reference_codes"]
    assert audit["riferimenti_normativi"]
    assert audit["table_code"] == "A2"
    assert audit["compliance_status"] == "snapshot_esatto"


def test_preventivo_legacy_senza_audit_si_carica_senza_errori():
    preventivo = Preventivo.from_dict(
        {
            "id": "legacy-1",
            "numero": "2026/001",
            "id_cliente": "cliente-1",
            "id_fascicolo": None,
            "data_emissione": "2026-05-07",
            "data_scadenza": None,
            "oggetto": "Preventivo legacy",
            "voci": [{"descrizione": "Compenso", "importo": 1000, "tipo": "onorario"}],
            "log_calcolo": None,
        }
    )

    assert preventivo.id == "legacy-1"
    assert preventivo.log_calcolo is None


def test_preventivo_da_dict_sincronizza_log_calcolo_dict_con_audit():
    preventivo = Preventivo.from_dict(
        {
            "id": "audit-1",
            "numero": "2026/002",
            "id_cliente": "cliente-1",
            "id_fascicolo": None,
            "data_emissione": "2026-05-07",
            "data_scadenza": None,
            "oggetto": "Preventivo con audit",
            "voci": [{"descrizione": "Compenso", "importo": 1000, "tipo": "onorario"}],
            "id_pratica": "atto_citazione",
            "regola_tariffaria": "civile_cognizione_primo_grado",
            "log_calcolo": {"tariffario": {"rule_code": "civile_cognizione_primo_grado"}},
        }
    )
    parsed = json.loads(preventivo.log_calcolo or "{}")

    assert parsed["tariffario"]["rule_code"] == "civile_cognizione_primo_grado"
    assert parsed["tariffario"]["table_code"] == "A2"
    assert parsed["tariffario"]["reference_codes"]


def test_frontend_non_contiene_formule_tariffarie_duplicate():
    forbidden = [
        "totale_minimo =",
        "totale_base =",
        "totale_massimo =",
        "DM 147/2022 +/-50%",
        "calcola_compenso(",
    ]
    frontend_files = [
        "frontend/src/components/TariffarioPage.tsx",
        "frontend/src/components/PreventivoWizardPage.tsx",
        "frontend/src/tariffarioData.ts",
        "frontend/src/preventivoWizardData.ts",
    ]
    haystack = "\n".join(open(path, encoding="utf-8").read() for path in frontend_files)

    for token in forbidden:
        assert token not in haystack
