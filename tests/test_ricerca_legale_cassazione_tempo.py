"""«Cerca norme e sentenze»: l'archivio Cassazione lento non ferma la ricerca (collaudo 21/11/2026, 91 s)."""
import time

import pytest

from web.services import react_legal_intelligence_bridge as bridge


class _CorpusLento:
    def cerca_sentenze(self, **kwargs):
        time.sleep(2)
        return []

    def _connect(self):
        import sqlite3
        return sqlite3.connect(":memory:")


def test_cassazione_oltre_il_tempo_diventa_un_avviso(monkeypatch):
    import pct.sentenzeweb_corpus as corpus

    monkeypatch.setattr(corpus, "configured_corpus", lambda: _CorpusLento())
    monkeypatch.setattr(bridge, "_CASSAZIONE_SECONDI", 0.3)
    inizio = time.monotonic()
    with pytest.raises(bridge._CassazioneScaduta):
        bridge._cassazione_entro_il_tempo("art. 2043 c.c.", 0)
    assert time.monotonic() - inizio < 1.5


def test_titoli_senza_codice_redazionale_e_diciture_tecniche():
    from lex.normativa.etichette_atti import senza_codice_redazionale

    assert senza_codice_redazionale("Approvazione del testo del Codice civile. (042U0262) (042U0262)") == "Approvazione del testo del Codice civile."
    sorgente = open(bridge.__file__, encoding="utf-8").read()
    for dicitura in ('"approvalLabel": "indicizzata"', "Stato sistema:", "Righe strutturate:", "contesto ricostruito"):
        assert dicitura not in sorgente, dicitura


def test_tabelle_con_controllo_online_fallito_mostrano_i_valori_del_software(tmp_path):
    from types import SimpleNamespace

    from pct.normative_tables import GestioneTabelleNormative

    gestione = GestioneTabelleNormative(str(tmp_path / "tabelle.json"))
    manager = SimpleNamespace(normative_tables=gestione)
    riga = dict(gestione.get_table("interesse_legale"), sync_status="fonte_non_raggiungibile",
                last_warning="Fonte monitorata non raggiungibile: Normattiva - art. 1284 c.c.")
    scheda = bridge._normative_table_record(manager, riga, 1)
    assert scheda["approvalLabel"] == "valori dalle tabelle del software"
    assert scheda["approvalTone"] == "info"
    assert "non raggiungibile" not in scheda["subtitle"]
    assert "1,60%" in scheda["keyPoints"][0] and "10 dicembre 2025" in scheda["keyPoints"][0]


def test_numeri_normattiva_uguali_a_codici_e_leggi(monkeypatch):
    import lex.normativa.cerdef_catalogo_salvato as salvato

    monkeypatch.setattr(salvato, "catalogo_cerdef_salvato", lambda data_dir, basi: [{"articles": 3000}, {"articles": 414}] * 2)
    conteggi = bridge._conteggi_come_codici_e_leggi({"available": True, "documents": 641, "articles": 43414}, {"DATA_DIR": "/dati"})
    assert conteggi["documents"] == 4 and conteggi["articles"] == 6828
    assert bridge._conteggi_come_codici_e_leggi({"documents": 641}, {}) == {"documents": 641}
