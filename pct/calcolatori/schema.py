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
}


def schema_calcolatore(tool_id: str) -> Dict[str, Any] | None:
    return SCHEMI_CALCOLATORI.get(str(tool_id or "").strip())


def strumenti_con_schema() -> List[str]:
    return sorted(SCHEMI_CALCOLATORI)
