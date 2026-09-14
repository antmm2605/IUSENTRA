"""La conoscenza procedurale: fonti verificate, schede coerenti, template esistenti."""

from __future__ import annotations

import re

from pct.procedura_fasi import (
    SCHEDE_DEPOSITO,
    SCHEDE_NOTIFICA,
    SCHEDE_RITO,
    VERSIONE_CONOSCENZA,
    canale_deposito,
    canale_notifica,
    fase_deposito,
    fase_notifica,
    fonte,
    norme,
    rito_per_fascicolo,
    schede_per_fascicolo,
)
from pct.procedura_fasi.fonti import FONTI
from pct.termini_processuali import _DEFAULT_TEMPLATES_BY_CODE


def _fonti_di(scheda: dict) -> list[str]:
    identificativi: list[str] = []
    for fase in scheda.get("fasi", []):
        identificativi.extend(fase.get("fonti", []))
        for adempimento in fase.get("adempimenti", []):
            identificativi.extend(adempimento["fonti"])
    for voce in scheda.get("tempistiche", []):
        identificativi.extend(voce["fonti"])
    return identificativi


def test_ogni_fonte_ha_norma_url_ufficiale_data_di_verifica_ed_estratto():
    assert len(FONTI) >= 55
    for identificativo, voce in FONTI.items():
        assert voce["norma"] and voce["titolo"], identificativo
        assert voce["url"].startswith("https://"), identificativo
        assert "2026" in voce["verifica"], identificativo
        if identificativo != "cpa_dpcm_40_2016":
            assert len(voce["estratto"]) > 60, identificativo
            assert "normattiva.it" in voce["url"] or "pst.giustizia.it" in voce["url"], identificativo


def test_le_norme_di_normattiva_usano_l_urn_del_testo_vigente():
    for identificativo, voce in FONTI.items():
        if "normattiva.it" in voce["url"]:
            assert re.search(r"urn:nir:[a-z.]+:[a-z.]+:\d{4}-\d{2}-\d{2};\d+~art\w+$", voce["url"]), identificativo


def test_ogni_scheda_cita_solo_fonti_registrate_e_template_esistenti():
    for gruppo in (SCHEDE_DEPOSITO, SCHEDE_NOTIFICA, SCHEDE_RITO):
        for codice, scheda in gruppo.items():
            fonti_scheda = _fonti_di(scheda)
            assert fonti_scheda, codice
            assert all(identificativo in FONTI for identificativo in fonti_scheda), codice
            for fase in scheda.get("fasi", []):
                for adempimento in fase.get("adempimenti", []):
                    if adempimento.get("template"):
                        assert adempimento["template"] in _DEFAULT_TEMPLATES_BY_CODE, adempimento["template"]


def test_i_termini_dichiarati_coincidono_con_i_template_del_motore():
    attesi = {
        "CIV_COSTITUZIONE_ATTORE_165": ("dieci giorni", 10),
        "CIV_COSTITUZIONE_CONVENUTO_166": ("settanta giorni", 70),
        "CIV_MEMORIA_171_TER_1": ("quaranta giorni", 40),
        "CIV_OPPOSIZIONE_DI": ("quaranta giorni", 40),
        "CIV_DI_NOTIFICA_644": ("sessanta giorni", 60),
        "CIV_APPELLO_BREVE": ("trenta giorni", 30),
        "ESE_PRECETTO_EFFICACIA_90GG": ("novanta giorni", 90),
        "ESE_OPPOSIZIONE_ATTI_617": ("venti giorni", 20),
        "CIV_RECLAMO_CAUTELARE_669_TERDECIES": ("quindici giorni", 15),
    }
    adempimenti = {
        adempimento["template"]: adempimento
        for scheda in SCHEDE_RITO.values() for fase in scheda["fasi"] for adempimento in fase["adempimenti"] if adempimento.get("template")
    }
    for codice, (parole, giorni) in attesi.items():
        assert parole in adempimenti[codice]["termine"], codice
        assert _DEFAULT_TEMPLATES_BY_CODE[codice].base_value == giorni, codice


def test_i_canali_di_deposito_del_software_hanno_una_scheda():
    from pct.deposito_guidato import DEPOSIT_CHANNELS

    assert set(DEPOSIT_CHANNELS) == set(SCHEDE_DEPOSITO)
    for scheda in SCHEDE_DEPOSITO.values():
        stati = set(scheda["stati_software"])
        assert {"INVIATO", "ACCETTATO_CANCELLERIA", "RIFIUTATO_CANCELLERIA", "ERRORE_CONTROLLI"} <= stati
        codici = {fase["codice"] for fase in scheda["fasi"]}
        assert set(scheda["stati_software"].values()) <= codici


def test_fasi_del_deposito_civile_seguono_le_specifiche_dgsia():
    assert canale_deposito("pct") == "PCT_TELEMATICO" and canale_deposito("PDP") == "PDP_PENALE" and canale_deposito("boh") == ""
    consegna = fase_deposito("PCT_TELEMATICO", "CONSEGNATO")
    assert "il deposito è avvenuto" in consegna["nome"]
    assert "dispatt_196sexies" in consegna["fonti"]
    rifiuto = fase_deposito("PCT", "RIFIUTATO_CANCELLERIA")
    assert rifiuto["codice"] == "esito_cancelleria" and "dgsia_art17" in rifiuto["fonti"]
    penale = fase_deposito("PDP_PENALE", "RIFIUTATO")
    assert "dgsia_art19" in penale["fonti"]
    assert "RIFIUTATO" in fonte("dgsia_art19")["estratto"] and "ERRORE TECNICO" in fonte("dgsia_art19")["estratto"]


def test_fasi_della_notifica_pec_seguono_l_art_147_cpc():
    assert canale_notifica("PEC") == "pec" and canale_notifica("Non PEC") == "posta" and canale_notifica("UNEP") == "unep"
    attesa_rac = fase_notifica("pec", "SENT_WAITING_RAC")
    assert "notificante" in attesa_rac["nome"] and "cpc_147" in attesa_rac["fonti"]
    consegna = fase_notifica("pec", "RAC_RECEIVED")
    assert "destinatario" in consegna["nome"]
    assert "ore 7" in fonte("cpc_147")["estratto"]
    prova = fase_notifica("pec", "DELIVERY_COMPLETE")
    assert prova["codice"] == "deposito_prova" and {"dgsia_art26", "l53_art9"} <= set(prova["fonti"])
    assert fase_notifica("posta", "DELIVERY_COMPLETE")["codice"] == "perfezionamento"
    assert "dieci giorni" in fonte("l890_art8")["estratto"]


def test_il_processo_tributario_cita_il_testo_unico_175_2024_non_il_546_abrogato():
    scheda = SCHEDE_RITO["tributario"]
    assert "175/2024" in scheda["nome"]
    assert all("546" not in FONTI[identificativo]["url"] for identificativo in _fonti_di(scheda))
    assert "sessanta giorni" in fonte("tu175_art67")["estratto"] and "trenta giorni" in fonte("tu175_art68")["estratto"]


def test_rito_dal_tipo_di_fascicolo_e_dal_procedimento():
    assert rito_per_fascicolo("CIVILE") == "ordinario"
    assert rito_per_fascicolo("CIVILE", "Opposizione a decreto ingiuntivo") == "decreto_ingiuntivo"
    assert rito_per_fascicolo("CIVILE", "procedimento semplificato ex art. 281-undecies") == "semplificato"
    assert rito_per_fascicolo("LAVORO") == "lavoro"
    assert rito_per_fascicolo("PENALE") == "penale"
    assert rito_per_fascicolo("AMMINISTRATIVO") == "amministrativo"
    assert rito_per_fascicolo("TRIBUTARIO") == "tributario"
    assert rito_per_fascicolo("ALTRO") == ""


def test_schede_per_fascicolo_portano_rito_deposito_notifiche_e_fonti():
    schede = schede_per_fascicolo(tipo="PENALE", canali_notifica=["UNEP", "pec", "pec"])
    assert schede["versione"] == VERSIONE_CONOSCENZA
    assert schede["rito"]["codice"] == "penale"
    assert schede["deposito"]["canale"] == "PDP_PENALE"
    assert [voce["canale"] for voce in schede["notifiche"]] == ["unep", "pec"]
    assert all(voce["url"].startswith("https://") for voce in schede["deposito"]["fonti"])
    assert norme(["cpc_165", "assente", "cpc_165"]) == "art. 165 c.p.c."
