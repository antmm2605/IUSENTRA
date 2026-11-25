"""Controllore della stesura rafforzato (confronto scrittori, 21/11/2026)."""
from __future__ import annotations

import lex.harness.scrittura as S
import lex.harness.scrittura_segnaposto as SP

SCHEMA = ("**Cosa ho capito**\n- Separazione.\n\n**Conclusione**\n- Ricorso al Tribunale di Bari. (art. 473-bis.12 c.p.c.)\n\n"
          "**Come e perché**\n*Inquadramento*\n- La separazione giudiziale si chiede per fatti che rendono intollerabile la "
          "convivenza. (art. 151 c.c.)\n*Condizioni di procedibilità*\n- Mediazione e negoziazione assistita non sono condizioni "
          "di procedibilità per la separazione. (art. 5 d.lgs. 28/2010)\n\n**Norme applicate**\n- art. 151 c.c.")


def test_norma_inventata_non_arriva_all_avvocato_neppure_nella_nota(monkeypatch):
    # Il testo esatto di Ministral: aggiunge l'art. 49 c.p.c., assente dallo schema.
    monkeypatch.setattr(S, "_chiama", lambda *a, **k: (
        "La separazione giudiziale si chiede per fatti che rendono intollerabile la convivenza, ai sensi dell'art. 151 c.c.; "
        "la competenza si radica secondo l'art. 49 c.p.c.; mediazione e negoziazione assistita non sono condizioni di "
        "procedibilità per la separazione (art. 5 d.lgs. 28/2010)."))
    r = S.scrivi(SCHEMA, "openai:x|prova")
    assert not r.accettata and "art. 49" not in r.testo and "norme non presenti" in r.testo


def test_conclusione_e_avvertenze_restano_deterministiche():
    prima, blocco, dopo = S._sezioni(SCHEMA + "\n\n**Avvertenze**\n- Attenzione.")
    assert "**Conclusione**" in prima and "**Conclusione**" not in blocco and "**Avvertenze**" not in blocco


def test_operatore_decisivo_perso_scartato():
    assert "non e obbligatori" in S.elementi_persi("- La mediazione non è obbligatoria.", "La mediazione è prevista.")


def test_per_punto_la_norma_resta_sulla_sua_affermazione(monkeypatch):
    monkeypatch.setattr(SP, "_chiama", lambda *a, **k: (
        "[1] La separazione giudiziale presuppone fatti tali da rendere intollerabile la prosecuzione della convivenza.\n"
        "[2] Per la separazione non sono condizioni di procedibilità né la mediazione né la negoziazione assistita."))
    r = SP.scrivi_per_punto(SCHEMA, "openai:x|prova")
    assert r.accettata and r.motivo.startswith("punti riscritti 2/2")
    assert "prosecuzione della convivenza. (art. 151 c.c.)" in r.testo
    assert "negoziazione assistita. (art. 5 d.lgs. 28/2010)" in r.testo
    assert "- Ricorso al Tribunale di Bari. (art. 473-bis.12 c.p.c.)" in r.testo     # conclusione intatta


def test_per_punto_frase_con_dato_inventato_resta_deterministica(monkeypatch):
    monkeypatch.setattr(SP, "_chiama", lambda *a, **k: (
        "[1] La separazione giudiziale si chiede entro 30 giorni.\n[2] Non servono mediazione né negoziazione assistita."))
    r = SP.scrivi_per_punto(SCHEMA, "openai:x|prova")
    assert "entro 30 giorni" not in r.testo and "intollerabile la convivenza. (art. 151 c.c.)" in r.testo


def test_senza_variabile_nessuna_risposta_grezza_su_disco(tmp_path, monkeypatch):
    import os

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LEX_BANCO_GREZZI", raising=False)
    monkeypatch.setattr(SP, "registra_grezza", None)
    monkeypatch.setattr(SP, "_chiama", lambda *a, **k: "[1] Frase riscritta in modo corretto e scorrevole.\n[2] Altra frase.")
    SP.scrivi_per_punto(SCHEMA, "openai:x|prova")
    assert list(tmp_path.iterdir()) == []
    from tests.lex_collaudo.scrittori import attiva_registro_grezzi

    attiva_registro_grezzi()                      # senza variabile non attiva nulla
    assert SP.registra_grezza is None
    file = tmp_path / "grezzi.jsonl"
    monkeypatch.setenv("LEX_BANCO_GREZZI", str(file))
    attiva_registro_grezzi()
    SP.scrivi_per_punto(SCHEMA, "openai:x|prova")
    assert file.exists() and oct(os.stat(file).st_mode & 0o777) == "0o600"


def test_stesura_integrale_conserva_ancore_importi_e_date(monkeypatch):
    schema = SCHEMA.replace("La separazione giudiziale si chiede per fatti",
                            "Il 12/03/2026 è stato richiesto un contributo di € 850. La separazione si chiede per fatti")
    def risposta(_, richiesta, *args, **kwargs):
        return richiesta.split("\\n\\nSegnaposto da usare", 1)[0]

    monkeypatch.setattr(SP, "_chiama", risposta)
    esito = SP.scrivi_con_segnaposto(schema, "openai:x|prova")
    assert esito.accettata, esito.motivo
    assert "12/03/2026" in esito.testo and "€ 850" in esito.testo
    assert "art. 151 c.c." in esito.testo and "{{" not in esito.testo


def test_stesura_integrale_sostituzione_e_fallback(monkeypatch):
    assert SP.sostituisci("Somma euro {{IMPORTO_1}}", {"IMPORTO_1": "€ 850"}) == "Somma € 850"

    monkeypatch.setattr(SP, "_chiama", lambda *args, **kwargs: "{{NORMA_999}}")
    proposta = SP.scrivi_con_segnaposto(SCHEMA, "openai:x|prova")
    assert not proposta.accettata and "segnaposto inesistenti" in proposta.motivo and proposta.testo == SCHEMA

    def indisponibile(*args, **kwargs):
        raise TimeoutError("Timeout del servizio")

    monkeypatch.setattr(SP, "_chiama", indisponibile)
    proposta = SP.scrivi_con_segnaposto(SCHEMA, "openai:x|prova")
    assert not proposta.accettata and "TimeoutError" in proposta.motivo and proposta.testo == SCHEMA
