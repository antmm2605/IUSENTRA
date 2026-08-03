from pathlib import Path

from werkzeug.datastructures import MultiDict

from pct.auth import GestioneUtenti, RuoloUtente
from pct.economico_context import carica_log_calcolo
from pct.fascicoli import Fascicolo, TipoFascicolo
from pct.motore_preventivo import catalogo_wizard
from web.app import create_app
from web.blueprints.preventivi import (
    _area_pratica_da_fascicolo,
    _contesto_fascicolo_wizard,
    _contesto_log_wizard_da_form,
)
from web.services.react_preventivo_wizard_bridge import build_react_preventivo_wizard_calculation_payload
from web.helpers import get_preventivi

from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def _mk_fascicolo(tipo: TipoFascicolo, **overrides) -> Fascicolo:
    data = {
        "id": "fasc-001",
        "numero": "2026/001",
        "titolo": "Vendita di cose immobili",
        "tipo": tipo,
        "id_cliente": "cli-001",
    }
    data.update(overrides)
    return Fascicolo(**data)


def test_area_pratica_da_fascicolo_mappa_tipo_su_macro_area_wizard():
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.CIVILE)) == "Civile"
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.LAVORO)) == "Civile"
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.STRAGIUDIZIALE)) == "Stragiudiziale"
    assert _area_pratica_da_fascicolo(_mk_fascicolo(TipoFascicolo.PENALE)) == "Penale"


def test_contesto_fascicolo_wizard_espone_rg_label_e_area_proposta():
    fascicolo = _mk_fascicolo(
        TipoFascicolo.CIVILE,
        oggetto="Vendita di cose immobili",
        numero_rg="1025",
        anno_rg=2024,
        tribunale="Tribunale di Torino",
    )

    context = _contesto_fascicolo_wizard(fascicolo)

    assert context["rg_label"] == "RG 1025/2024"
    assert context["context_label"] == "RG 1025/2024 — Vendita di cose immobili"
    assert context["display_label"] == "RG 1025/2024 — Vendita di cose immobili"
    assert context["area_pratica"] == "Civile"
    assert context["tribunale"] == "Tribunale di Torino"


def test_contesto_fascicolo_wizard_usa_titolo_quando_oggetto_manca():
    fascicolo = _mk_fascicolo(TipoFascicolo.TRIBUTARIO, titolo="Avviso di accertamento IMU")

    context = _contesto_fascicolo_wizard(fascicolo)

    assert context["context_label"] == "Avviso di accertamento IMU"
    assert context["area_pratica"] == "Tributario"


def test_contesto_log_wizard_da_form_conserva_tassonomia_fonti_e_flag_booleani():
    form = MultiDict(
        {
            "oggetto": "Licenziamento disciplinare",
            "id_pratica": "licenziamento",
            "area_pratica": "Civile",
            "area_tassonomica": "Giudiziale",
            "macro_area_tassonomica": "Diritto del Lavoro",
            "sottobranca_tassonomica": "Lavoro subordinato, licenziamenti e differenze retributive",
            "tassonomia_codice": "GIU_LAV_LAVORO",
            "procedura_operativa_codice": "PROC_LIC_IMP_001",
            "procedura_operativa_nome": "Impugnazione licenziamento individuale",
            "subbranch_operativa_codice": "SB_LAVORO_LICENZIAMENTI",
            "workflow_operativo_codice": "WF_CONTENZIOSO_LAVORO",
            "copertura_operativa": "FULL",
            "canale_operativo": "TRIBUNALE",
            "registro_operativo": "LAVORO",
            "tipo_compenso": "Per fasi processuali (D.M. 55/2014)",
            "tipo_procedimento": "Rito lavoro",
            "grado_sede": "Tribunale",
            "regola_tariffaria": "lavoro_subordinato",
            "complessita": "media",
            "valore_controversia": "15000",
            "bonus_telematico": "0",
            "spese_generali": "0",
            "perc_spese_generali": "15",
            "anticipazioni_art15": "43,50",
            "adr_accordo": "0",
            "fonti_tassonomia_json": (
                '[{"title":"Codice di procedura civile","article":"rito lavoro","url":"https://www.normattiva.it/"},'
                '{"title":"Ministero del Lavoro","article":"licenziamenti","url":"https://www.lavoro.gov.it/"}]'
            ),
            "classificazioni_tassonomiche_json": (
                '[{"uid":"row-1","area_tassonomica":"Giudiziale","macro_area_tassonomica":"Diritto del Lavoro",'
                '"sottobranca_tassonomica":"Licenziamenti","tipologia_pratica_id":"impugnazione_licenziamento",'
                '"tipologia_pratica_label":"Impugnazione licenziamento"}]'
            ),
        }
    )

    payload = carica_log_calcolo(_contesto_log_wizard_da_form(form))

    assert payload["area_tassonomica"] == "Giudiziale"
    assert payload["macro_area_tassonomica"] == "Diritto del Lavoro"
    assert payload["sottobranca_tassonomica"] == "Lavoro subordinato, licenziamenti e differenze retributive"
    assert payload["tassonomia_codice"] == "GIU_LAV_LAVORO"
    assert payload["procedura_operativa_codice"] == "PROC_LIC_IMP_001"
    assert payload["procedura_operativa_nome"] == "Impugnazione del licenziamento individuale"
    assert payload["workflow_operativo_codice"].startswith("WF_")
    assert payload["copertura_operativa"]
    assert payload["canale_operativo"]
    assert payload["registro_operativo"]
    assert payload["bonus_telematico"] is False
    assert payload["spese_generali"] is False
    assert payload["adr"]["accordo"] is False
    assert payload["classificazioni_tassonomiche"][0]["tipologia_pratica_id"] == "impugnazione_licenziamento"
    assert payload["riferimenti_tassonomia"] == [
        "Codice di procedura civile — rito lavoro",
        "Ministero del Lavoro — licenziamenti",
    ]


def test_catalogo_wizard_espone_inquadramento_operativo_per_le_tipologie_mappate():
    rows = [
        item
        for items in catalogo_wizard().values()
        for item in items
        if item.get("procedura_operativa_codice")
    ]

    assert rows, "Il catalogo del wizard deve esporre almeno una procedura operativa mappata"
    sample = rows[0]
    assert sample["procedura_operativa_nome"]
    assert sample["workflow_operativo_codice"]
    assert sample["canale_operativo"]
    assert sample["registro_operativo"]


def test_template_dettaglio_preventivo_espone_classificazione_tassonomica_e_fonti():
    template = Path("web/templates/preventivi/dettaglio_preventivo.html").read_text(encoding="utf-8")

    assert "Classificazione tassonomica" in template
    assert "Inquadramento operativo" in template
    assert "Procedura operativa" in template
    assert "Agganci di prodotto" in template
    assert "p.area_tassonomica" in template
    assert "p.macro_area_tassonomica" in template
    assert "p.sottobranca_tassonomica" in template
    assert "p.fonti_tassonomia" in template


def test_template_wizard_espone_classificazione_operativa_visibile():
    template = Path("web/templates/preventivi/wizard.html").read_text(encoding="utf-8")

    assert "procedura_operativa_codice" in template
    assert "classificazioni_tassonomiche_json" in template
    assert "Classificazione operativa" in template
    assert "Classificazioni tassonomiche aggiuntive" in template
    assert "Aggiungi classificazione" in template
    assert "Procedura / servizio" in template
    assert "Tassonomia tecnica di supporto" in template
    assert "Inquadramento operativo" in template
    assert "Agganci di prodotto" in template
    assert "workflow_operativo_codice" in template
    assert "wizardInlineStatus" in template
    assert "scheduleRecalcoloPreventivo" in template
    assert "Calcola e aggiorna la bozza" in template
    assert "Costi organismo mediazione D.M. 150/2023" in template
    assert "Includi costi organismo nel preventivo" in template
    assert "+20% art. 31, comma 3" in template


def test_template_wizard_non_mischia_nullish_e_or_nelle_espressioni_js():
    template = Path("web/templates/preventivi/wizard.html").read_text(encoding="utf-8")

    assert "data.totale_bozza ?? data.totale || 0" not in template
    assert "data.compenso_bozza ?? data.totale_base ?? data.onorario_base ?? data.onorario_selezionato || 0" not in template


def test_template_wizard_spese_generali_voce_separata_non_art15():
    template = Path("web/templates/preventivi/wizard.html").read_text(encoding="utf-8")

    assert "function syncSpeseGeneraliRow" in template
    assert "Spese generali ${percentuale}" in template
    assert "upsertVocePerRuolo(role, speseGeneraliLabel(data, suffix), importo, 'Spesa forfettaria')" in template
    assert "syncSpeseGeneraliRow('spese-generali-main', data)" in template
    assert "setAnticipazioniExtra('spese-generali-main', firstDefined(data.spese_generali_bozza" not in template


def test_template_wizard_allinea_clausola_controversie_al_form_classico():
    template = Path("web/templates/preventivi/wizard.html").read_text(encoding="utf-8")

    assert "Clausola per la risoluzione delle controversie" in template
    assert template.count("Includi clausola per la risoluzione delle controversie") == 1
    assert "Tutela cliente / consumatore" in template
    assert "Testo da adattare" in template
    assert "Ripristina testo standard" in template
    assert "Fonte modello: nessuna fonte impostata" in template
    assert "ripristinaClausolaControversie" in template
    assert "chkClausolaContAttiva" not in template
    assert "Fac-simile conferimento incarico + Studio Cataldi / Primavera Forense" not in template


def test_template_wizard_espone_compenso_unico_come_flag_calcolabile():
    template = Path("web/templates/preventivi/wizard.html").read_text(encoding="utf-8")

    assert "Fasi accorpate dal motore" not in template
    assert "compenso_unico: 'Compenso unico'" in template
    assert "availablePhaseKeysForPractice" in template
    assert "return ['compenso_unico']" not in template
    assert "defaultPhaseSet.add('compenso_unico')" not in template
    assert "le fasi operative restano visibili" in template
    assert "ripartisce in modo operativo l'importo unico" in template
    assert "Fasi tabellari, compenso unico, complessita stimata, spese generali e bonus." in template
    assert "Include anche il flag compenso unico quando previsto." in template
    assert "Il motore applica anche CPA, IVA, anticipazioni ex art. 15 e compenso orario." in template
    assert "selectedRegolaTariffariaForPractice" in template
    assert "defaultCalculationPhaseKeysForPractice" in template
    assert "phaseInputs.length) return checked" in template


def test_calcolo_wizard_allinea_contributo_unificato_al_valore_della_pratica():
    payload = build_react_preventivo_wizard_calculation_payload(
        {
            "id_pratica": "atto_citazione",
            "valore": "10000",
            "grado": "Tribunale",
            "regola_tariffaria": "civile_cognizione_primo_grado",
            "complessita": "media",
            "fasi": ["studio", "introduttiva", "istruttoria", "decisionale"],
            "spese_generali": False,
            "applica_cpa": False,
            "applica_iva": False,
            "esborsi": ["atto_citazione:0"],
        }
    )

    assert payload["ok"] is True
    assert payload["profile"]["esborsi_tipici"][0]["descrizione"] == "Contributo Unificato"
    assert payload["profile"]["esborsi_tipici"][0]["importo"] == 237.0
    contributo = next(row for row in payload["rows"] if row["id"] == "esborso_atto_citazione:0")
    assert contributo["descrizione"] == "Contributo Unificato"
    assert contributo["importo"] == 237.0


def _crea_admin(app) -> None:
    with app.app_context():
        gestore = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
            bootstrap_admin_password=app.config["BOOTSTRAP_ADMIN_PASSWORD"],
            bootstrap_admin_credentials_path=app.config["BOOTSTRAP_ADMIN_CREDENTIALS_PATH"],
        )
        if not any(user.username == "operatore" for user in gestore.tutti()):
            gestore.crea(
                username="operatore",
                password="Operatore123!",
                ruolo=RuoloUtente.AMMINISTRATORE,
                email="operatore@example.it",
                nome_completo="Operatore Preventivi",
                must_change_password=False,
            )


def _login(client) -> None:
    response = client.post(
        "/login",
        data={"username": "operatore", "password": "Operatore123!"},
        follow_redirects=True,
    )
    assert response.status_code == 200


def test_ajax_cliente_rapido_crea_subito_l_anagrafica_minima(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/preventivi/ajax/cliente-rapido",
            data={
                "cliente_rapido_tipo": "PERSONA_FISICA",
                "cliente_rapido_nome": "Mario",
                "cliente_rapido_cognome": "Rossi",
                "cliente_rapido_codice_fiscale": "RSSMRA80A01H501U",
                "avvocato_referente": "Avv. Test",
            },
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["id_cliente"]
    assert "Rossi" in payload["label"]


def test_wizard_calcola_rispetta_fasi_e_spese_generali(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        solo_studio = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "ricorso_tributario",
                "valore": "10000",
                "grado": "CGT di primo grado",
                "complessita": "media",
                "fasi": "studio",
                "spese_generali": "0",
            },
        )
        tutte_fasi = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "ricorso_tributario",
                "valore": "10000",
                "grado": "CGT di primo grado",
                "complessita": "media",
                "fasi": "studio,introduttiva,istruttoria,decisionale",
                "spese_generali": "0",
            },
        )
        con_spese = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "ricorso_tributario",
                "valore": "10000",
                "grado": "CGT di primo grado",
                "complessita": "media",
                "fasi": "studio,introduttiva,istruttoria,decisionale",
                "spese_generali": "1",
                "perc_spese_generali": "15",
            },
        )

    payload_solo_studio = solo_studio.get_json()
    payload_tutte_fasi = tutte_fasi.get_json()
    payload_con_spese = con_spese.get_json()

    assert solo_studio.status_code == 200
    assert tutte_fasi.status_code == 200
    assert con_spese.status_code == 200
    assert payload_tutte_fasi["onorario_base"] > payload_solo_studio["onorario_base"]
    assert payload_tutte_fasi["spese_generali"] == 0
    assert payload_con_spese["spese_generali"] > 0
    assert payload_con_spese["totale"] > payload_tutte_fasi["totale"]


def test_wizard_calcola_compenso_unico_rispetta_flag_attivo_disattivo(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        flag_attivo = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "decreto_ingiuntivo",
                "valore": "10000",
                "grado": "Tribunale",
                "regola_tariffaria": "civile_monitorio",
                "complessita": "media",
                "fasi": "studio,introduttiva,decisionale,compenso_unico",
                "spese_generali": "0",
            },
        )
        flag_disattivo = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "decreto_ingiuntivo",
                "valore": "10000",
                "grado": "Tribunale",
                "regola_tariffaria": "civile_monitorio",
                "complessita": "media",
                "fasi": "studio,introduttiva,decisionale",
                "spese_generali": "0",
            },
        )
        tutto_disattivo = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "decreto_ingiuntivo",
                "valore": "10000",
                "grado": "Tribunale",
                "regola_tariffaria": "civile_monitorio",
                "complessita": "media",
                "fasi": "",
                "spese_generali": "0",
            },
        )

    payload_attivo = flag_attivo.get_json()
    payload_disattivo = flag_disattivo.get_json()
    payload_tutto_disattivo = tutto_disattivo.get_json()

    assert flag_attivo.status_code == 200
    assert flag_disattivo.status_code == 200
    assert tutto_disattivo.status_code == 200
    assert payload_attivo["onorario_base"] > 0
    assert "Compenso unico" in payload_attivo["fasi"]
    assert payload_disattivo["onorario_base"] > 0
    assert "Compenso unico" not in payload_disattivo["fasi"]
    assert set(payload_disattivo["fasi"]) == {"Studio", "Introduttiva", "Decisionale"}
    assert payload_disattivo["onorario_base"] > payload_attivo["onorario_base"]
    assert payload_tutto_disattivo["onorario_base"] == 0
    assert payload_tutto_disattivo["fasi"] == {}


def test_wizard_calcola_compenso_unico_e_fasi_rispettano_complessita(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    expected_unico = {
        "bassa": ("minimo", 685.0),
        "media": ("base", 1370.0),
        "alta": ("massimo", 2055.0),
    }
    expected_fasi = {
        "bassa": ("minimo", 1698.5),
        "media": ("base", 3397.0),
        "alta": ("massimo", 5095.5),
    }

    with app.test_client() as client:
        _login(client)
        payloads_unico = {}
        payloads_fasi = {}
        for complessita in ("bassa", "media", "alta"):
            response_unico = client.get(
                "/preventivi/wizard/calcola",
                query_string={
                    "id_pratica": "decreto_ingiuntivo",
                    "valore": "10000",
                    "grado": "Tribunale",
                    "regola_tariffaria": "civile_monitorio",
                    "complessita": complessita,
                    "fasi": "studio,introduttiva,decisionale,compenso_unico",
                    "spese_generali": "0",
                    "applica_cpa": "0",
                    "applica_iva": "0",
                },
            )
            response_fasi = client.get(
                "/preventivi/wizard/calcola",
                query_string={
                    "id_pratica": "decreto_ingiuntivo",
                    "valore": "10000",
                    "grado": "Tribunale",
                    "regola_tariffaria": "civile_monitorio",
                    "complessita": complessita,
                    "fasi": "studio,introduttiva,decisionale",
                    "spese_generali": "0",
                    "applica_cpa": "0",
                    "applica_iva": "0",
                },
            )
            assert response_unico.status_code == 200
            assert response_fasi.status_code == 200
            payloads_unico[complessita] = response_unico.get_json()
            payloads_fasi[complessita] = response_fasi.get_json()

    for complessita, (livello, importo) in expected_unico.items():
        assert payloads_unico[complessita]["livello_compenso"] == livello
        assert payloads_unico[complessita]["onorario_base"] == importo
        assert payloads_unico[complessita]["compenso_bozza"] == importo
        assert payloads_unico[complessita]["totale_bozza"] == importo
        assert set(payloads_unico[complessita]["fasi"]) == {"Compenso unico"}

    for complessita, (livello, importo) in expected_fasi.items():
        assert payloads_fasi[complessita]["livello_compenso"] == livello
        assert payloads_fasi[complessita]["onorario_base"] == importo
        assert payloads_fasi[complessita]["compenso_bozza"] == importo
        assert payloads_fasi[complessita]["totale_bozza"] == importo
        assert set(payloads_fasi[complessita]["fasi"]) == {"Studio", "Introduttiva", "Decisionale"}

    assert payloads_unico["bassa"]["onorario_base"] < payloads_unico["media"]["onorario_base"]
    assert payloads_unico["media"]["onorario_base"] < payloads_unico["alta"]["onorario_base"]
    assert payloads_fasi["bassa"]["onorario_base"] < payloads_fasi["media"]["onorario_base"]
    assert payloads_fasi["media"]["onorario_base"] < payloads_fasi["alta"]["onorario_base"]


def test_wizard_calcola_ignora_regola_non_ammissibile_per_pratica_target(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "mediazione",
                "valore": "10000",
                "grado": "Procedura ADR",
                "regola_tariffaria": "civile_monitorio",
                "complessita": "media",
                "fasi": "attivazione,rivitalizzazione,conciliazione",
                "spese_generali": "0",
            },
        )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["onorario_base"] > 0
    assert "Compenso unico" not in payload["fasi"]
    assert set(payload["fasi"]) == {
        "Fase di attivazione",
        "Fase di rivitalizzazione",
        "Fase di conciliazione",
    }


def test_wizard_calcola_sincronizza_complessita_con_colonne_tariffario_gdp(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    expected = {
        "bassa": ("minimo", 632.5, 94.88, 727.38),
        "media": ("base", 1265.0, 189.75, 1454.75),
        "alta": ("massimo", 1897.5, 284.62, 2182.12),
    }

    with app.test_client() as client:
        _login(client)
        payloads = {}
        for complessita in expected:
            response = client.get(
                "/preventivi/wizard/calcola",
                query_string={
                    "id_pratica": "atto_citazione",
                    "valore": "5000",
                    "grado": "Giudice di Pace",
                    "regola_tariffaria": "civile_gdp",
                    "complessita": complessita,
                    "fasi": "studio,introduttiva,istruttoria,decisionale",
                    "spese_generali": "1",
                    "perc_spese_generali": "15",
                    "applica_cpa": "0",
                    "applica_iva": "0",
                },
            )
            assert response.status_code == 200
            payloads[complessita] = response.get_json()

    for complessita, (livello, subtotale, spese_generali, totale_compenso) in expected.items():
        payload = payloads[complessita]
        assert payload["livello_compenso"] == livello
        assert payload["totale_minimo"] == 632.5
        assert payload["totale_base"] == 1265.0
        assert payload["totale_massimo"] == 1897.5
        assert payload["spese_generali"] == spese_generali
        assert payload["totale_con_spese"] == totale_compenso
        assert payload["onorario_base"] == totale_compenso
        assert payload["compenso_bozza"] == subtotale
        assert payload["imponibile_bozza"] == totale_compenso
        assert payload["totale_bozza"] == totale_compenso
        assert payload["totale"] == totale_compenso
        assert payload["anticipazioni_bozza"] == 0
        assert payload["spese_generali_bozza"] == spese_generali
        assert payload["spese_generali_in_compenso_bozza"] is False
        colonna = {"minimo": "min", "base": "base", "massimo": "max"}[livello]
        assert sum(v[colonna] for v in payload["fasi"].values()) == subtotale


def test_wizard_calcola_bonus_telematico_usa_livello_tariffario_selezionato(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    expected = {
        "bassa": ("minimo", 189.75, 822.25),
        "media": ("base", 379.5, 1644.5),
        "alta": ("massimo", 569.25, 2466.75),
    }

    with app.test_client() as client:
        _login(client)
        for complessita, (livello, bonus, totale_compenso) in expected.items():
            response = client.get(
                "/preventivi/wizard/calcola",
                query_string={
                    "id_pratica": "atto_citazione",
                    "valore": "5000",
                    "grado": "Giudice di Pace",
                    "regola_tariffaria": "civile_gdp",
                    "complessita": complessita,
                    "fasi": "studio,introduttiva,istruttoria,decisionale",
                    "bonus_telematico": "1",
                    "spese_generali": "0",
                    "applica_cpa": "0",
                    "applica_iva": "0",
                },
            )
            payload = response.get_json()

            assert response.status_code == 200
            assert payload["livello_compenso"] == livello
            assert payload["bonus_telematico"] == bonus
            assert payload["compenso_bozza"] == totale_compenso
            assert payload["totale"] == totale_compenso


def test_wizard_calcola_usa_totale_tariffario_nella_bozza_preventivo(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "ricorso_tributario",
                "valore": "10000",
                "grado": "CGT di primo grado",
                "complessita": "media",
                "fasi": "studio,introduttiva,istruttoria,decisionale",
                "spese_generali": "1",
                "perc_spese_generali": "15",
                "anticipazioni": "43,50",
            },
        )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["spese_generali_bozza"] == payload["spese_generali"]
    assert payload["spese_generali_in_compenso_bozza"] is False
    assert payload["compenso_bozza"] == payload["totale_base"]
    assert payload["imponibile_bozza"] == payload["totale_con_spese"]
    assert payload["compenso_bozza"] < payload["totale_con_spese"]
    assert payload["anticipazioni_bozza"] == 43.5
    assert payload["totale_bozza"] == payload["totale"]


def test_wizard_calcola_mediazione_odm_restituisce_costi_organismo_dm150(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        response = client.get(
            "/preventivi/wizard/calcola",
            query_string={
                "id_pratica": "mediazione",
                "valore": "10000",
                "grado": "Procedura ADR",
                "complessita": "media",
                "spese_generali": "0",
                "mediazione_odm_attiva": "1",
                "mediazione_odm_regime": "volontaria",
                "mediazione_odm_esito": "primo_incontro_senza_accordo",
            },
        )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["mediazione_odm"]["totale_organismo"] == 195.0
    assert "23G00163" in payload["mediazione_odm"]["riferimento_url"]
    assert payload["mediazione_odm"]["voce_label"].startswith("Costi organismo mediazione D.M. 150/2023")


def test_wizard_genera_salva_flag_reali_e_classificazioni_tassonomiche(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/preventivi/wizard/genera",
            data={
                "cliente_rapido_attivo": "1",
                "cliente_rapido_tipo": "PERSONA_FISICA",
                "cliente_rapido_nome": "Laura",
                "cliente_rapido_cognome": "Bianchi",
                "cliente_rapido_codice_fiscale": "BNCLRA80A41H501R",
                "avvocato_referente": "Avv. Preventivi",
                "oggetto": "Recupero crediti commerciale",
                "id_pratica": "decreto_ingiuntivo",
                "area_pratica": "Civile",
                "tipo_compenso": "Per fasi processuali (D.M. 55/2014)",
                "tipo_procedimento": "Procedimento monitorio",
                "valore_controversia": "18000",
                "applica_cassa": "0",
                "applica_iva": "0",
                "clausola_controversie_attiva": "0",
                "clausola_controversie_trattativa_individuale": "0",
                "voce_descr[]": "Compenso professionale",
                "voce_importo[]": "1250",
                "voce_tipo[]": "Onorario",
                "classificazioni_tassonomiche_json": (
                    '[{"uid":"row-1","area_tassonomica":"Giudiziale","macro_area_tassonomica":"Diritto civile",'
                    '"sottobranca_tassonomica":"Recupero crediti e monitori","tipologia_pratica_id":"decreto_ingiuntivo",'
                    '"tipologia_pratica_label":"Decreto ingiuntivo"}]'
                ),
            },
            follow_redirects=False,
        )

    assert response.status_code == 302

    with app.app_context():
        gestore = get_preventivi()
        preventivi = gestore.tutti_preventivi()

    assert len(preventivi) == 1
    preventivo = preventivi[0]
    assert preventivo.applica_cassa is False
    assert preventivo.applica_iva is False
    assert preventivo.clausola_controversie_attiva is False
    assert preventivo.clausola_controversie_trattativa_individuale is False
    assert preventivo.classificazioni_tassonomiche[0]["tipologia_pratica_id"] == "decreto_ingiuntivo"


def test_wizard_genera_salva_anticipazioni_totali_della_bozza(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    _crea_admin(app)

    with app.test_client() as client:
        _login(client)
        response = client.post(
            "/preventivi/wizard/genera",
            data={
                "cliente_rapido_attivo": "1",
                "cliente_rapido_tipo": "PERSONA_FISICA",
                "cliente_rapido_nome": "Luigi",
                "cliente_rapido_cognome": "Verdi",
                "cliente_rapido_codice_fiscale": "VRDLGU80A01H501W",
                "oggetto": "Ricorso tributario",
                "id_pratica": "ricorso_tributario",
                "area_pratica": "Tributario",
                "tipo_compenso": "Per fasi processuali (D.M. 55/2014)",
                "tipo_procedimento": "CGT di primo grado",
                "applica_cassa": "1",
                "applica_iva": "1",
                "anticipazioni_art15": "43,50",
                "anticipazioni_art15_totali": "193,50",
                "voce_descr[]": "Compenso professionale per Ricorso tributario",
                "voce_importo[]": "1000",
                "voce_tipo[]": "Onorario",
                "clausola_controversie_attiva": "0",
                "clausola_controversie_trattativa_individuale": "0",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302

    with app.app_context():
        gestore = get_preventivi()
        preventivo = gestore.tutti_preventivi()[0]

    assert round(preventivo.anticipazioni_art15, 2) == 193.50


def test_import_bridge_wizard_non_carica_le_tabelle_normative():
    """L'import del bridge non deve costruire il calcolatore del contributo unificato.

    `GestioneStrumentiLegali()` carica le tabelle normative (oltre 2 MB): a
    livello di modulo il costo veniva pagato ad ogni avvio di worker anche senza
    aprire mai il wizard preventivi. La verifica gira in un processo separato
    perché nella sessione pytest il modulo è già importato da altri test.
    """

    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    programma = (
        "import web.services.react_preventivo_wizard_bridge as b;"
        "assert b._STRUMENTI_LEGALI is None, 'costruito all import';"
        "assert b._strumenti_legali() is b._strumenti_legali(), 'singleton non stabile';"
        "print('ok')"
    )
    esito = subprocess.run(
        [sys.executable, "-c", programma],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert esito.returncode == 0, esito.stdout + esito.stderr
    assert "ok" in esito.stdout
