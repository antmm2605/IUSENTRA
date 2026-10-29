"""Correzioni dell'audit termini del 29/10/2026.

1. 4 ottobre (San Francesco d'Assisi) festività nazionale dal 2026 (L. 151/2025).
2. Proponente PEC: niente sospensione feriale nelle controversie di lavoro (art. 3 L. 742/1969).
3. Termine a mesi: lo spostamento per agosto si itera finché i giorni sospesi si stabilizzano.
4. «Almeno N giorni prima dell'udienza»: lettura prudenziale a giorni liberi, motore = scadenziario.
5. Materia: penale senza proroga del sabato (art. 172 c.p.p.), lavoro senza sospensione feriale.
6. «Oggi»/«adesso» in Europe/Rome.
7. Provenienza dei termini proposti dalla PEC persistita nella Scadenza.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta

import pytest

from pct import scadenziario as S
from pct.ora_italiana import ROME_TZ
from pct.pec_legal_deadline_proposer import propose_from_parsed, propose_legal_deadline
from pct.pec_pipeline import _legal_deadline_scadenza_fields
from pct.termini_processuali import (
    CALENDAR_VERSION,
    DEFAULT_TEMPLATES,
    ItalianDeadlineCalculator,
    national_holidays,
)

T = {template.code: template for template in DEFAULT_TEMPLATES}


def _engine(code: str, giorno: str, **overrides) -> str:
    return ItalianDeadlineCalculator().calculate_template(date.fromisoformat(giorno), T[code], overrides=overrides)["deadline"]


def _scadenziario(profile: str, giorno: str) -> str:
    esito = S.GestioneScadenziario.calcola_avanzata(start_at=date.fromisoformat(giorno), profile=S.PROFILI_TERMINE_BUILTIN[profile])
    return esito.legal_due_at[:10]


# --- 1. 4 ottobre ------------------------------------------------------------------


def test_4_ottobre_festivo_solo_dal_2026():
    assert date(2026, 10, 4) in national_holidays(2026)
    assert date(2027, 10, 4) in national_holidays(2027)
    assert date(2025, 10, 4) not in national_holidays(2025)
    assert date(2024, 10, 4) not in national_holidays(2024)
    assert date(2027, 10, 4) in S.festività_italiane(2027)
    assert date(2025, 10, 4) not in S.festività_italiane(2025)
    assert CALENDAR_VERSION.endswith("2026.2")


def test_4_ottobre_proroga_in_avanti_e_anticipa_a_ritroso():
    # 30 giorni dal 04/09/2027 = lunedì 04/10/2027, festivo -> martedì 05/10/2027.
    assert _engine("CIV_APPELLO_BREVE", "2027-09-04") == "2027-10-05"
    # Udienza 15/10/2027: 10 giorni liberi prima = 04/10 festivo, 03 domenica, 02 sabato -> 01/10/2027.
    assert _engine("CIV_MEMORIA_171_TER_3", "2027-10-15") == "2027-10-01"
    # Scadenziario: stesso risultato con la regola nazionale nat_1004 e con calcola_termine.
    assert _scadenziario("TERM_30_DAYS", "2027-09-04") == "2027-10-05"
    assert S.calcola_termine(date(2027, 9, 4), giorni=30) == date(2027, 10, 5)
    assert _scadenziario("TERM_10_DAYS_BEFORE", "2027-10-15") == "2027-10-01"


def test_4_ottobre_anni_precedenti_invariati():
    # 04/10/2024 venerdì: nel 2024 non era festivo, il termine resta al 4 ottobre.
    assert _engine("CIV_APPELLO_BREVE", "2024-09-04") == "2024-10-04"
    assert _scadenziario("TERM_30_DAYS", "2024-09-04") == "2024-10-04"
    rules = S.regole_calendario_nazionali()
    osservanza = next(rule for rule in rules if rule.code == "OCT_4_OBSERVANCE")
    assert osservanza.applies_to_legal_deadlines is False and osservanza.end_date == "2025-12-31"
    festa = next(rule for rule in rules if rule.id == "nat_1004")
    assert festa.applies_to_legal_deadlines is True and festa.start_date == "2026-01-01"


def test_4_ottobre_calcolatori_applicazioni():
    from web.services.applicazioni_runtime import _festivita_nazionali

    assert date(2026, 10, 4) in _festivita_nazionali(2026)
    assert date(2025, 10, 4) not in _festivita_nazionali(2025)


# --- 2. Proponente PEC e lavoro ---------------------------------------------------


def _parsed_lavoro() -> dict:
    return {
        "headers": {"subject": "Tribunale di Roma - Sezione Lavoro - RG 123/2026 LAV - comunicazione"},
        "body": {"text": "Il giudice del lavoro dispone la trattazione scritta ex art. 127-ter; le parti possono opporsi entro cinque giorni dalla comunicazione."},
    }


def test_proponente_lavoro_senza_sospensione_feriale():
    r = propose_from_parsed(_parsed_lavoro(), comunicazione_date="2026-07-29")
    assert r["ok"] is True
    assert r["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert r["deadline"] == "2026-08-03"
    assert r["materia_lavoro"] is True
    assert "art. 3 L. 742/1969" in r["explanation"]
    assert "labour_no_ferial_suspension_art_3_l742_1969" in r["rules_applied"]
    assert r["human_review_required"] is True


def test_proponente_civile_conserva_sospensione_feriale():
    parsed = {
        "headers": {"subject": "Tribunale di Roma - Sezione II civile - RG 123/2026"},
        "body": {"text": "Il giudice dispone la trattazione scritta ex art. 127-ter; le parti possono opporsi entro cinque giorni dalla comunicazione."},
    }
    r = propose_from_parsed(parsed, comunicazione_date="2026-07-29")
    assert r["deadline"] == "2026-09-03"
    assert r["materia_lavoro"] is False


# --- 3. Termine a mesi e agosto ----------------------------------------------------


@pytest.mark.parametrize(("pubblicazione", "attesa"), [("2026-02-10", "2026-09-10"), ("2026-02-28", "2026-09-28"), ("2026-03-15", "2026-10-16")])
def test_appello_lungo_iterazione_agosto_motore_uguale_scadenziario(pubblicazione: str, attesa: str):
    assert _engine("CIV_APPELLO_LUNGO", pubblicazione) == attesa
    assert S.calcola_termine(date.fromisoformat(pubblicazione), mesi=6, tipo="continui", sospensione_feriale=True).isoformat() == attesa
    assert _scadenziario("TERM_6_MONTHS_FERIAL", pubblicazione) == attesa


# --- 4. Giorni liberi prima dell'udienza ---------------------------------------------


def test_termini_prima_dell_udienza_tutti_liberi():
    for code in ("CIV_COSTITUZIONE_CONVENUTO_166", "CIV_MEMORIA_171_TER_1", "CIV_MEMORIA_171_TER_2", "CIV_MEMORIA_171_TER_3", "FAM_473BIS_COSTITUZIONE"):
        assert T[code].free_term is True, code
    assert T["CIV_COSTITUZIONE_CONVENUTO_166"].version == 3  # v3: doppia data, prudenziale e di legge (29/10/2026)
    assert all(T[c].metadata.get("lettura_prudenziale") for c in ("CIV_COSTITUZIONE_CONVENUTO_166", "CIV_MEMORIA_171_TER_1"))
    for profile in ("TERM_40_DAYS_BEFORE", "TERM_20_DAYS_BEFORE", "TERM_10_DAYS_BEFORE"):
        assert S.PROFILI_TERMINE_BUILTIN[profile].termine_libero is True


@pytest.mark.parametrize(
    ("code", "preset", "udienza", "attesa"),
    [
        ("CIV_MEMORIA_171_TER_3", "memoria_ex_171_ter_n3", "2026-11-20", "2026-11-09"),
        ("CIV_MEMORIA_171_TER_1", "memoria_ex_171_ter_n1", "2026-12-15", "2026-11-04"),
        ("CIV_MEMORIA_171_TER_2", "memoria_ex_171_ter_n2", "2026-11-23", "2026-11-02"),
        # Agosto saltato: 40° giorno sabato 11/07, giorno libero venerdì 10/07.
        ("CIV_MEMORIA_171_TER_1", "memoria_ex_171_ter_n1", "2026-09-20", "2026-07-10"),
        # Il giorno libero cade in agosto: si salta agosto (40° giorno 01/09 -> libero 31/07).
        ("CIV_MEMORIA_171_TER_1", "memoria_ex_171_ter_n1", "2026-10-11", "2026-07-31"),
    ],
)
def test_memorie_171ter_motore_uguale_scadenziario(code: str, preset: str, udienza: str, attesa: str):
    assert _engine(code, udienza) == attesa
    esito = S.GestioneScadenziario.calcola_avanzata(start_at=date.fromisoformat(udienza), profile=S.profilo_da_preset(preset))
    assert esito.legal_due_at[:10] == attesa


def test_costituzione_166_settanta_giorni_liberi():
    # 15/12/2026: 70 giorni liberi prima = 05/10/2026 (lunedì), non più 06/10.
    assert _engine("CIV_COSTITUZIONE_CONVENUTO_166", "2026-12-15") == "2026-10-05"


# --- 5. Materia ---------------------------------------------------------------------


def test_penale_sabato_non_proroga():
    r = ItalianDeadlineCalculator().calculate(date(2026, 10, 1), 30, matter_type="penal")
    assert r["deadline"] == "2026-10-31"  # sabato: art. 172, comma 3, c.p.p.
    assert "penal_no_saturday_extension_art_172_cpp" in r["rulesApplied"]
    assert "saturday_extension_out_of_hearing" not in r["rulesApplied"]
    civile = ItalianDeadlineCalculator().calculate(date(2026, 10, 1), 30)
    assert civile["deadline"] == "2026-11-02"  # 31/10 sabato, 01/11 festivo


def test_lavoro_senza_sospensione_salvo_forzatura_esplicita():
    calc = ItalianDeadlineCalculator()
    r = calc.calculate(date(2026, 7, 15), 30, matter_type="labor", suspend_august=True)
    assert r["deadline"] == "2026-08-14"
    assert "labour_no_ferial_suspension_art_3_l742_1969" in r["rulesApplied"]
    assert "ferial_suspension_1_31_august" not in r["rulesApplied"]
    forzata = calc.calculate(date(2026, 7, 15), 30, matter_type="labor", suspend_august=True, force_ferial_suspension=True)
    assert forzata["deadline"] == "2026-09-14"
    assert "labour_ferial_suspension_forced_override" in forzata["rulesApplied"]
    template = calc.calculate_template(date(2026, 7, 15), T["CIV_APPELLO_BREVE"], overrides={"matter_type": "labor"})
    assert template["deadline"] == "2026-08-14"


# --- 6. Europe/Rome -----------------------------------------------------------------


def test_adesso_roma_senza_fuso_e_formato_compatibile():
    adesso = S._adesso_roma()
    assert adesso.tzinfo is None
    riferimento = datetime.now(ROME_TZ).replace(tzinfo=None)
    assert abs(riferimento - adesso) < timedelta(seconds=5)
    creata = S.Scadenza(titolo="x").creata_il
    assert len(creata) == 19 and creata[10] == "T"


def test_strumenti_legali_oggi_roma(monkeypatch):
    import pct.strumenti_legali as strumenti

    monkeypatch.setattr(strumenti, "oggi_roma", lambda: date(2031, 1, 2))
    assert strumenti._today() == date(2031, 1, 2)


# --- 7. Provenienza -----------------------------------------------------------------


def test_proposta_porta_la_provenienza():
    r = propose_legal_deadline("Si dispone la trattazione scritta ex art. 127-ter c.p.c.", dies_a_quo_date="2026-03-02")
    prov = r["provenienza"]
    assert prov["ruleset_version"] == "2026.07"
    assert prov["rule_file"] == "legal_pec_deadline_rules_v2026_07.json"
    assert prov["matched_keyword"] == "127-ter"
    assert "127-ter" in prov["matched_snippet"]
    assert prov["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert prov["template_version"] == 1
    assert prov["reference_law"] == "Art. 127-ter c.p.c."
    assert prov["articolo"].startswith("Art. 127-ter")
    for key in ("ruleset_version", "rule_file", "matched_keyword", "matched_snippet", "template_version", "reference_law"):
        assert r[key] == prov[key]


def test_custom_processuale_ha_riferimento_normativo():
    assert T["CUSTOM_PROCESSUALE"].reference_law == "art. 155 c.p.c. (computo dei termini)"


def test_pipeline_passa_la_provenienza_alla_scadenza(tmp_path):
    legal = propose_from_parsed(_parsed_lavoro(), comunicazione_date="2026-07-29")
    proposal = {"legal_deadline_proposal": legal, "source_message_id": "msg-1", "document_sha256": "ab" * 32}
    fields = _legal_deadline_scadenza_fields(proposal)
    prov = fields["extra"]["provenienza"]
    assert prov["template_code"] == "CIV_OPPOSIZIONE_127_TER"
    assert prov["source_message_id"] == "msg-1"
    assert prov["document_sha256"] == "ab" * 32

    gs = S.GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    sc = gs.nuova(titolo="Opposizione 127-ter", tipo=S.TipoTermine.ADEMPIMENTO, data_scadenza=fields["due_date"], **fields["extra"])
    riletta = S.GestioneScadenziario(db_path=str(tmp_path / "scadenze.json")).get(sc.id)
    assert riletta.provenienza["matched_keyword"] == prov["matched_keyword"]
    assert riletta.provenienza["ruleset_version"] == "2026.07"


def test_scadenza_storica_senza_provenienza_resta_leggibile():
    assert S.Scadenza.from_dict({"titolo": "storica"}).provenienza == {}
    assert S.Scadenza.from_dict({"titolo": "x", "provenienza": None}).provenienza == {}
    assert S.Scadenza.from_dict({"titolo": "x", "provenienza": "non json"}).provenienza == {}
    assert S.Scadenza.from_dict({"titolo": "x", "provenienza": json.dumps({"a": 1})}).provenienza == {"a": 1}
