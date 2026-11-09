"""Guide pratiche del 09/11/2026: i 62 fascicoli dello studio senza guida e le schede che mancavano.

Norme lette sul testo vigente (archivio Normattiva del software; D.L. 669/1996 su normattiva.it):
artt. 431, 474, 475, 479, 480, 481 c.p.c.; art. 14 D.L. 669/1996; art. 11 R.D. 1611/1933; artt. 5 e 16 D.Lgs. 206/2007;
art. 2 L. 241/1990; artt. 31, 87, 112, 113, 114, 117 c.p.a.; art. 13, comma 6-bis, D.P.R. 115/2002; art. 124 disp. att. c.p.c.
"""

from __future__ import annotations

import json

import pytest

from pct.guida_pratica.regole_materia import controparte_pubblica, regola_della_materia
from pct.guida_pratica.service import get_guida_pratica_service


@pytest.fixture(scope="module")
def servizio():
    return get_guida_pratica_service()


@pytest.mark.parametrize(
    ("fascicolo", "atteso"),
    [
        ({"oggetto": "retribuzione", "titolo": "Vullo c. MIM", "tipo": "LAVORO"}, "222050"),
        ({"oggetto": "retribuzione", "titolo": "RG 771/2025", "tipo": "LAVORO", "controparte": "Ministero dell'Istruzione e del Merito"}, "222050"),
        ({"oggetto": "retribuzione", "titolo": "Rossi c. Alfa srl", "tipo": "LAVORO", "controparte": "Alfa srl"}, "220050"),
        ({"titolo": "Cicero c. MIM (ricorso per l'ottemperanza)", "tipo": "AMMINISTRATIVO"}, "GUIDA_AMMINISTRATIVO_OTTEMPERANZA"),
        ({"oggetto": "silenzio titolo estero", "tipo": "AMMINISTRATIVO"}, "GUIDA_AMMINISTRATIVO_SILENZIO_RICONOSCIMENTO_TITOLO_ESTERO"),
        ({"oggetto": "Ricorso avverso decreto ministero", "tipo": "AMMINISTRATIVO"}, "GUIDA_AMMINISTRATIVO_RICORSO_TAR"),
        ({"titolo": "Precetto Michela Emanuela ferie", "tipo": "CIVILE"}, "GUIDA_PRECETTO_ANCHE_CONTRO_PA"),
        ({"titolo": "Precetto scarfò Tar Roma", "tipo": "AMMINISTRATIVO"}, "GUIDA_PRECETTO_ANCHE_CONTRO_PA"),
    ],
)
def test_i_fascicoli_dello_studio_senza_guida_la_ricevono(servizio, fascicolo, atteso):
    proposta = servizio.suggest_guidance_from_fascicolo(fascicolo)
    assert proposta and proposta["codice"] == atteso and proposta["confirmation_required"] is True


def test_l_opposizione_a_precetto_non_prende_la_guida_del_precetto(servizio):
    assert regola_della_materia({"titolo": "Opposizione a precetto Rossi", "tipo": "CIVILE"}, servizio._kb_index) is None


def test_la_controparte_pubblica_decide_la_giurisdizione_sulla_retribuzione():
    assert controparte_pubblica({"controparte": "Ufficio Scolastico Regionale per la Calabria"})
    assert not controparte_pubblica({"controparte": "Beta S.p.A."})


def test_un_collegamento_gia_trovato_dal_catalogo_non_cambia(servizio):
    proposta = servizio.suggest_guidance_from_fascicolo({"oggetto": "Retribuzione (differenze retributive)", "tipo": "LAVORO"})
    assert proposta and not str(proposta.get("matched_by", "")).startswith("regola della materia")


def test_guida_del_precetto_con_i_termini_vigenti(servizio):
    scheda = servizio._kb_index["GUIDA_PRECETTO_ANCHE_CONTRO_PA"]
    termini = {t["norma"]: t for t in scheda["termini_processuali"]}
    assert termini["art. 14, comma 1, D.L. 669/1996"]["giorni"] == 120
    assert termini["art. 480, primo comma, c.p.c."]["giorni"] == 10
    assert termini["art. 481 c.p.c."]["giorni"] == 90
    testo = json.dumps(scheda, ensure_ascii=False)
    assert "sovraindebitamento" in testo and "giudice competente per l'esecuzione" in testo
    assert "duplicato informatico" in testo and scheda["depositabile"] is False


def test_guida_del_silenzio_sul_titolo_estero(servizio):
    scheda = servizio._kb_index["GUIDA_AMMINISTRATIVO_SILENZIO_RICONOSCIMENTO_TITOLO_ESTERO"]
    testo = json.dumps(scheda, ensure_ascii=False)
    assert "tre mesi" in testo and "un anno" in testo and "300" in testo
    assert any(n["articolo"] == "117" for n in scheda["normativa"])


def test_ottemperanza_allega_il_giudicato_e_non_un_provvedimento_impugnato(servizio):
    scheda = servizio._kb_index["GUIDA_AMMINISTRATIVO_OTTEMPERANZA"]
    allegati = {a["id"] for a in scheda["allegati_obbligatori"]}
    assert "provvedimento_impugnato" not in allegati and {"sentenza", "giudicato"} <= allegati
    assert "art. 113, comma 2" in scheda["competenza"] and "300" in json.dumps(scheda, ensure_ascii=False)


def test_carta_del_docente_e_lavoro_contro_la_pa_senza_oggetto(servizio):
    assert servizio.suggest_guidance_from_fascicolo({"titolo": "Rossi c. MIM - carta del docente", "tipo": "LAVORO"})["codice"] == "222050"
    proposta = servizio.suggest_guidance_from_fascicolo({"titolo": "Spadaro II ricorso C. MIM", "tipo": "LAVORO"})
    assert proposta["codice"] == "222050" and "controparte pubblica" in proposta["matched_by"]
    assert servizio.suggest_guidance_from_fascicolo({"titolo": "Bianchi c. Gamma srl", "tipo": "LAVORO"}) is None
