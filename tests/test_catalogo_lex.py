"""Seconda lettura di Lex: voci chiuse, citazione verificata, mai automatica."""
from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pct.document_intelligence import DocumentAIRepository
from pct.document_intelligence.catalog_lex import (
    CONFIDENZA_LEX,
    LOCATORE_LEX,
    NESSUNA_VOCE,
    VERSIONE_LETTURA,
    EsitoLex,
    applica_esito,
    citazione_nel_testo,
    da_rileggere,
    leggi_con_lex,
    schema_risposta,
    voci_catalogo,
)
from pct.document_intelligence.catalog_pipeline import FascicoloDocumentCatalogPipeline
from tests.test_fascicolo_document_catalog_pipeline import _ready_source

NOTE = (
    "Tribunale di Bari\nSezione Lavoro\nUdienza del 30.06.2026\nNote in sostituzione\nPer il sig. Mario Rossi\n"
    "Il ricorrente rassegna le seguenti conclusioni. Il ricorso e il pedissequo decreto di fissazione udienza "
    "sono stati notificati alla resistente."
)


def _risposta(etichetta: str, citazione: str, motivo: str = "atto di parte con conclusioni"):
    def genera(domanda: str, schema: dict) -> str:
        genera.domanda = domanda
        genera.schema = schema
        return json.dumps({"etichetta": etichetta, "citazione": citazione, "motivo": motivo})

    return genera


def _voce(label: str):
    return next(voce for voce in voci_catalogo() if voce.label == label)


def test_le_voci_sono_quelle_del_catalogo_senza_doppioni():
    voci = voci_catalogo()
    etichette = [voce.label for voce in voci]
    assert len(etichette) == len(set(etichette))
    for attesa in ("Sentenza", "Note scritte ex art. 127-ter c.p.c.", "Contratto di lavoro", "Procura alle liti"):
        assert attesa in etichette
    assert {voce.section for voce in voci} <= {
        "atti", "provvedimenti", "procure", "notifiche", "comunicazioni", "contratti", "pagamenti", "identita", "allegati", "da-verificare",
    }


def test_la_risposta_e_vincolata_all_elenco_chiuso():
    schema = schema_risposta(voci_catalogo())
    assert NESSUNA_VOCE in schema["properties"]["etichetta"]["enum"]
    assert "Sentenza" in schema["properties"]["etichetta"]["enum"]


def test_lex_sceglie_una_voce_con_una_citazione_vera():
    genera = _risposta("Note scritte ex art. 127-ter c.p.c.", "Il ricorrente rassegna le seguenti conclusioni")
    esito = leggi_con_lex(NOTE, genera=genera, contesto="Tribunale di Bari · R.G. 1/2026")
    assert esito.stato == "scelta"
    assert esito.voce.section == "atti"
    assert "Tribunale di Bari · R.G. 1/2026" in genera.domanda
    assert "DOCUMENTO:" in genera.domanda


def test_una_citazione_inventata_non_conta():
    esito = leggi_con_lex(NOTE, genera=_risposta("Note scritte ex art. 127-ter c.p.c.", "le parti precisano le conclusioni definitive"))
    assert esito.stato == "non_verificata"


@pytest.mark.parametrize("risposta", ["non e' json", json.dumps({"etichetta": "Atto inventato", "citazione": "Il ricorrente rassegna", "motivo": ""})])
def test_risposte_fuori_regola_sono_errori(risposta):
    assert leggi_con_lex(NOTE, genera=lambda domanda, schema: risposta).stato == "errore"


def test_la_citazione_si_confronta_senza_punteggiatura_ne_maiuscole():
    assert citazione_nel_testo("il RICORSO, e il pedissequo decreto", NOTE)
    assert not citazione_nel_testo("decreto", NOTE)  # troppo corta per provare qualcosa


def test_la_citazione_regge_alla_riga_della_firma_digitale_in_mezzo():
    testo = "Il Giudice\nRINVIA D'UFFICIO\nFirmato Da: MARIA NERI Emesso Da: CA DI FIRMA Serial#: 6841\nla causa all'udienza del 30.06.2026"
    assert citazione_nel_testo("RINVIA D'UFFICIO la causa all'udienza del 30.06.2026", testo)
    assert not citazione_nel_testo("RINVIA D'UFFICIO la causa al giudice istruttore", testo)


def _assegnazione(repo, tmp_path, testo: str):
    tenant_id, fascicolo_id = "studio-test", "FASC-LEX"
    source = _ready_source(repo, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id="DOC-LEX", filename="documento.pdf", sha256="7" * 64, text=testo)
    fascicolo = SimpleNamespace(
        id=fascicolo_id, area_pratica="Lavoro", tribunale="Tribunale di Bari", tipo_procedimento="Lavoro",
        canale_operativo="PCT", source="PST", profilo_deposito={"area": "Lavoro e previdenza", "branca": "Pubblico impiego", "sottobranca": "retribuzione"},
    )
    FascicoloDocumentCatalogPipeline(repo, text_provider=lambda document_id: testo).run(
        tenant_id=tenant_id, fascicolo=fascicolo, sources=[source], actor="operatore", process=True,
    )
    return repo.get_catalog_assignment(tenant_id, fascicolo_id, "DOC-LEX")


def test_una_regola_incerta_diventa_la_proposta_motivata_di_lex(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = _assegnazione(repo, tmp_path, NOTE)
    assignment = replace(assignment, status="review_required", confidence=60)
    esito = EsitoLex("scelta", "Note scritte ex art. 127-ter c.p.c.", "Il ricorrente rassegna le seguenti conclusioni", "atto di parte", _voce("Note scritte ex art. 127-ter c.p.c."))

    nuova, candidati, evidenze = applica_esito(assignment, repo.list_catalog_candidates(assignment.id), repo.list_catalog_evidence(assignment.id), esito, modello="qwen3:4b", durata_s=31.2)
    repo.save_catalog_assignment(nuova, candidates=candidati, evidence=evidenze)

    salvata = repo.get_catalog_assignment("studio-test", "FASC-LEX", "DOC-LEX")
    assert salvata.document_label == "Note scritte ex art. 127-ter c.p.c."
    assert salvata.status == "proposed"  # una proposta, mai una catalogazione automatica
    assert salvata.confidence == CONFIDENZA_LEX
    assert salvata.metadata["automatic_classification"] is False
    assert salvata.metadata["lex_lettura"]["versione"] == VERSIONE_LETTURA
    assert repo.list_catalog_candidates(salvata.id)[0].document_label == "Note scritte ex art. 127-ter c.p.c."
    assert any(e.locator.startswith(LOCATORE_LEX) and "rassegna" in e.excerpt for e in repo.list_catalog_evidence(salvata.id))
    assert not da_rileggere(salvata, modello="qwen3:4b")
    assert da_rileggere(salvata, modello="gemma3:4b")


def test_contro_una_regola_sicura_lex_non_decide_ma_segnala(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = replace(_assegnazione(repo, tmp_path, NOTE), document_label="Decreto di fissazione udienza", document_section="provvedimenti", status="proposed", confidence=98)
    esito = EsitoLex("scelta", "Note scritte ex art. 127-ter c.p.c.", "Il ricorrente rassegna le seguenti conclusioni", "atto di parte", _voce("Note scritte ex art. 127-ter c.p.c."))

    nuova, candidati, _ = applica_esito(assignment, [], [], esito, modello="qwen3:4b")

    assert nuova.document_label == "Decreto di fissazione udienza"
    assert nuova.status == "review_required"  # cambia perfino la sezione: la guarda l'avvocato
    assert nuova.metadata["automatic_classification"] is False
    assert candidati[-1].document_label == "Note scritte ex art. 127-ter c.p.c."


def test_lex_che_conferma_rende_motivata_una_proposta_dubbia(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = replace(_assegnazione(repo, tmp_path, NOTE), document_label="Sentenza", status="review_required", confidence=60)
    esito = EsitoLex("scelta", "Sentenza", "Il ricorrente rassegna le seguenti conclusioni", "", _voce("Sentenza"))
    nuova, _, evidenze = applica_esito(assignment, [], [], esito, modello="qwen3:4b")
    assert nuova.status == "proposed" and nuova.confidence == CONFIDENZA_LEX
    assert [e.locator for e in evidenze] == [f"{LOCATORE_LEX} (qwen3:4b)"]


def test_una_lettura_non_verificata_non_cambia_nulla(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = _assegnazione(repo, tmp_path, NOTE)
    esito = EsitoLex("non_verificata", "Sentenza", "frase inventata", "", _voce("Sentenza"))
    nuova, _, _ = applica_esito(assignment, [], [], esito, modello="qwen3:4b")
    assert (nuova.document_label, nuova.status, nuova.confidence) == (assignment.document_label, assignment.status, assignment.confidence)
    assert nuova.metadata["lex_lettura"]["esito"] == "non_verificata"


def test_le_catalogazioni_confermate_o_corrette_non_si_rileggono(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = _assegnazione(repo, tmp_path, NOTE)
    assert not da_rileggere(replace(assignment, status="confirmed"), modello="qwen3:4b")
    assert not da_rileggere(replace(assignment, source_state="manual_override"), modello="qwen3:4b")
    assert not da_rileggere(replace(assignment, status="proposed", confidence=96), modello="qwen3:4b")  # regola sicura
    assert da_rileggere(replace(assignment, status="proposed", confidence=82, metadata={}), modello="qwen3:4b")
    assert da_rileggere(replace(assignment, status="review_required", confidence=96, metadata={}), modello="qwen3:4b")


def test_la_coda_parte_dalle_proposte_piu_dubbie(tmp_path):
    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = _assegnazione(repo, tmp_path, NOTE)
    repo.save_catalog_assignment(replace(assignment, status="review_required", confidence=60))
    assert [voce.document_id for voce in repo.list_catalog_assignments_to_reread("studio-test")] == ["DOC-LEX"]
    assert repo.list_catalog_assignments_to_reread("altro-studio") == []
    repo.save_catalog_assignment(replace(assignment, status="confirmed"))
    assert repo.list_catalog_assignments_to_reread("studio-test") == []


def test_il_giro_rilegge_un_documento_e_si_ferma(tmp_path, monkeypatch):
    import web.helpers
    import web.services.archivio_letture_runtime as letture
    import web.services.document_intelligence_runtime as runtime
    from web.services.catalogo_lex_runtime import seconda_lettura_studio_corrente

    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db")
    assignment = _assegnazione(repo, tmp_path, NOTE)
    repo.save_catalog_assignment(replace(assignment, status="review_required", confidence=60))
    fascicolo = SimpleNamespace(id="FASC-LEX", tribunale="Tribunale di Bari", numero_rg="1", anno_rg="2026", oggetto="retribuzione")
    monkeypatch.setattr(runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=repo))
    monkeypatch.setattr(runtime, "document_ai_tenant_id", lambda: "studio-test")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: {"FASC-LEX": fascicolo})
    monkeypatch.setattr(letture, "testi_indice_archivio", lambda f: {"DOC-LEX": NOTE})

    genera = _risposta("Note scritte ex art. 127-ter c.p.c.", "Il ricorrente rassegna le seguenti conclusioni")
    primo = seconda_lettura_studio_corrente(genera=genera, modello="qwen3:4b")
    secondo = seconda_lettura_studio_corrente(genera=genera, modello="qwen3:4b")

    assert primo == {"lette": 1, "scelte": 1, "cambiate": 1, "errori": 0}
    assert secondo["lette"] == 0  # gia' letto per questo documento e questo modello
    assert repo.get_catalog_assignment("studio-test", "FASC-LEX", "DOC-LEX").document_label == "Note scritte ex art. 127-ter c.p.c."


def test_modello_del_catalogo_spark_con_riserva_qwen(monkeypatch):
    from web.services import catalogo_lex_runtime as runtime

    monkeypatch.delenv("PCT_LEX_CATALOGO_MODELLO", raising=False)
    monkeypatch.setattr(runtime, "_MODELLI_NON_ESEGUIBILI", set())
    assert runtime.modello_catalogo() == "maternion/spark-x2.5:4b"
    assert runtime._modello_non_eseguibile("llama runner: unknown model architecture: 'spark2_5'")
    assert not runtime._modello_non_eseguibile("connection refused")
    runtime._MODELLI_NON_ESEGUIBILI.add("maternion/spark-x2.5:4b")
    assert runtime.modello_catalogo() == "qwen3:4b"
