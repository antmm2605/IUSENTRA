"""Guida pratica: norme scelte per data (vigenza) e suggerimento delle guide interne per materia."""

from datetime import date

from pct.guida_pratica.service import get_guida_pratica_service
from pct.guida_pratica.vigenza import applica_vigenza, data_di_riferimento


def _guida_tributaria_di_prova():
    return {
        "normativa": [
            {"fonte": "D.Lgs. 546/1992", "articolo": "21", "vigente_fino_al": "2026-12-31"},
            {"fonte": "D.Lgs. 175/2024", "articolo": "67", "vigente_dal": "2027-01-01"},
            {"fonte": "D.Lgs. 175/2024", "articolo": "131"},
        ],
        "termini_processuali": [
            {"termine": "Ricorso", "giorni": 60, "norma": "art. 21 D.Lgs. 546/1992", "vigente_fino_al": "2026-12-31"},
            {"termine": "Ricorso", "giorni": 60, "norma": "art. 67 D.Lgs. 175/2024", "vigente_dal": "2027-01-01"},
        ],
        "avvertenze_redazionali": [],
    }


def test_prima_del_testo_unico_restano_le_norme_del_546_e_si_annuncia_il_cambio():
    guida = applica_vigenza(_guida_tributaria_di_prova(), {}, oggi=date(2026, 11, 6))
    assert [v["articolo"] for v in guida["normativa"]] == ["21", "131"]
    assert [v["norma"] for v in guida["termini_processuali"]] == ["art. 21 D.Lgs. 546/1992"]
    assert guida["vigenza_applicata"]["prossimo_cambio"] == "2027-01-01"
    assert guida["avvertenze_redazionali"][0].startswith("Norme e termini scelti per la data di oggi: 06/11/2026. Dal 01/01/2027")


def test_atto_da_compiere_nel_2027_usa_il_testo_unico():
    guida = applica_vigenza(_guida_tributaria_di_prova(), {"data_atto_da_compiere": "15/02/2027"}, oggi=date(2026, 11, 6))
    assert [v["articolo"] for v in guida["normativa"]] == ["67", "131"]
    assert [v["norma"] for v in guida["termini_processuali"]] == ["art. 67 D.Lgs. 175/2024"]
    assert guida["vigenza_applicata"]["prossimo_cambio"] == ""


def test_scheda_senza_vigenza_non_cambia():
    guida = {"normativa": [{"fonte": "c.p.c.", "articolo": "414"}], "avvertenze_redazionali": ["x"]}
    assert applica_vigenza(dict(guida), {}) == guida


def test_data_di_riferimento_usa_oggi_senza_indicazioni():
    assert data_di_riferimento({}, oggi=date(2026, 11, 6)) == (date(2026, 11, 6), "data di oggi")


def test_fascicolo_penale_riceve_la_guida_penale_e_non_un_codice_civile():
    servizio = get_guida_pratica_service()
    proposta = servizio.suggest_guidance_from_fascicolo({"oggetto": "Riesame ordinanza custodia cautelare", "tipo": "PENALE"})
    assert proposta["codice"] == "GUIDA_PENALE_RIESAME_MISURA"
    assert proposta["guide_only"] is True
    guida = servizio.get_guidance(proposta["codice"])
    assert any("art. 111-bis c.p.p." in avviso for avviso in guida["avvertenze_redazionali"])


def test_fascicolo_tributario_riceve_la_guida_di_procedura():
    proposta = get_guida_pratica_service().suggest_guidance_from_fascicolo({"oggetto": "Ricorso avviso di accertamento IRPEF 2021", "tipo": "TRIBUTARIO"})
    assert proposta["codice"] == "GUIDA_TRIBUTARIO_RICORSO_PRIMO_GRADO"


def test_fascicolo_civile_continua_a_usare_il_catalogo_ufficiale():
    proposta = get_guida_pratica_service().suggest_guidance_from_fascicolo({"oggetto": "Sfratto per morosità", "tipo": "CIVILE"})
    assert proposta["codice"] == "030011"
