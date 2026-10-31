"""Lettura a parti dell'AI locale: nessun taglio silenzioso oltre il contesto del modello."""

from __future__ import annotations

import pytest

from pct import local_ai
from pct.lettura_a_parti import (
    EsitoLettura,
    budget_caratteri,
    dividi_senza_perdite,
    gruppi_entro_budget,
    leggi_a_parti,
    sta_nel_contesto,
)


def test_budget_dal_contesto_del_modello(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "8192")
    monkeypatch.setenv("LEX_NUM_PREDICT", "700")
    assert budget_caratteri() == (8192 - 700 - 64) * 3
    assert budget_caratteri(riserva_token=10**6) == 1200
    assert sta_nel_contesto("abc", budget=3) and not sta_nel_contesto("abcd", budget=3)


def test_divisione_senza_perdite_e_gruppi():
    testo = "Primo paragrafo. " * 300 + "\n\n" + "Secondo paragrafo; " * 200
    parti = dividi_senza_perdite(testo, massimo=1000)
    assert "".join(parti) == testo and all(len(parte) <= 1000 for parte in parti)
    gruppi = gruppi_entro_budget(["a" * 400, "b" * 400, "c" * 400, "d" * 2500], budget=1000)
    assert all(len(gruppo) <= 1000 for gruppo in gruppi)
    assert "".join(g.replace("\n\n---\n\n", "") for g in gruppi) == "a" * 400 + "b" * 400 + "c" * 400 + "d" * 2500
    assert gruppi_entro_budget([], budget=10) == []


def test_parte_non_letta_dichiarata():
    def leggi(parte, numero, totale):
        if numero == 2:
            raise TimeoutError("modello lento")
        return f"letta {parte}"

    esito = leggi_a_parti(["uno", "due", "tre"], leggi)
    assert esito.mancanti == [2] and not esito.completo and esito.errori == ["parte 2: TimeoutError"]
    assert esito.risultati[0].startswith("[Parte 1 di 3]")
    assert "non lette le parti 2" in esito.nota()
    intero = leggi_a_parti(["uno", "due"], lambda p, n, t: p)
    assert intero.completo and intero.nota() == "Contenuto letto per intero in 2 parti."
    singola = leggi_a_parti(["uno"], lambda p, n, t: p)
    assert singola.risultati == ["uno"] and singola.nota() == ""
    assert EsitoLettura().completo is False


class _Modello:
    def __init__(self):
        self.prompt = []

    def generate_completion(self, model, prompt, **kwargs):
        self.prompt.append(prompt)
        if prompt.startswith("Sei l'assistente locale di IUSENTRA. Leggi questa parte"):
            return {"response": "Fatto utile [Fonte 1]"}
        return {"response": "Risposta finale"}


def test_chiedi_al_fascicolo_legge_a_parti_oltre_il_contesto(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "1024")
    monkeypatch.setenv("LEX_NUM_PREDICT", "64")
    modello = _Modello()
    template = f"Domanda e contesto\n{local_ai._SEGNAPOSTO_ESTRATTI}\nFine"
    blocchi = [f"[Fonte {i}] doc\n" + "testo " * 400 for i in range(1, 6)]
    prepared = {"prompt": template.replace(local_ai._SEGNAPOSTO_ESTRATTI, "\n".join(blocchi)), "prompt_template": template,
                "prompt_blocks": blocchi, "question": "Quando è l'udienza?"}
    prompt, lettura = local_ai._prompt_entro_il_contesto(modello, "m", prepared, keep_alive="5m")
    assert local_ai._SEGNAPOSTO_ESTRATTI not in prompt and "Fatto utile" in prompt
    assert lettura["parti"] >= 2 and lettura["mancanti"] == [] and "letto per intero" in lettura["nota"]
    assert len(prompt) <= budget_caratteri()
    # Dentro il contesto: nessuna lettura a parti.
    corto = {"prompt": "breve", "prompt_template": template, "prompt_blocks": ["x"], "question": "q"}
    assert local_ai._prompt_entro_il_contesto(modello, "m", corto, keep_alive="5m") == ("breve", {})


def test_note_troppo_lunghe_dichiarate(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "1024")
    monkeypatch.setenv("LEX_NUM_PREDICT", "64")

    class Prolisso(_Modello):
        def generate_completion(self, model, prompt, **kwargs):
            return {"response": "nota " * 300}

    template = "T " * 1100 + local_ai._SEGNAPOSTO_ESTRATTI
    blocchi = ["blocco " * 500 for _ in range(4)]
    prepared = {"prompt": template + "".join(blocchi), "prompt_template": template, "prompt_blocks": blocchi, "question": "q"}
    _prompt, lettura = local_ai._prompt_entro_il_contesto(Prolisso(), "m", prepared, keep_alive="5m")
    assert "Note non entrate nella sintesi finale" in lettura["nota"]


def test_estrattore_lex_dichiara_il_testo_non_riportato():
    from lex.tools import _doc_extractor as estrattore

    breve = estrattore._normalize("testo   breve\n\n\n\nfine")
    assert breve == "testo breve\n\nfine"
    lungo = estrattore._normalize("parola " * 3000)
    assert lungo.endswith(estrattore.NOTA_LETTO_IN_PARTE) and len(lungo) <= estrattore._MAX_TEXT_CHARS + 100


def test_estrattore_lex_legge_il_testo_nativo_oltre_le_quindici_pagine(monkeypatch):
    import sys
    import types

    from lex.tools import _doc_extractor as estrattore

    class Pagina:
        def __init__(self, testo):
            self.testo = testo

        def extract_text(self):
            return self.testo

    pagine = [Pagina(f"Pagina {i} con testo leggibile e completo per la verifica della qualita.") for i in range(20)]
    pagine[17] = Pagina("")  # pagina scansionata oltre la quindicesima

    class Pdf:
        def __init__(self, *_a):
            self.pages = pagine

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setitem(sys.modules, "pdfplumber", types.SimpleNamespace(open=Pdf))
    testo = estrattore._pdf_to_text(b"%PDF")
    assert "Pagina 19" in testo and "Pagine scansionate non lette in questa consultazione: 1" in testo
