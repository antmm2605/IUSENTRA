from pct.motore_preventivo import (
    catalogo_riferimenti_normativi,
    catalogo_wizard,
    get_tipo_pratica,
    motore_calcola,
    redattore_preventivo_iniziale,
)
from pct.tariffario import Fase, Grado


def test_atto_citazione_ha_metadata_professionali_e_riferimenti():
    tp = get_tipo_pratica("atto_citazione")
    assert tp is not None
    assert tp.summary
    assert tp.when_to_use
    assert tp.motore_label == "Motore parametrico giudiziale civile"
    assert tp.redattore_label == "Redattore preventivo giudiziale civile"
    assert tp.esborsi_tipici
    titles = {ref["title"] for ref in tp.normative_references}
    assert "L. 31 dicembre 2012, n. 247" in titles
    assert "D.M. 10 marzo 2014, n. 55" in titles
    assert any("art. 163 c.p.c." in (ref.get("article") or "") for ref in tp.normative_references)


def test_catalogo_wizard_espone_fasi_e_checklist_serializzabili():
    catalogo = catalogo_wizard()
    assert "Stragiudiziale" in catalogo
    mediazione = next(item for item in catalogo["Stragiudiziale"] if item["id"] == "mediazione")
    assert mediazione["fasi_default_keys"] == ["attivazione", "rivitalizzazione", "conciliazione"]
    assert mediazione["checklist_iniziale"]
    assert any(ref["title"] == "D.Lgs. 4 marzo 2010, n. 28" for ref in mediazione["normative_references"])


def test_redattore_preventivo_iniziale_restituisce_scheda_pronta_per_wizard():
    scheda = redattore_preventivo_iniziale("negoziazione_assistita")
    assert scheda["id"] == "negoziazione_assistita"
    assert scheda["oggetto_template"].startswith("Preventivo professionale")
    assert "Informativa resa ai sensi dell'art. 13" in scheda["note_template"]
    assert any(ref["title"] == "D.L. 12 settembre 2014, n. 132" for ref in scheda["normative_references"])


def test_mediazione_riporta_anche_il_regolamento_spese_post_cartabia():
    scheda = redattore_preventivo_iniziale("mediazione")
    titles = {ref["title"] for ref in scheda["normative_references"]}
    assert "D.M. 24 ottobre 2023, n. 150" in titles
    assert "Ministero della Giustizia" in titles


def test_mediazione_e_negoziazione_espongono_variation_policy_adr_per_wizard_e_tariffario():
    mediazione = redattore_preventivo_iniziale("mediazione")
    negoziazione = redattore_preventivo_iniziale("negoziazione_assistita")

    assert "tab. a27" in mediazione["base_normativa"].lower()
    assert "tab. a27" in negoziazione["base_normativa"].lower()

    policy_mediazione = mediazione["variation_policy"]
    policy_negoziazione = negoziazione["variation_policy"]

    assert policy_mediazione["kind"] == "adr_pm50_con_accordo"
    assert policy_negoziazione["kind"] == "adr_pm50_con_accordo"
    assert policy_mediazione["range_pct"] == {"min": -50, "max": 50, "default": 0}
    assert policy_negoziazione["range_pct"] == {"min": -50, "max": 50, "default": 0}
    assert [row["key"] for row in policy_mediazione["phase_controls"]] == ["attivazione", "rivitalizzazione", "conciliazione"]
    assert [row["key"] for row in policy_negoziazione["phase_controls"]] == ["attivazione", "negoziazione", "conciliazione"]
    assert policy_mediazione["agreement_bonus"]["pct"] == 30
    assert policy_mediazione["agreement_bonus"]["phase_keys"] == ["attivazione", "rivitalizzazione"]
    assert policy_negoziazione["agreement_bonus"]["phase_keys"] == ["attivazione", "negoziazione"]
    assert any("art. 19" in ref.lower() for ref in policy_mediazione["references"])
    assert any("art. 20" in ref.lower() for ref in policy_negoziazione["references"])


def test_catalogo_include_tipologie_civili_e_stragiudiziali_aggiunte():
    catalogo = catalogo_wizard()
    civile_ids = {item["id"] for item in catalogo["Civile"]}
    stragiud_ids = {item["id"] for item in catalogo["Stragiudiziale"]}
    assert "controversia_lavoro" in civile_ids
    assert "previdenza" in civile_ids
    assert "appello_previdenza" in civile_ids
    assert "cassazione_previdenza" in civile_ids
    assert "cassazione_lavoro" in civile_ids
    assert "opposizione_atti_esecutivi" in civile_ids
    assert "sfratto_morosita" in civile_ids
    assert "risarcimento_danni" in civile_ids
    assert "sinistro_stradale_stragiudiziale" in stragiud_ids


def test_sfratto_morosita_espone_mediazione_civile_nello_stesso_wizard():
    scheda = redattore_preventivo_iniziale("sfratto_morosita")
    assert scheda["accessori_calcolo"]
    accessorio = scheda["accessori_calcolo"][0]
    assert accessorio["tipo_pratica_id"] == "mediazione"
    assert accessorio["default_checked"] is True
    assert any("locazione" in (ref.get("article") or "").lower() for ref in accessorio["normative_references"])


def test_esborsi_tipici_non_propongono_piu_marca_da_bollo_nel_wizard_preventivi():
    catalogo = catalogo_wizard()
    descrizioni = [
        voce["descrizione"]
        for items in catalogo.values()
        for item in items
        for voce in item.get("esborsi_tipici", [])
    ]
    assert all("Marca da bollo" not in descrizione for descrizione in descrizioni)


def test_catalogo_riferimenti_normativi_deduplica_e_traccia_tipologie():
    riferimenti = catalogo_riferimenti_normativi()
    dm55 = next(
        row
        for row in riferimenti
        if row["title"] == "D.M. 10 marzo 2014, n. 55" and row["article"] == "parametri forensi"
    )
    assert "Civile" in dm55["areas"]
    assert "decreto_ingiuntivo" in dm55["tipologie_ids"]
    assert dm55["motori"]


def test_atto_citazione_espone_mediazione_generale_opzionale():
    scheda = redattore_preventivo_iniziale("atto_citazione")
    accessorio = next(item for item in scheda["accessori_calcolo"] if item["id"] == "mediazione_generale")
    assert accessorio["tipo_pratica_id"] == "mediazione"
    assert accessorio["default_checked"] is False
    assert any(ref["title"] == "D.Lgs. 4 marzo 2010, n. 28" for ref in accessorio["normative_references"])


def test_catalogo_wizard_espone_gradi_specializzati_per_tariffario_e_preventivi():
    catalogo = catalogo_wizard()
    ricorso_tar = next(item for item in catalogo["Amministrativo"] if item["id"] == "ricorso_tar")
    cautelare_tar = next(item for item in catalogo["Amministrativo"] if item["id"] == "cautelare_sospensiva")
    cassazione_tributaria = next(item for item in catalogo["Tributario"] if item["id"] == "cassazione_tributaria")
    consulenza = next(item for item in catalogo["Stragiudiziale"] if item["id"] == "consulenza")

    assert ricorso_tar["grado_default"] == "TAR"
    assert cautelare_tar["grado_default"] == "TAR"
    assert cassazione_tributaria["grado_default"] == "Corte di Cassazione"
    assert consulenza["grado_default"] == "Fuori giudizio"


def test_catalogo_wizard_espone_regole_tariffarie_e_gradi_consentiti():
    scheda = redattore_preventivo_iniziale("atto_citazione")

    assert scheda["regole_tariffarie"]
    assert scheda["regola_tariffaria_default"] == "civile_cognizione_primo_grado"
    assert "Tribunale" in scheda["gradi_consentiti"]
    assert "Giudice di Pace" in scheda["gradi_consentiti"]


def test_motore_preventivo_usa_la_complessita_come_driver_del_livello_compenso():
    basso = motore_calcola(
        "atto_citazione",
        valore_controversia=10000,
        grado=Grado.TRIBUNALE,
        complessita="bassa",
    )
    medio = motore_calcola(
        "atto_citazione",
        valore_controversia=10000,
        grado=Grado.TRIBUNALE,
        complessita="media",
    )
    alto = motore_calcola(
        "atto_citazione",
        valore_controversia=10000,
        grado=Grado.TRIBUNALE,
        complessita="alta",
    )

    assert basso.livello_compenso == "minimo"
    assert medio.livello_compenso == "base"
    assert alto.livello_compenso == "massimo"
    assert basso.onorario_selezionato < medio.onorario_selezionato < alto.onorario_selezionato


def test_motore_preventivo_permette_fasi_tabellari_senza_voce_unica_monitorio():
    fasi = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE]
    compenso_unico = motore_calcola(
        "decreto_ingiuntivo",
        valore_controversia=10000,
        grado=Grado.TRIBUNALE,
        regola_tariffaria="civile_monitorio",
        fasi=fasi,
        includi_spese_generali=False,
    )
    per_fasi = motore_calcola(
        "decreto_ingiuntivo",
        valore_controversia=10000,
        grado=Grado.TRIBUNALE,
        regola_tariffaria="civile_monitorio",
        profile_code_override="",
        fasi=fasi,
        includi_spese_generali=False,
    )

    assert "Compenso unico" in compenso_unico.calcolo_dm55.dettaglio
    assert set(per_fasi.calcolo_dm55.dettaglio) == {"Studio", "Introduttiva", "Decisionale"}
    assert per_fasi.onorario_base > compenso_unico.onorario_base


def test_motore_preventivo_ripartisce_compenso_unico_sulle_fasi_preventivate():
    fasi = [Fase.STUDIO, Fase.INTRODUTTIVA, Fase.DECISIONALE]
    compenso_unico = motore_calcola(
        "amministrazione_sostegno",
        valore_controversia=0,
        grado=Grado.GIUDICE_TUTELARE,
        regola_tariffaria="volontaria_amministrazione_sostegno",
        fasi=fasi,
        includi_spese_generali=False,
    )
    tutte_le_fasi = motore_calcola(
        "amministrazione_sostegno",
        valore_controversia=0,
        grado=Grado.GIUDICE_TUTELARE,
        regola_tariffaria="volontaria_amministrazione_sostegno",
        profile_code_override="",
        fasi=fasi,
        includi_spese_generali=False,
    )
    solo_studio = motore_calcola(
        "amministrazione_sostegno",
        valore_controversia=0,
        grado=Grado.GIUDICE_TUTELARE,
        regola_tariffaria="volontaria_amministrazione_sostegno",
        profile_code_override="",
        fasi=[Fase.STUDIO],
        includi_spese_generali=False,
    )

    assert set(compenso_unico.calcolo_dm55.dettaglio) == {"Compenso unico"}
    assert set(tutte_le_fasi.calcolo_dm55.dettaglio) == {"Studio", "Introduttiva", "Decisionale"}
    assert round(tutte_le_fasi.onorario_base, 2) == round(compenso_unico.onorario_base, 2)
    assert 0 < solo_studio.onorario_base < tutte_le_fasi.onorario_base
    assert round(solo_studio.onorario_base, 2) == round(tutte_le_fasi.onorario_base / 3, 2)
    assert "ripartito in quote operative" in solo_studio.calcolo_dm55.note


def test_appello_civile_espone_base_normativa_sdoppiata_per_competenza():
    scheda = redattore_preventivo_iniziale("appello_civile")
    regole = {row["rule_code"]: row for row in scheda["regole_tariffarie"]}

    assert "art. 341 c.p.c." in scheda["base_normativa"].lower()
    assert "tab. a2" in scheda["base_normativa"].lower()
    assert "tab. a12" in scheda["base_normativa"].lower()
    assert set(regole) >= {"civile_appello_da_gdp", "civile_appello"}


def test_default_grado_civile_lavoro_e_previdenza_sono_allineati_al_rito():
    sfratto = redattore_preventivo_iniziale("sfratto_morosita")
    lavoro = redattore_preventivo_iniziale("controversia_lavoro")
    licenziamento = redattore_preventivo_iniziale("licenziamento")
    previdenza = redattore_preventivo_iniziale("previdenza")
    appello_previdenza = redattore_preventivo_iniziale("appello_previdenza")
    cassazione_previdenza = redattore_preventivo_iniziale("cassazione_previdenza")
    cassazione_lavoro = redattore_preventivo_iniziale("cassazione_lavoro")
    danni = redattore_preventivo_iniziale("risarcimento_danni")

    assert sfratto["grado_default"] == "Tribunale"
    assert lavoro["grado_default"] == "Tribunale"
    assert licenziamento["grado_default"] == "Tribunale"
    assert previdenza["grado_default"] == "Tribunale"
    assert appello_previdenza["grado_default"] == "Corte d'Appello"
    assert cassazione_previdenza["grado_default"] == "Corte di Cassazione"
    assert cassazione_lavoro["grado_default"] == "Corte di Cassazione"
    assert danni["grado_default"] == "Tribunale"


def test_lavoro_e_previdenza_non_mischiano_piu_gradi_diversi_nella_stessa_tipologia():
    appello_lavoro = redattore_preventivo_iniziale("appello_lavoro")
    cassazione_lavoro = redattore_preventivo_iniziale("cassazione_lavoro")
    previdenza = redattore_preventivo_iniziale("previdenza")
    appello_previdenza = redattore_preventivo_iniziale("appello_previdenza")
    cassazione_previdenza = redattore_preventivo_iniziale("cassazione_previdenza")

    assert {row["rule_code"] for row in appello_lavoro["regole_tariffarie"]} == {"lavoro_appello"}
    assert {row["rule_code"] for row in cassazione_lavoro["regole_tariffarie"]} == {"lavoro_cassazione"}
    assert {row["rule_code"] for row in previdenza["regole_tariffarie"]} == {"previdenza_giudiziale"}
    assert {row["rule_code"] for row in appello_previdenza["regole_tariffarie"]} == {"previdenza_appello"}
    assert {row["rule_code"] for row in cassazione_previdenza["regole_tariffarie"]} == {"previdenza_cassazione"}


def test_esecuzioni_distinguono_opposizione_all_esecuzione_e_agli_atti():
    opposizione_esecuzione = redattore_preventivo_iniziale("opposizione_esecutiva")
    opposizione_atti = redattore_preventivo_iniziale("opposizione_atti_esecutivi")

    assert opposizione_esecuzione["label"] == "Opposizione all'esecuzione"
    assert "artt. 615 e 619 c.p.c." in opposizione_esecuzione["base_normativa"]
    assert {row["rule_code"] for row in opposizione_esecuzione["regole_tariffarie"]} == {"civile_opposizione_esecutiva"}

    assert opposizione_atti["label"] == "Opposizione agli atti esecutivi"
    assert "art. 617 c.p.c." in opposizione_atti["base_normativa"]
    assert {row["rule_code"] for row in opposizione_atti["regole_tariffarie"]} == {"civile_opposizione_atti_esecutivi"}


def test_famiglia_e_volontaria_separano_consensuale_giudiziale_camerale_e_minori():
    separazione_consensuale = redattore_preventivo_iniziale("separazione_consensuale")
    separazione_giudiziale = redattore_preventivo_iniziale("separazione_giudiziale")
    camerale = redattore_preventivo_iniziale("procedimenti_famiglia")
    minori = redattore_preventivo_iniziale("procedimenti_minori")

    assert separazione_consensuale["materia"] == "Volontaria giurisdizione"
    assert "tab. a7" in separazione_consensuale["base_normativa"].lower()
    assert {row["rule_code"] for row in separazione_consensuale["regole_tariffarie"]} == {"famiglia_separazione_consensuale"}

    assert separazione_giudiziale["materia"] == "Civile di cognizione"
    assert "tab. a2" in separazione_giudiziale["base_normativa"].lower()
    assert {row["rule_code"] for row in separazione_giudiziale["regole_tariffarie"]} == {"famiglia_separazione_giudiziale"}

    assert camerale["label"] == "Procedimento camerale di famiglia"
    assert camerale["materia"] == "Volontaria giurisdizione"
    assert {row["rule_code"] for row in camerale["regole_tariffarie"]} == {"famiglia_camerale"}

    assert minori["label"] == "Procedimenti relativi ai minori"
    assert minori["materia"] == "Civile di cognizione"
    assert {row["rule_code"] for row in minori["regole_tariffarie"]} == {"famiglia_procedimenti_minori"}
    assert any(ref["title"] == "D.Lgs. 10 ottobre 2022, n. 149" for ref in minori["normative_references"])


def test_famiglia_aggiunge_modifica_condizioni_responsabilita_reclamo_appello_e_ads():
    modifica = redattore_preventivo_iniziale("modifica_condizioni_famiglia")
    responsabilita = redattore_preventivo_iniziale("responsabilita_genitoriale")
    reclamo = redattore_preventivo_iniziale("reclamo_famiglia_minori")
    appello = redattore_preventivo_iniziale("appello_famiglia_minori")
    ads = redattore_preventivo_iniziale("amministrazione_sostegno")

    assert modifica["grado_default"] == "Tribunale"
    assert "473-bis.29" in modifica["base_normativa"]
    assert {row["rule_code"] for row in modifica["regole_tariffarie"]} == {"famiglia_modifica_condizioni"}

    assert responsabilita["materia"] == "Civile di cognizione"
    assert "337-bis" in responsabilita["base_normativa"]
    assert {row["rule_code"] for row in responsabilita["regole_tariffarie"]} == {"famiglia_responsabilita_genitoriale"}

    assert reclamo["grado_default"] == "Corte d'Appello"
    assert "473-bis.24" in reclamo["base_normativa"]
    assert {row["rule_code"] for row in reclamo["regole_tariffarie"]} == {"famiglia_reclamo"}

    assert appello["grado_default"] == "Corte d'Appello"
    assert "473-bis.30" in appello["base_normativa"]
    assert {row["rule_code"] for row in appello["regole_tariffarie"]} == {"famiglia_appello_minori"}

    assert ads["materia"] == "Volontaria giurisdizione"
    assert ads["grado_default"] == "Giudice tutelare"
    assert {row["rule_code"] for row in ads["regole_tariffarie"]} == {"volontaria_amministrazione_sostegno"}
    assert any(ref["article"] == "art. 404" for ref in ads["normative_references"])


def test_tutelare_estende_nomina_modifica_tutela_e_reclamo_con_gradi_corretti():
    nomina_ads = redattore_preventivo_iniziale("nomina_amministratore_sostegno")
    modifica_ads = redattore_preventivo_iniziale("modifica_revoca_ads")
    tutela = redattore_preventivo_iniziale("tutela_curatela")
    reclamo_gt = redattore_preventivo_iniziale("reclamo_giudice_tutelare")

    assert nomina_ads["grado_default"] == "Giudice tutelare"
    assert "artt. 404 e 405" in nomina_ads["base_normativa"]
    assert {row["rule_code"] for row in nomina_ads["regole_tariffarie"]} == {"volontaria_nomina_ads"}

    assert modifica_ads["grado_default"] == "Giudice tutelare"
    assert "art. 413" in modifica_ads["base_normativa"]
    assert {row["rule_code"] for row in modifica_ads["regole_tariffarie"]} == {"volontaria_modifica_ads"}

    assert tutela["materia"] == "Volontaria giurisdizione"
    assert "343" in tutela["base_normativa"]
    assert {row["rule_code"] for row in tutela["regole_tariffarie"]} == {"volontaria_tutela_curatela"}

    assert reclamo_gt["grado_default"] == "Tribunale"
    assert "art. 739" in reclamo_gt["base_normativa"]
    assert {row["rule_code"] for row in reclamo_gt["regole_tariffarie"]} == {"volontaria_reclamo_giudice_tutelare"}
    assert any(ref["article"] == "art. 739" for ref in reclamo_gt["normative_references"])


def test_catalogo_wizard_estende_tabelle_ufficiali_dm147_nel_preventivo_guidato():
    catalogo = catalogo_wizard()
    civile_ids = {item["id"] for item in catalogo["Civile"]}
    penale_ids = {item["id"] for item in catalogo["Penale"]}
    speciali_ids = {item["id"] for item in catalogo["Speciali"]}

    assert {"istruzione_preventiva", "cautelare_civile"} <= civile_ids
    assert {"giudice_pace_penale", "indagini_difensive", "convalida_arresto", "misure_cautelari_penali", "sorveglianza_penale"} <= penale_ids
    assert {"giudizio_corte_conti", "giurisdizioni_superiori", "iscrizione_ipotecaria_tavolare", "apertura_liquidazione_giudiziale", "accertamento_passivo"} <= speciali_ids


def test_nuove_tipologie_tariffarie_espongono_regole_gradi_e_fonti_specialistiche():
    istruzione = redattore_preventivo_iniziale("istruzione_preventiva")
    corte_conti = redattore_preventivo_iniziale("giudizio_corte_conti")
    giurisdizioni_superiori = redattore_preventivo_iniziale("giurisdizioni_superiori")
    passivo = redattore_preventivo_iniziale("accertamento_passivo")
    cautelari_penali = redattore_preventivo_iniziale("misure_cautelari_penali")
    sorveglianza = redattore_preventivo_iniziale("sorveglianza_penale")

    assert istruzione["grado_default"] == "Giudice competente"
    assert {row["rule_code"] for row in istruzione["regole_tariffarie"]} == {"civile_istruzione_preventiva"}
    assert any("692" in (ref.get("article") or "") for ref in istruzione["normative_references"])

    assert corte_conti["materia"] == "Contabile / Corte dei Conti"
    assert corte_conti["grado_default"] == "Corte dei Conti"
    assert {row["rule_code"] for row in corte_conti["regole_tariffarie"]} == {"contabile_corte_conti"}
    assert any(ref["title"] == "D.Lgs. 26 agosto 2016, n. 174" for ref in corte_conti["normative_references"])

    assert giurisdizioni_superiori["materia"] == "Giurisdizioni superiori / europee"
    assert giurisdizioni_superiori["grado_default"] == "Corte costituzionale"
    assert {row["rule_code"] for row in giurisdizioni_superiori["regole_tariffarie"]} == {
        "giurisdizioni_superiori_corte_costituzionale",
        "giurisdizioni_superiori_corte_edu",
        "giurisdizioni_superiori_corte_giustizia_ue",
    }

    assert passivo["materia"] == "Crisi d'impresa / concorsuale"
    assert passivo["grado_default"] == "Tribunale concorsuale"
    assert {row["rule_code"] for row in passivo["regole_tariffarie"]} == {"crisi_impresa_passivo"}
    assert any(ref["title"] == "D.Lgs. 12 gennaio 2019, n. 14" for ref in passivo["normative_references"])

    assert {row["rule_code"] for row in cautelari_penali["regole_tariffarie"]} == {"penale_cautelari_personali", "penale_cautelari_reali"}
    assert any("272" in (ref.get("article") or "") for ref in cautelari_penali["normative_references"])

    assert {row["rule_code"] for row in sorveglianza["regole_tariffarie"]} == {"penale_sorveglianza_tribunale", "penale_sorveglianza_magistrato"}
    assert any(ref["title"] == "L. 26 luglio 1975, n. 354" for ref in sorveglianza["normative_references"])
