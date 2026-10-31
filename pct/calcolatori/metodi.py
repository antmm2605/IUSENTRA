"""Metodi di calcolo e cataloghi di opzioni della suite Strumenti legali: fonte unica.

Ogni strumento con modulo dichiarato (``pct.calcolatori.schema``) si calcola con un
metodo di ``GestioneStrumentiLegali``. La mappa vive nel dominio perché la usano la
pagina React, gli endpoint e Lex (``lex/calcoli_certi``): il modello non calcola,
chiede al software (V37, verifica del 31/10/2026).
"""
from __future__ import annotations

from typing import Any, Dict, List

TOOL_METHODS = {
    "uffici_competenti": "ricerca_uffici_competenti",
    "contributo_unificato": "calcola_contributo_unificato",
    "interessi": "calcola_interessi",
    "nota_credito": "genera_nota_precisazione_credito",
    "pignoramento": "simula_pignoramento",
    "ctu": "calcola_ctu",
    "rivalutazione_istat": "calcola_rivalutazione_istat",
    "canone_locazione": "calcola_adeguamento_canone",
    "usura": "verifica_soglia_usura",
    "contributi_cassa_forense": "calcola_contributi_cassa_forense",
    "tfr": "calcola_tfr",
    "onorari_forensi": "calcola_onorari_forensi",
    "custodia_cautelare": "calcola_custodia_cautelare",
    "prescrizione_penale": "calcola_prescrizione_penale",
    "termini_penali": "calcola_termini_penali",
    "indagini_preliminari": "calcola_indagini_preliminari",
    "custodia_durata": "calcola_custodia_durata",
    "improcedibilita_penale": "calcola_improcedibilita_penale",
    "successione_legittima": "calcola_successione_legittima",
    "cedolare_secca": "calcola_cedolare_secca",
    "indennita_licenziamento": "calcola_indennita_licenziamento",
    "piano_ammortamento": "calcola_piano_ammortamento",
    "prescrizione": "calcola_prescrizione",
    "danno_biologico": "calcola_danno_biologico",
    "danno_premorienza": "calcola_danno_premorienza",
    "danno_terminale": "calcola_danno_terminale",
    "lite_temeraria": "calcola_lite_temeraria",
    "consenso_informato": "calcola_consenso_informato",
    "diffamazione": "calcola_diffamazione",
    "capitalizzazione_rendita": "calcola_capitalizzazione_rendita",
    "imposta_registro": "calcola_imposta_registro",
    "interessi_acconti": "calcola_interessi_acconti",
    "maggior_danno": "calcola_maggior_danno",
    "crediti_lavoro": "calcola_crediti_lavoro",
    "danno_parentale": "calcola_danno_parentale",
    "usufrutto": "calcola_usufrutto",
    "quote_riserva": "calcola_quote_riserva",
    "assegno_mantenimento": "stima_assegno_mantenimento",
    "pena_riti_alternativi": "calcola_pena_riti_alternativi",
    "indennita_mediazione": "calcola_indennita_mediazione",
    "patrocinio_spese_stato": "verifica_patrocinio_spese_stato",
    "competenza_valore": "calcola_competenza_valore",
    "termini_processuali": "calcola_termini_processuali",
    "impugnazioni": "calcola_impugnazioni",
    "ravvedimento_operoso": "calcola_ravvedimento_operoso",
    "compenso_a_tempo": "calcola_compenso_a_tempo",
    "conta_giorni": "calcola_conta_giorni",
    "scorporo_iva": "calcola_scorporo_iva",
    "percentuali": "calcola_percentuali",
    "codice_fiscale": "calcola_codice_fiscale",
    "tabella_istat": "tabella_variazioni_istat",
    "tabella_tassi": "tabella_tassi_interesse",
    "taeg": "calcola_taeg",
    "surroga": "calcola_surroga",
    "rivalutazione_media": "calcola_rivalutazione_media",
    "rendimento_bot": "calcola_rendimento_bot",
    "pronti_contro_termine": "calcola_pronti_contro_termine",
    "grado_parentela": "calcola_grado_parentela",
    "perfezionamento_notifica": "calcola_perfezionamento_notifica",
    "valore_causa": "calcola_valore_causa",
    "procedibilita_adr": "calcola_procedibilita_adr",
    "reversibilita": "calcola_reversibilita",
    "imposte_successione": "calcola_imposte_successione",
    "valore_catastale": "calcola_valore_catastale",
    "imu": "calcola_imu",
    "imposte_compravendita": "calcola_imposte_compravendita",
    "riparto_spese": "calcola_riparto_spese",
    "categorie_catastali": "tabella_categorie_catastali",
    "irpef": "calcola_irpef_lorda",
    "acconto_imposte": "calcola_acconto_imposte",
    "rateazione_imposte": "calcola_rateazione_imposte",
    "detrazioni_familiari": "calcola_detrazioni_familiari",
    "detrazioni_reddito": "calcola_detrazioni_reddito",
    "detrazione_canone": "calcola_detrazione_canone",
    "regime_forfettario": "calcola_regime_forfettario",
    "fattura_agente": "calcola_fattura_agente",
    "prestazione_occasionale": "calcola_prestazione_occasionale",
}


def sorgenti_opzioni(gestore: Any) -> Dict[str, List[Dict[str, str]]]:
    """Cataloghi di opzioni già esposti dal dominio, indicizzati per nome.

    Gli schemi dichiarano ``options_from`` invece di congelare gli elenchi:
    materie e gradi del D.M. 55/2014 e categorie del contributo unificato
    restano una fonte sola, quella del gestore.
    """

    onorari = gestore.opzioni_onorari_forensi()
    return {
        "onorari_materie": list(onorari.get("materie", [])),
        "onorari_gradi": list(onorari.get("gradi", [])),
        "onorari_complessita": list(onorari.get("complessita", [])),
        "onorari_fasi": list(onorari.get("fasi", [])),
        "contributo_unificato_categorie": list(gestore.opzioni_contributo_unificato()),
        "contributo_unificato_valore": list(gestore.opzioni_valore_contributo_unificato()),
        "termini_processuali_modelli": list(gestore.opzioni_termini_processuali()),
    }


__all__ = ["TOOL_METHODS", "sorgenti_opzioni"]
