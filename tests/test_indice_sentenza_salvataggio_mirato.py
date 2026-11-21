"""L'esito dell'indice della sentenza si salva sul solo fascicolo.

Dal ciclo delle letture l'archivio dei fascicoli è caricato in parte e il salvataggio integrale è bloccato
(pct/fascicoli.py, _salva): usarlo interrompeva l'intera lettura del fascicolo (52 fascicoli sull'8080, 21/11/2026).
"""
from types import SimpleNamespace

from web.services import document_intelligence_runtime as runtime


class _ArchivioParziale:
    def __init__(self):
        self.fascicolo = SimpleNamespace(pagamenti={})
        self.mirati = []

    def get(self, fascicolo_id):
        return self.fascicolo

    def aggiorna(self, fascicolo_id, **campi):
        raise RuntimeError("Salvataggio integrale bloccato: l'archivio è stato caricato solo parzialmente.")

    def aggiorna_pagamenti(self, fascicolo_id, pagamenti):
        self.mirati.append((fascicolo_id, pagamenti))
        self.fascicolo.pagamenti = pagamenti


def test_esito_indice_sentenza_usa_il_salvataggio_mirato():
    archivio = _ArchivioParziale()
    runtime._record_vector_index_result(
        fascicoli_repository=archivio,
        fascicolo_id="9A681FDF",
        document_key="2657592E",
        vector_result={"ok": True, "status": "indexed"},
    )
    assert len(archivio.mirati) == 1
    fascicolo_id, pagamenti = archivio.mirati[0]
    assert fascicolo_id == "9A681FDF"
    indici = pagamenti[runtime.AUTOMATION_KEY]["vector_indexes"]
    assert indici["2657592E"] == {"ok": True, "status": "indexed"}
