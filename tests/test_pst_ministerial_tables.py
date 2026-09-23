from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from legal_deposit.errors.rejection_analyzer import (
    PST_CONTROL_ERROR_RULES,
    PST_CONTROL_ERRORS_SHA256,
    RejectionAnalyzer,
)
from pct.beni_mobili_pst import (
    SCOPE_INDIVIDUAL_ENFORCEMENT,
    SCOPE_INSOLVENCY,
    SOURCE_SHA256,
    mobile_asset_entries,
    mobile_asset_options,
    require_mobile_asset_code,
)
from pct.deposito_telematico_catalogo import resolve_deposit_type_payload

ROOT = Path(__file__).resolve().parents[1]


def _sha256(relative_path: str) -> str:
    return hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest().upper()


def test_fonti_pdf_pst_hanno_le_impronte_acquisite_dalle_schede_ufficiali():
    assert _sha256("docs/specs/ministero/Codifiche_Beni_Mobili.pdf") == SOURCE_SHA256
    assert _sha256("docs/specs/ministero/Codifica_errori_controlli_1.0.pdf") == PST_CONTROL_ERRORS_SHA256


def test_catalogo_beni_mobili_riproduce_le_due_sezioni_del_pdf_ufficiale():
    individual = mobile_asset_entries(scope=SCOPE_INDIVIDUAL_ENFORCEMENT)
    insolvency = mobile_asset_entries(scope=SCOPE_INSOLVENCY)

    assert len(individual) == 27
    assert [row["code"] for row in individual] == [str(value) for value in range(27)]
    assert individual[0]["label"] == "Compendio pignorato"
    assert individual[23]["label"] == "Credito unitario"
    assert len(insolvency) == 485
    assert any(row == {"code": "702.999", "label": "Varie", "scope": SCOPE_INSOLVENCY} for row in insolvency)


def test_codici_duplicati_pubblicati_non_vengono_nascosti_o_inventati():
    rows_115_1 = [
        row["label"]
        for row in mobile_asset_entries(scope=SCOPE_INSOLVENCY)
        if row["code"] == "115.1"
    ]
    assert rows_115_1 == ["Apparecchiature per optometria", "Amplificatori e Casse acustiche"]
    assert dict(mobile_asset_options(scope=SCOPE_INSOLVENCY))["115.1"] == (
        "Apparecchiature per optometria / Amplificatori e Casse acustiche"
    )


@pytest.mark.parametrize("code", ["0", "3", "23", "26"])
def test_codice_bene_mobile_accetta_solo_valori_ufficiali(code):
    assert require_mobile_asset_code(code) == code


@pytest.mark.parametrize("code", ["", "MOBILI", "ARREDI", "CREDITO", "999"])
def test_codice_bene_mobile_rifiuta_testo_libero_e_valori_non_ufficiali(code):
    with pytest.raises(ValueError, match="codice ufficiale PST"):
        require_mobile_asset_code(code)


def test_campi_siecic_e_unep_espongono_i_27_codici_ufficiali():
    siecic = resolve_deposit_type_payload(
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoDebitore"
    )
    unep = resolve_deposit_type_payload("Atti_UNEP::RichiestaPignoramentoMobiliare")
    assert siecic is not None
    assert unep is not None

    siecic_field = next(field for field in siecic["schema"]["inputFields"] if field["id"] == "beni_pignorati")
    unep_field = next(field for field in unep["schema"]["inputFields"] if field["id"] == "unep_beni")
    expected = [{"value": str(code), "label": label} for code, label in mobile_asset_options()]
    assert siecic_field["options"] == expected
    assert unep_field["options"] == expected
    assert len(expected) == 27


@pytest.mark.parametrize(
    ("raw", "category", "level", "severity", "can_resubmit"),
    [
        ("Busta non elaborabile", "busta_non_elaborabile", "FATAL", "critical", True),
        ("IndiceBusta.xml non presente", "indice_busta_assente", "FATAL", "critical", True),
        ("Certificato firma scaduto", "certificato_firma_scaduto", "ERROR", "high", True),
        ("Numero di ruolo non esistente nel registro di cancelleria", "numero_ruolo_non_valido", "ERROR", "high", True),
        ("Atto depositato fuori termine", "deposito_fuori_termine", "WARN", "warning", False),
        ("Allegato Procura alle liti assente", "procura_assente", "WARN", "warning", False),
    ],
)
def test_rejection_analyzer_mappa_i_livelli_ufficiali(
    raw, category, level, severity, can_resubmit
):
    diagnosis = RejectionAnalyzer().analyze(raw)
    assert diagnosis.category == category
    assert diagnosis.ministerial_level == level
    assert diagnosis.severity == severity
    assert diagnosis.can_resubmit is can_resubmit
    assert diagnosis.ministerial_source.endswith("Codifica_errori_controlli_1.0.pdf")


@pytest.mark.parametrize("category,level,_message,_action,patterns", PST_CONTROL_ERROR_RULES)
def test_ogni_regola_ufficiale_e_raggiungibile(
    category, level, _message, _action, patterns
):
    diagnosis = RejectionAnalyzer().analyze(patterns[0])
    assert diagnosis.category == category
    assert diagnosis.ministerial_level == level


def test_livello_ministeriale_sconosciuto_resta_fail_closed():
    diagnosis = RejectionAnalyzer().analyze("FATAL codice futuro non presente nella versione 1.0")
    assert diagnosis.category == "messaggio_ministeriale_non_catalogato"
    assert diagnosis.ministerial_level == "FATAL"
    assert diagnosis.can_resubmit is False
    assert diagnosis.requires_lawyer_review is True