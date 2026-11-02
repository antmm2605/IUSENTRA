"""Catalogo contratti: integrità, selezione per fatti e distinzione redazione/stipula."""
from datetime import date

import pytest

from pct.contratti import carica_catalogo, famiglia, regole_comuni, valuta
from pct.contratti.catalogo import _indice

OGGI = date(2026, 11, 2)


def test_catalogo_copre_tutte_le_aree_e_ogni_voce_ha_norma():
    cat = carica_catalogo()
    assert len(cat["aree"]) == 15 and cat["totale"] >= 190
    assert all(a["voci"] for a in cat["aree"])
    assert all(c.riferimenti for c in _indice().values())


def test_regole_comuni_e_scheda_dodici_campi():
    r = regole_comuni()
    assert len(r["regole_comuni"]) == 14 and len(r["scheda_controllo"]) == 12
    scheda = valuta("mutuo", {}, OGGI)["scheda"]
    assert [c[0] for c in r["scheda_controllo"]] == list(scheda)


def test_locazione_seleziona_variante_e_blocca_deposito():
    fatti = {"regime_canone": "concordato", "durata_transitoria": False, "conduttore_studente": False,
             "comune_accordo_territoriale": False, "deposito_mensilita": 4, "cedolare_secca": True}
    r = valuta("locazione_abitativa", fatti, OGGI)
    assert r["variante"]["id"] == "canone_concordato"
    assert {b["id"] for b in r["bloccanti"]} == {"deposito_oltre_tre"}
    assert any(p["id"] == "accordo_territoriale" for p in r["punti_avvocato"])
    assert not r["pronto_per_redazione"]


def test_locazione_senza_fatti_lascia_scelta_all_avvocato():
    r = valuta("locazione_abitativa", {}, OGGI)
    assert r["variante"] is None and r["domande_aperte"]
    assert any(p["id"] == "variante" for p in r["punti_avvocato"])


def test_incarico_avvocato_patto_quota_lite_e_ia():
    r = valuta("incarico_avvocato", {"tipo_incarico": "giudiziale", "patto_cessione_lite": True, "uso_ia": True}, OGGI)
    assert r["variante"]["id"] == "giudiziale"
    assert r["bloccanti"][0]["norma"].startswith("art. 13, comma 4")
    assert any("L. 132/2025" in a["norma"] for a in r["adempimenti"])


def test_sviluppo_software_dora_e_qualificazione_mista():
    r = valuta("sviluppo_software", {"fornitore_impresa": True, "committente_finanziario": True}, OGGI)
    assert r["variante"]["id"] == "appalto"
    assert any(b["id"] == "dora" for b in r["bloccanti"])
    assert any(p["id"] == "qualificazione" for p in r["punti_avvocato"])


@pytest.mark.parametrize("cid", ["societa_capitali", "donazione", "convenzioni_matrimoniali", "patto_famiglia"])
def test_forma_notarile_segnalata(cid):
    assert valuta(cid, {}, OGGI)["forma"]["richiede_pubblico_ufficiale"]


def test_compravendita_rimanda_al_notaio_per_trascrizione():
    r = valuta("compravendita_immobiliare", {"immobile_da_costruire": False, "vendita_a_corpo": True}, OGGI)
    assert any(a["norma"] == "art. 2657 c.c." for a in r["adempimenti"])


def test_ecommerce_odr_dismessa_e_novita():
    r = valuta("condizioni_online", {"cita_odr": True, "recesso_online": True, "claim_ambientali": False}, OGGI)
    assert r["bloccanti"][0]["norma"] == "Reg. UE 2024/3228"
    assert any(n["id"] == "recesso_online" for n in r["novita"])


def test_contratto_sconosciuto_fail_closed():
    with pytest.raises(LookupError):
        famiglia("contratto_inventato")
