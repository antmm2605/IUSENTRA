"""Contratto di input dei calcolatori modulari, dichiarato una volta sola.

Ogni voce descrive i campi che ``calcola()`` legge dal payload: nome, etichetta
in italiano, tipo di controllo e opzioni ammesse. La dichiarazione vive accanto
ai calcolatori perché è parte del loro contratto, non una scelta grafica: la
shell React la usa per costruire il modulo e il backend la usa per sapere quali
strumenti sa già rendere senza la vista classica.

Uno strumento assente da questo registro resta pienamente utilizzabile nella
vista classica: la migrazione è incrementale e non toglie funzioni all'utente.
"""
from __future__ import annotations

from typing import Any, Dict, List

CampoSchema = Dict[str, Any]


def _numero(nome: str, etichetta: str, *, minimo: float = 0, passo: str = "0.01", aiuto: str = "") -> CampoSchema:
    return {"name": nome, "label": etichetta, "type": "number", "min": minimo, "step": passo, "help": aiuto}


def _intero(nome: str, etichetta: str, *, minimo: int = 0, massimo: int | None = None, aiuto: str = "") -> CampoSchema:
    campo: CampoSchema = {"name": nome, "label": etichetta, "type": "number", "min": minimo, "step": "1", "help": aiuto}
    if massimo is not None:
        campo["max"] = massimo
    return campo


def _scelta(nome: str, etichetta: str, opzioni: List[tuple[str, str]], *, aiuto: str = "") -> CampoSchema:
    return {
        "name": nome,
        "label": etichetta,
        "type": "select",
        "options": [{"value": valore, "label": testo} for valore, testo in opzioni],
        "help": aiuto,
    }


def _si_no(nome: str, etichetta: str, *, aiuto: str = "") -> CampoSchema:
    return _scelta(nome, etichetta, [("0", "No"), ("1", "Sì")], aiuto=aiuto)


def _data(nome: str, etichetta: str, *, aiuto: str = "") -> CampoSchema:
    return {"name": nome, "label": etichetta, "type": "date", "help": aiuto}


def _testo(nome: str, etichetta: str, *, aiuto: str = "") -> CampoSchema:
    return {"name": nome, "label": etichetta, "type": "text", "help": aiuto}


def _dinamico(nome: str, etichetta: str, sorgente: str, *, aiuto: str = "") -> CampoSchema:
    """Select le cui opzioni vivono già nel dominio e vanno risolte a runtime.

    Congelarle qui creerebbe un secondo elenco da tenere allineato: la voce
    dichiara solo il nome della sorgente (``options_from``) e il bridge React la
    risolve chiamando il gestore, così cataloghi come le materie del D.M.
    55/2014 o le categorie del contributo unificato restano una fonte sola.
    """

    return {"name": nome, "label": etichetta, "type": "select", "options_from": sorgente, "help": aiuto}


SCHEMI_CALCOLATORI: Dict[str, Dict[str, Any]] = {
    "pena_riti_alternativi": {
        "azione": "Calcola pena",
        "campi": [
            _intero("pena_anni", "Pena base — anni"),
            _intero("pena_mesi", "Mesi", massimo=11),
            _intero("pena_giorni", "Giorni", massimo=29),
            _scelta("pena_tipo_reato", "Tipo di reato", [("delitto", "Delitto"), ("contravvenzione", "Contravvenzione")]),
            _intero("pena_eta_imputato", "Età imputato", massimo=120, aiuto="Incide sui limiti della sospensione condizionale (art. 163 c.p.)."),
            _scelta(
                "pena_rito",
                "Rito",
                [
                    ("ordinario", "Rito ordinario"),
                    ("abbreviato", "Giudizio abbreviato (art. 442 c.p.p.)"),
                    ("patteggiamento", "Pena su richiesta (art. 444 c.p.p.)"),
                ],
            ),
            _scelta(
                "pena_frazione_patteggiamento",
                "Diminuzione concordata",
                [("un_terzo", "Un terzo (massima)"), ("un_quarto", "Un quarto"), ("un_quinto", "Un quinto")],
                aiuto="Rilevante solo con il patteggiamento.",
            ),
            _si_no("pena_attenuanti_generiche", "Attenuanti generiche (art. 62-bis c.p.)"),
            _intero("pena_reati_satellite", "Reati satellite"),
            _intero("pena_aumento_per_reato_giorni", "Aumento per reato (giorni)"),
            _si_no("pena_recidiva_reiterata", "Recidiva reiterata"),
            _si_no("pena_mancata_impugnazione", "Mancata impugnazione", aiuto="Ulteriore sesto ex art. 442, comma 2-bis, c.p.p."),
        ],
    },
    "indennita_mediazione": {
        "azione": "Calcola indennità",
        "campi": [
            _numero("med_valore", "Valore della lite"),
            _scelta("med_valore_tipo", "Tipo di valore", [("determinato", "Determinato"), ("indeterminabile", "Indeterminabile")]),
            _scelta(
                "med_regime",
                "Regime",
                [("volontaria", "Volontaria"), ("obbligatoria_demandata", "Obbligatoria o demandata")],
            ),
            _scelta(
                "med_esito",
                "Esito",
                [
                    ("primo_incontro_senza_accordo", "Primo incontro senza accordo"),
                    ("primo_incontro_con_accordo", "Primo incontro con accordo"),
                    ("incontri_successivi_senza_accordo", "Incontri successivi senza accordo"),
                    ("incontri_successivi_con_accordo", "Incontri successivi con accordo"),
                ],
            ),
            _si_no("med_art31", "Maggiorazione art. 31, comma 3"),
        ],
    },
    "quote_riserva": {
        "azione": "Calcola riserva",
        "campi": [
            _numero("ris_patrimonio", "Patrimonio relitto"),
            _numero("ris_debiti", "Debiti"),
            _numero("ris_donazioni", "Donazioni (donatum)"),
            _si_no("ris_coniuge", "Coniuge"),
            _intero("ris_figli", "Numero figli"),
            _si_no("ris_ascendenti", "Ascendenti"),
        ],
    },
    "usufrutto": {
        "azione": "Calcola valore",
        "campi": [
            _numero("usu_valore_piena", "Valore della piena proprietà"),
            _intero("usu_eta", "Età dell'usufruttuario", massimo=120),
            _numero("usu_quota_perc", "Quota in percentuale", passo="0.01", aiuto="Lasciare 100 per l'intera proprietà."),
        ],
    },
    "maggior_danno": {
        "azione": "Calcola maggior danno",
        "campi": [
            _numero("md_importo", "Importo del credito"),
            _scelta("md_tipo_indice", "Indice ISTAT", [("FOI", "FOI"), ("NIC", "NIC")]),
            _scelta("md_base_interessi", "Base degli interessi", [("rivalutato", "Capitale rivalutato"), ("nominale", "Capitale nominale")]),
            _intero("md_anno_base", "Anno iniziale", minimo=1947),
            _intero("md_mese_base", "Mese iniziale", minimo=1, massimo=12),
            _intero("md_anno_fine", "Anno finale", minimo=1947),
            _intero("md_mese_fine", "Mese finale", minimo=1, massimo=12),
        ],
    },
    "interessi_acconti": {
        "azione": "Calcola interessi",
        "campi": [
            _scelta("acc_tipo", "Tipo di interessi", [("legali", "Legali"), ("mora_commerciale", "Mora commerciale")]),
            _numero("acc_capitale", "Capitale"),
            _data("acc_data_inizio", "Data iniziale"),
            _data("acc_data_fine", "Data finale"),
            _testo("acc_acconti", "Acconti", aiuto="Una riga per acconto: data e importo, ad esempio 12/03/2025 1500,00"),
        ],
    },
    "assegno_mantenimento": {
        "azione": "Stima assegno",
        "campi": [
            _scelta("man_tipo", "Tipo di assegno", [("figli", "Mantenimento figli"), ("coniuge", "Assegno al coniuge")]),
            _numero("man_reddito_obbligato", "Reddito mensile obbligato"),
            _numero("man_reddito_beneficiario", "Reddito mensile beneficiario"),
            _intero("man_figli", "Numero figli"),
            _si_no("man_collocamento_paritetico", "Collocamento paritetico"),
            _si_no("man_casa_assegnata", "Casa familiare assegnata"),
            _intero("man_durata_matrimonio", "Durata del matrimonio (anni)"),
        ],
    },
    "danno_parentale": {
        "azione": "Calcola danno",
        "campi": [
            _scelta(
                "dp_categoria",
                "Rapporto con la vittima",
                [("nucleo_primario", "Genitore, figlio o coniuge"), ("altri_congiunti", "Fratello, sorella, nonno o nipote")],
            ),
            _intero("dp_eta_vittima", "Età della vittima", massimo=120),
            _intero("dp_eta_congiunto", "Età del congiunto", massimo=120),
            _si_no("dp_convivenza", "Convivenza"),
            _si_no("dp_unico_superstite", "Unico superstite"),
            _intero("dp_qualita_relazione", "Qualità della relazione", minimo=0, massimo=10, aiuto="Parametro di intensità del legame, da 0 a 10."),
        ],
    },
    "crediti_lavoro": {
        "azione": "Calcola rivalutazione e interessi",
        "campi": [
            _numero("lav_importo", "Credito di lavoro maturato"),
            _data("lav_data_maturazione", "Maturazione del diritto", aiuto="Decorrenza imposta dall'art. 429, comma 3, c.p.c."),
            _data("lav_data_liquidazione", "Liquidazione o pagamento"),
            _scelta(
                "lav_regime",
                "Regime del rapporto",
                [("privato", "Lavoro privato"), ("pubblico", "Pubblico impiego")],
                aiuto="Nel pubblico impiego rivalutazione e interessi non sono cumulabili (art. 22, comma 36, L. 724/1994).",
            ),
            _scelta("lav_tipo_indice", "Indice ISTAT", [("foi", "FOI"), ("nic", "NIC")]),
            _scelta(
                "lav_base_interessi",
                "Base degli interessi",
                [
                    ("rivalutato_progressivo", "Capitale progressivamente rivalutato"),
                    ("semisomma", "Semisomma"),
                    ("originario", "Capitale originario"),
                ],
            ),
        ],
    },
    "contributo_unificato": {
        "azione": "Calcola contributo",
        "campi": [
            _dinamico("cu_categoria", "Tipologia di procedimento", "contributo_unificato_categorie"),
            _scelta("cu_grado", "Grado", [("primo_grado", "Primo grado"), ("appello", "Appello"), ("cassazione", "Cassazione")]),
            _dinamico("cu_valore_tipo", "Tipo di valore", "contributo_unificato_valore"),
            _numero("cu_valore", "Valore della causa"),
            _si_no("cu_anticipazione_forfettaria", "Anticipazione forfettaria"),
            _intero("cu_numero_parti_ricorrenti", "Parti ricorrenti", minimo=1),
            _si_no("cu_sezione_specializzata_impresa", "Sezione specializzata impresa"),
            _si_no("cu_dati_obbligatori_mancanti", "Dati obbligatori mancanti", aiuto="Comporta l'aumento ex art. 13, comma 3-bis, D.P.R. 115/2002."),
        ],
    },
    "interessi": {
        "azione": "Calcola interessi",
        "campi": [
            _scelta("int_tipo", "Regime", [("legali", "Interessi legali"), ("mora_commerciale", "Mora commerciale D.Lgs. 231/2002")]),
            _numero("int_capitale", "Capitale"),
            _data("int_data_inizio", "Dal"),
            _data("int_data_fine", "Al"),
        ],
    },
    "nota_credito": {
        "azione": "Genera nota",
        "campi": [
            _testo("note_tribunale", "Tribunale o ufficio"),
            _testo("note_rg", "R.G."),
            _testo("note_creditore", "Creditore"),
            _testo("note_debitore", "Debitore"),
            _testo("note_titolo", "Titolo o oggetto"),
            _numero("note_capitale", "Capitale"),
            _scelta("note_interessi_tipo", "Interessi", [("legali", "Legali"), ("mora_commerciale", "Mora D.Lgs. 231/2002"), ("manuale", "Manuale")]),
            _numero("note_interessi_manual", "Interessi indicati manualmente"),
            _data("note_data_inizio", "Decorrenza"),
            _data("note_data_fine", "Fino al"),
            _numero("note_spese_vive", "Spese vive"),
            _numero("note_compensi", "Compensi"),
            _numero("note_cpa_perc", "CPA %"),
            _numero("note_iva_perc", "IVA %"),
            _numero("note_acconti", "Acconti"),
            _testo("note_luogo", "Luogo"),
            _data("note_data", "Data"),
            _testo("note_avvocato", "Difensore"),
        ],
    },
    "pignoramento": {
        "azione": "Simula quota",
        "campi": [
            _scelta("pig_tipo_reddito", "Reddito", [("stipendio", "Stipendio"), ("pensione", "Pensione")]),
            _scelta("pig_tipo_credito", "Tipo di credito", [("ordinario", "Ordinario"), ("esattoriale", "Esattoriale"), ("alimentare", "Alimentare")]),
            _numero("pig_importo_netto", "Netto mensile"),
            _numero("pig_aliquota_alimentare", "Aliquota credito alimentare %"),
        ],
    },
    "ctu": {
        "azione": "Calcola compenso",
        "campi": [
            _scelta("ctu_modalita", "Modalità", [("vacazioni", "Vacazioni"), ("manuale", "Onorario manuale")]),
            _numero("ctu_ore", "Ore", passo="0.25"),
            _intero("ctu_vacazioni", "Vacazioni"),
            _numero("ctu_onorario", "Onorario"),
            _numero("ctu_spese", "Spese documentate"),
            _numero("ctu_cpa_perc", "CPA %"),
            _numero("ctu_iva_perc", "IVA %"),
        ],
    },
    "rivalutazione_istat": {
        "azione": "Rivaluta importo",
        "campi": [
            _numero("riv_importo", "Importo"),
            _scelta("riv_tipo", "Indice ISTAT", [("nic", "NIC"), ("foi", "FOI")]),
            _intero("riv_anno_base", "Anno base", minimo=1947),
            _intero("riv_mese_base", "Mese base", minimo=1, massimo=12),
            _intero("riv_anno_fine", "Anno finale", minimo=1947),
            _intero("riv_mese_fine", "Mese finale", minimo=1, massimo=12),
        ],
    },
    "canone_locazione": {
        "azione": "Aggiorna canone",
        "campi": [
            _numero("loc_canone", "Canone mensile"),
            _intero("loc_perc_adeguamento", "Percentuale applicata", minimo=1, massimo=100, aiuto="75% è la quota ordinaria ex L. 431/1998."),
            _intero("loc_anno_base", "Anno base", minimo=1947),
            _intero("loc_mese_base", "Mese base", minimo=1, massimo=12),
            _intero("loc_anno_fine", "Anno di aggiornamento", minimo=1947),
            _intero("loc_mese_fine", "Mese di aggiornamento", minimo=1, massimo=12),
        ],
    },
    "usura": {
        "azione": "Verifica soglia",
        "campi": [
            _numero("usura_tasso", "Tasso applicato %"),
            _scelta(
                "usura_categoria",
                "Categoria",
                [
                    ("aperture_credito_cc_fino_5000", "Aperture in c/c fino a € 5.000"),
                    ("aperture_credito_cc_oltre_5000", "Aperture in c/c oltre € 5.000"),
                    ("credito_personale", "Credito personale"),
                    ("credito_finalizzato", "Credito finalizzato"),
                    ("mutui_ipotecari_fisso", "Mutui ipotecari a tasso fisso"),
                    ("mutui_ipotecari_variabile", "Mutui ipotecari a tasso variabile"),
                    ("carte_credito_revolving", "Carte di credito revolving"),
                ],
            ),
            _data("usura_data", "Data dell'operazione"),
        ],
    },
    "contributi_cassa_forense": {
        "azione": "Calcola contributi",
        "campi": [
            _intero("cf_anno", "Anno", minimo=2000),
            _numero("cf_reddito", "Reddito netto professionale"),
            _numero("cf_compensi", "Compensi lordi fatturati"),
        ],
    },
    "prescrizione": {
        "azione": "Calcola scadenza",
        "campi": [
            _scelta(
                "presc_tipo",
                "Tipologia",
                [
                    ("ordinaria_10", "Ordinaria — 10 anni"),
                    ("quinquennale_5", "Quinquennale — 5 anni"),
                    ("extracontrattuale_5", "Extracontrattuale — 5 anni"),
                    ("cambiari_3", "Cambiali e assegni — 3 anni"),
                    ("assicurazioni_2", "Assicurazioni — 2 anni"),
                    ("breve_1", "Breve — 1 anno"),
                ],
            ),
            _data("presc_data_decorrenza", "Data di decorrenza"),
            _data("presc_atto_interruttivo", "Atto interruttivo"),
            _testo("presc_descrizione", "Descrizione della pratica o del credito"),
        ],
    },
    "danno_biologico": {
        "azione": "Calcola danno",
        "campi": [
            _intero("db_eta", "Età", minimo=0, massimo=120),
            _numero("db_perc_ip", "Invalidità permanente %"),
            _intero("db_giorni_itt", "Giorni di inabilità totale"),
            _intero("db_giorni_itp", "Giorni di inabilità parziale"),
            _scelta("db_perc_itp", "Percentuale ITP", [("25", "25%"), ("50", "50%"), ("75", "75%")]),
            _numero("db_personalizzazione", "Personalizzazione %"),
            _si_no("db_includi_morale", "Includi danno morale"),
        ],
    },
    "imposta_registro": {
        "azione": "Calcola imposta",
        "campi": [
            _scelta(
                "reg_tipo_atto",
                "Tipo di atto",
                [
                    ("sentenza_condanna", "Sentenza di condanna"),
                    ("sentenza_immobili", "Sentenza su trasferimento immobili"),
                    ("decreto_ingiuntivo", "Decreto ingiuntivo"),
                    ("decreto_ingiuntivo_definitivo", "Decreto ingiuntivo definitivo"),
                    ("verbale_conciliazione", "Verbale di conciliazione"),
                    ("lodo_arbitrale", "Lodo arbitrale"),
                    ("sentenza_separazione", "Separazione o divorzio"),
                ],
            ),
            _numero("reg_valore", "Valore dell'atto"),
            _intero("reg_parti", "Numero di parti", minimo=1),
        ],
    },
    "tfr": {
        "azione": "Calcola TFR",
        "campi": [
            _numero("tfr_retribuzione_annua", "Retribuzione annua lorda"),
            _intero("tfr_anni_servizio", "Anni di servizio"),
            _intero("tfr_mesi_servizio", "Mesi di servizio", massimo=11),
            _numero("tfr_inflazione_perc", "Inflazione %"),
            _numero("tfr_anticipazioni", "Anticipazioni erogate"),
            _numero("tfr_montante_pregresso", "Montante pregresso da rivalutare"),
        ],
    },
    "onorari_forensi": {
        "azione": "Calcola onorari",
        "campi": [
            _dinamico("onorari_materia", "Materia", "onorari_materie"),
            _dinamico("onorari_grado", "Grado", "onorari_gradi"),
            _numero("onorari_valore", "Valore della controversia"),
            _dinamico("onorari_complessita", "Complessità", "onorari_complessita"),
            _si_no("onorari_bonus_telematico", "Bonus telematico"),
            _scelta("onorari_includi_spese_generali", "Spese generali", [("1", "Includi"), ("0", "Escludi")]),
            _si_no("onorari_cliente_qualificato", "Cliente soggetto a equo compenso"),
            _si_no("onorari_convenzione_predisposta_avvocato", "Accordo predisposto dallo studio"),
            _si_no("onorari_equo_compenso_verificato", "Equo compenso verificato"),
            _si_no("onorari_informativa_scritta", "Informativa scritta"),
        ],
    },
    "custodia_cautelare": {
        "azione": "Calcola termini",
        "campi": [
            _scelta("custodia_tipo_misura", "Tipo di misura", [("carcere", "Custodia in carcere"), ("domiciliari", "Arresti domiciliari"), ("altro", "Altra misura")]),
            _data("custodia_data_esecuzione", "Data di esecuzione"),
            _data("custodia_data_istanza_riesame", "Data istanza di riesame"),
            _data("custodia_data_decisione_riesame", "Data decisione del riesame"),
        ],
    },
    "prescrizione_penale": {
        "azione": "Calcola termine",
        "campi": [
            _data("presc_data_fatto", "Data del fatto"),
            _intero("presc_massimo_edittale_anni", "Massimo edittale — anni"),
            _intero("presc_massimo_edittale_mesi", "Mesi", massimo=11),
            _si_no("presc_contravvenzione", "Contravvenzione"),
            _numero("presc_coeff_interruzione", "Coefficiente di interruzione", minimo=1, passo="0.01"),
            _intero("presc_giorni_sospensione", "Giorni di sospensione"),
        ],
    },
    "successione_legittima": {
        "azione": "Calcola quote",
        "campi": [
            _numero("successione_asse", "Asse ereditario"),
            _si_no("successione_coniuge", "Coniuge"),
            _intero("successione_figli", "Figli"),
            _intero("successione_ascendenti", "Ascendenti"),
            _intero("successione_fratelli", "Fratelli"),
        ],
    },
    "cedolare_secca": {
        "azione": "Calcola imposta",
        "campi": [
            _numero("cedolare_canone_annuo", "Canone annuo"),
            _scelta("cedolare_aliquota", "Aliquota", [("21", "21%"), ("10", "10%")]),
            _intero("cedolare_annualita", "Annualità", minimo=1),
        ],
    },
    "indennita_licenziamento": {
        "azione": "Calcola indennità",
        "campi": [
            _numero("lic_retribuzione_mensile", "Retribuzione mensile"),
            _intero("lic_anni_servizio", "Anni di servizio"),
            _intero("lic_mesi_servizio", "Mesi di servizio", massimo=11),
            _scelta("lic_regime", "Regime", [("jobs_act", "Tutele crescenti"), ("piccola_impresa", "Piccola impresa"), ("preavviso", "Preavviso")]),
            _numero("lic_mensilita_preavviso", "Mensilità di preavviso", passo="0.5"),
        ],
    },
    "patrocinio_spese_stato": {
        "azione": "Verifica ammissibilità",
        "campi": [
            _scelta(
                "pat_processo",
                "Tipo di processo",
                [
                    ("civile", "Civile, amministrativo, contabile o tributario"),
                    ("penale", "Penale"),
                ],
                aiuto="Nel penale i limiti sono elevati per ogni familiare convivente (art. 92 D.P.R. 115/2002).",
            ),
            _numero("pat_reddito_richiedente", "Reddito imponibile del richiedente"),
            _numero(
                "pat_redditi_conviventi",
                "Redditi dei familiari conviventi",
                aiuto="Somma dei redditi degli altri componenti del nucleo convivente (art. 76, comma 2).",
            ),
            _intero("pat_familiari_conviventi", "Familiari conviventi", aiuto="Numero di conviventi oltre al richiedente."),
            _si_no(
                "pat_solo_reddito_personale",
                "Solo reddito personale",
                aiuto="Diritti della personalità o conflitto di interessi con i conviventi (art. 76, comma 4).",
            ),
            _data("pat_data_riferimento", "Data di riferimento", aiuto="La soglia cambia con i decreti di adeguamento biennale."),
        ],
    },
    "competenza_valore": {
        "azione": "Individua il giudice",
        "campi": [
            _scelta(
                "comp_materia",
                "Tipo di causa",
                [
                    ("beni_mobili", "Cause relative a beni mobili"),
                    ("danno_circolazione", "Danno da circolazione di veicoli e natanti"),
                ],
            ),
            _numero("comp_valore", "Valore della causa", aiuto="Determinato secondo gli artt. 10 e seguenti c.p.c."),
            _data(
                "comp_data_introduzione",
                "Instaurazione del procedimento",
                aiuto="Le soglie elevate valgono per i procedimenti instaurati dopo il 28 febbraio 2023.",
            ),
        ],
    },
    "termini_processuali": {
        "azione": "Calcola scadenza",
        "campi": [
            _dinamico("term_modello", "Modello di termine", "termini_processuali_modelli"),
            _data("term_data_evento", "Data dell'evento", aiuto="Notifica, deposito o udienza a seconda del modello."),
            _si_no(
                "term_urgente",
                "Materia urgente",
                aiuto="Esclude la sospensione feriale dal 1 al 31 agosto (L. 742/1969).",
            ),
            _intero(
                "term_valore_personalizzato",
                "Durata personalizzata",
                aiuto="Lascia vuoto o 0 per usare la durata del modello.",
            ),
            _testo("term_riferimento", "Riferimento di pratica", aiuto="R.G. o riferimento interno, riportato nell'esito."),
        ],
    },
    "piano_ammortamento": {
        "azione": "Crea piano",
        "campi": [
            _numero("amm_capitale", "Capitale"),
            _numero("amm_tasso_annuo", "Tasso annuo %"),
            _intero("amm_durata_anni", "Durata in anni", minimo=1),
            _scelta("amm_rate_anno", "Rate per anno", [("12", "12"), ("6", "6"), ("4", "4"), ("2", "2"), ("1", "1")]),
            _scelta("amm_tipo", "Metodo", [("francese", "Francese"), ("italiano", "Italiano")]),
            _data("amm_data_prima_rata", "Prima rata"),
        ],
    },
}


def schema_calcolatore(tool_id: str) -> Dict[str, Any] | None:
    return SCHEMI_CALCOLATORI.get(str(tool_id or "").strip())


def strumenti_con_schema() -> List[str]:
    return sorted(SCHEMI_CALCOLATORI)
