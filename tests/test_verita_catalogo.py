"""Etichette certe del catalogo: deposito telematico e decisioni dell'avvocato (dati sintetici)."""
from __future__ import annotations

import json
from types import SimpleNamespace

from pct.document_intelligence.verita import (
    LIVELLO_AVVOCATO,
    LIVELLO_DEPOSITO,
    censisci,
    chiave_portale,
    etichetta_dal_portale,
    etichette_dalle_decisioni,
    riepilogo,
)
from web.services.document_catalog_conferma import NOTA_CONFERMA_MASSIVA
from web.services.verita_catalogo_runtime import conferme_massive


def _assegnazione(documento: str, voce: str, *, stato: str = "proposed", origine: str = "verified_snapshot", sezione: str = "atti"):
    return SimpleNamespace(fascicolo_id="F1", document_id=documento, document_label=voce, document_section=sezione,
                           status=stato, source_state=origine, document_sha256=f"sha-{documento}")


def _documento(documento: str, classificazione: str = "", tipo_atto: str = ""):
    return SimpleNamespace(id=documento, classificazione_portale=classificazione, tipo_atto_portale=tipo_atto,
                           hash_sha256=f"sha-{documento}", eliminato_il="")


def test_decisioni_dell_avvocato_ma_non_le_conferme_massive():
    assegnazioni = [
        _assegnazione("d1", "Atto di citazione", origine="manual_override", stato="confirmed"),
        _assegnazione("d2", "Sentenza", stato="confirmed", sezione="provvedimenti"),
        _assegnazione("d3", "Procura alle liti", stato="confirmed", sezione="procure"),
        _assegnazione("d4", "Memoria difensiva", stato="rejected"),
        _assegnazione("d5", "Querela"),  # proposta mai decisa
    ]
    etichette = {e.document_id: e for e in etichette_dalle_decisioni(assegnazioni, conferme_massive={"d3"})}
    assert set(etichette) == {"d1", "d2", "d4"}
    assert etichette["d1"].fonte == "correzione_avvocato" and etichette["d1"].livello == LIVELLO_AVVOCATO
    assert etichette["d2"].fonte == "conferma_avvocato"
    assert etichette["d4"].negativa is True


def test_conferme_massive_dall_audit_nuovo_e_storico():
    eventi = [
        {"document_id": "d1", "event_type": "document_catalog.reviewed", "status": "confirmed", "payload": {"modalita": "massiva"}},
        {"document_id": "d2", "event_type": "document_catalog.reviewed", "status": "confirmed",
         "payload": {"note_length": len(NOTA_CONFERMA_MASSIVA)}},  # prima che l'audit dichiarasse la modalità
        {"document_id": "d3", "event_type": "document_catalog.reviewed", "status": "confirmed", "payload": {"modalita": "singola"}},
        # Una conferma massiva seguita da una correzione: conta la correzione.
        {"document_id": "d4", "event_type": "document_catalog.reviewed", "status": "confirmed", "payload": {"modalita": "massiva"}},
        {"document_id": "d4", "event_type": "document_catalog.overridden", "status": "confirmed", "payload": {}},
    ]
    assert conferme_massive(eventi) == {"d1", "d2"}


def test_portale_etichetta_atti_principali_e_provvedimenti():
    provvedimento = etichetta_dal_portale(_documento("p1", "PROVVEDIMENTO", "Provvedimento — Decreto Ingiuntivo"), fascicolo_id="F1")
    ricorso = etichetta_dal_portale(_documento("a1", "ATTO", "Decreto Ingiuntivo"), fascicolo_id="F1")
    assert provvedimento.etichetta == "Decreto ingiuntivo" and provvedimento.livello == LIVELLO_DEPOSITO
    assert ricorso.etichetta == "Ricorso per decreto ingiuntivo"
    # Un allegato appartiene alla busta del decreto ingiuntivo, ma non è un decreto ingiuntivo.
    assert etichetta_dal_portale(_documento("x1", "ALLEGATO", "Decreto Ingiuntivo"), fascicolo_id="F1") is None
    # Un tipo atto non dichiarato nella tabella non diventa un'etichetta per somiglianza.
    assert etichetta_dal_portale(_documento("x2", "ATTO", "Istanza generica di visibilità"), fascicolo_id="F1") is None
    assert chiave_portale(_documento("x3")) is None


def test_censimento_conflitti_concordanza_e_tipi_non_mappati():
    documenti = [
        _documento("p1", "PROVVEDIMENTO", "Decreto Ingiuntivo"),
        _documento("a1", "ATTO", "Decreto Ingiuntivo"),
        _documento("a2", "ATTO", "Atto di citazione"),
        _documento("a3", "ATTO", "Ricorso ex art. 702 bis"),
    ]
    assegnazioni = [
        _assegnazione("p1", "Decreto ingiuntivo", sezione="provvedimenti"),  # il catalogo concorda
        _assegnazione("a1", "Istanza"),  # il catalogo sbaglia
        _assegnazione("a2", "Comparsa di costituzione e risposta", origine="manual_override", stato="confirmed"),
        _assegnazione("x9", "Dati strutturati PST — DatiAtto", sezione="allegati"),
    ]
    censimento = censisci(documenti, assegnazioni, fascicolo_id="F1")
    assert {(e.document_id, e.etichetta) for e in censimento["etichette"]} == {
        ("p1", "Decreto ingiuntivo"), ("a1", "Ricorso per decreto ingiuntivo"), ("a2", "Comparsa di costituzione e risposta"),
    }
    assert censimento["conflitti"] == [{"document_id": "a2", "portale": "Atto di citazione", "avvocato": "Comparsa di costituzione e risposta"}]
    assert censimento["portale_non_mappati"] == {"ATTO: ricorso ex art 702 bis": 1}
    assert censimento["strutturali"] == 1

    sintesi = riepilogo([censimento], minimo_per_voce=1)
    assert sintesi["etichette_positive"] == 3
    assert sintesi["per_livello"] == {"deposito_telematico": 2, "avvocato": 1}
    assert sintesi["concordanza_catalogo_con_deposito"]["Ricorso per decreto ingiuntivo"] == {"misurati": 1, "concordi": 0}
    assert sintesi["concordanza_catalogo_con_deposito"]["Decreto ingiuntivo"] == {"misurati": 1, "concordi": 1}


def test_il_riepilogo_non_contiene_identificativi_ne_impronte():
    censimento = censisci([_documento("DOC-SEGRETO", "ATTO", "Atto di citazione")],
                          [_assegnazione("DOC-SEGRETO", "Atto di citazione")], fascicolo_id="FASC-SEGRETO")
    testo = json.dumps(riepilogo([censimento]), ensure_ascii=False)
    assert "SEGRETO" not in testo and "sha-" not in testo


def test_repository_sqlite_elenca_le_decisioni_del_fascicolo_in_ordine(tmp_path):
    from pct.document_intelligence.repository import DocumentAIRepository

    repo = DocumentAIRepository.from_sqlite_db(tmp_path / "studio.db", storage_root=tmp_path / "storage")
    base = {"tenant_id": "tenant-a", "fascicolo_id": "fas-1", "document_id": "d1", "version_id": None, "user_id": "avv",
            "sha256": "", "filename": ""}
    repo.append_audit_event({**base, "id": "e1", "event_type": "document_catalog.reviewed", "timestamp": "2026-10-29T10:00:00Z",
                             "status": "confirmed", "payload": {"modalita": "massiva"}})
    repo.append_audit_event({**base, "id": "e2", "event_type": "document_catalog.overridden", "timestamp": "2026-10-29T10:05:00Z",
                             "status": "confirmed", "payload": {"prima": {"voce": "Istanza"}, "dopo": {"voce": "Atto di citazione"}}})
    repo.append_audit_event({**base, "id": "e3", "event_type": "document_ai.upload.completed", "timestamp": "2026-10-29T10:06:00Z"})
    repo.append_audit_event({**base, "id": "e4", "fascicolo_id": "fas-2", "event_type": "document_catalog.reviewed",
                             "timestamp": "2026-10-29T10:07:00Z", "status": "confirmed"})

    eventi = repo.list_catalog_decision_events("tenant-a", "fas-1")

    assert [e["event_type"] for e in eventi] == ["document_catalog.reviewed", "document_catalog.overridden"]
    assert eventi[0]["payload"] == {"modalita": "massiva"} and eventi[0]["status"] == "confirmed"
    assert eventi[1]["payload"]["dopo"] == {"voce": "Atto di citazione"}
    assert conferme_massive(eventi) == set()  # l'ultima decisione su d1 è la correzione
    repo.close()


def test_censimento_dello_studio_percorre_tutti_i_fascicoli_anche_archiviati(monkeypatch):
    # Il primo censimento sul server (2.457.8) trattava il gestore dei fascicoli come un dizionario.
    import web.helpers as helpers
    import web.services.document_intelligence_runtime as di_runtime
    from web.services.verita_catalogo_runtime import censimento_studio_corrente

    fascicoli = [SimpleNamespace(id="F1", documenti=[_documento("p1", "PROVVEDIMENTO", "Sentenza")]),
                 SimpleNamespace(id="F2", documenti=[_documento("a1", "ATTO", "Atto di citazione", )])]
    chiamate = []

    class _Gestore:
        def tutti(self, archiviati=False):
            chiamate.append(archiviati)
            return fascicoli

    class _Repository:
        def list_catalog_assignments(self, tenant_id, fascicolo_id):
            if fascicolo_id == "F2":
                raise RuntimeError("catalogo non pronto")
            return [_assegnazione("p1", "Sentenza", sezione="provvedimenti")]

        def list_catalog_decision_events(self, tenant_id, fascicolo_id):
            return []

    monkeypatch.setattr(helpers, "get_fascicoli", lambda: _Gestore())
    monkeypatch.setattr(di_runtime, "build_document_ai_service", lambda: SimpleNamespace(repository=_Repository()))
    monkeypatch.setattr(di_runtime, "document_ai_tenant_id", lambda: "tenant")

    censimenti = censimento_studio_corrente()

    assert chiamate == [True]
    assert [c["fascicolo_id"] for c in censimenti] == ["F1"]  # F2 senza catalogo non ferma il censimento
    assert riepilogo(censimenti)["per_voce"] == {"Sentenza": 1}


def _doc_fascicolo(id_doc: str, nome: str, **campi):
    from pct.fascicoli import Documento, TipoDocumento

    return Documento(id=id_doc, nome=nome, tipo=TipoDocumento.ALTRO, percorso=f"{id_doc}.pdf", hash_sha256=f"sha-{id_doc}", **campi)


def test_depositi_dal_portale_etichettano_atto_e_provvedimento_ma_non_gli_allegati():
    from pct.document_intelligence.verita import etichette_dai_depositi
    from pct.fascicoli import EsitoDepositoPCT

    deposito = EsitoDepositoPCT(
        id="dep1", timestamp="2026-01-15T10:00:00", stato="ACCETTATO_CANCELLERIA", tipo_atto="Decreto Ingiuntivo",
        pec_destinatario="", documenti_ids=["d1", "d2", "d3"], fonte_portale="PolisWeb",
        documenti_portale=[
            {"id_documento": "P-1", "nome": "ricorso.pdf", "tipo": "ATTO", "tipo_atto": "Decreto Ingiuntivo"},
            {"id_documento": "P-2", "nome": "procura.pdf", "tipo": "ALLEGATO", "tipo_atto": "Decreto Ingiuntivo"},
            {"id_documento": "P-3", "nome": "decreto.pdf", "tipo": "PROVVEDIMENTO", "tipo_atto": "Provvedimento — Decreto Ingiuntivo"},
        ],
    )
    fascicolo = SimpleNamespace(id="F1", depositi_pct=[deposito], documenti=[
        _doc_fascicolo("d1", "ricorso.pdf", id_documento_portale="P-1"),
        _doc_fascicolo("d2", "procura.pdf", id_documento_portale="P-2"),
        _doc_fascicolo("d3", "decreto.pdf", id_documento_portale="P-3"),
    ])

    esito = etichette_dai_depositi(fascicolo)

    assert {(e.document_id, e.etichetta) for e in esito["etichette"]} == {
        ("d1", "Ricorso per decreto ingiuntivo"), ("d3", "Decreto ingiuntivo")}
    assert esito["conteggi"] == {"depositi_portale": 1}


def test_deposito_dello_studio_etichetta_solo_l_atto_principale_e_conta_i_tipi_nuovi():
    from pct.document_intelligence.verita import etichette_dai_depositi
    from pct.fascicoli import EsitoDepositoPCT

    nota = EsitoDepositoPCT(id="dep1", timestamp="2026-02-01T09:00:00", stato="INVIATO", tipo_atto="Note scritte",
                            pec_destinatario="", documenti_ids=["n1", "a1"], nome_atto_principale="note.pdf")
    nuovo = EsitoDepositoPCT(id="dep2", timestamp="2026-03-01T09:00:00", stato="INVIATO", tipo_atto="Istanza di visibilità",
                             pec_destinatario="", documenti_ids=["i1"], nome_atto_principale="istanza.pdf")
    fascicolo = SimpleNamespace(id="F1", depositi_pct=[nota, nuovo], documenti=[
        _doc_fascicolo("n1", "note.pdf"), _doc_fascicolo("a1", "allegato.pdf"), _doc_fascicolo("i1", "istanza.pdf"),
    ])

    esito = etichette_dai_depositi(fascicolo)

    assert [(e.document_id, e.etichetta, e.fonte) for e in esito["etichette"]] == [
        ("n1", "Note di trattazione scritta", "deposito_telematico_studio")]
    assert esito["non_mappati"] == {"studio: istanza di visibilita": 1}
    assert esito["conteggi"] == {"depositi_studio": 2}


def test_statistiche_del_catalogo_e_candidate_argento():
    from pct.document_intelligence.verita.censimento import statistiche_catalogo

    assegnazioni = [
        SimpleNamespace(status="proposed", source_state="verified_snapshot", document_label="Sentenza", confidence=99),
        SimpleNamespace(status="proposed", source_state="verified_snapshot", document_label="Istanza", confidence=80),
        SimpleNamespace(status="review_required", source_state="review_required", document_label="Contenuto da verificare", confidence=40),
        SimpleNamespace(status="proposed", source_state="verified_snapshot", document_label="Dati strutturati PST — Ricorso", confidence=99),
    ]
    statistiche = statistiche_catalogo(assegnazioni)
    assert statistiche["argento_per_voce"] == {"Sentenza": 1}
    assert statistiche["fasce_confidenza_proposte"] == {"96-100": 1, "75-89": 1}
    assert statistiche["stati"]["proposed/verified_snapshot"] == 3


def test_il_riepilogo_non_porta_nomi_dei_clienti() -> None:
    """Le voci intitolate al titolare o scritte a mano escono dal server solo come voce del catalogo."""
    from pct.document_intelligence.verita import voce_pubblicabile
    from pct.document_intelligence.verita.censimento import VOCE_FUORI_ELENCO

    assert voce_pubblicabile("Carta d'identità di Mario Rossi") == "Carta d'identità"
    assert voce_pubblicabile("Patente di guida di Mario Rossi") == "Patente di guida"
    assert voce_pubblicabile("Sentenza") == "Sentenza"
    assert voce_pubblicabile("Contratto di consulenza con Mario Rossi") == VOCE_FUORI_ELENCO
    # Voci fisse del resolver e del catalogo del fascicolo, scritte per esteso nel codice.
    assert voce_pubblicabile("Contributo unificato / esenzione") == "Contributo unificato / esenzione"
    assert voce_pubblicabile("Messaggio email") == "Messaggio email"
    assert voce_pubblicabile("Indice dei documenti depositati") == "Indice dei documenti depositati"
    assert voce_pubblicabile("Istanza ex art 492.PDF") == VOCE_FUORI_ELENCO

    assegnazioni = [
        SimpleNamespace(document_id=f"D{n}", document_label="Carta d'identità di Mario Rossi", status="proposed",
                        source_state="verified_snapshot", confidence=99)
        for n in range(3)
    ] + [SimpleNamespace(document_id="X", document_label="Lettera a Mario Rossi", status="confirmed",
                         source_state="manual_override", confidence=100, document_section="atti", fascicolo_id="F1",
                         updated_by="avv", updated_at="2026-10-29", metadata={})]
    esito = riepilogo([censisci([], assegnazioni, fascicolo_id="F1")], minimo_per_voce=1)
    testo = json.dumps(esito, ensure_ascii=False)
    assert "Rossi" not in testo
    assert esito["argento_per_voce"] == {"Carta d'identità": 3}
    assert VOCE_FUORI_ELENCO not in esito["voci_addestrabili"]
