from __future__ import annotations

from types import SimpleNamespace
import copy
import pytest

import web.services.react_fascicoli_bridge as bridge
import web.services.sentenza_economic_runtime as runtime
from pct.sentenza_economic_repository import SentenzaEconomicRepository


SENT_DISTRAZIONE = """TRIBUNALE ORDINARIO DI MILANO - R.G. 1234/2025
definitivamente pronunciando, accoglie la domanda di Mario Rossi contro Beta S.r.l.;
condanna la parte convenuta al pagamento delle spese di lite, che liquida in complessivi euro 4.200,00
con distrazione in favore del procuratore antistatario avv. Bianchi."""


def _fasc():
    return SimpleNamespace(id="F1", numero_rg="1234", anno_rg=2025, nome_cliente="Mario Rossi",
                           tribunale="Tribunale di Milano", controparte="Beta S.r.l.", valore_causa=3000.0)


def _sentenza_doc():
    return SimpleNamespace(id="D1", nome="sentenza-tribunale.pdf", tipo="SENTENZA", hash_sha256="hash-sentenza")


def test_bridge_helper_espone_gli_importi_liquidati(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True,
        "summary": {
            "kpi": {"label": "Spese da sentenza", "value": "€ 4.200,00", "tone": "primary"},
            "worklist": [{"label": "Spese distratte in favore dell'avvocato", "hint": "Credito diretto ex art. 93 c.p.c.", "value": "€ 4.200,00", "tone": "info"}],
            "totals": {"sentenze_lette": 1, "sentenze_verificate": 1, "da_verificare": 0,
                       "crediti_cliente": 0.0, "crediti_avvocato_antistatario": 4200.0,
                       "spese_liquidate_totale": 4200.0, "contributo_unificato_alert": 0},
        },
    })
    block = bridge._sentenze_economiche("F1")
    assert block is not None
    assert block["totals"]["spese_liquidate_totale"] == 4200.0
    assert block["totals"]["crediti_avvocato_antistatario"] == 4200.0
    assert any("art. 93" in item["hint"] for item in block["worklist"])


def test_bridge_helper_none_se_flag_spento(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {"ok": False, "code": "feature_disabled"})
    assert bridge._sentenze_economiche("F1") is None


def test_bridge_helper_none_se_nessuna_sentenza(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True, "summary": {"kpi": {}, "worklist": [], "totals": {"sentenze_lette": 0}},
    })
    assert bridge._sentenze_economiche("F1") is None


def test_bridge_helper_non_mostra_id_documento_numerico():
    assert bridge._readable_document_source("20260317101453130") == "Documento indicizzato del fascicolo"
    assert bridge._readable_document_source("20260317101453130.PDF") == "Documento indicizzato del fascicolo"


def test_payment_item_non_espone_id_documento_numerico():
    item = bridge._payment_item(
        "contributo_unificato",
        {
            "status": "pagato",
            "importo": 49.0,
            "documento_fonte": "20260317101453130.PDF",
        },
        "F1",
    )

    assert item["documentoFonte"] == "Ricevuta pagoPA"
    assert item["documentoFonteRaw"] == "20260317101453130.PDF"


def test_bridge_helper_sanitizza_fonte_sentenza_runtime(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True,
        "summary": {
            "kpi": {"label": "Evidenze economiche lette", "value": "€ 258,00", "tone": "success"},
            "worklist": [{
                "label": "Liquidazione letta",
                "value": "€ 258,00",
                "hint": "Pagato - Fonte: sentenza_key:studio|F1|2026-06-15|652|2026|912|2026",
                "tone": "success",
            }],
            "totals": {"sentenze_lette": 1, "sentenze_verificate": 0, "da_verificare": 0,
                       "crediti_cliente": 0.0, "crediti_avvocato_antistatario": 0.0,
                       "spese_liquidate_totale": 258.0, "contributo_unificato_alert": 0},
        },
    })

    block = bridge._sentenze_economiche("F1")

    assert block is not None
    assert "sentenza_key" not in block["worklist"][0]["hint"]
    assert "Sentenza del 15/06/2026" in block["worklist"][0]["hint"]


def test_bridge_helper_mostra_evidenze_economiche_gia_lette_se_audit_vuoto(monkeypatch):
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": {
        "ok": True, "summary": {"kpi": {}, "worklist": [], "totals": {"sentenze_lette": 0}},
    })
    block = bridge._sentenze_economiche("F1", payment_summary={
        "items": {
            "liquidazione_giudice": {
                "status": "pagato",
                "statusLabel": "Pagato",
                "importo": 258.0,
                "documentoFonte": "sentenza_key:studio|F1|2026-06-15|652|2026|912|2026",
                "tone": "success",
            },
            "parcella": {
                "status": "da_emettere",
                "statusLabel": "Da emettere",
                "importo": 376.46,
                "documentoFonte": "sentenza_key:studio|F1|2026-06-15|652|2026|912|2026",
                "tone": "warning",
            },
        },
    })

    assert block is not None
    assert block["totals"]["sentenze_lette"] == 1
    assert block["totals"]["spese_liquidate_totale"] == 258.0
    assert block["kpi"]["value"] == "€ 258,00"
    assert any(item["label"] == "Liquidazione letta" and item["value"] == "€ 258,00" for item in block["worklist"])
    assert all("sentenza_key" not in item["hint"] for item in block["worklist"])
    assert any("Sentenza del 15/06/2026" in item["hint"] for item in block["worklist"])


def test_importi_repository_non_confermati_restano_evidenze(monkeypatch, tmp_path):
    # Semina un audit reale (distrazione -> credito avvocato 4200) nel repo tenant.
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    runtime.run_analysis(
        fascicolo=_fasc(), testo=SENT_DISTRAZIONE, repo=repo,
        cu_tiers=[(1100.0, 43.0), (5200.0, 98.0)], tenant_id="studio-a",
        actor_id="avv", documento_id="D1", document_hash_sha256="hh",
    )
    # Il runtime (percorso vivo del payload) legge quel repo per il tenant/fascicolo.
    monkeypatch.setattr(runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(runtime, "_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_repo", lambda: repo)

    payload = runtime.build_sentenza_economic_payload("F1")
    assert payload["ok"] is True
    totals = payload["summary"]["totals"]
    assert totals["sentenze_lette"] == 1
    assert totals["crediti_avvocato_antistatario"] == 0.0
    assert totals["spese_liquidate_totale"] == 0.0
    assert any(row["value"] == "€ 4.200,00" and row["tone"] == "warning" for row in payload["summary"]["worklist"])
    # E il bridge lo trasforma nel blocco che il frontend renderizza.
    monkeypatch.setattr(runtime, "build_sentenza_economic_payload", lambda fid="": payload)
    block = bridge._sentenze_economiche("F1")
    assert block["totals"]["spese_liquidate_totale"] == 0.0


def test_payload_get_non_avvia_analisi_documenti_sentenza(monkeypatch, tmp_path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    fascicolo = _fasc()
    fascicolo.documenti = [_sentenza_doc()]
    monkeypatch.setattr(runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(runtime, "_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_repo", lambda: repo)
    monkeypatch.setattr(runtime, "_resolve_fascicolo", lambda fid: fascicolo if fid == "F1" else None)
    monkeypatch.setattr(runtime, "_document_texts_for_fascicolo", lambda _fascicolo, _tenant_id: {"D1": SENT_DISTRAZIONE})

    payload = runtime.build_sentenza_economic_payload("F1")
    assert payload["ok"] is True
    assert payload["autoAnalysis"] == {"ok": True, "source": "archivio_letture", "analyzed": 0}
    assert payload["summary"]["totals"]["sentenze_lette"] == 0

    second = runtime.build_sentenza_economic_payload("F1")
    assert second["autoAnalysis"] == {"ok": True, "source": "archivio_letture", "analyzed": 0}
    assert second["summary"]["totals"]["sentenze_lette"] == 0


def test_payload_get_non_analizza_le_sentenze_candidate(monkeypatch, tmp_path):
    repo = SentenzaEconomicRepository(tmp_path / "se.db")
    fascicolo = _fasc()
    fascicolo.documenti = [
        SimpleNamespace(id=f"D{index}", nome=f"sentenza-{index}.pdf", tipo="SENTENZA", hash_sha256=f"hash-{index}")
        for index in range(10)
    ]
    monkeypatch.setattr(runtime, "_flag_on", lambda: True)
    monkeypatch.setattr(runtime, "_tenant_id", lambda: "studio-a")
    monkeypatch.setattr(runtime, "_repo", lambda: repo)
    monkeypatch.setattr(runtime, "_resolve_fascicolo", lambda fid: fascicolo if fid == "F1" else None)
    monkeypatch.setattr(
        runtime,
        "_document_texts_for_fascicolo",
        lambda _fascicolo, _tenant_id: {f"D{index}": SENT_DISTRAZIONE for index in range(10)},
    )

    payload = runtime.build_sentenza_economic_payload("F1")

    assert payload["ok"] is True
    assert payload["autoAnalysis"] == {"ok": True, "source": "archivio_letture", "analyzed": 0}
    assert payload["summary"]["totals"]["sentenze_lette"] == 0


def test_resolve_fascicolo_usa_repository_mirato_senza_helper_globale(monkeypatch):
    from flask import Flask

    marker = SimpleNamespace(id="F1")

    class _TargetedRepo:
        def get(self, fascicolo_id):
            return marker if fascicolo_id == "F1" else None

    monkeypatch.setattr("web.helpers.get_fascicoli", lambda: (_ for _ in ()).throw(AssertionError("helper globale chiamato")))
    app = Flask(__name__)
    app.extensions["core_runtime"] = {"get_fascicoli_mirato": lambda: _TargetedRepo()}
    with app.app_context():
        assert runtime._resolve_fascicolo("F1") is marker


class _EconomicFascicoliRepo:
    def __init__(self, fascicolo):
        self.fascicolo = fascicolo

    def get(self, fascicolo_id):
        return self.fascicolo if fascicolo_id == self.fascicolo.id else None

    def tutti(self):
        return [self.fascicolo]

    def aggiorna(self, fascicolo_id, **changes):
        assert fascicolo_id == self.fascicolo.id
        for key, value in changes.items():
            setattr(self.fascicolo, key, value)
        return self.fascicolo


class _EconomicFatturazioneRepo:
    def per_fascicolo(self, _fascicolo_id):
        return []

    def elimina(self, _documento_id):
        return True


def _economic_fascicolo(payments=None):
    return SimpleNamespace(
        id="F-PROFORMA",
        id_cliente="C-PROFORMA",
        titolo="Calabrò Daniela",
        numero_rg="3571",
        anno_rg=2025,
        pagamenti=payments or {},
        documenti=[],
    )


@pytest.mark.parametrize("state", ["DEFINITO", "ARCHIVIATO", "DA_ARCHIVIARE", "APERTO"])
@pytest.mark.parametrize("amount", [None, 321.0])
def test_sentenza_o_segnaposto_importato_non_impongono_parcella(state, amount):
    case = _economic_fascicolo({"parcella": {"status": "da_emettere", "note": "Presidio creato dall'import pratiche"},
                                "liquidazione_giudice": {"status": "da_registrare", "importo": amount}})
    case.stato = state
    before = copy.deepcopy(case.pagamenti)
    items = {kind: bridge._payment_item(kind, raw, case.id) for kind, raw in case.pagamenti.items()}
    result = bridge._proforma_presidio_for_fascicolo(case, items=items)
    assert result["status"] == "facoltativa" and not result["requiresAction"]
    assert result["existingCount"] == 0
    assert case.pagamenti == before
    assert items["liquidazione_giudice"]["importo"] == amount


def test_parcella_facoltativa_preserva_incasso_e_documento_esistente():
    case = _economic_fascicolo({"parcella": {"status": "pagato", "incasso_importo": 1315.6, "proforma_id": "P-1"}})
    case.stato = "DEFINITO"
    items = {"parcella": bridge._payment_item("parcella", case.pagamenti["parcella"], case.id)}
    paid = bridge._proforma_presidio_for_fascicolo(case, items=items)
    assert paid["status"] == "pagato" and paid["total"] == 1315.6
    assert not paid["requiresAction"]
    document = SimpleNamespace(id="P-1", numero="2026/006", stato="EMESSA", importo_totale=1315.6)
    existing = bridge._proforma_presidio_for_fascicolo(case, items=items, parcelle=[document])
    assert existing["status"] == "presente" and existing["existingCount"] == 1
    assert existing["total"] == 1315.6 and case.pagamenti["parcella"]["proforma_id"] == "P-1"


@pytest.mark.parametrize("payments", [{}, {"parcella": {"status": "da_emettere"}}])
def test_parcella_facoltativa_non_chiude_la_discordanza_fascicoli_duplicati(payments):
    case = _economic_fascicolo(payments)
    case.stato = "DEFINITO"
    items = {"parcella": bridge._payment_item("parcella", case.pagamenti.get("parcella", {}), case.id)}
    result = bridge._proforma_presidio_for_fascicolo(case, items=items, duplicate_group={"count": 2})
    assert result["status"] == "doppione_da_riconciliare" and result["requiresAction"]


def test_parcella_assente_e_rinuncia_registrata_restano_distinte():
    case = _economic_fascicolo()
    case.stato = "DEFINITO"
    items = {"parcella": bridge._payment_item("parcella", {}, case.id)}
    assert bridge._proforma_presidio_for_fascicolo(case, items=items)["status"] == "facoltativa"
    case.pagamenti["parcella"] = {"status": "non_previsto", "updated_by": "Avvocato", "previsto": False}
    items["parcella"] = bridge._payment_item("parcella", case.pagamenti["parcella"], case.id)
    assert bridge._proforma_presidio_for_fascicolo(case, items=items)["status"] == "non_previsto"


def test_genera_proforma_persiste_la_base_economica_del_pannello_e_restituisce_apertura(monkeypatch):
    import web.services.react_fatturazione_bridge as fatturazione_bridge

    fascicolo = _economic_fascicolo()
    fascicoli = _EconomicFascicoliRepo(fascicolo)
    fatturazione = _EconomicFatturazioneRepo()
    captured = {}

    def _create(**kwargs):
        captured.update(kwargs)
        fatturazione.per_fascicolo = lambda _fid: [SimpleNamespace(id="P-1", netto_a_pagare=354.15)]
        return {
            "ok": True,
            "existing": False,
            "message": "Proforma 2026/001 creata.",
            "item": {"id": "P-1", "number": "2026/001"},
            "redirect_href": "/fatturazione?id_documento=P-1",
        }, 201

    monkeypatch.setattr(fatturazione_bridge, "create_react_fascicolo_proforma", _create)

    result, status = bridge.generate_react_fascicolo_proforma(
        get_fascicoli=lambda: fascicoli,
        get_fatturazione=lambda: fatturazione,
        get_clienti=lambda: object(),
        get_utenti=lambda: object(),
        get_preventivi=None,
        current_user=SimpleNamespace(id="U-1"),
        id_fasc=fascicolo.id,
        payload={
            "basis": {
                "sourceKind": "parcella",
                "status": "da_emettere",
                "importo": "296,70",
                "dataPagamento": "2026-07-13",
            }
        },
        config={},
        actor="Avv. Test",
    )

    assert status == 200
    assert result["ok"] is True
    assert result["proformaId"] == "P-1"
    assert result["redirectHref"] == "/fatturazione?id_documento=P-1"
    assert captured["amount"] == 296.7
    assert fascicolo.pagamenti["parcella"]["importo"] == 354.15
    assert fascicolo.pagamenti["parcella"]["proforma_id"] == "P-1"


def test_genera_proforma_blocca_un_importo_ui_diverso_da_quello_salvato():
    fascicolo = _economic_fascicolo({
        "parcella": {"status": "da_emettere", "importo": 296.7},
    })
    fascicoli = _EconomicFascicoliRepo(fascicolo)

    result, status = bridge.generate_react_fascicolo_proforma(
        get_fascicoli=lambda: fascicoli,
        get_fatturazione=lambda: _EconomicFatturazioneRepo(),
        get_clienti=lambda: object(),
        get_utenti=lambda: object(),
        get_preventivi=None,
        current_user=SimpleNamespace(id="U-1"),
        id_fasc=fascicolo.id,
        payload={"basis": {"sourceKind": "parcella", "status": "da_emettere", "importo": 300}},
        config={},
    )

    assert status == 409
    assert result["ok"] is False
    assert "cambiati" in result["message"]
def test_presidio_economico_puntuale_non_enumera_archivio_ne_crea_proforme(monkeypatch):
    case = _economic_fascicolo()
    seen = []
    repo = _EconomicFascicoliRepo(case)
    repo.tutti = lambda **kw: (_ for _ in ()).throw(AssertionError("Archivio completo non richiesto"))
    monkeypatch.setattr(bridge, "_ensure_contributo_unificato_for_fascicolo", lambda **kw: seen.append(kw["fascicolo"].id) or {"status": "existing"})
    monkeypatch.setattr(bridge, "_ensure_fascicolo_definito_from_economics", lambda **kw: {"updated": False})
    monkeypatch.setattr(bridge, "_fascicolo_is_defined", lambda item: True)
    monkeypatch.setattr(bridge, "_ensure_auto_proforma_for_fascicolo", lambda **kw: (_ for _ in ()).throw(AssertionError("Nessuna scelta di creare proforma")))
    result = bridge.run_react_fascicoli_economic_presidio(get_fascicoli=lambda: repo,
        get_fatturazione=lambda: _EconomicFatturazioneRepo(), fascicolo_ids=[case.id])
    assert result["ok"] and result["createdCount"] == 0 and seen == [case.id]
    rejected = bridge.run_react_fascicoli_economic_presidio(get_fascicoli=lambda: repo,
        get_fatturazione=lambda: _EconomicFatturazioneRepo(), fascicolo_ids=[case.id, "ALTRO-TENANT"])
    assert not rejected["ok"] and seen == [case.id]

def test_nuova_verifica_cu_non_sostituisce_pagamento_registrato(monkeypatch):
    raw = {"status": "pagato", "importo": 49, "data_pagamento": "2026-10-12",
           "origine": "Archivio delle letture", "updated_by": "IUSENTRA automatico"}
    pending = {"status": "da_registrare", "importo": None, "richiedeConferma": True,
               "verificheMancanti": ["Codice fiscale della fonte da verificare."], "importiLetti": ["49.00"]}
    merged = bridge._merge_auto_payment_source(raw, pending, kind="contributo_unificato", replace_automatic=True)
    assert merged["status"] == "pagato" and merged["importo"] == 49
    assert merged["data_pagamento"] == "2026-10-12" and merged["richiedeConferma"]
    assert merged["verificheMancanti"]
    case = _economic_fascicolo({"contributo_unificato": raw})
    monkeypatch.setattr(bridge, "_importi_dall_archivio", lambda *args: {"contributo_unificato": pending})
    projected = bridge._payments_with_automatic_sources(case, case.pagamenti, enabled=False)
    assert projected["contributo_unificato"]["status"] == "pagato"
    assert projected["contributo_unificato"]["importo"] == 49

def test_nuova_prova_sql_invalida_presidio_senza_rilettura_del_documento(monkeypatch):
    from pct.registro_letture import Fatto
    case = _economic_fascicolo()
    facts = []
    monkeypatch.setattr(bridge, "_fatti_archivio", lambda source, **filters: facts if filters.get("categoria") == "importo" else [])
    before = bridge._document_analysis_fingerprint(case)
    facts.append(Fatto(categoria="importo", campo="contributo_unificato", valore="49.00", id="F-CU",
                       sha256="a" * 64, verifica="verificata", prove=[{"codice": "stato", "esito": "ok", "dettaglio": "pagato"}]))
    after = bridge._document_analysis_fingerprint(case)
    assert after != before
    facts[0].letto_il = "2026-10-13T01:00:00Z"
    assert bridge._document_analysis_fingerprint(case) == after



def test_lista_economica_vede_nuove_prove_sql_senza_aprire_documenti(monkeypatch):
    from pct.registro_letture import Fatto
    case = _economic_fascicolo()
    facts = []
    monkeypatch.setattr(bridge, "_fatti_archivio", lambda source, **filters: facts if filters.get("categoria") == "importo" else [])
    case.pagamenti["_presidio_documentale"] = {"status": "aggiornato", "fingerprint": "DOC", "economicFactsFingerprint": bridge._economic_archive_fingerprint(case)}
    monkeypatch.setattr(bridge, "_economic_analysis_documents_for_fascicolo", lambda *args: (_ for _ in ()).throw(AssertionError("Nessuna apertura documentale nella lista")))
    before = bridge._document_analysis_marker_state(case)
    assert before["status"] == "aggiornato"
    facts.append(Fatto(categoria="importo", campo="contributo_unificato", valore="49.00", id="CU-NEW", sha256="a" * 64, verifica="verificata"))
    after = bridge._document_analysis_marker_state(case)
    assert after["status"] == "da_rianalizzare" and after["fingerprint"] != before["fingerprint"]
    case.pagamenti["_presidio_documentale"]["economicFactsFingerprint"] = bridge._economic_archive_fingerprint(case)
    assert bridge._document_analysis_marker_state(case)["status"] == "aggiornato"


def test_data_economica_storica_italiana_alimenta_input_iso():
    item = bridge._payment_item("contributo_unificato", {"status": "pagato", "importo": 49, "data_pagamento": "12/10/2026"}, "CASE")
    assert item["dataPagamento"] == "12/10/2026"
    assert item["dataPagamentoIso"] == "2026-10-12"


def test_fonte_cf_non_confrontabile_resta_visibile_senza_importo_associato(monkeypatch):
    from pct.registro_letture import Fatto
    import web.services.registro_letture_runtime as registry
    fact = Fatto(id="NEG", oggetto_id="DOC", tipo="documento", categoria="evento", campo="importi_identita_non_verificata", valore="non_attribuiti", verifica="plausibile", sha256="a" * 64, contesto="Codice fiscale non confrontabile.")
    monkeypatch.setattr(bridge, "_fatti_archivio", lambda source, **filters: [fact] if filters.get("categoria") == "evento" else [])
    original = SimpleNamespace(presente=True, impronta=fact.sha256, nome="sentenza-negativa.pdf")
    monkeypatch.setattr(registry, "registro_corrente", lambda: SimpleNamespace(oggetto=lambda *args: original))
    monkeypatch.setattr(registry, "tenant_corrente", lambda: "TENANT")
    case = _economic_fascicolo({"liquidazione_giudice": {"importo": 1100, "status": "pagato", "data_pagamento": "2026-10-12", "updated_by": "Avv. Test", "proforma_id": "P-1"}})
    projected = bridge._payments_with_automatic_sources(case, case.pagamenti, enabled=False)["liquidazione_giudice"]
    assert projected["importo"] == 1100 and projected["status"] == "pagato" and projected["proforma_id"] == "P-1"
    assert projected["richiedeConferma"] and any("non confrontabile" in warning for warning in projected["verificheMancanti"])
    assert projected["fontiVerifica"][0]["previewHref"].endswith("/documenti/DOC/visualizza")
    assert case.pagamenti["liquidazione_giudice"]["importo"] == 1100


_SCHEMA_REGISTRO_ESENTE = """Ruolo Generale N. 493/2024
TRIBUNALE ORDINARIO DI PALMI
Iscritto il : 17/02/2024
Ruolo Sezionale N. 00000493
Num. R.G. : 493/2024
Contributo Unificato: Esente
Attori/Ricorrenti/Appellanti : BIANCHI ANNA
Resistenti/Ingiunti/Appellati : MINISTERO
"""


def _fatto_registro_esente():
    from pct.archivio_letture.estrazione_importi import importo_contributo_unificato

    case = SimpleNamespace(nome_cliente="Bianchi Anna", numero_rg="493", anno_rg="2024", tribunale="Tribunale di Palmi")
    fact, = importo_contributo_unificato(_SCHEMA_REGISTRO_ESENTE, metadata={"fascicolo": case}, origine="nativo")
    fact.sha256, fact.oggetto_id, fact.id = "a" * 64, "REGISTRO", "PROVA-REGISTRO"
    return fact


def test_esenzione_attestata_registro_automatica_senza_incasso_ne_anticipazione():
    import json
    from pct.archivio_letture.presidio_economico import contributo_verificato

    fact = _fatto_registro_esente()
    declaration = next(p for p in fact.prove if p["codice"] == "dichiarazione_economica")
    assert "Il registro indica contributo unificato esente" in json.loads(declaration["dettaglio"])["motivo"]
    before = copy.deepcopy(fact)
    result = contributo_verificato([fact, copy.deepcopy(fact)])
    assert result["status"] == "non_previsto" and not result["previsto"]
    assert not result["pagato"] and result["importo"] is None
    assert not result["richiedeConferma"] and not result["data_pagamento"]
    assert result["documento_id"] == "REGISTRO"
    assert fact == before


@pytest.mark.parametrize("missing", ["cliente_economico", "rg_economico", "ufficio_economico", "cf_economico", "impronta", "ocr"])
def test_esenzione_registro_non_promossa_senza_prova_congiunta(missing):
    from pct.archivio_letture.presidio_economico import contributo_verificato

    fact = _fatto_registro_esente()
    if missing == "impronta":
        fact.sha256 = ""
    elif missing == "ocr":
        fact.origine, fact.verifica = "ocr", "plausibile"
    else:
        fact.prove = [p for p in fact.prove if p["codice"] != missing]
    result = contributo_verificato([fact])
    assert result["richiedeConferma"] and result["status"] != "non_previsto"


def test_autocertificazione_o_richiamo_non_diventano_attestazione_del_registro():
    import json
    from pct.archivio_letture.verifica_economica import prova_dichiarazione

    for text in ("Contributo Unificato: Esente. Tribunale di Palmi RG 493/2024 Bianchi Anna", "Autocertificazione reddituale: dichiara reddito non superiore a euro 35.240,04 relativamente all'anno 2023"):
        proof = json.loads(prova_dichiarazione(text)["dettaglio"])
        assert not proof["esenzione_attestata_registro"]
        assert not proof["requisiti_verificati"]


def test_esenzione_e_ricevuta_concordante_restano_discordanti_senza_sovrascritture():
    from pct.archivio_letture.presidio_economico import contributo_verificato

    exemption = _fatto_registro_esente()
    payment = copy.deepcopy(exemption)
    payment.campo, payment.valore, payment.id = "contributo_unificato", "49.00", "RT"
    payment.prove += [{"codice": "stato", "esito": "ok", "dettaglio": "pagato"}, {"codice": "data", "esito": "ok", "dettaglio": "17/02/2024"}]
    result = contributo_verificato([exemption, payment])
    assert result["richiedeConferma"] and result["importo"] is None
    assert result["status"] != "non_previsto" and not result["pagato"]
    assert any("discordanti" in issue for issue in result["verificheMancanti"])
    assert len(result["fontiVerifica"]) == 2


_AUTOCERTIFICAZIONE_SINTETICA = """AUTOCERTIFICAZIONE DELLA SITUAZIONE REDDITUALE
ESENZIONE DAL CONTRIBUTO UNIFICATO DI ISCRIZIONE A RUOLO
La sottoscritta Bianchi Anna DICHIARA che il proprio reddito non supera
l'importo di Euro 38.514,03 relativamente all'anno 2024. Firma Bianchi Anna.
"""


def _autocertificazione_contestuale(text=_AUTOCERTIFICAZIONE_SINTETICA, *, hash_corretto=True):
    from pct.archivio_letture.estrazione_importi import importo_contributo_unificato
    sha = "b" * 64
    case = SimpleNamespace(id="CASE", nome_cliente="Bianchi Anna", numero_rg="900", anno_rg="2026",
                           tribunale="Tribunale di Vicenza",
                           documenti=[SimpleNamespace(id="AUTOCERT", hash_sha256=sha)])
    fact, = importo_contributo_unificato(text, metadata={"fascicolo": case, "documento_id": "AUTOCERT",
        "document_hash_sha256": sha if hash_corretto else "c" * 64}, origine="ocr")
    fact.sha256, fact.oggetto_id, fact.fascicolo_id, fact.id = sha, "AUTOCERT", "CASE", "FACT"
    return fact


@pytest.mark.parametrize("formula", ["l'importo di Euro", "di Euro", "Euro"])
def test_autocertificazione_collegata_non_richiede_ricevuta_rg_ufficio_o_data_pagamento(formula):
    from pct.archivio_letture.presidio_economico import contributo_verificato
    fact = _autocertificazione_contestuale(_AUTOCERTIFICAZIONE_SINTETICA.replace("l'importo di Euro", formula))
    before = copy.deepcopy(fact)
    result = contributo_verificato([fact, copy.deepcopy(fact)])
    assert result["status"] == "non_previsto" and not result["richiedeConferma"]
    assert result["importo"] is None and not result["pagato"] and not result["data_pagamento"]
    assert result["documento_id"] == "AUTOCERT" and result["verificheMancanti"] == []
    assert all(fonte["identitaConcordante"] for fonte in result["fontiVerifica"])
    assert fact == before


@pytest.mark.parametrize("difetto", ["cliente", "impronta", "rg_discordante", "altro_fascicolo", "dichiarazione_contraria"])
def test_autocertificazione_non_attribuita_per_cartella_nome_file_o_riferimenti_discordanti(difetto):
    from pct.archivio_letture.presidio_economico import contributo_verificato
    text = _AUTOCERTIFICAZIONE_SINTETICA
    if difetto == "cliente":
        text = text.replace("Bianchi Anna", "Rossi Maria")
    if difetto == "rg_discordante":
        text += " R.G. 901/2026"
    if difetto == "dichiarazione_contraria":
        text = text.replace("non supera", "supera")
    fact = _autocertificazione_contestuale(text, hash_corretto=difetto != "impronta")
    if difetto == "altro_fascicolo":
        fact.fascicolo_id = "OTHER"
    result = contributo_verificato([fact])
    assert result["status"] != "non_previsto" and result["richiedeConferma"]
    assert result["importo"] is None and not result["pagato"]
    assert not any("Data del pagamento" in warning for warning in result["verificheMancanti"])


@pytest.mark.parametrize("backend", ["sqlite", "postgresql"])
def test_autocertificazione_sql_riapertura_ripetizione_e_isolamento_tenant(tmp_path, backend):
    import os
    import uuid
    from pct.registro_letture import Fatto, Oggetto, RegistroLetture
    from pct.archivio_letture.presidio_economico import contributo_verificato

    dsn = os.environ.get("IUSENTRA_ECONOMIC_TEST_POSTGRES_DSN", "") if backend == "postgresql" else ""
    if backend == "postgresql" and not dsn:
        pytest.skip("PostgreSQL isolato non configurato per questo guardrail")
    tenant = "autocert-test-" + uuid.uuid4().hex
    path = tmp_path / "registry.db"
    registry = RegistroLetture(path, postgres_dsn=dsn)
    source = Oggetto(tipo="documento", oggetto_id="AUTOCERT", sha256="b" * 64, nome="autocertificazione.pdf")
    registry.registra_inventario(tenant, "CASE", [source])
    fact = _autocertificazione_contestuale()
    manual = Fatto(categoria="data", campo="udienza", valore="2026-03-12", verifica="corretta")
    registry.registra_fatti(tenant, "CASE", source, "documenti", [fact, manual])
    before = registry.fatti(tenant, "CASE", verifiche=None)
    reopened = RegistroLetture(path, postgres_dsn=dsn)
    for _ in range(2):
        reopened.registra_fatti(tenant, "CASE", source, "documenti", [_autocertificazione_contestuale()])
    after = reopened.fatti(tenant, "CASE", verifiche=None)
    assert {(f.id, f.campo, f.verifica) for f in after} == {(f.id, f.campo, f.verifica) for f in before}
    result = contributo_verificato(after)
    assert result["status"] == "non_previsto" and not result["richiedeConferma"]
    assert result["importo"] is None and not result["pagato"] and not result["data_pagamento"]
    assert result["documento_id"] == "AUTOCERT"
    assert reopened.fatti(tenant + "-other", "CASE", verifiche=None) == []
    assert reopened.fatti(tenant, "OTHER", verifiche=None) == []
