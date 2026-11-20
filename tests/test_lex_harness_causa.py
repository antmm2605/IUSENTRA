"""Fase dei fatti dentro un fascicolo: l'harness legge il modello della causa (pct/ragionamento), con le prove."""
from __future__ import annotations

from pct.ragionamento import ragiona
from tests.test_ragionamento_casi_collaudo import PIGNORAMENTO, VERBALE_631, fonti


def _causa(_fid):
    return ragiona(fonti({"id": "F1", "rg": "792/2025", "tipo_procedimento": "esecuzione mobiliare"}, [PIGNORAMENTO, VERBALE_631]))


def test_fatti_dal_modello_con_documento_e_data():
    from lex.harness.causa import fatti_del_fascicolo

    f = fatti_del_fascicolo("F1", costruttore=_causa)
    testo = f.sezione()
    assert "21/12/2026" in testo or "16/12/2026" in testo        # udienza o termine letti dal verbale
    assert "12631033s.pdf" in testo                              # la prova: il documento da cui è letto


def test_domanda_nel_fascicolo_senza_regola_risponde_dal_modello():
    from lex.harness.http import payload_harness

    p = payload_harness("Entro quando devo depositare le note scritte in questo fascicolo?", fascicolo_id="F1", causa=_causa)
    assert p is not None and "Dal fascicolo" in p["answer"] and "16/12/2026" in p["answer"]
    assert p["lex_harness"]["2_fatti"]["origine"] == "modello_causa"


def test_fascicolo_assente_o_in_errore_non_inventa():
    from lex.harness.causa import fatti_del_fascicolo

    def guasto(_):
        raise RuntimeError("archivio non leggibile")

    assert fatti_del_fascicolo("F9", costruttore=guasto) is None
    assert fatti_del_fascicolo("", costruttore=_causa) is None
