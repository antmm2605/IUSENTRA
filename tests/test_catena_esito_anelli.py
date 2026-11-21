"""L'esito del controllo della catena anello per anello: ogni incoerenza del guardiano appartiene a un anello."""
import re
from pathlib import Path

from pct.catena.esito import ANELLO_DEL_CODICE, anello_di, esito_anelli


def test_ogni_codice_del_guardiano_ha_il_suo_anello():
    sorgente = Path("pct/catena/guardiano.py").read_text(encoding="utf-8")
    codici = set(re.findall(r'Incoerenza\(\s*"([a-z_]+)"', sorgente))
    assert codici, "nessun codice letto dal guardiano"
    assert codici - {"pannello_superato"} <= set(ANELLO_DEL_CODICE), sorted(codici - set(ANELLO_DEL_CODICE))


def test_pannello_superato_va_all_anello_del_pannello():
    assert anello_di({"codice": "pannello_superato", "dati": {"pannello": "conto-economico"}}) == "economia"
    assert anello_di({"codice": "pannello_superato", "dati": {"pannello": "lettura"}}) == "letture"
    assert anello_di({"codice": "pannello_superato", "dati": {"pannello": "scadenze"}}) == "termini"


def test_esiti_nell_ordine_della_catena():
    avviso = {"codice": "quadro_diverso_dalla_lettura", "dati": {}}
    riparata = {"codice": "udienza_non_in_agenda", "dati": {}}
    esiti = esito_anelli(stato="verificato", avvisi=[avviso], riparate=[riparata])
    assert [(a["codice"], a["esito"]) for a in esiti] == [
        ("letture", "verificato"), ("termini", "riparato"), ("passi", "verificato"), ("economia", "verificato"),
        ("quadro", "da_verificare")]
    assert {a["esito"] for a in esito_anelli(stato="in_aggiornamento", avvisi=[], riparate=[])} == {"in_aggiornamento"}
    assert {a["esito"] for a in esito_anelli(stato="mai_controllato", avvisi=[], riparate=[])} == {"non_controllato"}
