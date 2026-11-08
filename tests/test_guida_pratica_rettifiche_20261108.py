"""Schede della Guida pratica rettificate l'08/11/2026 sul testo vigente (archivio Normattiva del software).

- art. 208 D.Lgs. 14/2019: tardiva entro 6 mesi dal deposito del decreto di esecutività (prorogabile a 12);
- art. 47 D.P.R. 639/1970: decadenza di un anno per le prestazioni della gestione dell'art. 24 L. 88/1989 (malattia);
- art. 17-bis D.Lgs. 546/1992 abrogato dall'art. 2, comma 3, lett. a), D.Lgs. 220/2023;
- art. 567 c.p.c.: documentazione ipocatastale nel termine dell'art. 497 (45 giorni), prorogabile una volta di 45;
- art. 3 D.L. 132/2014 e art. 5 D.Lgs. 28/2010: negoziazione assistita per l'RCA, mediazione per la subfornitura;
- art. 7 D.Lgs. 150/2011: rito del lavoro; art. 14 D.Lgs. 150/2011: rito semplificato per i compensi dell'avvocato.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "pct" / "data"


@lru_cache(maxsize=None)
def _kb_full() -> dict:
    return json.loads((DATA / "legal_knowledge_base.full.json").read_text(encoding="utf-8"))


def _scheda(suffisso: str) -> dict:
    kb = _kb_full()
    righe = list(kb.get("codici_materia") or [])
    for sezione in kb.get("sezioni") or []:
        righe.extend(sezione.get("codici_materia") or [])
    trovate = [r for r in righe if str(r.get("codice", "")).endswith(suffisso)]
    if len(trovate) > 1:  # «143105» è anche il codice PST del noleggio: la guida ha il codice logico «GUIDA_…_143105»
        trovate = [r for r in trovate if str(r.get("codice", "")).startswith("GUIDA_")]
    assert len(trovate) == 1, suffisso
    return trovate[0]


def _testo(scheda: dict) -> str:
    return json.dumps(scheda, ensure_ascii=False)


def test_insinuazione_tardiva_sei_mesi_dal_decreto_di_esecutivita():
    s = _scheda("500015")
    tardiva = next(t for t in s["termini_processuali"] if t["termine"] == "Insinuazione tardiva")
    assert tardiva["mesi"] == 6 and "art. 208" in tardiva["norma"] and "esecutivit" in tardiva["decorrenza"]
    assert "12 MESI dall'udienza" not in _testo(s) and "reclamo_212" not in _testo(s)


def test_decadenza_previdenziale_malattia_un_anno():
    termine = _scheda("230001")["termini_processuali"][0]
    assert termine.get("giorni") != 90 and termine["mesi"] == 12 and "art. 47" in termine["norma"]


def test_reclamo_mediazione_tributario_non_piu_obbligatorio():
    for codice in ("512005", "512060"):
        s = _scheda(codice)
        assert s["obbligo_mediazione"]["obbligatoria"] is False
        assert "220/2023" in s["obbligo_mediazione"]["fonte"]
        assert not any("Reclamo/mediazione obbligatori" in a for a in s["atto_principale"]["avvertimenti_obbligatori"])
    assert "novantesimo giorno" in _testo(_scheda("512060"))


def test_documentazione_ipocatastale_45_giorni_prorogabili():
    termine = next(t for t in _scheda("610001")["termini_processuali"] if "ipocatastale" in t["termine"])
    assert termine["giorni"] == 45 and "567" in termine["norma"] and "120" not in termine["natura"]


def test_rca_negoziazione_assistita_e_subfornitura_mediazione():
    rca = _scheda("156020")
    assert rca["obbligo_mediazione"]["obbligatoria"] is False and rca["obbligo_mediazione"]["negoziazione_assistita_obbligatoria"] is True
    assert "132/2014" in rca["rito"]
    sub = _scheda("143105")
    assert sub["obbligo_mediazione"]["obbligatoria"] is True and "28/2010" in sub["obbligo_mediazione"]["fonte"]


def test_riti_di_codice_della_strada_e_compenso_avvocato():
    assert "Rito del lavoro" in _scheda("240020")["rito"]
    compenso = _scheda("413090")
    assert "semplificato" in compenso["rito"] and "702-bis e ss." not in [n.get("articolo") for n in compenso["normativa"]]
    assert "non è appellabile" in compenso["procedimento_14_D_Lgs_150_2011"]["impugnazione"]


def test_ogni_rettifica_porta_la_fonte():
    for codice in ("500015", "512005", "512060", "156020", "143105", "240020", "413090"):
        rettifiche = _scheda(codice)["rettifiche_normative"]
        assert rettifiche and all(r["fonti"] and r["verificato_il"] == "2026-11-08" for r in rettifiche), codice
