"""Lo script di analisi dei fatti respinti (V13) conta senza esporre dati del cliente."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import mock

from pct.registro_letture import Fatto, Oggetto, RegistroLetture


def _script():
    percorso = Path(__file__).resolve().parents[1] / "deploy" / "hetzner" / "analisi_fatti_respinti.py"
    spec = importlib.util.spec_from_file_location("analisi_fatti_respinti", percorso)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_conta_esiti_e_prove_senza_valori_ne_contesti(tmp_path):
    registro = RegistroLetture(tmp_path / "letture.sqlite")
    oggetto = Oggetto(tipo="documento", oggetto_id="doc-riservato", sha256="a" * 64)
    fatti = [
        Fatto(categoria="data", campo="udienza", valore="2026-13-40", valore_letto="40/13/2026", contesto="Mario Rossi contro",
              verifica="respinta", prove=[{"codice": "calendario", "esito": "respinta", "dettaglio": "non è una data"}]),
        Fatto(categoria="data", campo="termine", valore="2026-11-12", valore_letto="12/11/2026", contesto="entro il",
              verifica="plausibile", prove=[{"codice": "orizzonte", "esito": "attenzione", "dettaglio": "lontana"}]),
    ]
    registro.registra_fatti("studio-x", "F-RISERVATO", oggetto, "documenti", fatti, versione="v1")
    modulo = _script()
    with mock.patch("web.services.archivio_letture_runtime.registro_corrente", return_value=registro), \
            mock.patch("web.services.archivio_letture_runtime.tenant_corrente", return_value="studio-x"):
        esito = modulo.riepilogo_studio_corrente()
    assert esito["fatti"] == 2 and esito["esiti"] == {"respinta": 1, "plausibile": 1}
    assert esito["prove_respinte"] == {"calendario": 1} and esito["respinti_con_una_sola_prova"] == {"calendario": 1}
    assert esito["respinti_per_campo"] == {"data/udienza": {"respinti": 1, "totali": 1}}
    assert esito["prove_attenzione"] == {"orizzonte": 1}
    testo = json.dumps(esito, ensure_ascii=False)
    for riservato in ("Mario Rossi", "F-RISERVATO", "doc-riservato", "2026-13-40", "non è una data"):
        assert riservato not in testo
