"""Fonti puntuali delle attività del piano del giorno («Apri» → fonte, non fascicolo)."""

from datetime import date
from types import SimpleNamespace

from pct.daily_plan.collectors import Budget, CasePresidioCollector, CollectorContext
from pct.daily_plan.clock import Clock
from pct.daily_plan.models import DailyWorkItem, SignalEvidence
from pct.daily_plan.serializers import deterministic_summary, item_summary_payload
from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
from web.services import daily_plan_runtime, daily_plan_source_cards
from web.services.daily_plan_sources import resolve_item_sources

TODAY = date(2026, 9, 11)


def _item(**overrides):
    base = dict(
        id="dpi-1",
        tenant_id="default",
        target_date=TODAY.isoformat(),
        title="Deposito note scritte ex art. 127-ter c.p.c.",
        action_kind="document_review",
        dedupe_key="k1",
        priority="P0",
        fascicolo_id="FASC-1",
        fascicolo_label="2026/316",
        href="/fascicoli/FASC-1#udienze",
        evidence=[],
    )
    base.update(overrides)
    return DailyWorkItem(**base)


class _Store:
    def __init__(self, rows):
        self._rows = rows

    def get(self, key):
        return self._rows.get(key)


def _fascicolo():
    return SimpleNamespace(
        id="FASC-1",
        documenti=[
            SimpleNamespace(id="DOC-DECRETO", nome="Decreto 127-ter.pdf"),
            SimpleNamespace(id="DOC-CU", nome="Contributo unificato Moscato.PDF"),
        ],
    )


def test_presidio_documentale_espone_il_documento_sorgente():
    presidio = build_fascicolo_operational_presidio(
        fascicolo=SimpleNamespace(id="FASC-1"),
        document_presidio={
            "status": "presidiato",
            "actions": [
                {
                    "type": "note_127_ter",
                    "title": "Deposito note scritte ex art. 127-ter c.p.c.",
                    "description": "Il decreto fissa la sostituzione dell'udienza.",
                    "dateIso": "2026-09-20",
                    "peremptory": True,
                    "source": "Decreto 127-ter.pdf",
                    "documentId": "DOC DECRETO",
                }
            ],
        },
        notification_relata={},
        payment_summary={},
        deposits=[],
        today=TODAY,
    )
    azione = next(a for a in presidio["actions"] if a["sector"] == "documenti")
    assert azione["documentId"] == "DOC DECRETO"
    assert azione["sourceHref"] == "/fascicoli/FASC-1/documenti/DOC%20DECRETO/visualizza"
    # le azioni di sezione restano senza documento: nessuna fonte inventata
    assert all(a["sourceHref"] == "" for a in presidio["actions"] if a["sector"] != "documenti")


def test_collettore_non_spezza_l_evidenza_testuale_e_collega_la_fonte():
    def provider(ctx):
        yield {
            "fascicolo": {"id": "FASC-1", "numero": "2026/316"},
            "actions": [
                {
                    "id": "documenti-note_127_ter-0",
                    "sector": "documenti",
                    "title": "Deposito note scritte ex art. 127-ter c.p.c.",
                    "source": "Decreto 127-ter.pdf",
                    "evidence": "Decreto 127-ter.pdf",
                    "documentId": "DOC-DECRETO",
                    "sourceHref": "/fascicoli/FASC-1/documenti/DOC-DECRETO/visualizza",
                }
            ],
        }

    ctx = CollectorContext(
        tenant_id="default", clock=Clock(), budget=Budget(), presidio_provider=provider
    )
    sig = CasePresidioCollector().collect(ctx).signals[0]
    assert [e.label for e in sig.evidence] == ["Decreto 127-ter.pdf"]
    assert sig.evidence[0].href == "/fascicoli/FASC-1/documenti/DOC-DECRETO/visualizza"
    assert sig.metadata["document_id"] == "DOC-DECRETO"


def test_card_mostra_nome_fonte_e_sintesi_senza_codici_interni():
    item = _item(
        evidence=[SignalEvidence(source_type="case_presidio", source_id="FASC-1:x", label="Decreto 127-ter.pdf")]
    )
    riga = item_summary_payload(item)
    assert riga["fonte_tipo"] == "case_presidio"
    assert riga["fonte_label"] == "Decreto 127-ter.pdf"

    storico = _item(evidence=[SignalEvidence(source_type="case_presidio", source_id="FASC-1:x", label="D")])
    assert item_summary_payload(storico)["fonte_label"] == ""

    plan = SimpleNamespace(summary={"per_priorita": {"P0": 1}}, work_items=[storico], coverage_complete=True)
    testo = deterministic_summary(plan)
    assert "case_presidio" not in testo
    assert "Fonte: documenti del fascicolo." in testo


def test_apri_risolve_documento_da_snapshot_storico_senza_link(monkeypatch):
    monkeypatch.setattr(daily_plan_runtime, "_fascicoli_store", lambda paths: _Store({"FASC-1": _fascicolo()}))
    monkeypatch.setattr(
        daily_plan_runtime,
        "operational_presidio_actions",
        lambda fascicolo, today: [
            {
                "id": "documenti-note_127_ter-2",
                "sector": "documenti",
                "title": "Deposito note scritte ex art. 127-ter c.p.c.",
                "dateIso": "2026-09-20",
                "source": "Decreto 127-ter.pdf",
                "documentId": "DOC-DECRETO",
                "sourceHref": "/fascicoli/FASC-1/documenti/DOC-DECRETO/visualizza",
            }
        ],
    )
    # l'indice salvato (-0) non coincide più con quello corrente (-2): conta l'evento
    item = _item(
        due_at="2026-09-20",
        evidence=[SignalEvidence(source_type="case_presidio", source_id="FASC-1:documenti-note_127_ter-0", label="D")],
    )
    payload = resolve_item_sources(item, paths={}, tenant_label="default", today=TODAY)
    assert payload["fonti"][0]["tipo"] == "documento"
    assert payload["fonti"][0]["etichetta"] == "Decreto 127-ter.pdf"
    assert payload["fonti"][0]["href"] == "/fascicoli/FASC-1/documenti/DOC-DECRETO/visualizza"
    assert payload["fascicolo_href"] == "/fascicoli/FASC-1"


def test_apri_voce_economica_trova_solo_il_documento_con_nome_identico(monkeypatch):
    monkeypatch.setattr(daily_plan_runtime, "_fascicoli_store", lambda paths: _Store({"FASC-1": _fascicolo()}))
    actions = [
        {"id": "economico-contributo_unificato", "sector": "economico", "title": "Registrare contributo unificato (€ 21,50)", "source": "Contributo unificato Moscato.PDF"},
        {"id": "economico-parcella", "sector": "economico", "title": "Emettere o aggiornare parcella", "source": "Contributo unificato.PDF", "href": "/fascicoli/FASC-1#economia", "legalBasis": "Controllo economico fascicolo"},
    ]
    monkeypatch.setattr(daily_plan_runtime, "operational_presidio_actions", lambda fascicolo, today: actions)

    trovato = resolve_item_sources(
        _item(
            title="Registrare contributo unificato (€ 21,50)",
            evidence=[SignalEvidence(source_type="case_presidio", source_id="FASC-1:economico-contributo_unificato")],
        ),
        paths={}, tenant_label="default", today=TODAY,
    )
    assert trovato["fonti"][0]["href"] == "/fascicoli/FASC-1/documenti/DOC-CU/visualizza"

    sezione = resolve_item_sources(
        _item(
            title="Emettere o aggiornare parcella",
            evidence=[SignalEvidence(source_type="case_presidio", source_id="FASC-1:economico-parcella")],
        ),
        paths={}, tenant_label="default", today=TODAY,
    )
    fonte = sezione["fonti"][0]
    assert fonte["tipo"] == "fascicolo"
    assert fonte["href"] == ""
    assert fonte["apri_href"] == "/fascicoli/FASC-1#economia"
    assert "non da un singolo documento" in fonte["nota"]


def test_apri_pec_usa_allegato_indicizzato_nel_lettore(monkeypatch):
    monkeypatch.setattr(
        daily_plan_source_cards,
        "pec_profiles_for",
        lambda items, paths, tenant_label: {"MSG-1": {"_indexed_source_name": "Decreto.pdf.zip"}},
    )
    item = _item(
        action_kind="pec_review",
        evidence=[SignalEvidence(source_type="pec", source_id="MSG-1", timestamp="2026-09-10T10:00:00")],
    )
    fonte = resolve_item_sources(item, paths={}, tenant_label="default", today=TODAY)["fonti"][0]
    assert fonte["tipo"] == "pec"
    assert fonte["href"] == "/api/v1/ui/email/source/MSG-1?name=Decreto.pdf.zip"
    assert fonte["apri_href"] == "/email/?audit_id=MSG-1"
    assert fonte["rilevata_il"] == "2026-09-10T10:00:00"


def test_apri_senza_fonti_lo_dichiara():
    item = _item(href="", evidence=[SignalEvidence(source_type="health", source_id="x")])
    payload = resolve_item_sources(item, paths={}, tenant_label="default", today=TODAY)
    assert payload["fonti"] == []
    assert "non risulta ancora una fonte" in payload["messaggio"]


def test_sintesi_mostra_immediate_dello_studio_anche_senza_attivita_personali():
    piano = SimpleNamespace(
        summary={"per_priorita": {}, "da_assegnare_studio": 5, "immediate_da_assegnare_studio": 2},
        work_items=[], coverage_complete=True,
    )
    assert "Da assegnare nello studio: 5, di cui 2 immediate." in deterministic_summary(piano)
    piano.work_items = [_item(title="Parcella dallo storico", priority="P3")]
    assert "Parcella dallo storico" not in deterministic_summary(piano)


def test_decorrenza_pec_rimane_un_riscontro_e_il_termine_gia_registrato_ha_una_sola_voce():
    from dataclasses import replace
    from pct.daily_plan.models import OperationalSignal
    from pct.daily_plan.deduplication import merge_signals
    from pct.daily_plan.priority_engine import decide_priority
    from pct.daily_plan.service import _segnali_operativi

    pec = OperationalSignal(
        id="pec", tenant_id="default", source_type="pec", kind="pec_deadline",
        title="Conferma il termine ricevuto via PEC", dedupe_key="identita-persistita",
        event_at="2026-09-04T10:00:00+02:00", due_at="2026-09-04", peremptory=True,
        reason="Accertare decorrenza e associazione.",
    )
    groups = merge_signals(_segnali_operativi([pec]))
    group, = groups
    assert group.primary.due_at == "" and not group.primary.peremptory
    assert group.primary.metadata["dies_a_quo_date"] == "2026-09-04"
    assert group.primary.dedupe_key == pec.dedupe_key
    assert decide_priority(group, today=TODAY).priority == "P1"
    assert pec.due_at == "2026-09-04" and pec.peremptory

    confirmed = replace(pec, metadata={"scadenziario_id": "sc-1", "esito_deterministico": "ok"})
    scadenza = replace(pec, id="sc-1", source_type="scadenziario", kind="deadline_fulfill", due_at="2026-09-10")
    assert list(_segnali_operativi([confirmed, scadenza])) == [scadenza]
    weak = replace(confirmed, metadata={**confirmed.metadata, "fascicolo_match": "weak"})
    assert len(list(_segnali_operativi([weak, scadenza]))) == 2
