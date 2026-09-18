"""Tabelle milanesi 2024: parentale, premorienza e danno terminale.

I valori attesi sono quelli pubblicati dall'Osservatorio sulla giustizia civile
di Milano nel documento P. 7599/24, compresi gli esempi di calcolo che il
documento stesso riporta in allegato.
"""
from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from pct.calcolatori import danno_parentale, danno_premorienza, danno_terminale
from pct.calcolatori.danno_biologico import parentale, premorienza, tabelle, terminale


# ── Perdita del rapporto parentale ───────────────────────────────────────


def test_valori_punto_e_tetti_della_tabella_parentale():
    nucleo = parentale.categoria(parentale.NUCLEO_PRIMARIO)
    fratelli = parentale.categoria(parentale.FRATELLO_NIPOTE)
    assert nucleo["valore_punto"] == 3911.00
    assert nucleo["punti_massimi"] == 118
    assert nucleo["cap"] == 391103.18
    assert nucleo["forbice_minima"] == 195551.59
    assert fratelli["valore_punto"] == 1698.00
    assert fratelli["punti_massimi"] == 116
    assert fratelli["cap"] == 169830.60


# Esempi dell'allegato 1 al documento: i punteggi dei parametri da A a D.
# Gli importi degli esempi usano il valore punto dell'edizione 2022, quindi il
# confronto e' sui punti, che sono la parte strutturale della tabella.
@pytest.mark.parametrize(
    "categoria,eta_primaria,eta_secondaria,convivenza,superstiti,punti_attesi",
    [
        ("nucleo_primario", 15, 45, "convivenza", 2, 74),
        ("nucleo_primario", 10, 39, "convivenza", 0, 82),
        ("nucleo_primario", 45, 68, "nessuna", 2, 48),
        ("nucleo_primario", 80, 85, "convivenza", 1, 50),
        ("nucleo_primario", 48, 49, "convivenza", 1, 70),
        ("nucleo_primario", 40, 6, "convivenza", 2, 78),
        ("fratello_nipote", 51, 45, "nessuna", 5, 26),
        ("fratello_nipote", 11, 5, "convivenza", 2, 72),
        ("fratello_nipote", 15, 75, "nessuna", 5, 28),
    ],
)
def test_esempi_di_calcolo_pubblicati(categoria, eta_primaria, eta_secondaria, convivenza, superstiti, punti_attesi):
    punti = (
        parentale.punti_eta_vittima_primaria(categoria, eta_primaria)
        + parentale.punti_eta_vittima_secondaria(categoria, eta_secondaria)
        + parentale.punti_convivenza(categoria, convivenza)
        + parentale.punti_superstiti(categoria, superstiti)
    )
    assert punti == punti_attesi


def test_oltre_tre_superstiti_il_parametro_d_non_da_punti():
    # Negli esempi pubblicati i casi con cinque superstiti valgono zero punti.
    assert parentale.punti_superstiti("nucleo_primario", 3) == 9
    assert parentale.punti_superstiti("nucleo_primario", 4) == 0
    assert parentale.punti_superstiti("fratello_nipote", 5) == 0


def test_la_convivenza_prolungata_vale_solo_per_fratelli_e_nipoti():
    assert "convivenza_oltre_40_anni" in parentale.opzioni_convivenza("fratello_nipote")
    assert "convivenza_oltre_40_anni" not in parentale.opzioni_convivenza("nucleo_primario")
    with pytest.raises(ValueError, match="convivenza"):
        danno_parentale.calcola({
            "dp_categoria": "nucleo_primario", "dp_eta_vittima": 40, "dp_eta_congiunto": 40,
            "dp_convivenza": "convivenza_oltre_40_anni", "dp_superstiti": 0,
        })


def test_il_totale_parentale_e_limitato_dal_tetto_della_categoria():
    risultato = danno_parentale.calcola({
        "dp_categoria": "nucleo_primario", "dp_eta_vittima": 5, "dp_eta_congiunto": 5,
        "dp_convivenza": "convivenza", "dp_superstiti": 0, "dp_qualita_relazione": "massima",
    })
    assert risultato["punti_totali"] == 118
    assert risultato["importo"] == 391103.18
    assert any("tetto" in avviso for avviso in risultato["warnings"])


def test_il_calcolo_parentale_dichiara_la_fonte():
    risultato = danno_parentale.calcola({
        "dp_categoria": "fratello_nipote", "dp_eta_vittima": 30, "dp_eta_congiunto": 35,
        "dp_convivenza": "nessuna", "dp_superstiti": 1, "dp_qualita_relazione": "ordinaria",
    })
    assert risultato["tabelle_applicate"][0]["id"] == tabelle.MILANO_2024_PARENTALE
    # Host confrontato per intero: «https://tribunale-milano.giustizia.it.altro»
    # comincia allo stesso modo ma non e' il sito del Tribunale di Milano.
    assert urlsplit(risultato["sources"][0]["url"]).netloc == "tribunale-milano.giustizia.it"


# ── Premorienza ──────────────────────────────────────────────────────────


def test_la_tabella_premorienza_copre_tutti_i_punti():
    dati = tabelle.carica(tabelle.MILANO_2024_PREMORIENZA)
    assert sorted(int(k) for k in dati["punti"]) == list(range(1, 101))
    for punto in dati["punti"].values():
        for colonna in ("primo_anno", "primo_e_secondo_anno", "anno_successivo"):
            voce = punto[colonna]
            assert voce["totale"] == voce["biologico"] + voce["sofferenza"]


def test_le_colonne_della_premorienza_sono_crescenti_nei_punti():
    dati = tabelle.carica(tabelle.MILANO_2024_PREMORIENZA)["punti"]
    for colonna in ("primo_anno", "primo_e_secondo_anno", "anno_successivo"):
        serie = [dati[str(p)][colonna]["totale"] for p in range(1, 101)]
        assert all(serie[i] < serie[i + 1] for i in range(len(serie) - 1)), colonna


def test_liquidazione_premorienza_per_anni_di_sopravvivenza():
    # Punto 35: colonna 1 = 8.438 + 4.219, colonna 2 = 14.767 + 7.384,
    # colonna 3 = 4.219 + 2.110 per ogni anno oltre il secondo.
    assert premorienza.liquida(35, 1)["totale"] == 12_657
    assert premorienza.liquida(35, 2)["totale"] == 22_151
    assert premorienza.liquida(35, 5)["totale"] == 22_151 + 3 * 6_329


def test_premorienza_calcola_gli_anni_dalle_date():
    risultato = danno_premorienza.calcola({
        "pm_perc_ip": 35, "pm_data_lesione": "2020-01-10", "pm_data_decesso": "2024-03-01",
    })
    # Quattro anni e mezzo: ogni anno iniziato conta per intero, quindi cinque.
    assert risultato["anni_sopravvivenza"] == 5
    assert risultato["totale"] == 22_151 + 3 * 6_329


def test_premorienza_rifiuta_un_decesso_anteriore_alla_lesione():
    with pytest.raises(ValueError, match="decesso"):
        danno_premorienza.calcola({
            "pm_perc_ip": 10, "pm_data_lesione": "2024-01-10", "pm_data_decesso": "2023-01-10",
        })


def test_premorienza_limita_la_personalizzazione_al_50_per_cento():
    risultato = danno_premorienza.calcola({"pm_perc_ip": 10, "pm_anni": 1, "pm_personalizzazione": 80})
    assert risultato["personalizzazione_pct"] == 50
    assert any("supera" in avviso for avviso in risultato["warnings"])


# ── Danno terminale ──────────────────────────────────────────────────────


def test_la_tabella_terminale_copre_i_giorni_da_quattro_a_cento():
    dati = tabelle.carica(tabelle.MILANO_2024_TERMINALE)
    assert sorted(int(k) for k in dati["importo_pro_die"]) == list(range(4, 101))
    assert sorted(int(k) for k in dati["importo_cumulato_dal_quarto_giorno"]) == list(range(4, 101))


def test_il_cumulato_terminale_e_la_somma_dei_pro_die():
    """Le due colonne pubblicate si controllano a vicenda."""
    totale = 0
    for giorno in range(4, 101):
        totale += terminale.importo_pro_die(giorno)
        assert terminale.importo_cumulato(giorno) == totale, giorno


def test_il_pro_die_terminale_decresce_dal_quarto_al_centesimo_giorno():
    serie = [terminale.importo_pro_die(g) for g in range(4, 101)]
    assert serie[0] == 1_175
    assert serie[-1] == 116
    assert all(serie[i] > serie[i + 1] for i in range(len(serie) - 1))


def test_esempio_pubblicato_del_danno_terminale():
    """Il documento calcola 35.247,00 + 11.989,50 = 47.236,50 € per dieci giorni."""
    risultato = danno_terminale.calcola({"dt_giorni": 10, "dt_personalizzazione": 50})
    assert risultato["primi_tre_giorni"] == 35_247.00
    assert risultato["giorni_successivi"] == 7_993.00
    assert risultato["importo_personalizzazione"] == 3_996.50
    assert risultato["totale"] == 47_236.50


def test_la_personalizzazione_terminale_non_tocca_i_primi_tre_giorni():
    senza = danno_terminale.calcola({"dt_giorni": 3})
    assert senza["giorni_successivi"] == 0.0
    assert senza["totale"] == 35_247.00
    con = danno_terminale.calcola({"dt_giorni": 3, "dt_personalizzazione": 50})
    assert con["totale"] == senza["totale"]


def test_i_primi_tre_giorni_terminali_sono_limitati_dal_tetto():
    risultato = danno_terminale.calcola({"dt_giorni": 5, "dt_importo_primi_tre": 50_000})
    assert risultato["primi_tre_giorni"] == 35_247.00
    assert any("tetto" in avviso for avviso in risultato["warnings"])


def test_oltre_il_centesimo_giorno_il_terminale_avvisa():
    risultato = danno_terminale.calcola({"dt_giorni": 150})
    assert risultato["giorni_successivi"] == terminale.importo_cumulato(100)
    assert any("100" in avviso for avviso in risultato["warnings"])


def test_terminale_calcola_i_giorni_dalle_date():
    risultato = danno_terminale.calcola({"dt_data_lesione": "2026-01-01", "dt_data_decesso": "2026-01-10"})
    assert risultato["giorni"] == 10
    assert risultato["giorni_successivi"] == 7_993.00


# ── Somma equitativa per abuso del processo (art. 96, comma 3, c.p.c.) ───


def test_esempio_pubblicato_dell_articolo_96_comma_3():
    """Il documento: compenso 5.000 € → 5.000 €, riducibile a 2.500, aumentabile a 7.500."""
    from pct.calcolatori import lite_temeraria

    risultato = lite_temeraria.calcola({"lt_compenso": 5000})
    assert risultato["importo_base"] == 5_000.00
    assert risultato["importo_minimo"] == 2_500.00
    assert risultato["importo_massimo"] == 7_500.00
    assert risultato["importo_proposto"] == 5_000.00


def test_gli_indici_di_graduazione_non_superano_il_massimo():
    from pct.calcolatori import lite_temeraria

    risultato = lite_temeraria.calcola({
        "lt_compenso": 5000, "lt_valore_elevato": "1", "lt_processo_lungo": "1",
        "lt_piu_parti": "1", "lt_dolo": "1", "lt_affaticamento": "1",
    })
    assert risultato["coefficiente"] == 1.5
    assert risultato["importo_proposto"] == risultato["importo_massimo"]


def test_l_articolo_96_richiede_il_compenso_liquidato():
    from pct.calcolatori import lite_temeraria

    with pytest.raises(ValueError, match="compenso"):
        lite_temeraria.calcola({"lt_compenso": 0})


# ── Consenso informato ───────────────────────────────────────────────────


def test_le_quattro_fasce_del_consenso_informato():
    from pct.calcolatori.danno_biologico import fasce, tabelle as tab

    voci = fasce.fasce(tab.MILANO_2024_CONSENSO)
    assert [v["id"] for v in voci] == ["lieve", "media", "grave", "eccezionale"]
    assert (voci[0]["minimo"], voci[0]["massimo"]) == (1162.00, 4649.00)
    assert (voci[1]["minimo"], voci[1]["massimo"]) == (4650.00, 10460.00)
    assert (voci[2]["minimo"], voci[2]["massimo"]) == (10461.00, 23245.00)
    assert (voci[3]["minimo"], voci[3]["massimo"]) == (23246.00, None)
    # Le fasce si susseguono senza sovrapporsi.
    for prima, dopo in zip(voci, voci[1:]):
        assert dopo["minimo"] > prima["massimo"] or dopo["minimo"] == prima["massimo"] + 1


def test_il_consenso_informato_posiziona_nella_fascia():
    from pct.calcolatori import consenso_informato

    minimo = consenso_informato.calcola({"ci_fascia": "media", "ci_posizione": 0})
    massimo = consenso_informato.calcola({"ci_fascia": "media", "ci_posizione": 100})
    meta = consenso_informato.calcola({"ci_fascia": "media", "ci_posizione": 50})
    assert minimo["importo_proposto"] == 4650.00
    assert massimo["importo_proposto"] == 10460.00
    assert meta["importo_proposto"] == pytest.approx((4650.00 + 10460.00) / 2, abs=0.01)


def test_la_fascia_eccezionale_del_consenso_non_ha_tetto():
    from pct.calcolatori import consenso_informato

    risultato = consenso_informato.calcola({"ci_fascia": "eccezionale", "ci_importo_eccezionale": 50000})
    assert risultato["importo_massimo"] is None
    assert risultato["importo_proposto"] == 50000.00
    assert any("non ha un tetto" in avviso for avviso in risultato["warnings"])


# ── Diffamazione ─────────────────────────────────────────────────────────


def test_le_cinque_fasce_della_diffamazione():
    from pct.calcolatori.danno_biologico import fasce, tabelle as tab

    voci = fasce.fasce(tab.MILANO_2024_DIFFAMAZIONE)
    attese = [
        ("tenue", 1175.00, 11750.00),
        ("modesta", 11750.00, 23498.00),
        ("media", 23498.00, 35247.00),
        ("elevata", 35247.00, 58745.00),
        ("eccezionale", 58745.00, None),
    ]
    assert [(v["id"], v["minimo"], v.get("massimo")) for v in voci] == attese


def test_la_riparazione_pecuniaria_va_da_un_ottavo_a_un_terzo():
    from pct.calcolatori import diffamazione

    risultato = diffamazione.calcola({"df_fascia": "media", "df_posizione": 50, "df_riparazione": "1"})
    importo = risultato["importo_proposto"]
    assert risultato["riparazione_pecuniaria"]["minimo"] == pytest.approx(importo / 8, abs=0.02)
    assert risultato["riparazione_pecuniaria"]["massimo"] == pytest.approx(importo / 3, abs=1.0)


def test_la_diffamazione_riporta_la_media_del_campione():
    from pct.calcolatori import diffamazione

    assert diffamazione.calcola({"df_fascia": "tenue"})["importo_medio_campione"] == 30888.00


# ── Capitalizzazione di una rendita ──────────────────────────────────────


def test_le_tabelle_di_capitalizzazione_coprono_tutte_le_eta():
    from pct.calcolatori import capitalizzazione_rendita as cr
    from pct.calcolatori.danno_biologico import tabelle as tab

    coefficienti = tab.carica(tab.MILANO_2024_CAPITALIZZAZIONE)["coefficienti"]
    for sesso in ("maschi", "femmine"):
        assert sorted(int(e) for e in coefficienti[sesso]) == list(range(0, 101))


def test_il_coefficiente_cresce_con_gli_anni_e_cala_con_l_eta():
    from pct.calcolatori import capitalizzazione_rendita as cr

    for sesso in ("maschi", "femmine"):
        serie = [cr.coefficiente(sesso, 40, anni) for anni in range(1, 40)]
        assert all(serie[i] < serie[i + 1] for i in range(len(serie) - 1))
        per_eta = [cr.coefficiente(sesso, eta, 20) for eta in range(40, 80)]
        assert all(per_eta[i] >= per_eta[i + 1] for i in range(len(per_eta) - 1))


def test_la_donna_ha_coefficienti_non_inferiori_all_uomo():
    """Sopravvivenza attesa maggiore: la tabella femminile non puo' stare sotto."""
    from pct.calcolatori import capitalizzazione_rendita as cr

    for eta in (20, 40, 60, 80):
        for anni in (5, 10, 20):
            maschile = cr.coefficiente("maschi", eta, anni)
            femminile = cr.coefficiente("femmine", eta, anni)
            if maschile is not None and femminile is not None:
                assert femminile >= maschile - 0.01, (eta, anni)


def test_la_capitalizzazione_ricava_la_durata_dall_eta_finale():
    from pct.calcolatori import capitalizzazione_rendita as cr

    risultato = cr.calcola({"cr_sesso": "maschi", "cr_eta": 45, "cr_eta_finale": 67, "cr_reddito": 24000})
    assert risultato["anni_applicati"] == 22
    assert risultato["coefficiente"] == cr.coefficiente("maschi", 45, 22)
    assert risultato["capitale"] == round(24000 * risultato["coefficiente"], 2)


def test_la_capitalizzazione_si_ferma_all_orizzonte_della_tabella():
    from pct.calcolatori import capitalizzazione_rendita as cr

    risultato = cr.calcola({"cr_sesso": "maschi", "cr_eta": 80, "cr_anni": 40, "cr_reddito": 20000})
    assert risultato["anni_applicati"] == cr.orizzonte_massimo("maschi", 80)
    assert any("si ferma" in avviso for avviso in risultato["warnings"])


def test_la_quota_riduce_il_capitale():
    from pct.calcolatori import capitalizzazione_rendita as cr

    intero = cr.calcola({"cr_sesso": "femmine", "cr_eta": 30, "cr_anni": 20, "cr_reddito": 30000})
    meta = cr.calcola({"cr_sesso": "femmine", "cr_eta": 30, "cr_anni": 20, "cr_reddito": 30000, "cr_quota_perc": 50})
    assert meta["capitale_quota"] == pytest.approx(intero["capitale"] / 2, abs=0.01)


def test_la_capitalizzazione_richiede_la_durata():
    from pct.calcolatori import capitalizzazione_rendita as cr

    with pytest.raises(ValueError, match="quanti anni"):
        cr.calcola({"cr_sesso": "maschi", "cr_eta": 40, "cr_reddito": 20000})
