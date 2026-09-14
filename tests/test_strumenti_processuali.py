"""Strumenti processuali: perfezionamento della notifica, valore della causa, procedibilità.

Le attese sono ricavate dai testi di legge citati nei moduli, non dal
comportamento del codice: se una regola cambia, il test deve rompersi.
"""

from __future__ import annotations

import pytest

from pct.calcolatori._base import fmt_eur
from pct.calcolatori.perfezionamento_notifica import GIORNI_GIACENZA, GIORNI_IRREPERIBILE, calcola as notifica
from pct.calcolatori.procedibilita_adr import (
    MATERIE_MEDIAZIONE,
    PRIMO_INCONTRO_MAX_GIORNI,
    PRIMO_INCONTRO_MIN_GIORNI,
    SOGLIA_NEGOZIAZIONE,
    calcola as adr,
)
from pct.calcolatori.valore_causa import calcola as valore
from pct.strumenti_legali import GestioneStrumentiLegali


# --------------------------------------------------------------- formattazione

def test_gli_importi_escono_in_formato_italiano():
    """Il punto separa le migliaia e la virgola i decimali, come in un atto."""
    assert fmt_eur(30000) == "30.000,00"
    assert fmt_eur(1234567.891) == "1.234.567,89"
    assert fmt_eur(50000, 0) == "50.000"


# ------------------------------------------------- perfezionamento della notifica

def test_pec_il_notificante_si_libera_con_la_ricevuta_di_accettazione():
    esito = notifica({
        "not_canale": "pec",
        "not_data_invio": "2026-09-10", "not_ora_invio": "21:35",
        "not_data_consegna": "2026-09-10", "not_ora_consegna": "21:40",
    })
    assert esito["perfezionamento_notificante"] == "10/09/2026 alle 21:35"


def test_pec_dopo_le_21_il_destinatario_slitta_alle_7_del_giorno_dopo():
    """Art. 147, comma 3, c.p.c.: RdAC fra le 21 e le 7 → perfezionamento alle 7."""
    esito = notifica({
        "not_canale": "pec",
        "not_data_invio": "2026-09-10",
        "not_data_consegna": "2026-09-10", "not_ora_consegna": "21:40",
    })
    assert esito["perfezionamento_destinatario"] == "11/09/2026 alle 07:00"
    assert esito["differimento_ore_7"] is True


def test_pec_prima_delle_7_il_destinatario_slitta_alle_7_dello_stesso_giorno():
    esito = notifica({
        "not_canale": "pec",
        "not_data_invio": "2026-09-10",
        "not_data_consegna": "2026-09-11", "not_ora_consegna": "03:00",
    })
    assert esito["perfezionamento_destinatario"] == "11/09/2026 alle 07:00"


def test_pec_dentro_la_fascia_diurna_non_si_differisce():
    esito = notifica({
        "not_canale": "pec",
        "not_data_invio": "2026-09-10",
        "not_data_consegna": "2026-09-10", "not_ora_consegna": "10:00",
    })
    assert esito["perfezionamento_destinatario"] == "10/09/2026 alle 10:00"
    assert esito["differimento_ore_7"] is False


def test_pec_senza_ora_di_consegna_il_modulo_lo_dichiara():
    esito = notifica({"not_canale": "pec", "not_data_invio": "2026-09-10", "not_data_consegna": "2026-09-10"})
    assert any("non indicata" in nota for nota in esito["notes"])


def test_pec_la_consegna_non_puo_precedere_l_accettazione():
    with pytest.raises(ValueError, match="non può precedere"):
        notifica({"not_canale": "pec", "not_data_invio": "2026-09-10", "not_data_consegna": "2026-09-09"})


def test_posta_il_notificante_si_libera_alla_consegna_all_ufficiale_giudiziario():
    """Art. 149 c.p.c.: i due perfezionamenti sono scissi."""
    esito = notifica({
        "not_canale": "posta", "not_data_invio": "2026-09-01",
        "not_esito_posta": "consegnato", "not_data_consegna": "2026-09-05",
    })
    assert esito["perfezionamento_notificante"] == "01/09/2026"
    assert esito["perfezionamento_destinatario"] == "05/09/2026"


def test_posta_la_compiuta_giacenza_decorre_dalla_spedizione_dell_avviso():
    """Art. 8, comma 4, L. 890/1982: dieci giorni dalla spedizione della raccomandata."""
    esito = notifica({
        "not_canale": "posta", "not_data_invio": "2026-09-01",
        "not_esito_posta": "giacenza", "not_data_avviso": "2026-09-05",
    })
    assert GIORNI_GIACENZA == 10
    assert esito["perfezionamento_destinatario"] == "15/09/2026"


def test_posta_il_ritiro_anticipato_prevale_sulla_compiuta_giacenza():
    """Art. 8, comma 5, L. 890/1982."""
    esito = notifica({
        "not_canale": "posta", "not_data_invio": "2026-09-01",
        "not_esito_posta": "giacenza", "not_data_avviso": "2026-09-05", "not_data_ritiro": "2026-09-09",
    })
    assert esito["perfezionamento_destinatario"] == "09/09/2026"


def test_posta_il_ritiro_tardivo_non_sposta_il_perfezionamento():
    esito = notifica({
        "not_canale": "posta", "not_data_invio": "2026-09-01",
        "not_esito_posta": "giacenza", "not_data_avviso": "2026-09-05", "not_data_ritiro": "2026-09-20",
    })
    assert esito["perfezionamento_destinatario"] == "15/09/2026"


def test_posta_in_giacenza_senza_data_dell_avviso_il_calcolo_si_ferma():
    with pytest.raises(ValueError, match="compiuta giacenza"):
        notifica({"not_canale": "posta", "not_data_invio": "2026-09-01", "not_esito_posta": "giacenza"})


def test_art140_dieci_giorni_dalla_raccomandata_informativa():
    """Corte cost. 3/2010: ricevimento della raccomandata o dieci giorni dalla spedizione."""
    esito = notifica({"not_canale": "art140", "not_data_invio": "2026-09-01", "not_data_avviso": "2026-09-02"})
    assert esito["perfezionamento_destinatario"] == "12/09/2026"


def test_art143_ventesimo_giorno_dalle_formalita():
    """Art. 143, terzo comma, c.p.c."""
    esito = notifica({"not_canale": "art143", "not_data_invio": "2026-09-01"})
    assert GIORNI_IRREPERIBILE == 20
    assert esito["perfezionamento_destinatario"] == "21/09/2026"


def test_consegna_a_mani_i_due_perfezionamenti_coincidono():
    esito = notifica({"not_canale": "mani", "not_data_consegna": "2026-09-10", "not_ora_consegna": "11:00"})
    assert esito["perfezionamento_notificante"] == esito["perfezionamento_destinatario"] == "10/09/2026 alle 11:00"


def test_consegna_a_mani_fuori_orario_viene_segnalata():
    """Art. 147, primo comma, c.p.c.: non prima delle 7 né dopo le 21."""
    esito = notifica({"not_canale": "mani", "not_data_consegna": "2026-09-10", "not_ora_consegna": "22:30"})
    assert any("fuori dalla fascia" in nota for nota in esito["notes"])


def test_il_termine_decorre_dal_perfezionamento_per_il_destinatario():
    esito = notifica({
        "not_canale": "pec",
        "not_data_invio": "2026-09-10",
        "not_data_consegna": "2026-09-10", "not_ora_consegna": "10:00",
        "not_termine_durata": "30",
    })
    # Art. 155 c.p.c.: il giorno iniziale non si computa.
    assert esito["dies_a_quo"] == "10/09/2026"
    assert esito["scadenza"] == "12/10/2026"


def test_ora_malformata_viene_respinta_con_messaggio_leggibile():
    with pytest.raises(ValueError, match="formato 24 ore"):
        notifica({
            "not_canale": "pec", "not_data_invio": "2026-09-10",
            "not_data_consegna": "2026-09-10", "not_ora_consegna": "sera",
        })


# ------------------------------------------------------------- valore della causa

def test_gli_accessori_anteriori_si_sommano_al_capitale():
    """Art. 10, secondo comma, c.p.c."""
    esito = valore({
        "val_criterio": "somma_mobili", "val_importo": "12000",
        "val_interessi_scaduti": "800", "val_spese_danni": "300",
    })
    assert esito["valore"] == 13100.0


def test_le_quote_di_obbligazione_si_valutano_sull_intera_obbligazione():
    """Art. 11 c.p.c."""
    esito = valore({"val_criterio": "quote_obbligazione", "val_importo": "60000"})
    assert esito["valore"] == 60000.0
    assert esito["riferimento_normativo"] == "Art. 11 c.p.c."


def test_gli_alimenti_periodici_valgono_due_annualita():
    """Art. 13, primo comma, c.p.c."""
    assert valore({"val_criterio": "alimenti", "val_importo": "6000"})["valore"] == 12000.0


def test_la_rendita_perpetua_cumula_venti_annualita():
    """Art. 13, secondo comma, c.p.c."""
    assert valore({"val_criterio": "rendita_perpetua", "val_importo": "1200"})["valore"] == 24000.0


def test_la_rendita_temporanea_si_ferma_a_dieci_annualita():
    esito = valore({"val_criterio": "rendita_temporanea", "val_importo": "1000", "val_annualita": "15"})
    assert esito["valore"] == 10000.0
    assert any("massimo di 10" in nota for nota in esito["notes"])


@pytest.mark.parametrize(
    ("diritto", "atteso"),
    [("proprieta", 180000.0), ("usufrutto", 90000.0), ("servitu", 45000.0)],
)
def test_i_moltiplicatori_dell_immobile_seguono_l_articolo_15(diritto, atteso):
    """Art. 15, primo comma, c.p.c.: 200 proprietà, 100 diritti minori, 50 servitù."""
    esito = valore({"val_criterio": "immobile", "val_importo": "900", "val_diritto": diritto})
    assert esito["valore"] == atteso


def test_senza_rendita_l_immobile_rimanda_al_valore_indeterminabile():
    with pytest.raises(ValueError, match="indeterminabile"):
        valore({"val_criterio": "immobile", "val_importo": "0", "val_diritto": "proprieta"})


def test_l_opposizione_all_esecuzione_vale_il_credito_per_cui_si_procede():
    """Art. 17 c.p.c."""
    assert valore({"val_criterio": "opposizione_esecuzione", "val_importo": "25000"})["valore"] == 25000.0


# ------------------------------------------------------------ condizione di procedibilità

def test_le_materie_dell_articolo_5_sono_quelle_del_testo_di_legge():
    """L'elenco è chiuso: ventun materie nell'art. 5, comma 1, D.Lgs. 28/2010."""
    assert len(MATERIE_MEDIAZIONE) == 21
    for chiave in ("condominio", "locazione", "responsabilita_medica", "subfornitura"):
        assert chiave in MATERIE_MEDIAZIONE


def test_la_materia_dell_elenco_rende_la_mediazione_obbligatoria():
    esito = adr({"adr_materia": "condominio", "adr_procedimento": "ordinario"})
    assert esito["strumento"] == "mediazione"
    assert esito["condizione_procedibilita"] is True


def test_i_termini_della_mediazione_seguono_gli_articoli_6_e_8():
    esito = adr({"adr_materia": "condominio", "adr_procedimento": "ordinario", "adr_data_avvio": "2026-09-14"})
    date_passaggi = {voce["passaggio"]: voce["data"] for voce in esito["passaggi"]}
    assert PRIMO_INCONTRO_MIN_GIORNI == 20 and PRIMO_INCONTRO_MAX_GIORNI == 40
    assert date_passaggi[f"Primo incontro: non prima di {PRIMO_INCONTRO_MIN_GIORNI} giorni (art. 8, comma 1)"] == "04/10/2026"
    assert date_passaggi[f"Primo incontro: non oltre {PRIMO_INCONTRO_MAX_GIORNI} giorni (art. 8, comma 1)"] == "24/10/2026"
    # Art. 6: sei mesi dal deposito, non tre.
    assert date_passaggi["Scadenza della durata di 6 mesi (art. 6, commi 1 e 3)"] == "14/03/2027"


@pytest.mark.parametrize("procedimento", ["ingiunzione", "sfratto", "possessorio", "camera_consiglio"])
def test_i_procedimenti_dell_articolo_5_comma_6_escludono_la_mediazione(procedimento):
    esito = adr({"adr_materia": "locazione", "adr_procedimento": procedimento})
    assert esito["strumento"] == "nessuno"
    assert "art. 5, comma 6" in esito["motivo"]


def test_l_esclusione_temporanea_viene_dichiarata():
    esito = adr({"adr_materia": "locazione", "adr_procedimento": "sfratto"})
    assert any("mutamento del rito" in nota for nota in esito["notes"])


def test_il_danno_da_circolazione_passa_dalla_negoziazione_assistita():
    """Art. 3, comma 1, primo periodo, D.L. 132/2014."""
    esito = adr({"adr_materia": "circolazione", "adr_procedimento": "ordinario"})
    assert esito["strumento"] == "negoziazione"


def test_la_soglia_della_negoziazione_e_cinquantamila_euro():
    assert SOGLIA_NEGOZIAZIONE == 50000.0
    assert adr({"adr_materia": "pagamento_somme", "adr_procedimento": "ordinario", "adr_valore": "50000"})["strumento"] == "negoziazione"
    assert adr({"adr_materia": "pagamento_somme", "adr_procedimento": "ordinario", "adr_valore": "50000.01"})["strumento"] == "nessuno"


def test_il_contratto_con_il_consumatore_resta_fuori_dalla_negoziazione():
    esito = adr({
        "adr_materia": "pagamento_somme", "adr_procedimento": "ordinario",
        "adr_valore": "3000", "adr_consumatore": "1",
    })
    assert esito["strumento"] == "nessuno"
    assert "consumatori" in esito["motivo"]


def test_l_opposizione_esecutiva_esclude_anche_la_negoziazione():
    """Art. 3, comma 3, lett. c), D.L. 132/2014."""
    esito = adr({"adr_materia": "circolazione", "adr_procedimento": "opposizione_esecutiva"})
    assert esito["strumento"] == "nessuno"
    assert "art. 3, comma 3" in esito["motivo"]


def test_lo_sfratto_esclude_la_mediazione_ma_non_la_negoziazione():
    """Gli elenchi dell'art. 5, comma 6, e dell'art. 3, comma 3, non coincidono."""
    esito = adr({"adr_materia": "circolazione", "adr_procedimento": "sfratto"})
    assert esito["strumento"] == "negoziazione"


# -------------------------------------------------------------- prescrizione penale

def _prescrizione(**payload):
    return GestioneStrumentiLegali().calcola_prescrizione_penale(payload)


def test_il_delitto_non_scende_sotto_i_sei_anni():
    """Art. 157, primo comma, c.p."""
    esito = _prescrizione(presc_data_fatto="2024-03-15", presc_massimo_edittale_anni="5")
    assert esito["termine_base_anni"] == 6.0
    assert any("minimo di legge" in nota for nota in esito["notes"])


def test_la_contravvenzione_non_scende_sotto_i_quattro_anni():
    esito = _prescrizione(presc_data_fatto="2024-03-15", presc_massimo_edittale_anni="2", presc_contravvenzione="1")
    assert esito["termine_base_anni"] == 4.0


def test_il_raddoppio_opera_sul_termine_gia_portato_al_minimo():
    """Art. 157, commi 6 e 7, c.p.: si raddoppia il termine, non il massimo edittale."""
    esito = _prescrizione(presc_data_fatto="2024-03-15", presc_massimo_edittale_anni="5", presc_raddoppio="1")
    assert esito["termine_base_anni"] == 12.0


def test_l_ergastolo_non_produce_una_data_di_prescrizione():
    """Art. 157, ultimo comma, c.p."""
    esito = _prescrizione(presc_data_fatto="2024-03-15", presc_ergastolo="1")
    assert esito["imprescrittibile"] is True
    assert esito["data_prescrizione_base"] == ""


@pytest.mark.parametrize(
    ("campo", "valore_assurdo", "atteso"),
    [
        ("presc_massimo_edittale_anni", "10000", "ergastolo"),
        ("presc_coeff_interruzione", "10000", "art. 161"),
        ("presc_giorni_sospensione", "10000000", "vent'anni"),
    ],
)
def test_i_valori_fuori_scala_danno_un_messaggio_e_non_un_errore_interno(campo, valore_assurdo, atteso):
    """Prima di questo controllo un input assurdo usciva dal calendario con OverflowError."""
    payload = {"presc_data_fatto": "2024-03-15", "presc_massimo_edittale_anni": "5", campo: valore_assurdo}
    with pytest.raises(ValueError, match=atteso):
        GestioneStrumentiLegali().calcola_prescrizione_penale(payload)


# ------------------------------------------------- costituzione delle parti (nuovi modelli)

def _termine(modello: str, evento: str) -> dict:
    return GestioneStrumentiLegali().calcola_termini_processuali(
        {"term_modello": modello, "term_data_evento": evento}
    )


def test_l_attore_si_costituisce_entro_dieci_giorni_dalla_notificazione():
    """Art. 165, primo comma, c.p.c."""
    esito = _termine("CIV_COSTITUZIONE_ATTORE_165", "2026-09-14")
    assert esito["durata"] == 10
    assert esito["scadenza"] == "24/09/2026"
    assert esito["riferimento_normativo"] == "Art. 165, primo comma, c.p.c."


def test_il_convenuto_si_costituisce_settanta_giorni_prima_dell_udienza():
    """Art. 166 c.p.c.: termine a ritroso, con l'agosto escluso dal computo."""
    esito = _termine("CIV_COSTITUZIONE_CONVENUTO_166", "2026-11-20")
    assert esito["durata"] == 70
    assert "ritroso" in esito["direzione"].lower()
    assert esito["scadenza"] == "11/09/2026"
