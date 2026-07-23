from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Mapping

from pct.formatting import format_decimal_it, format_euro_it


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fmt_money(value: Any) -> str:
    return format_euro_it(value)


def _fmt_percent(value: Any) -> str:
    try:
        amount = round(float(value or 0.0), 2)
    except (TypeError, ValueError):
        amount = 0.0
    return format_decimal_it(amount)


def _fmt_date_it(value: Any) -> str:
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    raw = _clean_text(value)
    if not raw:
        return ""
    for parser in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:19], parser).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _metric(label: str, value: str, subtext: str = "") -> Dict[str, str]:
    return {"label": label, "value": value, "subtext": subtext}


TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "uffici_competenti": {
        "title": "Uffici competenti per Comune",
        "subtitle": "Ricerca ministeriale con Tribunale, Giudice di Pace, Procura, UNEP e Corte d'Appello.",
        "submit_label": "Cerca uffici",
        "method": "ricerca_uffici_competenti",
        "fields": [
            {"name": "comune", "label": "Comune", "type": "text", "required": True},
            {
                "name": "includi_speciali",
                "label": "Mostra anche uffici nazionali e speciali",
                "type": "checkbox",
            },
        ],
    },
    "contributo_unificato": {
        "title": "Contributo unificato",
        "subtitle": "Calcolo operativo con categoria, grado e anticipazione forfettaria.",
        "submit_label": "Calcola contributo",
        "method": "calcola_contributo_unificato",
        "fields": [
            {"name": "cu_categoria", "label": "Tipologia", "type": "select", "options": "contributo_unificato"},
            {
                "name": "cu_grado",
                "label": "Grado",
                "type": "select",
                "options": [
                    {"value": "primo_grado", "label": "Primo grado"},
                    {"value": "appello", "label": "Appello"},
                    {"value": "cassazione", "label": "Cassazione"},
                ],
            },
            {
                "name": "cu_valore_tipo",
                "label": "Tipo valore",
                "type": "select",
                "options": [
                    {"value": "determinato", "label": "Valore determinato"},
                    {"value": "indeterminabile", "label": "Valore indeterminabile"},
                    {"value": "non_indicato", "label": "Valore non indicato"},
                ],
            },
            {"name": "cu_valore", "label": "Valore causa", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "cu_anticipazione_forfettaria",
                "label": "Anticipazione forfettaria",
                "type": "select",
                "options": [
                    {"value": "1", "label": "Sì"},
                    {"value": "0", "label": "No"},
                ],
            },
            {"name": "cu_numero_parti_ricorrenti", "label": "Parti ricorrenti", "type": "number", "step": "1", "min": "1"},
            {
                "name": "cu_sezione_specializzata_impresa",
                "label": "Sezione impresa",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
            {
                "name": "cu_dati_obbligatori_mancanti",
                "label": "Dati obbligatori mancanti",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
        ],
    },
    "interessi": {
        "title": "Interessi legali e moratori",
        "subtitle": "Segmentazione per periodo, tasso legale e mora commerciale.",
        "submit_label": "Calcola interessi",
        "method": "calcola_interessi",
        "fields": [
            {
                "name": "int_tipo",
                "label": "Regime",
                "type": "select",
                "options": [
                    {"value": "legali", "label": "Interessi legali"},
                    {"value": "mora_commerciale", "label": "Mora commerciale D.Lgs. 231/2002"},
                ],
            },
            {"name": "int_capitale", "label": "Capitale", "type": "number", "step": "0.01", "min": "0"},
            {"name": "int_data_inizio", "label": "Dal", "type": "date"},
            {"name": "int_data_fine", "label": "Al", "type": "date"},
        ],
    },
    "nota_credito": {
        "title": "Nota di precisazione del credito",
        "subtitle": "Bozza professionale con capitale, interessi, spese, CPA, IVA e acconti.",
        "submit_label": "Genera nota",
        "method": "genera_nota_precisazione_credito",
        "fields": [
            {"name": "note_creditore", "label": "Creditore", "type": "text"},
            {"name": "note_debitore", "label": "Debitore", "type": "text"},
            {"name": "note_titolo", "label": "Titolo del credito", "type": "text"},
            {"name": "note_capitale", "label": "Capitale", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "note_interessi_tipo",
                "label": "Interessi",
                "type": "select",
                "options": [
                    {"value": "legali", "label": "Calcolo automatico legali"},
                    {"value": "mora_commerciale", "label": "Calcolo automatico mora commerciale"},
                    {"value": "manuale", "label": "Importo manuale"},
                ],
            },
            {"name": "note_interessi_manual", "label": "Interessi manuali", "type": "number", "step": "0.01", "min": "0"},
            {"name": "note_spese_vive", "label": "Spese vive", "type": "number", "step": "0.01", "min": "0"},
            {"name": "note_compensi", "label": "Compensi", "type": "number", "step": "0.01", "min": "0"},
            {"name": "note_cpa_perc", "label": "CPA %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "note_iva_perc", "label": "IVA %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "note_acconti", "label": "Acconti", "type": "number", "step": "0.01", "min": "0"},
            {"name": "note_luogo", "label": "Luogo", "type": "text"},
            {"name": "note_data", "label": "Data", "type": "date"},
            {"name": "note_avvocato", "label": "Avvocato", "type": "text"},
        ],
    },
    "pignoramento": {
        "title": "Simulatore pignoramento",
        "subtitle": "Stipendio o pensione con ordinario, esattoriale e alimentare.",
        "submit_label": "Simula pignoramento",
        "method": "simula_pignoramento",
        "fields": [
            {
                "name": "pig_tipo_reddito",
                "label": "Reddito",
                "type": "select",
                "options": [
                    {"value": "stipendio", "label": "Stipendio"},
                    {"value": "pensione", "label": "Pensione"},
                ],
            },
            {
                "name": "pig_tipo_credito",
                "label": "Tipo credito",
                "type": "select",
                "options": [
                    {"value": "ordinario", "label": "Ordinario"},
                    {"value": "esattoriale", "label": "Esattoriale"},
                    {"value": "alimentare", "label": "Alimentare"},
                ],
            },
            {"name": "pig_importo_netto", "label": "Importo netto mensile", "type": "number", "step": "0.01", "min": "0"},
            {"name": "pig_aliquota_alimentare", "label": "Aliquota alimentare %", "type": "number", "step": "0.01", "min": "0"},
        ],
    },
    "ctu": {
        "title": "CTU e compensi ausiliari",
        "subtitle": "Vacazioni, onorario, spese documentate e accessori professionali.",
        "submit_label": "Calcola compenso CTU",
        "method": "calcola_ctu",
        "fields": [
            {
                "name": "ctu_modalita",
                "label": "Modalità",
                "type": "select",
                "options": [
                    {"value": "vacazioni", "label": "Vacazioni"},
                    {"value": "onorario_libero", "label": "Onorario libero"},
                ],
            },
            {"name": "ctu_vacazioni", "label": "Vacazioni", "type": "number", "step": "1", "min": "0"},
            {"name": "ctu_onorario", "label": "Onorario base", "type": "number", "step": "0.01", "min": "0"},
            {"name": "ctu_spese", "label": "Spese", "type": "number", "step": "0.01", "min": "0"},
            {"name": "ctu_cpa_perc", "label": "CPA %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "ctu_iva_perc", "label": "IVA %", "type": "number", "step": "0.01", "min": "0"},
        ],
    },
    "rivalutazione_istat": {
        "title": "Rivalutazione monetaria ISTAT",
        "subtitle": "FOI e NIC per danni, assegni, adeguamenti e liquidazioni.",
        "submit_label": "Calcola rivalutazione",
        "method": "calcola_rivalutazione_istat",
        "fields": [
            {"name": "riv_importo", "label": "Importo", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "riv_tipo",
                "label": "Indice",
                "type": "select",
                "options": [
                    {"value": "foi", "label": "FOI"},
                    {"value": "nic", "label": "NIC"},
                ],
            },
            {"name": "riv_anno_base", "label": "Anno base", "type": "number", "step": "1", "min": "2000"},
            {"name": "riv_mese_base", "label": "Mese base", "type": "number", "step": "1", "min": "1", "max": "12"},
            {"name": "riv_anno_fine", "label": "Anno finale", "type": "number", "step": "1", "min": "2000"},
            {"name": "riv_mese_fine", "label": "Mese finale", "type": "number", "step": "1", "min": "1", "max": "12"},
        ],
    },
    "canone_locazione": {
        "title": "Adeguamento canone di locazione",
        "subtitle": "Aggiornamento annuo del canone con percentuale ISTAT applicata.",
        "submit_label": "Calcola adeguamento",
        "method": "calcola_adeguamento_canone",
        "fields": [
            {"name": "loc_canone", "label": "Canone annuo", "type": "number", "step": "0.01", "min": "0"},
            {"name": "loc_perc_adeguamento", "label": "Percentuale adeguamento", "type": "number", "step": "0.01", "min": "0", "max": "100"},
            {"name": "loc_anno_base", "label": "Anno base", "type": "number", "step": "1", "min": "2000"},
            {"name": "loc_mese_base", "label": "Mese base", "type": "number", "step": "1", "min": "1", "max": "12"},
            {"name": "loc_anno_fine", "label": "Anno finale", "type": "number", "step": "1", "min": "2000"},
            {"name": "loc_mese_fine", "label": "Mese finale", "type": "number", "step": "1", "min": "1", "max": "12"},
        ],
    },
    "usura": {
        "title": "Verifica soglia usura",
        "subtitle": "Confronto tra tasso applicato, TEGM e soglia antiusura trimestrale.",
        "submit_label": "Verifica soglia",
        "method": "verifica_soglia_usura",
        "fields": [
            {"name": "usura_tasso", "label": "Tasso applicato %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "usura_categoria", "label": "Categoria", "type": "select", "options": "usura"},
            {"name": "usura_data", "label": "Data riferimento", "type": "date"},
        ],
    },
    "contributi_cassa_forense": {
        "title": "Contributi Cassa Forense",
        "subtitle": "Soggettivo, integrativo e maternita con aliquote annuali.",
        "submit_label": "Calcola contributi",
        "method": "calcola_contributi_cassa_forense",
        "fields": [
            {"name": "cf_anno", "label": "Anno", "type": "number", "step": "1", "min": "2020"},
            {"name": "cf_reddito", "label": "Reddito professionale", "type": "number", "step": "0.01", "min": "0"},
            {"name": "cf_compensi", "label": "Compensi IVA", "type": "number", "step": "0.01", "min": "0"},
        ],
    },
    "prescrizione": {
        "title": "Prescrizione civile",
        "subtitle": "Termine ordinario o breve con atto interruttivo e residuo operativo.",
        "submit_label": "Calcola prescrizione",
        "method": "calcola_prescrizione",
        "fields": [
            {
                "name": "presc_tipo",
                "label": "Termine",
                "type": "select",
                "options": [
                    {"value": "ordinaria_10", "label": "Ordinaria 10 anni"},
                    {"value": "quinquennale", "label": "Quinquennale"},
                    {"value": "triennale", "label": "Triennale"},
                    {"value": "annuale", "label": "Annuale"},
                ],
            },
            {"name": "presc_data_decorrenza", "label": "Decorrenza", "type": "date"},
            {"name": "presc_atto_interruttivo", "label": "Atto interruttivo", "type": "date"},
            {"name": "presc_descrizione", "label": "Descrizione", "type": "text"},
        ],
    },
    "danno_biologico": {
        "title": "Danno biologico",
        "subtitle": "Stima operativa con IP, ITT, ITP, morale e personalizzazione.",
        "submit_label": "Calcola danno",
        "method": "calcola_danno_biologico",
        "fields": [
            {"name": "db_eta", "label": "Eta", "type": "number", "step": "1", "min": "0"},
            {"name": "db_perc_ip", "label": "Invalidita permanente %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "db_giorni_itt", "label": "Giorni ITT", "type": "number", "step": "1", "min": "0"},
            {"name": "db_giorni_itp", "label": "Giorni ITP", "type": "number", "step": "1", "min": "0"},
            {"name": "db_perc_itp", "label": "Percentuale ITP", "type": "number", "step": "0.01", "min": "0", "max": "100"},
            {"name": "db_personalizzazione", "label": "Personalizzazione %", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "db_includi_morale",
                "label": "Danno morale",
                "type": "select",
                "options": [
                    {"value": "1", "label": "Includi"},
                    {"value": "0", "label": "Escludi"},
                ],
            },
        ],
    },
    "imposta_registro": {
        "title": "Imposta di registro",
        "subtitle": "Atti giudiziari con minimo fisso, aliquota e quota per parte.",
        "submit_label": "Calcola imposta",
        "method": "calcola_imposta_registro",
        "fields": [
            {
                "name": "reg_tipo_atto",
                "label": "Tipo atto",
                "type": "select",
                "options": [
                    {"value": "sentenza_condanna", "label": "Sentenza di condanna"},
                    {"value": "decreto_ingiuntivo", "label": "Decreto ingiuntivo"},
                    {"value": "ordinanza", "label": "Ordinanza"},
                ],
            },
            {"name": "reg_valore", "label": "Valore atto", "type": "number", "step": "0.01", "min": "0"},
            {"name": "reg_parti", "label": "Numero parti", "type": "number", "step": "1", "min": "1"},
        ],
    },
    "tfr": {
        "title": "TFR",
        "subtitle": "Quota maturata, rivalutazione, anticipazioni e totale lordo.",
        "submit_label": "Calcola TFR",
        "method": "calcola_tfr",
        "fields": [
            {"name": "tfr_retribuzione_annua", "label": "Retribuzione annua", "type": "number", "step": "0.01", "min": "0"},
            {"name": "tfr_anni_servizio", "label": "Anni servizio", "type": "number", "step": "1", "min": "0"},
            {"name": "tfr_mesi_servizio", "label": "Mesi servizio", "type": "number", "step": "1", "min": "0", "max": "11"},
            {"name": "tfr_montante_pregresso", "label": "Montante pregresso", "type": "number", "step": "0.01", "min": "0"},
            {"name": "tfr_inflazione_perc", "label": "Inflazione %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "tfr_anticipazioni", "label": "Anticipazioni", "type": "number", "step": "0.01", "min": "0"},
        ],
    },
    "onorari_forensi": {
        "title": "Onorari forensi",
        "subtitle": "Parametri DM 55/2014 con materia, grado, fasi e complessità.",
        "submit_label": "Calcola onorari",
        "method": "calcola_onorari_forensi",
        "fields": [
            {"name": "onorari_materia", "label": "Materia", "type": "select", "options": "onorari_materie"},
            {"name": "onorari_grado", "label": "Grado", "type": "select", "options": "onorari_gradi"},
            {"name": "onorari_valore", "label": "Valore", "type": "number", "step": "0.01", "min": "0"},
            {"name": "onorari_complessita", "label": "Complessità", "type": "select", "options": "onorari_complessita"},
            {
                "name": "onorari_bonus_telematico",
                "label": "Bonus telematico",
                "type": "select",
                "options": [
                      {"value": "0", "label": "No"},
                      {"value": "1", "label": "Sì"},
                  ],
              },
            {
                "name": "onorari_includi_spese_generali",
                "label": "Spese generali",
                "type": "select",
                "options": [
                    {"value": "1", "label": "Includi"},
                    {"value": "0", "label": "Escludi"},
                  ],
              },
              {
                  "name": "onorari_cliente_qualificato",
                  "label": "Cliente soggetto a equo compenso",
                  "type": "select",
                  "options": [
                      {"value": "0", "label": "No"},
                      {"value": "1", "label": "Sì"},
                  ],
              },
              {
                  "name": "onorari_convenzione_predisposta_avvocato",
                  "label": "Accordo predisposto dallo studio",
                  "type": "select",
                  "options": [
                      {"value": "0", "label": "No"},
                      {"value": "1", "label": "Sì"},
                  ],
              },
              {
                  "name": "onorari_equo_compenso_verificato",
                  "label": "Equo compenso verificato",
                  "type": "select",
                  "options": [
                      {"value": "0", "label": "No"},
                      {"value": "1", "label": "Sì"},
                  ],
              },
              {
                  "name": "onorari_informativa_scritta",
                  "label": "Informativa scritta",
                  "type": "select",
                  "options": [
                      {"value": "0", "label": "No"},
                      {"value": "1", "label": "Sì"},
                  ],
              },
              {"name": "onorari_fasi", "label": "Fasi", "type": "multiselect", "options": "onorari_fasi"},
          ],
      },
    "custodia_cautelare": {
        "title": "Custodia cautelare",
        "subtitle": "Timeline di interrogatorio, riesame, decisione e deposito motivi.",
        "submit_label": "Calcola timeline",
        "method": "calcola_custodia_cautelare",
        "fields": [
            {
                "name": "custodia_tipo_misura",
                "label": "Tipo misura",
                "type": "select",
                "options": [
                    {"value": "carcere", "label": "Carcere"},
                    {"value": "domiciliari", "label": "Domiciliari"},
                    {"value": "divieto_dimora", "label": "Divieto di dimora"},
                ],
            },
            {"name": "custodia_data_esecuzione", "label": "Data esecuzione", "type": "date"},
            {"name": "custodia_data_istanza_riesame", "label": "Istanza riesame", "type": "date"},
            {"name": "custodia_data_decisione_riesame", "label": "Decisione riesame", "type": "date"},
        ],
    },
    "prescrizione_penale": {
        "title": "Prescrizione penale",
        "subtitle": "Termine base, massimo, sospensioni e coefficiente di interruzione.",
        "submit_label": "Calcola prescrizione penale",
        "method": "calcola_prescrizione_penale",
        "fields": [
            {"name": "presc_data_fatto", "label": "Data del fatto", "type": "date"},
            {"name": "presc_massimo_edittale_anni", "label": "Massimo edittale anni", "type": "number", "step": "1", "min": "0"},
            {"name": "presc_massimo_edittale_mesi", "label": "Massimo edittale mesi", "type": "number", "step": "1", "min": "0"},
            {
                "name": "presc_contravvenzione",
                "label": "Contravvenzione",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
            {"name": "presc_coeff_interruzione", "label": "Coefficiente interruzione", "type": "number", "step": "0.01", "min": "1"},
            {"name": "presc_giorni_sospensione", "label": "Giorni sospensione", "type": "number", "step": "1", "min": "0"},
        ],
    },
    "successione_legittima": {
        "title": "Successione legittima",
        "subtitle": "Riparto quote tra coniuge, figli, ascendenti e fratelli.",
        "submit_label": "Calcola successione",
        "method": "calcola_successione_legittima",
        "fields": [
            {"name": "successione_asse", "label": "Asse ereditario", "type": "number", "step": "0.01", "min": "0"},
            {"name": "successione_coniuge", "label": "Coniuge", "type": "number", "step": "1", "min": "0"},
            {"name": "successione_figli", "label": "Figli", "type": "number", "step": "1", "min": "0"},
            {"name": "successione_ascendenti", "label": "Ascendenti", "type": "number", "step": "1", "min": "0"},
            {"name": "successione_fratelli", "label": "Fratelli", "type": "number", "step": "1", "min": "0"},
        ],
    },
    "cedolare_secca": {
        "title": "Cedolare secca",
        "subtitle": "Imposta annua, registro evitato e costo pluriennale.",
        "submit_label": "Calcola cedolare",
        "method": "calcola_cedolare_secca",
        "fields": [
            {"name": "cedolare_canone_annuo", "label": "Canone annuo", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "cedolare_aliquota",
                "label": "Aliquota",
                "type": "select",
                "options": [
                    {"value": "21", "label": "21%"},
                    {"value": "10", "label": "10%"},
                ],
            },
            {"name": "cedolare_annualita", "label": "Annualita", "type": "number", "step": "1", "min": "1"},
        ],
    },
    "indennita_licenziamento": {
        "title": "Indennita licenziamento",
        "subtitle": "Tutele crescenti, piccole imprese e stima mensilita.",
        "submit_label": "Calcola indennita",
        "method": "calcola_indennita_licenziamento",
        "fields": [
            {"name": "lic_retribuzione_mensile", "label": "Retribuzione mensile", "type": "number", "step": "0.01", "min": "0"},
            {"name": "lic_anni_servizio", "label": "Anni servizio", "type": "number", "step": "1", "min": "0"},
            {"name": "lic_mesi_servizio", "label": "Mesi servizio", "type": "number", "step": "1", "min": "0", "max": "11"},
            {
                "name": "lic_regime",
                "label": "Regime",
                "type": "select",
                "options": [
                    {"value": "jobs_act", "label": "Jobs Act"},
                    {"value": "piccola_impresa", "label": "Piccola impresa"},
                    {"value": "tutela_reale", "label": "Tutela reale"},
                ],
            },
            {"name": "lic_mensilita_preavviso", "label": "Mensilita preavviso", "type": "number", "step": "0.01", "min": "0"},
        ],
    },
    "piano_ammortamento": {
        "title": "Piano di ammortamento",
        "subtitle": "Metodo francese o italiano con rata, interessi e piano rateale.",
        "submit_label": "Calcola piano",
        "method": "calcola_piano_ammortamento",
        "fields": [
            {"name": "amm_capitale", "label": "Capitale", "type": "number", "step": "0.01", "min": "0"},
            {"name": "amm_tasso_annuo", "label": "Tasso annuo %", "type": "number", "step": "0.01", "min": "0"},
            {"name": "amm_durata_anni", "label": "Durata anni", "type": "number", "step": "1", "min": "1"},
            {"name": "amm_rate_anno", "label": "Rate anno", "type": "number", "step": "1", "min": "1"},
            {
                "name": "amm_tipo",
                "label": "Metodo",
                "type": "select",
                "options": [
                    {"value": "francese", "label": "Francese"},
                    {"value": "italiano", "label": "Italiano"},
                ],
            },
            {"name": "amm_data_prima_rata", "label": "Prima rata", "type": "date"},
        ],
    },
    "interessi_acconti": {
        "title": "Interessi con acconti",
        "subtitle": "Imputazione degli acconti prima a interessi e poi a capitale ex art. 1194 c.c.",
        "submit_label": "Calcola residuo",
        "method": "calcola_interessi_acconti",
        "fields": [
            {
                "name": "acc_tipo",
                "label": "Regime",
                "type": "select",
                "options": [
                    {"value": "legali", "label": "Interessi legali (art. 1284 c.c.)"},
                    {"value": "mora_commerciale", "label": "Mora commerciale (D.Lgs. 231/2002)"},
                    {"value": "legali_1284_4", "label": "Art. 1284, comma 4, c.c."},
                ],
            },
            {"name": "acc_capitale", "label": "Capitale", "type": "number", "step": "0.01", "min": "0"},
            {"name": "acc_data_inizio", "label": "Decorrenza", "type": "date"},
            {"name": "acc_data_fine", "label": "Data finale", "type": "date"},
            {"name": "acc_acconti", "label": "Acconti (una riga: data importo)", "type": "textarea"},
        ],
    },
    "maggior_danno": {
        "title": "Maggior danno da svalutazione",
        "subtitle": "Art. 1224 co. 2 c.c.: rivalutazione ISTAT più interessi legali sulla base scelta.",
        "submit_label": "Calcola maggior danno",
        "method": "calcola_maggior_danno",
        "fields": [
            {"name": "md_importo", "label": "Importo", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "md_tipo_indice",
                "label": "Indice ISTAT",
                "type": "select",
                "options": [
                    {"value": "foi", "label": "FOI (netto tabacchi)"},
                    {"value": "nic", "label": "NIC"},
                ],
            },
            {
                "name": "md_base_interessi",
                "label": "Base interessi",
                "type": "select",
                "options": [
                    {"value": "rivalutato_annuale", "label": "Capitale rivalutato anno per anno"},
                    {"value": "semisomma", "label": "Semisomma"},
                    {"value": "originario", "label": "Capitale originario"},
                ],
            },
            {"name": "md_anno_base", "label": "Anno iniziale", "type": "number", "step": "1", "min": "1900"},
            {"name": "md_mese_base", "label": "Mese iniziale", "type": "number", "step": "1", "min": "1", "max": "12"},
            {"name": "md_anno_fine", "label": "Anno finale", "type": "number", "step": "1", "min": "1900"},
            {"name": "md_mese_fine", "label": "Mese finale", "type": "number", "step": "1", "min": "1", "max": "12"},
        ],
    },
    "danno_parentale": {
        "title": "Danno da perdita parentale",
        "subtitle": "Tabella a punti Milano 2024 con i cinque parametri della Cassazione.",
        "submit_label": "Calcola danno",
        "method": "calcola_danno_parentale",
        "fields": [
            {
                "name": "dp_categoria",
                "label": "Rapporto",
                "type": "select",
                "options": [
                    {"value": "nucleo_primario", "label": "Genitore, figlio o coniuge"},
                    {"value": "altri_congiunti", "label": "Fratello, sorella, nonno o nipote"},
                ],
            },
            {"name": "dp_eta_vittima", "label": "Età della vittima", "type": "number", "step": "1", "min": "0"},
            {"name": "dp_eta_congiunto", "label": "Età del congiunto", "type": "number", "step": "1", "min": "0"},
            {
                "name": "dp_convivenza",
                "label": "Convivenza",
                "type": "select",
                "options": [
                    {"value": "1", "label": "Sì"},
                    {"value": "0", "label": "No"},
                ],
            },
            {
                "name": "dp_unico_superstite",
                "label": "Unico superstite del nucleo",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
            {
                "name": "dp_qualita_relazione",
                "label": "Qualità della relazione",
                "type": "select",
                "options": [
                    {"value": "eccezionale", "label": "Eccezionale"},
                    {"value": "intensa", "label": "Intensa"},
                    {"value": "ordinaria", "label": "Ordinaria"},
                    {"value": "ridotta", "label": "Ridotta"},
                    {"value": "assente", "label": "Assente o conflittuale"},
                ],
            },
        ],
    },
    "usufrutto": {
        "title": "Usufrutto e nuda proprietà",
        "subtitle": "Valore fiscale per fasce d'età (D.P.R. 131/1986) con il tasso legale corrente.",
        "submit_label": "Calcola valori",
        "method": "calcola_usufrutto",
        "fields": [
            {"name": "usu_valore_piena", "label": "Valore piena proprietà", "type": "number", "step": "0.01", "min": "0"},
            {"name": "usu_eta", "label": "Età usufruttuario", "type": "number", "step": "1", "min": "1"},
            {"name": "usu_quota_perc", "label": "Quota %", "type": "number", "step": "0.01", "min": "1", "max": "100"},
        ],
    },
    "quote_riserva": {
        "title": "Quote di riserva legittimari",
        "subtitle": "Riserva di coniuge, figli e ascendenti con riunione fittizia ex art. 556 c.c.",
        "submit_label": "Calcola riserva",
        "method": "calcola_quote_riserva",
        "fields": [
            {"name": "ris_patrimonio", "label": "Patrimonio relitto", "type": "number", "step": "0.01", "min": "0"},
            {"name": "ris_debiti", "label": "Debiti", "type": "number", "step": "0.01", "min": "0"},
            {"name": "ris_donazioni", "label": "Donazioni (donatum)", "type": "number", "step": "0.01", "min": "0"},
            {
                "name": "ris_coniuge",
                "label": "Coniuge",
                "type": "select",
                "options": [
                    {"value": "1", "label": "Sì"},
                    {"value": "0", "label": "No"},
                ],
            },
            {"name": "ris_figli", "label": "Numero figli", "type": "number", "step": "1", "min": "0"},
            {
                "name": "ris_ascendenti",
                "label": "Ascendenti",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
        ],
    },
    "assegno_mantenimento": {
        "title": "Assegno di mantenimento",
        "subtitle": "Stima orientativa per figli e coniuge su criteri di prassi dichiarati.",
        "submit_label": "Stima assegno",
        "method": "stima_assegno_mantenimento",
        "fields": [
            {
                "name": "man_tipo",
                "label": "Tipo di assegno",
                "type": "select",
                "options": [
                    {"value": "figli", "label": "Mantenimento figli"},
                    {"value": "coniuge", "label": "Assegno al coniuge"},
                ],
            },
            {"name": "man_reddito_obbligato", "label": "Reddito mensile obbligato", "type": "number", "step": "0.01", "min": "0"},
            {"name": "man_reddito_beneficiario", "label": "Reddito mensile beneficiario", "type": "number", "step": "0.01", "min": "0"},
            {"name": "man_figli", "label": "Numero figli", "type": "number", "step": "1", "min": "0"},
            {
                "name": "man_collocamento_paritetico",
                "label": "Collocamento paritetico",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
            {
                "name": "man_casa_assegnata",
                "label": "Casa familiare assegnata",
                "type": "select",
                "options": [
                    {"value": "0", "label": "No"},
                    {"value": "1", "label": "Sì"},
                ],
            },
            {"name": "man_durata_matrimonio", "label": "Durata matrimonio (anni)", "type": "number", "step": "1", "min": "0"},
        ],
    },
}


TOOL_PRESET_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "calcolo_interessi_di_mora": {"int_tipo": "mora_commerciale"},
    "tabella_interessi_di_mora": {"int_tipo": "mora_commerciale"},
    "interessi_mora_appalti": {"int_tipo": "mora_commerciale"},
    "tabella_tassi_appalti": {"int_tipo": "mora_commerciale"},
    "interessi_1284_cc": {"int_tipo": "legali"},
    "calcolo_inflazione": {"riv_tipo": "nic", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "rivalutazione_mensile": {"riv_tipo": "foi", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "interessi_vari_sul_capitale_rivalutato": {"riv_tipo": "foi", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "rivalutazione_storica": {"riv_tipo": "foi", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "variazioni_storiche_istat": {"riv_tipo": "foi", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "tabella_variazioni_istat": {"riv_tipo": "foi", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "ultimo_indice_istat": {"riv_tipo": "nic", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "rivalutazione_annuale_media": {"riv_tipo": "foi", "riv_anno_fine": "2025", "riv_mese_fine": "3"},
    "rivalutazione_tfr": {"tfr_inflazione_perc": "2.00"},
    "calcolo_tasso_di_usura": {"usura_categoria": "credito_personale"},
    "calcolo_surroga": {"amm_tipo": "francese"},
    "calcolo_taeg": {"amm_tipo": "francese"},
    "tabella_contributo_unificato": {"cu_categoria": "civile_ordinario"},
    "pignoramento_stipendio_o_pensione": {"pig_tipo_reddito": "stipendio"},
    "calcolo_eredita": {"successione_coniuge": "1", "successione_figli": "1"},
    "calcolo_tfr": {"tfr_inflazione_perc": "2.00"},
}


def resolve_runtime(entry: Mapping[str, Any]) -> Dict[str, Any]:
    entry_id = _clean_text(entry.get("id"))
    endpoint = _clean_text(entry.get("endpoint"))
    params = dict(entry.get("params") or {})
    tool_id = _clean_text(params.get("tool"))
    if endpoint == "strumenti_legali.index" and tool_id in TOOL_SCHEMAS:
        return {
            "kind": "tool",
            "tool_id": tool_id,
            "schema": TOOL_SCHEMAS[tool_id],
            "preset_overrides": dict(TOOL_PRESET_OVERRIDES.get(entry_id, {})),
        }

    section_id = _clean_text(entry.get("section_id"))
    if section_id in {"rassegna_stampa"}:
        return {"kind": "rassegna"}
    if section_id in {"scadenze_e_termini"}:
        return {"kind": "scadenze"}
    if section_id in {"atti_giudiziari"}:
        if "telematico" in entry_id or "fascicolo_telematico" in entry_id or "causa_a_ruolo" in entry_id:
            return {"kind": "telematico"}
        if "ufficio" in entry_id or "pec" in entry_id or "unep" in entry_id:
            return {"kind": "lookup"}
        return {"kind": "template_atti"}
    if section_id in {"fatturazione_avvocati", "dichiarazione_redditi"}:
        return {"kind": "economico"}
    if section_id in {"diritto_penale"}:
        return {"kind": "giurisprudenza"}
    if section_id in {"applicazioni_varie", "utilita"}:
        if "partita_iva" in entry_id or "iban" in entry_id or "codice_fiscale" in entry_id:
            return {"kind": "lookup"}
        return {"kind": "utility"}
    if section_id in {"investimenti_finanziari", "proprieta_successioni"}:
        return {"kind": "patrimonio"}
    return {"kind": "catalogo_operativo"}


def build_tool_result(tool_id: str, result: Mapping[str, Any]) -> Dict[str, Any]:
    metrics: List[Dict[str, str]] = []
    tables: List[Dict[str, Any]] = []
    preview_text = ""

    if tool_id == "uffici_competenti":
        offices = list(result.get("offices") or [])
        metrics = [
            _metric("Comune", str(result.get("comune") or "")),
            _metric("Uffici mostrati", str(result.get("totalVisible") or len(offices))),
            _metric("Uffici fonte", str(result.get("totalOfficial") or len(offices))),
        ]
        tables.append(
            {
                "title": "Riepilogo uffici",
                "headers": ["Tipo", "Ufficio", "Sede", "Recapito"],
                "rows": [
                    [
                        str(office.get("typeLabel") or ""),
                        str(office.get("name") or ""),
                        " - ".join(
                            part
                            for part in [
                                str(office.get("address") or ""),
                                str(office.get("city") or ""),
                            ]
                            if part
                        ),
                        str(office.get("phone") or office.get("email") or office.get("pec") or ""),
                    ]
                    for office in offices[:12]
                ],
            }
        )
    elif tool_id == "contributo_unificato":
        metrics = [
            _metric("Tipologia", str(result.get("categoria_label") or ""), str(result.get("grado_label") or "")),
            _metric("Contributo base", f"{_fmt_money(result.get('base'))}"),
            _metric("Anticipazione", f"{_fmt_money(result.get('anticipazione_forfettaria'))}"),
            _metric("Totale", f"{_fmt_money(result.get('totale'))}"),
        ]
        regole = list(result.get("regole_applicate") or [])
        if regole:
            tables.append(
                {
                    "title": "Regole applicate",
                    "headers": ["Regola", "Fattore"],
                    "rows": [
                        [str(row.get("label") or row.get("code") or ""), str(row.get("factor") or "")]
                        for row in regole
                    ],
                }
            )
    elif tool_id == "interessi":
        metrics = [
            _metric("Regime", str(result.get("label") or ""), f"{result.get('covered_days', 0)} giorni coperti"),
            _metric("Interessi maturati", f"{_fmt_money(result.get('total_interest'))}"),
            _metric("Capitale + interessi", f"{_fmt_money(result.get('total_amount'))}", f"{result.get('days', 0)} giorni complessivi"),
        ]
        tables.append(
            {
                "title": "Segmenti di calcolo",
                "headers": ["Periodo", "Giorni", "Tasso", "Interessi"],
                "rows": [
                    [
                        f"{_fmt_date_it(row.get('start'))} - {_fmt_date_it(row.get('end'))}",
                        str(row.get("days") or 0),
                        f"{_fmt_percent(row.get('rate'))}%",
                        f"{_fmt_money(row.get('interest'))}",
                    ]
                    for row in list(result.get("segments") or [])
                ],
            }
        )
    elif tool_id == "nota_credito":
        metrics = [
            _metric("Creditore", str(result.get("creditore") or "")),
            _metric("Debitore", str(result.get("debitore") or "")),
            _metric("Totale lordo", f"{_fmt_money(result.get('totale_lordo'))}"),
            _metric("Residuo", f"{_fmt_money(result.get('residuo'))}"),
        ]
        tables.append(
            {
                "title": "Breakdown economico",
                "headers": ["Voce", "Importo"],
                "rows": [
                    [str(row.get("label") or ""), f"{_fmt_money(row.get('value'))}"]
                    for row in list(result.get("breakdown") or [])
                ],
            }
        )
        preview_text = str(result.get("rendered_text") or "")
    elif tool_id == "pignoramento":
        metrics = [
            _metric("Reddito", str(result.get("tipo_reddito_label") or "")),
            _metric("Credito", str(result.get("tipo_credito_label") or "")),
            _metric("Quota massima", f"{_fmt_money(result.get('quota_massima'))}"),
            _metric("Residuo debitore", f"{_fmt_money(result.get('residuo'))}"),
        ]
    elif tool_id == "ctu":
        metrics = [
            _metric("Modalità", str(result.get("modalita_label") or "")),
            _metric("Onorario base", f"{_fmt_money(result.get('onorario_base'))}"),
            _metric("Spese", f"{_fmt_money(result.get('spese'))}"),
            _metric("Totale", f"{_fmt_money(result.get('totale'))}"),
        ]
    elif tool_id == "rivalutazione_istat":
        metrics = [
            _metric("Indice", str(result.get("tipo_label") or "")),
            _metric("Importo originale", f"{_fmt_money(result.get('importo_originale'))}"),
            _metric("Importo rivalutato", f"{_fmt_money(result.get('importo_rivalutato'))}"),
            _metric("Differenza", f"{_fmt_money(result.get('differenza'))}", f"{_fmt_percent(result.get('variazione_perc'))}%"),
        ]
    elif tool_id == "canone_locazione":
        metrics = [
            _metric("Canone annuo", f"{_fmt_money(result.get('canone_annuo'))}"),
            _metric("Canone aggiornato", f"{_fmt_money(result.get('canone_annuo_aggiornato'))}"),
            _metric("Incremento mensile", f"{_fmt_money(result.get('incremento_mensile'))}"),
            _metric("Variazione applicata", f"{_fmt_percent(result.get('variazione_applicata'))}%"),
        ]
    elif tool_id == "usura":
        metrics = [
            _metric("Categoria", str(result.get("categoria_label") or "")),
            _metric("Tasso applicato", f"{_fmt_percent(result.get('tasso_applicato'))}%"),
            _metric("Soglia", f"{_fmt_percent(result.get('soglia'))}%"),
            _metric("Esito", str(result.get("esito") or ""), f"Margine {_fmt_percent(result.get('margine'))}%"),
        ]
    elif tool_id == "contributi_cassa_forense":
        metrics = [
            _metric("Anno", str(result.get("anno") or "")),
            _metric("Reddito", f"{_fmt_money(result.get('reddito'))}"),
            _metric("Compensi", f"{_fmt_money(result.get('compensi'))}"),
            _metric("Totale contributi", f"{_fmt_money(result.get('totale'))}"),
        ]
        contributi = dict(result.get("contributi") or {})
        tables.append(
            {
                "title": "Dettaglio contributi",
                "headers": ["Voce", "Importo"],
                "rows": [[str(key).replace("_", " ").title(), f"{_fmt_money(value)}"] for key, value in contributi.items()],
            }
        )
    elif tool_id == "prescrizione":
        metrics = [
            _metric("Termine", str(result.get("tipo_label") or "")),
            _metric("Decorrenza", _fmt_date_it(result.get("data_decorrenza"))),
            _metric("Scadenza", _fmt_date_it(result.get("data_scadenza")), f"{result.get('giorni_residui', 0)} giorni residui"),
            _metric("Dopo interruzione", _fmt_date_it(result.get("data_scadenza_post_interruzione")), f"{result.get('giorni_residui_post_interruzione', 0)} giorni residui"),
        ]
    elif tool_id == "danno_biologico":
        metrics = [
            _metric("Eta", str(result.get("eta") or "")),
            _metric("Danno IP", f"{_fmt_money(result.get('danno_ip'))}"),
            _metric("Totale biologico", f"{_fmt_money(result.get('totale_biologico'))}"),
            _metric("Totale complessivo", f"{_fmt_money(result.get('totale_comprensivo'))}"),
        ]
    elif tool_id == "imposta_registro":
        metrics = [
            _metric("Tipo atto", str(result.get("tipo_label") or "")),
            _metric("Imposta", f"{_fmt_money(result.get('imposta'))}"),
            _metric("Quota per parte", f"{_fmt_money(result.get('quota_parte'))}"),
            _metric("Aliquota", f"{_fmt_percent(result.get('aliquota_pct'))}%"),
        ]
    elif tool_id == "tfr":
        metrics = [
            _metric("Quota annua", f"{_fmt_money(result.get('quota_annua'))}"),
            _metric("Quota periodo", f"{_fmt_money(result.get('quota_periodo'))}", f"{result.get('anni_equivalenti') or 0} anni equivalenti"),
            _metric("Rivalutazione", f"{_fmt_money(result.get('rivalutazione'))}"),
            _metric("Totale lordo", f"{_fmt_money(result.get('totale_lordo'))}"),
        ]
    elif tool_id == "onorari_forensi":
        metrics = [
            _metric("Materia", str(result.get("materia_label") or "")),
            _metric("Grado", str(result.get("grado_label") or "")),
            _metric("Scaglione", str(result.get("scaglione") or "")),
            _metric(
                "Riepilogo suggerito",
                f"{_fmt_money((result.get('riepilogo_suggerito') or {}).get('totale_complessivo'))}",
                str(result.get("livello_suggerito") or ""),
            ),
        ]
        tables.append(
            {
                "title": "Fasi considerate",
                "headers": ["Fase", "Compenso"],
                "rows": [
                    [str(row.get("fase_label") or row.get("fase") or ""), f"{_fmt_money(row.get('compenso'))}"]
                    for row in list(result.get("fase_rows") or [])
                ],
            }
        )
        presidi = list(result.get("presidi_deontologici") or [])
        if presidi:
            tables.append(
                {
                    "title": "Presidi deontologici",
                    "headers": ["Presidio", "Stato", "Fonte"],
                    "rows": [
                        [
                            str(row.get("label") or ""),
                            str(row.get("status") or ""),
                            str(row.get("source") or ""),
                        ]
                        for row in presidi
                    ],
                }
            )
    elif tool_id == "custodia_cautelare":
        metrics = [
            _metric("Misura", str(result.get("tipo_misura_label") or "")),
            _metric("Interrogatorio entro", str(result.get("interrogatorio_entra_it") or "")),
            _metric("Riesame entro", str(result.get("riesame_entra_it") or "")),
            _metric("Deposito motivi", str(result.get("deposito_entra_it") or "")),
        ]
        tables.append(
            {
                "title": "Timeline",
                "headers": ["Passaggio", "Scadenza"],
                "rows": [
                    [str(row.get("label") or ""), _fmt_date_it(row.get("date"))]
                    for row in list(result.get("timeline") or [])
                ],
            }
        )
    elif tool_id == "prescrizione_penale":
        metrics = [
            _metric("Regime", str(result.get("regime_label") or "")),
            _metric("Termine base", f"{_fmt_percent(result.get('termine_base_anni'))} anni"),
            _metric("Prescrizione base", str(result.get("data_prescrizione_base_it") or "")),
            _metric("Prescrizione massima", str(result.get("data_prescrizione_massima_it") or "")),
        ]
    elif tool_id == "successione_legittima":
        metrics = [
            _metric("Asse", f"{_fmt_money(result.get('asse'))}"),
            _metric("Quote coperte", f"{_fmt_percent(result.get('quota_totale_percent'))}%"),
        ]
        tables.append(
            {
                "title": "Riparto quote",
                "headers": ["Soggetto", "Quota %", "Importo", "Per testa"],
                "rows": [
                    [
                        str(row.get("label") or ""),
                        f"{_fmt_percent(row.get('quota_percent'))}%",
                        f"{_fmt_money(row.get('importo'))}",
                        f"{_fmt_money(row.get('per_testa'))}",
                    ]
                    for row in list(result.get("rows") or [])
                ],
            }
        )
    elif tool_id == "cedolare_secca":
        metrics = [
            _metric("Aliquota", f"{_fmt_percent(result.get('aliquota'))}%"),
            _metric("Imposta annua", f"{_fmt_money(result.get('imposta_annua'))}"),
            _metric("Registro evitato", f"{_fmt_money(result.get('registro_evitato'))}"),
            _metric("Totale periodo", f"{_fmt_money(result.get('totale_periodo'))}"),
        ]
    elif tool_id == "indennita_licenziamento":
        metrics = [
            _metric("Regime", str(result.get("regime_label") or "")),
            _metric("Anzianita", str(result.get("anzianita") or "")),
            _metric("Mensilita", f"{_fmt_percent(result.get('mensilita'))}"),
            _metric("Importo", f"{_fmt_money(result.get('importo'))}"),
        ]
    elif tool_id == "piano_ammortamento":
        metrics = [
            _metric("Metodo", str(result.get("tipo_label") or "")),
            _metric("Numero rate", str(result.get("numero_rate") or "")),
            _metric("Rata iniziale", f"{_fmt_money(result.get('rata_iniziale'))}"),
            _metric("Totale interessi", f"{_fmt_money(result.get('totale_interessi'))}"),
        ]
        preview = list(result.get("preview_schedule") or result.get("schedule") or [])[:6]
        tables.append(
            {
                "title": "Prime rate",
                "headers": ["N.", "Data", "Rata", "Quota capitale", "Quota interessi", "Residuo"],
                "rows": [
                    [
                        str(row.get("numero") or ""),
                        _fmt_date_it(row.get("data")),
                        f"{_fmt_money(row.get('rata'))}",
                        f"{_fmt_money(row.get('quota_capitale'))}",
                        f"{_fmt_money(row.get('quota_interessi'))}",
                        f"{_fmt_money(row.get('residuo'))}",
                    ]
                    for row in preview
                ],
            }
        )

    elif tool_id == "interessi_acconti":
        metrics = [
            _metric("Regime", str(result.get("label") or "")),
            _metric("Acconti imputati", f"{_fmt_money(result.get('acconti_totali'))}", f"{result.get('numero_acconti', 0)} versamenti"),
            _metric("Residuo capitale", f"{_fmt_money(result.get('residuo_capitale'))}"),
            _metric("Residuo complessivo", f"{_fmt_money(result.get('totale_residuo'))}", f"interessi {_fmt_money(result.get('residuo_interessi'))}"),
        ]
        tables.append(
            {
                "title": "Imputazione degli acconti",
                "headers": ["Data", "Acconto", "A interessi", "A capitale", "Capitale residuo"],
                "rows": [
                    [
                        _fmt_date_it(row.get("data")),
                        f"{_fmt_money(row.get('importo'))}",
                        f"{_fmt_money(row.get('quota_interessi'))}",
                        f"{_fmt_money(row.get('quota_capitale'))}",
                        f"{_fmt_money(row.get('residuo_capitale'))}",
                    ]
                    for row in list(result.get("imputazioni") or [])
                ],
            }
        )
    elif tool_id == "maggior_danno":
        metrics = [
            _metric("Importo rivalutato", f"{_fmt_money(result.get('importo_rivalutato'))}", f"da {_fmt_money(result.get('importo_originale'))}"),
            _metric("Rivalutazione", f"{_fmt_money(result.get('rivalutazione'))}"),
            _metric("Interessi legali", f"{_fmt_money(result.get('totale_interessi'))}"),
            _metric("Totale dovuto", f"{_fmt_money(result.get('totale'))}"),
        ]
        tables.append(
            {
                "title": "Segmenti interessi",
                "headers": ["Periodo", "Giorni", "Tasso", "Base", "Interessi"],
                "rows": [
                    [
                        f"{_fmt_date_it(row.get('from'))} - {_fmt_date_it(row.get('to'))}",
                        str(row.get("days") or 0),
                        f"{_fmt_percent(row.get('rate'))}%",
                        f"{_fmt_money(row.get('base'))}",
                        f"{_fmt_money(row.get('interest'))}",
                    ]
                    for row in list(result.get("segments") or [])
                ],
            }
        )
    elif tool_id == "danno_parentale":
        metrics = [
            _metric("Categoria", str(result.get("categoria_label") or "")),
            _metric("Punti liquidati", f"{result.get('punti_liquidati', 0)}", f"massimo {result.get('punti_max', 0)}"),
            _metric("Valore punto", f"{_fmt_money(result.get('valore_punto'))}"),
            _metric("Importo", f"{_fmt_money(result.get('importo'))}"),
        ]
        tables.append(
            {
                "title": "Parametri della tabella a punti",
                "headers": ["Parametro", "Dato", "Punti", "Massimo"],
                "rows": [
                    [
                        str(row.get("label") or ""),
                        str(row.get("detail") or ""),
                        str(row.get("punti") or 0),
                        str(row.get("max") or 0),
                    ]
                    for row in list(result.get("parametri") or [])
                ],
            }
        )
    elif tool_id == "usufrutto":
        metrics = [
            _metric("Usufrutto", f"{_fmt_money(result.get('valore_usufrutto'))}", f"{result.get('percentuale_usufrutto', 0)}%"),
            _metric("Nuda proprietà", f"{_fmt_money(result.get('valore_nuda_proprieta'))}", f"{result.get('percentuale_nuda', 0)}%"),
            _metric("Coefficiente", str(result.get("coefficiente") or "")),
            _metric("Tasso legale", f"{_fmt_percent(result.get('tasso_legale'))}%"),
        ]
    elif tool_id == "quote_riserva":
        metrics = [
            _metric("Massa ex art. 556 c.c.", f"{_fmt_money(result.get('massa'))}"),
            _metric("Quota riservata", f"{result.get('quota_riservata_percent', 0)}%"),
            _metric("Disponibile", f"{_fmt_money(result.get('disponibile'))}", f"{result.get('disponibile_percent', 0)}%"),
        ]
        tables.append(
            {
                "title": "Quote di riserva",
                "headers": ["Legittimario", "% massa", "Importo", "Riferimento"],
                "rows": [
                    [
                        str(row.get("label") or ""),
                        f"{row.get('quota_percent', 0)}%",
                        f"{_fmt_money(row.get('importo'))}",
                        str(row.get("riferimento") or ""),
                    ]
                    for row in list(result.get("rows") or [])
                ],
            }
        )
    elif tool_id == "assegno_mantenimento":
        metrics = [
            _metric("Tipo", str(result.get("label") or "")),
            _metric("Stima mensile", f"{_fmt_money(result.get('stima_mensile'))}"),
            _metric("Stima annua", f"{_fmt_money(result.get('stima_annua'))}"),
        ]
        tables.append(
            {
                "title": "Criteri applicati",
                "headers": ["Criterio", "Dettaglio", "Importo progressivo"],
                "rows": [
                    [
                        str(row.get("label") or ""),
                        str(row.get("detail") or ""),
                        f"{_fmt_money(row.get('importo'))}",
                    ]
                    for row in list(result.get("criteri") or [])
                ],
            }
        )

    return {
        "metrics": metrics,
        "tables": tables,
        "preview_text": preview_text,
    }
