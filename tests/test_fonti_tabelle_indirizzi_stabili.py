"""Contributo unificato e interessi legali: fonti monitorate con indirizzi stabili (collaudo 21/11/2026).

Causa di «fonte non raggiungibile»: l'art. 13 D.P.R. 115/2002 puntava a def.giustiziatributaria.gov.it (catena del
certificato incompleta, errore SSL a ogni controllo) e l'art. 1284 c.c. originario a un «caricaArticolo» di
Normattiva che risponde 500. Entrambi ora usano l'indirizzo per URN di Normattiva (risposta 200 il 21/11/2026).
"""
import json
from pathlib import Path

from pct.normative_tables import FONTI_OPERATIVE

RADICE = Path(__file__).resolve().parents[1]


def test_contributo_unificato_da_normattiva_per_urn():
    url = FONTI_OPERATIVE["dpr_115_2002"].url
    assert url == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:2002-05-30;115~art13"


def test_art_1284_originario_per_urn_alla_data():
    fonti = json.loads((RADICE / "pct/data/tassi_storici.json").read_text(encoding="utf-8"))["fonti"]
    url = fonti["interesse_legale_cc_1942"]["url"]
    assert url.startswith("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262~art1284")
    assert "caricaArticolo" not in url
