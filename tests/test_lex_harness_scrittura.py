"""Controllo della stesura del modello di scrittura: nessuna norma, data o importo fuori dallo schema."""
from __future__ import annotations

from lex.harness import scrittura

SCHEMA = ("**Conclusione**\n- Condanna al pagamento di € 50.000 entro il 01/08/2026. (art. 1385 c.c.)\n"
          "**Termini**\n- Negoziazione entro trenta giorni. (art. 3 d.l. 132/2014)")


def test_stesura_fedele_accettata():
    s = ("Si propone la condanna al pagamento di € 50.000, con riferimento al termine del 01/08/2026, ai sensi dell'art. "
         "1385 c.c.; prima della causa va esperita la negoziazione assistita (art. 3 d.l. 132/2014).")
    assert scrittura.controlla(SCHEMA, s) == ""


def test_norma_inventata_respinta():
    s = "Condanna a € 50.000 entro il 01/08/2026 (art. 1385 c.c. e art. 1453 c.c.)."
    assert "norme non presenti" in scrittura.controlla(SCHEMA, s)


def test_data_cambiata_o_persa_respinta():
    assert "date" in scrittura.controlla(SCHEMA, "Condanna a € 50.000 entro il 02/08/2026 (art. 1385 c.c.), lungo testo di prova.")
    assert "date dello schema perse" in scrittura.controlla(SCHEMA, "Condanna a € 50.000 (art. 1385 c.c.), testo lungo per la prova.")


def test_importo_cambiato_respinto():
    assert "importi" in scrittura.controlla(SCHEMA, "Condanna a € 25.000 entro il 01/08/2026 (art. 1385 c.c.), testo lungo per la prova.")


def test_servizio_assente_risposta_deterministica(monkeypatch):
    def guasto(*a, **k):
        raise TimeoutError("nessuna risposta")

    monkeypatch.setattr(scrittura, "_chiama", guasto)
    s = scrittura.scrivi(SCHEMA + "\n**Cosa fare**\n1. x", "ollama:prova")
    assert not s.accettata and SCHEMA in s.testo and "non è disponibile" in s.testo


def test_senza_scrittore_solo_deterministico(monkeypatch):
    monkeypatch.delenv("LEX_HARNESS_SCRITTORE", raising=False)
    assert scrittura.scrivi(SCHEMA).scrittore == "deterministico"
