"""Tabelle di liquidazione del danno biologico: dati, scelta del regime, calcolo.

I valori attesi non sono inventati: sono le celle pubblicate nell'allegato II
del D.P.R. 13 gennaio 2025 n. 12, i coefficienti dell'art. 139 D.Lgs. 209/2005
e le celle della griglia delle tabelle milanesi edizione 2024.
"""
from __future__ import annotations

from datetime import date

import pytest

from pct.calcolatori.danno_biologico import art139, calcola, milano, regime, tabelle, tun
from pct.strumenti_legali import GestioneStrumentiLegali


# ── Integrità dei dati tabellari ──────────────────────────────────────────


def test_tabella_unica_nazionale_copre_tutti_i_punti_e_le_eta():
    dati = tabelle.carica(tabelle.TUN_2025)
    biologico = tabelle.mappa_numerica(dati, "coefficiente_moltiplicatore_biologico")
    morale = tabelle.mappa_terne(dati, "coefficiente_moltiplicatore_morale")
    eta = tabelle.mappa_numerica(dati, "coefficiente_riduzione_eta")

    assert sorted(biologico) == list(range(10, 101))
    assert sorted(morale) == list(range(10, 101))
    assert sorted(eta) == list(range(1, 101))
    # Il coefficiente del punto cresce, quello dell'età decresce.
    assert all(biologico[p] < biologico[p + 1] for p in range(10, 100))
    assert all(eta[e] >= eta[e + 1] for e in range(1, 100))
    for minimo, medio, massimo in morale.values():
        assert minimo < medio < massimo


def test_tabelle_milanesi_coprono_tutti_i_punti_e_le_eta():
    dati = tabelle.carica(tabelle.MILANO_2024)
    assert sorted(int(k) for k in dati["punti"]) == list(range(1, 101))
    assert sorted(tabelle.mappa_numerica(dati, "demoltiplicatore_eta")) == list(range(1, 101))
    for punto in dati["punti"].values():
        # La colonna B è la percentuale dichiarata della colonna A.
        atteso = round(punto["biologico"] * punto["sofferenza_pct"] / 100.0, 2)
        assert abs(punto["sofferenza"] - atteso) <= 0.02


def test_ogni_tabella_dichiara_la_propria_fonte_ufficiale():
    for identificativo in (tabelle.ART_139, tabelle.TUN_2025, tabelle.MILANO_2024):
        fonte = tabelle.fonte(identificativo)
        assert fonte.riferimento_normativo
        assert fonte.url_ufficiale.startswith("https://")
        assert fonte.data_consultazione


def test_i_decreti_dell_articolo_139_sono_in_ordine_di_decorrenza():
    decreti = tabelle.carica(tabelle.ART_139)["decreti_aggiornamento"]
    decorrenze = [d["decorrenza"] for d in decreti]
    assert decorrenze == sorted(decorrenze)
    for decreto in decreti:
        assert decreto["gazzetta"]
        assert decreto["primo_punto"] > 0
        assert decreto["giorno_inabilita_assoluta"] > 0


# ── Riproduzione delle griglie pubblicate ────────────────────────────────


# Celle dell'allegato II del D.P.R. 12/2025, tabella 1 (danno biologico),
# calcolate sul valore del primo punto di 947,30 € usato dal decreto.
_PRIMO_PUNTO_ALLEGATO_II = 947.30


@pytest.mark.parametrize(
    "punti,eta,atteso",
    [
        (10, 1, 26_124),
        (10, 10, 24_948),
        (20, 1, 79_242),
        (26, 1, 121_311),
        (26, 10, 115_852),
        (40, 1, 245_554),
        (40, 10, 234_504),
        (71, 10, 591_767),
        (71, 1, 619_652),
        (100, 1, 1_037_028),
        (100, 10, 990_362),
    ],
)
def test_griglia_del_dpr_12_2025_riprodotta_dai_coefficienti(punti, eta, atteso):
    assert tun.danno_biologico(punti, eta, _PRIMO_PUNTO_ALLEGATO_II) == atteso


def test_valore_del_punto_del_dpr_12_2025():
    # Allegato II, colonna "valore del punto": 2.612,40 € per dieci punti.
    assert tun.valore_punto(10, _PRIMO_PUNTO_ALLEGATO_II) == 2_612.40
    assert tun.valore_punto(26, _PRIMO_PUNTO_ALLEGATO_II) == 4_665.79
    assert tun.valore_punto(40, _PRIMO_PUNTO_ALLEGATO_II) == 6_138.85
    assert tun.valore_punto(71, _PRIMO_PUNTO_ALLEGATO_II) == 8_727.49
    assert tun.valore_punto(100, _PRIMO_PUNTO_ALLEGATO_II) == 10_370.28


def test_incremento_morale_del_dpr_12_2025():
    # Tavola 2: per dieci punti l'incremento minimo è il 21 per cento.
    assert tun.valore_punto_morale(10, _PRIMO_PUNTO_ALLEGATO_II, "minimo") == 548.60
    biologico = tun.danno_biologico(10, 10, _PRIMO_PUNTO_ALLEGATO_II)
    morale = tun.danno_morale(10, 10, _PRIMO_PUNTO_ALLEGATO_II, "minimo")
    assert biologico == 24_948
    assert morale == 5_239
    assert biologico + morale == 30_187


@pytest.mark.parametrize(
    "punti,eta,atteso",
    [
        (1, 1, 1_742),
        (1, 10, 1_663),
        (26, 1, 167_180),
        (100, 1, 1_436_820),
        (100, 100, 725_594),
    ],
)
def test_griglia_delle_tabelle_milanesi_2024(punti, eta, atteso):
    assert milano.danno_permanente(punti, eta)["totale"] == atteso


def test_valore_pro_die_delle_tabelle_milanesi_2024():
    assert milano.valore_giorno_inabilita_totale() == 115.00
    assert milano.danno_temporaneo(10, 50.0) == 575.00


# ── Art. 139: coefficienti e decreti ─────────────────────────────────────


def test_coefficienti_del_comma_6_dell_articolo_139():
    attesi = {1: 1.0, 2: 1.1, 3: 1.2, 4: 1.3, 5: 1.5, 6: 1.7, 7: 1.9, 8: 2.1, 9: 2.3}
    for punti, atteso in attesi.items():
        assert art139.coefficiente_punto(punti) == atteso


def test_riduzione_per_eta_dell_articolo_139():
    # Nessuna riduzione fino al decimo anno, poi mezzo punto percentuale l'anno.
    assert art139.coefficiente_eta(0) == 1.0
    assert art139.coefficiente_eta(10) == 1.0
    assert art139.coefficiente_eta(11) == pytest.approx(0.995)
    assert art139.coefficiente_eta(40) == pytest.approx(0.85)


def test_decreto_vigente_e_l_ultimo_con_decorrenza_utile():
    assert art139.decreto_vigente(date(2026, 9, 13))["primo_punto"] == 988.45
    assert art139.decreto_vigente(date(2026, 9, 13))["giorno_inabilita_assoluta"] == 57.64
    # D.M. 16/07/2024 (G.U. n. 173 del 25/07/2024) e D.M. 18/07/2025 (G.U. n. 176 del 31/07/2025).
    assert art139.decreto_vigente(date(2024, 6, 1))["primo_punto"] == 947.30
    assert art139.decreto_vigente(date(2025, 6, 1))["primo_punto"] == 963.40
    assert art139.decreto_vigente(date(2024, 3, 31))["primo_punto"] == 939.78
    # Prima della prima decorrenza si usa comunque il decreto più antico noto.
    assert art139.decreto_vigente(date(2005, 1, 1))["primo_punto"] == 688.28


def test_danno_permanente_dell_articolo_139():
    # 988,45 € x coefficiente 1,7 x 6 punti x riduzione 0,875 (età 35).
    assert art139.danno_permanente(6, 35, 988.45) == 8_821.92


# ── Scelta del regime ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ambito,punti,giorno,atteso",
    [
        ("circolazione", 9, date(2026, 1, 1), regime.REGIME_ART_139),
        ("circolazione", 10, date(2026, 1, 1), regime.REGIME_TUN),
        ("circolazione", 10, date(2025, 3, 5), regime.REGIME_TUN),
        ("circolazione", 10, date(2025, 3, 4), regime.REGIME_MILANO),
        ("sanitaria", 4, date(2026, 1, 1), regime.REGIME_ART_139),
        ("sanitaria", 60, date(2026, 1, 1), regime.REGIME_TUN),
        ("civile", 4, date(2026, 1, 1), regime.REGIME_MILANO),
        ("civile", 60, date(2026, 1, 1), regime.REGIME_MILANO),
    ],
)
def test_scelta_della_tabella_per_ambito_punti_e_data(ambito, punti, giorno, atteso):
    assert regime.scegli(ambito, punti, giorno).codice == atteso


# ── Calcolo completo ─────────────────────────────────────────────────────


def _payload(**extra):
    base = {
        "db_ambito": "circolazione",
        "db_data_sinistro": "2026-01-15",
        "db_data_liquidazione": "2026-09-13",
        "db_eta": 40,
        "db_perc_ip": 35,
        "db_giorni_itt": 30,
        "db_giorni_itp": 60,
        "db_perc_itp": 50,
        "db_morale_livello": "medio",
        "db_personalizzazione": 0,
    }
    base.update(extra)
    return base


def test_la_data_del_sinistro_e_obbligatoria():
    with pytest.raises(ValueError, match="data del sinistro"):
        calcola(_payload(db_data_sinistro=""))


def test_la_liquidazione_non_puo_precedere_il_sinistro():
    with pytest.raises(ValueError, match="non puo' precedere"):
        calcola(_payload(db_data_sinistro="2026-05-01", db_data_liquidazione="2026-01-01"))


def test_calcolo_con_tabella_unica_nazionale():
    risultato = calcola(_payload())
    assert risultato["regime"] == regime.REGIME_TUN
    # Liquidazione al 13/09/2026: tavola 1.B del D.M. MIMIT 28/09/2026 (G.U. n. 235
    # del 09/10/2026, 26A05220), in vigore dal mese di aprile 2026; prima il test
    # confrontava con la tavola del testo originario del D.P.R. 12/2025, superata.
    assert risultato["danno_permanente"] == tun.danno_biologico(35, 40, 988.45, date(2026, 9, 13))
    assert risultato["danno_permanente"] != tun.danno_biologico(35, 40, 988.45)
    assert risultato["danno_morale"] > 0
    assert risultato["subtotale"] == pytest.approx(
        risultato["danno_permanente"] + risultato["danno_morale"] + risultato["danno_temporaneo"]
    )
    assert risultato["totale"] == risultato["subtotale"]
    identificativi = [t["id"] for t in risultato["tabelle_applicate"]]
    assert identificativi == [tabelle.TUN_2025, tabelle.ART_139]


def test_calcolo_con_articolo_139_non_aggiunge_danno_morale():
    risultato = calcola(_payload(db_perc_ip=6))
    assert risultato["regime"] == regime.REGIME_ART_139
    assert risultato["danno_morale"] == 0.0
    assert risultato["personalizzazione_massima_permanente_pct"] == 20


def test_macrolesione_anteriore_al_5_marzo_2025_usa_le_tabelle_milanesi():
    risultato = calcola(_payload(db_data_sinistro="2024-11-01"))
    assert risultato["regime"] == regime.REGIME_MILANO
    assert any("5 marzo 2025" in avviso for avviso in risultato["warnings"])


def test_la_personalizzazione_e_limitata_dal_tetto_della_tabella():
    risultato = calcola(_payload(db_personalizzazione=90))
    assert risultato["personalizzazione_pct"] == 30
    assert any("supera il limite" in avviso for avviso in risultato["warnings"])
    # Sul temporaneo resta il tetto dell'art. 139, comma 3.
    assert risultato["personalizzazione_massima_temporanea_pct"] == 20


def test_ogni_voce_di_dettaglio_dichiara_il_proprio_criterio():
    risultato = calcola(_payload(db_personalizzazione=10))
    assert risultato["dettaglio"]
    for voce in risultato["dettaglio"]:
        assert voce["voce"] and voce["criterio"]
        assert isinstance(voce["importo"], float)


def test_il_totale_è_la_somma_delle_voci_di_dettaglio():
    risultato = calcola(_payload(db_personalizzazione=15))
    somma = round(sum(voce["importo"] for voce in risultato["dettaglio"]), 2)
    assert somma == pytest.approx(risultato["totale"], abs=0.02)


def test_eta_zero_usa_il_coefficiente_pieno():
    assert tun.coefficiente_eta(0) == tun.coefficiente_eta(1) == 1.0
    assert milano.demoltiplicatore_eta(0) == milano.demoltiplicatore_eta(1) == 1.0


# ── Tavola 1.B aggiornata dai decreti MIMIT (art. 1, comma 2, D.P.R. 12/2025) ──
#
# Valori trascritti dai PDF ufficiali della Gazzetta Ufficiale: testo originario
# (G.U. n. 40 del 18/02/2025, S.O. n. 4/L), D.M. 10/12/2025 (G.U. n. 299 del
# 27/12/2025, S.O. n. 41, 25A06873) e D.M. 28/09/2026 (G.U. n. 235 del
# 09/10/2026, S.O. n. 41, 26A05220).

_ORIGINARIO = date(2025, 3, 5)
_DM_2025 = date(2025, 6, 1)
_DM_2026 = date(2026, 10, 31)


def test_versioni_della_tavola_1b_complete_e_in_ordine():
    versioni = tun.versioni_tavola_eta()
    assert [v["decorrenza"] for v in versioni] == ["2025-03-05", "2025-04-01", "2026-04-01"]
    assert [v.get("codice_redazionale") for v in versioni[1:]] == ["25A06873", "26A05220"]
    for versione in versioni:
        assert versione["url_ufficiale"].startswith("https://www.gazzettaufficiale.it/eli/gu/")
        assert versione["gazzetta"]
        mappa = tabelle.mappa_numerica(versione, "coefficiente_riduzione_eta")
        assert sorted(mappa) == list(range(1, 101))
        assert mappa[1] == 1.0
        assert all(mappa[e] >= mappa[e + 1] for e in range(1, 100))


@pytest.mark.parametrize(
    "giorno,atteso",
    [
        (_DM_2025, {7: 0.97, 30: 0.857, 60: 0.711, 100: 0.533}),
        (_DM_2026, {7: 0.971, 30: 0.858, 60: 0.714, 100: 0.542}),
        (_ORIGINARIO, {7: 0.97, 30: 0.856, 60: 0.708, 100: 0.522}),
    ],
)
def test_coefficienti_eta_pubblicati_per_ciascuna_versione(giorno, atteso):
    for eta, coefficiente in atteso.items():
        assert tun.coefficiente_eta(eta, giorno) == coefficiente


@pytest.mark.parametrize(
    "giorno,decorrenza",
    [
        (None, "2025-03-05"),
        (date(2025, 3, 31), "2025-03-05"),
        (date(2025, 4, 1), "2025-04-01"),
        (date(2026, 3, 31), "2025-04-01"),
        (date(2026, 4, 1), "2026-04-01"),
        (date(2026, 10, 31), "2026-04-01"),
    ],
)
def test_si_applica_la_tavola_vigente_alla_data(giorno, decorrenza):
    assert tun.versione_tavola_eta(giorno)["decorrenza"] == decorrenza


# Celle dell'allegato II, tabella 1 (solo danno biologico), dei due decreti.
@pytest.mark.parametrize(
    "giorno,primo_punto,punti,eta,valore_del_punto,atteso",
    [
        (_DM_2025, 963.40, 10, 1, 2_656.80, 26_568),
        (_DM_2025, 963.40, 10, 30, 2_656.80, 22_769),
        (_DM_2025, 963.40, 26, 40, 4_745.09, 99_685),
        (_DM_2025, 963.40, 100, 100, 10_546.53, 562_130),
        (_DM_2026, 988.45, 10, 7, 2_725.88, 26_468),
        (_DM_2026, 988.45, 10, 30, 2_725.88, 23_388),
        (_DM_2026, 988.45, 71, 10, 9_106.61, 618_120),
        (_DM_2026, 988.45, 100, 100, 10_820.76, 586_485),
        # Prodotto esatto 173.695,50 €: pubblicato 173.695.
        (_DM_2026, 988.45, 44, 90, 6_806.25, 173_695),
        # Prodotto esatto 368.880,50 €: pubblicato 368.880.
        (_DM_2026, 988.45, 50, 1, 7_377.61, 368_880),
    ],
)
def test_griglie_dei_decreti_di_aggiornamento(giorno, primo_punto, punti, eta, valore_del_punto, atteso):
    assert tun.valore_punto(punti, primo_punto) == valore_del_punto
    assert tun.danno_biologico(punti, eta, primo_punto, giorno) == atteso


@pytest.mark.parametrize(
    "giorno,primo_punto,livello,punti,eta,atteso",
    [
        (_DM_2025, 963.40, "minimo", 10, 30, 4_781),
        # Prodotto esatto 7.000,50 €: pubblicato 7.001 (tabella 2.B, D.M. 10/12/2025).
        (_DM_2025, 963.40, "medio", 12, 73, 7_001),
        (_DM_2026, 988.45, "minimo", 10, 30, 4_911),
        (_DM_2026, 988.45, "minimo", 10, 7, 5_558),
        (_DM_2026, 988.45, "minimo", 44, 1, 116_196),
        (_DM_2026, 988.45, "massimo", 100, 100, 351_891),
        # Colonna B con mezzo centesimo esatto (1.598,585 €), testo originario.
        (_ORIGINARIO, 947.30, "medio", 23, 1, 36_767),
    ],
)
def test_danno_morale_delle_griglie_pubblicate(giorno, primo_punto, livello, punti, eta, atteso):
    assert tun.danno_morale(punti, eta, primo_punto, livello, giorno) == atteso


def test_colonna_b_arrotondata_al_pari_sul_mezzo_centesimo():
    assert tun.valore_punto_morale(23, 947.30, "medio") == 1_598.58
    assert tun.valore_punto_morale(44, 988.45, "minimo") == 2_640.82


@pytest.mark.parametrize(
    "liquidazione,eta,atteso",
    [
        ("2026-10-31", 30, 23_388.0),
        ("2026-10-31", 7, 26_468.0),
        ("2025-06-01", 30, 22_769.0),
    ],
)
def test_calcolo_completo_sulla_tavola_vigente(liquidazione, eta, atteso):
    risultato = calcola(_payload(
        db_data_sinistro="2025-04-10", db_data_liquidazione=liquidazione, db_eta=eta, db_perc_ip=10,
        db_giorni_itt=0, db_giorni_itp=0, db_morale_livello="nessuno",
    ))
    assert risultato["regime"] == regime.REGIME_TUN
    assert risultato["danno_permanente"] == atteso
    assert risultato["totale"] == atteso
    codice = "26A05220" if liquidazione.startswith("2026") else "25A06873"
    assert any(codice in sorgente["title"] for sorgente in risultato["sources"])
    assert any("tavola 1.B" in nota and codice in nota for nota in risultato["notes"])


def test_collaudo_normativo_del_danno_biologico():
    from pct.calcolatori.collaudo import CASI, collauda

    assert len(CASI["danno_biologico"]) >= 4
    assert collauda(GestioneStrumentiLegali())["danno_biologico"] == []
