from pct.motore_preventivo import (
    CATALOGO,
    catalogo_fonti_tassonomia,
    catalogo_tassonomia_incompleto,
    catalogo_tassonomia_preventivi,
    redattore_preventivo_iniziale,
)
from pct.preventivi import GestionePreventivi, TipoVoce, VocePreventivo


def test_catalogo_wizard_espone_tassonomia_professionale_sulle_tipologie():
    lavoro = redattore_preventivo_iniziale("licenziamento")
    famiglia = redattore_preventivo_iniziale("separazione_giudiziale")
    ads = redattore_preventivo_iniziale("amministrazione_sostegno")
    ricorso_tar = redattore_preventivo_iniziale("ricorso_tar")
    passivo = redattore_preventivo_iniziale("accertamento_passivo")

    assert lavoro["area_tassonomica"] == "Giudiziale"
    assert lavoro["macro_area_tassonomica"] == "Diritto del Lavoro"
    assert lavoro["sottobranca_tassonomica"] == "Lavoro subordinato, licenziamenti e differenze retributive"

    assert famiglia["macro_area_tassonomica"] == "Diritto di Famiglia"
    assert famiglia["sottobranca_tassonomica"] == "Separazione, divorzio, minori e reclami"

    assert ads["area_tassonomica"] == "Volontaria Giurisdizione"
    assert ads["macro_area_tassonomica"] == "Protezione della persona"

    assert ricorso_tar["macro_area_tassonomica"] == "Giustizia Amministrativa"
    assert passivo["macro_area_tassonomica"] == "Crisi d'impresa e concorsuale"

    assert lavoro["tassonomia_sources"]
    assert any("Normattiva" in (row.get("authority") or "") or "Giustizia" in (row.get("authority") or "") for row in lavoro["tassonomia_sources"])


def test_catalogo_tassonomia_non_lascia_tipologie_scoperte():
    assert catalogo_tassonomia_incompleto() == []

    catalogo = catalogo_tassonomia_preventivi()
    totale = sum(
        sub["count"]
        for area in catalogo
        for macro in area["macros"]
        for sub in macro["subs"]
    )

    assert totale == len(CATALOGO)


def test_catalogo_fonti_tassonomia_traccia_fonti_istituzionali_aggiornate():
    fonti = catalogo_fonti_tassonomia()
    titles = {row["title"] for row in fonti}

    assert "Giustizia Amministrativa | Funzioni della Giustizia Amministrativa" in titles
    assert "L. 31 agosto 2022, n. 130" in titles
    assert "Ministero della Giustizia | Amministrazione di sostegno" in titles


def test_preventivo_persist_tassonomia_e_fonti(tmp_path):
    gp = GestionePreventivi(db_path=str(tmp_path / "preventivi.json"))
    preventivo = gp.crea_preventivo(
        id_cliente="cli-001",
        oggetto="Preventivo prova tassonomia",
        voci=[VocePreventivo(descrizione="Compenso", importo=100.0, tipo=TipoVoce.ONORARIO)],
        id_pratica="licenziamento",
        area_pratica="Civile",
        area_tassonomica="Giudiziale",
        macro_area_tassonomica="Diritto del Lavoro",
        sottobranca_tassonomica="Lavoro subordinato, licenziamenti e differenze retributive",
        tassonomia_codice="GIU_LAV_LAVORO",
        fonti_tassonomia=[
            {
                "title": "L. 31 dicembre 2012, n. 247",
                "article": "art. 13",
                "url": "https://www.gazzettaufficiale.it/eli/id/2013/01/18/13G00018/sg",
            }
        ],
    )

    gp_reload = GestionePreventivi(db_path=str(tmp_path / "preventivi.json"))
    loaded = gp_reload.get_preventivo(preventivo.id)

    assert loaded is not None
    assert loaded.area_tassonomica == "Giudiziale"
    assert loaded.macro_area_tassonomica == "Diritto del Lavoro"
    assert loaded.sottobranca_tassonomica == "Lavoro subordinato, licenziamenti e differenze retributive"
    assert loaded.tassonomia_codice == "GIU_LAV_LAVORO"
    assert loaded.fonti_tassonomia
