"""Sospensione feriale esclusa per legge: regressione del calcolatore dei termini (valutazione del 25/11/2026).

Norme (testo vigente, biblioteca del software): art. 1 e 3 L. 742/1969; art. 92 R.D. 12/1941; art. 669-terdecies,
641, 645, 155 c.p.c.; art. 203 d.lgs. 285/1992; art. 2963, terzo comma, c.c.; art. 9 d.lgs. 14/2019.
"""
from __future__ import annotations

from datetime import date

import pytest

from pct.calcolatori.termini_scadenza import calcola
from pct.termini_esclusioni_feriali import esclusione_per_norma
from pct.termini_processuali import DeadlineTemplate, ItalianDeadlineCalculator


def _scadenza(modello: str, evento: str, **campi: str) -> dict:
    return calcola({"term_modello": modello, "term_data_evento": evento, **campi})


def test_reclamo_cautelare_notificato_il_20_luglio_scade_il_4_agosto():
    esito = _scadenza("CIV_RECLAMO_CAUTELARE_669_TERDECIES", "2026-07-20")
    assert esito["scadenza"] == "04/08/2026"
    assert esito["sospensione_feriale"] is False


def test_ricorso_al_prefetto_notificato_il_15_luglio():
    # 60 giorni dal 15/07/2026: 13/09/2026, domenica; il festivo proroga al lunedì (art. 2963, terzo comma, c.c.).
    esito = _scadenza("CDS_RICORSO_PREFETTO_60GG", "2026-07-15")
    assert esito["scadenza_senza_proroghe"] == "13/09/2026"
    assert esito["scadenza"] == "14/09/2026"
    assert esito["sospensione_feriale"] is False


def test_ricorso_al_prefetto_non_ha_la_proroga_del_sabato():
    # Ricorso amministrativo: l'art. 155, quinto comma, c.p.c. (proroga del sabato) vale solo per gli atti processuali.
    evento = date(2026, 7, 6)  # + 60 = 04/09/2026, venerdì
    sabato = date(2026, 7, 7)  # + 60 = 05/09/2026, sabato
    assert _scadenza("CDS_RICORSO_PREFETTO_60GG", evento.isoformat())["scadenza"] == "04/09/2026"
    assert _scadenza("CDS_RICORSO_PREFETTO_60GG", sabato.isoformat())["scadenza"] == "05/09/2026"


@pytest.mark.parametrize("campi", [{"term_modello": "LAV_OPPOSIZIONE_DI"},
                                   {"term_modello": "CIV_OPPOSIZIONE_DI", "term_materia_lavoro": "1"}])
def test_opposizione_decreto_ingiuntivo_lavoro_senza_sospensione(campi):
    # 40 giorni dal 20/07/2026 = 29/08/2026, sabato: atto fuori udienza, proroga al lunedì 31/08 (art. 155, quinto
    # comma, c.p.c.). Senza la sospensione feriale (art. 3 L. 742/1969).
    esito = calcola({**campi, "term_data_evento": "2026-07-20"})
    assert esito["scadenza_senza_proroghe"] == "29/08/2026"
    assert esito["scadenza"] == "31/08/2026"
    assert esito["sospensione_feriale"] is False


def test_opposizione_decreto_ingiuntivo_civile_mantiene_la_sospensione():
    esito = _scadenza("CIV_OPPOSIZIONE_DI", "2026-07-20")
    assert esito["sospensione_feriale"] is True
    assert esito["scadenza"] == "29/09/2026"  # 11 giorni a luglio, agosto sospeso, 29 a settembre


def _modello_salvato(**campi) -> DeadlineTemplate:
    """Un modello come quelli importati dalla Guida Pratica negli archivi degli studi: sospensione attiva."""
    base = {"code": "GP_PROVA", "name": "Termine", "matter_type": "civil", "base_value": 15,
            "suspend_august": True, "ferial_suspension_policy": "applies", "reference_law": ""}
    return DeadlineTemplate.from_dict({**base, **campi})


def _calcolo(modello: DeadlineTemplate, evento: date = date(2026, 7, 20)) -> dict:
    return ItalianDeadlineCalculator().calculate_template(evento, modello)


def test_reclamo_cautelare_importato_con_sospensione_attiva_non_slitta():
    modello = _modello_salvato(name="Reclamo contro provvedimento cautelare", matter_type="admin",
                               reference_law="c.p.c. art. 669-terdecies")
    esito = _calcolo(modello)
    assert esito["deadline"] == "2026-08-04"
    assert "ferial_excluded_cautelare" in esito["rulesApplied"]
    assert "art. 92 R.D. 12/1941" in esito["explanation"]


def test_forzatura_esplicita_resta_possibile():
    modello = _modello_salvato(name="Reclamo cautelare", reference_law="art. 669-terdecies c.p.c.",
                               metadata={"force_ferial_suspension": True})
    assert _calcolo(modello)["deadline"] == "2026-09-04"


def test_merito_dopo_cautelare_resta_dubbio_con_data_prudente():
    modello = _modello_salvato(name="Instaurazione causa di merito post-sequestro", base_value=60,
                               reference_law="art. 669-octies c.p.c.")
    esito = _calcolo(modello, date(2026, 7, 10))
    assert esito["deadline"] == "2026-09-08"
    assert esito["requiresLegalReview"] is True
    assert esito.get("dubbio")


def test_rito_locatizio_resta_soggetto_alla_sospensione():
    modello = _modello_salvato(name="Costituzione resistente", matter_type="labor", base_value=10,
                               reference_law="art. 416 c.p.c. richiamato da 447-bis")
    esito = _calcolo(modello)
    assert "ferial_suspension_1_31_august" in esito["rulesApplied"]
    assert "lease_rite_ferial_applies_art_447_bis_cpc" in esito["rulesApplied"]


@pytest.mark.parametrize("nome, norma, atteso", [
    ("Reclamo contro provvedimento cautelare", "c.p.c. art. 669-terdecies", "ferial_excluded_cautelare"),
    ("Reclamo", "", None),
    ("Reclamo Corte d'Appello", "art. 720-bis c.p.c.", "ferial_excluded_ads_interdizione"),
    ("Opposizione a intimazione di sfratto", "art. 665 c.p.c.", "ferial_excluded_sfratto"),
    ("Opposizione all'esecuzione", "art. 615 c.p.c.", "ferial_excluded_opposizione_esecuzione"),
    ("Opposizione agli atti esecutivi", "art. 617 c.p.c.", None),
    ("Reclamo contro la sentenza di liquidazione giudiziale", "art. 51 d.lgs. 14/2019", "ferial_excluded_ccii"),
    ("Impugnazione dello stato passivo", "art. 206 e 207 d.lgs. 14/2019", None),
    ("Ricorso", "art. 35-bis c. 2 D.Lgs. 25/2008", "ferial_excluded_protezione_internazionale"),
    ("Appello nel rito del lavoro", "art. 434 c.p.c.", "labour_no_ferial_suspension_art_3_l742_1969"),
    ("Ricorso al Prefetto", "art. 203 CdS", "ferial_not_applicable_ricorso_amministrativo"),
    ("Opposizione", "art. 641 c.p.c.", None),
    ("Appello", "Art. 325 c.p.c.", None),
    ("GIUDIZIO DI MERITO post sequestro", "", None),
])
def test_catalogo_delle_esclusioni(nome, norma, atteso):
    esclusione = esclusione_per_norma(nome, norma, "civil")
    assert (esclusione.codice if esclusione else None) == atteso


def test_reclamo_senza_norma_di_una_scheda_cautelare():
    guida = "GUIDA_PROVVEDIMENTO_D_URGENZA_ATIPICO_INIBITORIA_CAUTELARE_ART_700_C_P_C_190015"
    assert esclusione_per_norma("Reclamo", "", "civil", guida).codice == "ferial_excluded_cautelare"


def test_materia_penale_fuori_da_questa_regola():
    assert esclusione_per_norma("Riesame", "art. 309 c.p.p. cautelare", "penal") is None
