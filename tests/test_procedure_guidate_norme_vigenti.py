"""Procedure guidate (/legal-skills): passi e termini sul testo vigente (collaudo 21/11/2026).

Ogni affermazione controllata qui è stata letta sul testo vigente dell'archivio Normattiva
del software (codice di procedura civile aggiornato al D.Lgs. 164/2024, D.Lgs. 28/2010
aggiornato al D.Lgs. 216/2024, L. 604/1966, D.Lgs. 104/2010).
"""

from __future__ import annotations

import json
from pathlib import Path

from lex.legal_skills.prompt_library.pathways import PATHWAYS_DIR, get_pathway_catalog

ROOT = Path(__file__).resolve().parents[1]


def _percorso(percorso_id: str) -> dict:
    return json.loads((PATHWAYS_DIR / f"{percorso_id}.json").read_text(encoding="utf-8"))


def _passo(percorso: dict, passo_id: str) -> dict:
    return next(passo for passo in percorso["passi"] if passo["passo_id"] == passo_id)


def _testo(passo: dict) -> str:
    return " ".join([passo["descrizione"], *passo["termini"], *passo["riferimenti"]])


def test_le_dieci_procedure_si_caricano():
    percorsi = get_pathway_catalog().percorsi()
    assert len(percorsi) == 10


def test_monitorio_provvisoria_esecuzione_nel_ricorso_art_642():
    ricorso = _passo(_percorso("recupero_credito_monitorio"), "ricorso_decreto")
    assert "art. 642 c.p.c." in ricorso["riferimenti"]
    testo = _testo(ricorso)
    assert "cambiale" in testo and "pericolo di grave pregiudizio" in testo
    assert "MON_002" in ricorso["template_refs"]


def test_monitorio_esecutorieta_e_copia_esecutiva_prima_del_precetto():
    percorso = _percorso("recupero_credito_monitorio")
    ordine = [passo["passo_id"] for passo in percorso["passi"]]
    assert ordine.index("notifica_decreto") < ordine.index("esecutorieta_decreto") < ordine.index("precetto")
    passo = _passo(percorso, "esecutorieta_decreto")
    assert {"art. 647 c.p.c.", "art. 654 c.p.c.", "art. 475 c.p.c."} <= set(passo["riferimenti"])
    testo = _testo(passo)
    # Art. 654 vigente: il precetto menziona il provvedimento di esecutorietà.
    assert "menzionare il provvedimento" in testo
    # Art. 475 vigente (D.Lgs. 149/2022 e 164/2024): niente più apposizione della formula esecutiva.
    assert "copia attestata conforme" in testo
    assert "non si appone più" in testo


def test_monitorio_iscrizione_a_ruolo_pignoramento_presso_terzi_30_giorni():
    passo = _passo(_percorso("recupero_credito_monitorio"), "pignoramento")
    testo = _testo(passo)
    assert "entro 30 giorni dalla consegna" in testo
    assert "a pena di inefficacia del pignoramento" in testo
    assert "avviso di avvenuta iscrizione a ruolo" in testo


def test_opposizione_mediazione_onere_del_creditore_opposto_art_5_bis():
    passo = _passo(_percorso("opposizione_decreto_ingiuntivo"), "mediazione")
    testo = _testo(passo)
    assert "grava sul creditore" in testo
    assert "revoca il decreto" in testo
    assert "15 giorni" not in testo  # regola anteriore alla riforma, non più vigente


def test_mediazione_durata_sei_mesi_dopo_dlgs_216_2024():
    testo = _testo(_passo(_percorso("mediazione_civile"), "accordo_o_azione"))
    assert "6 mesi" in testo
    assert "3 mesi, prorogabile di 3" not in testo


def test_licenziamento_alternativa_conciliazione_e_60_giorni_dal_rifiuto():
    testo = _testo(_passo(_percorso("impugnazione_licenziamento"), "conciliazione"))
    assert "entro 60 giorni dal rifiuto o dal mancato accordo" in testo


def test_tar_rito_abbreviato_non_dimezza_il_termine_del_ricorso():
    testo = _testo(_passo(_percorso("ricorso_tar"), "parere_impugnabilita"))
    assert "non quello per notificare il ricorso introduttivo" in testo
    assert "controinteressato" in testo


def test_pagina_procedure_guidate_senza_parole_tecniche():
    sorgenti = [
        ROOT / "frontend/src/features/legal-skills/pages/LegalSkillsCatalogPage.tsx",
        ROOT / "frontend/src/features/legal-skills/components/PercorsiGuidati.tsx",
        ROOT / "frontend/src/features/legal-skills/pages/PromptPathwaysPage.tsx",
    ]
    catalogo = sorgenti[0].read_text(encoding="utf-8")
    assert 'title="Procedure guidate"' in catalogo
    assert "<PercorsiGuidati />" in catalogo
    for sorgente in sorgenti:
        testo = sorgente.read_text(encoding="utf-8")
        for vietata in ("Apri pack", "skill disponibili", "Tutti i pack", "Legal Skills\"", "LegalSkills Italia", "Apri prompt"):
            assert vietata not in testo, f"{vietata!r} a video in {sorgente.name}"
    for pack in (ROOT / "lex/legal_skills/seed_packs").glob("*/pack.json"):
        descrizione = json.loads(pack.read_text(encoding="utf-8"))["description"]
        assert "skill" not in descrizione.lower() and "read-only" not in descrizione


def test_data_breach_sul_testo_ufficiale_del_garante():
    fonte = ROOT / "docs/specs/ministero/fonti_ufficiali/2026-11-21/garante-regolamento-ue-2016-679-testo-coordinato.json"
    scheda = json.loads(fonte.read_text(encoding="utf-8"))
    assert scheda["url"].startswith("https://www.garanteprivacy.it/") and scheda["sha256"]
    assert (fonte.with_suffix(".pdf")).exists()
    percorso = _percorso("violazione_dati_personali")
    notifica = _testo(_passo(percorso, "notifica_garante"))
    assert "entro 72 ore" in notifica and "motivi del ritardo" in notifica
    comunicazione = _testo(_passo(percorso, "comunicazione_interessati"))
    assert "rischio elevato" in comunicazione and "cifrati" in comunicazione
