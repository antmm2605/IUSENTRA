from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import EvidenceItem, LexRequest
from lex.guards.orchestrator import GuardOrchestrator


def test_guard_orchestrator_blocks_missing_tenant():
    guards = GuardOrchestrator()
    request = LexRequest(tenant_id="", user_id="user-1", session_id="session-1", query="test")
    context = {"permessi": {"can_use_lex": True}}

    verdict = guards.run_pre(request, context, "chat")

    assert verdict.allowed is False
    assert "Missing tenant_id" in verdict.reasons


def test_guard_orchestrator_warns_on_empty_evidence():
    guards = GuardOrchestrator()
    request = LexRequest(tenant_id="tenant-1", user_id="user-1", session_id="session-1", query="test")
    context = {"permessi": {"can_use_lex": True}}
    draft = SimpleNamespace(text="risposta di test")

    verdict = guards.run_post(request, context, "chat", {"items": []}, draft)

    assert verdict.allowed is True
    assert verdict.warnings


def test_guard_orchestrator_blocks_case_law_pdf_without_verified_reference():
    guards = GuardOrchestrator()
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="Scarica il PDF della sentenza Cassazione n. 1234/2024",
    )
    context = {"permessi": {"can_use_lex": True}}
    draft = SimpleNamespace(text="Ecco il PDF della sentenza richiesta.")
    evidence = {
        "items": [
            EvidenceItem(
                source_type="giurisprudenza",
                source_id="cass-1",
                title="Richiamo giurisprudenziale non verificato",
                content="Estratto generico non verificato.",
                score=0.62,
            )
        ],
        "citations": [],
    }

    verdict = guards.run_post(request, context, "giurisprudenza", evidence, draft)

    assert verdict.allowed is False
    assert verdict.risk_level == "high"
    assert any("PDF" in warning or "Riferimento giurisprudenziale" in warning for warning in verdict.warnings)


# Citazioni nella forma breve senza «n.» e Sezioni Unite: lex.json, guardia anti-invenzione.
def _evidenza_cassazione_verificata() -> dict:
    return {
        "items": [
            EvidenceItem(
                source_type="giurisprudenza",
                source_id="cass-1111-2019",
                title="Cass. n. 1111/2019",
                content="Cassazione civile, sentenza n. 1111/2019: principio sul punto.",
                score=0.9,
                trust_class="A",
                official_url="https://www.italgiure.giustizia.it/",
            )
        ],
        "citations": [],
    }


def _verdetti(testo: str):
    from lex.guards.hallucination_guard import HallucinationGuard
    from lex.guards.legal_reference_guard import LegalReferenceGuard

    request = LexRequest(tenant_id="tenant-1", user_id="user-1", session_id="session-1", query="giurisprudenza sul punto")
    kwargs = {"request": request, "workflow": "giurisprudenza", "evidence": _evidenza_cassazione_verificata(),
              "draft": SimpleNamespace(text=testo)}
    return HallucinationGuard().check(**kwargs), LegalReferenceGuard().check(**kwargs)


def test_pronuncia_inventata_senza_n_bloccata_nel_workflow_rigoroso():
    for testo in ("v. Cass. 22222/2023", "come affermato da Corte cost. 77/2018", "Cons. Stato 1234/2020",
                  "Cass. SS.UU. n. 9999/2021", "Cass., Sez. Un., 9999/2021", "Cass. S.U. 9999/2021"):
        allucinazione, riferimenti = _verdetti(f"Si veda Cass. n. 1111/2019 e {testo}.")
        assert allucinazione.allowed is False, testo
        assert riferimenti.allowed is False, testo
        assert any("non presenti" in w for w in [*allucinazione.warnings, *riferimenti.warnings]), testo


def test_pronuncia_presente_nelle_evidenze_passa_anche_senza_n():
    allucinazione, riferimenti = _verdetti("Il principio e' in Cass. 1111/2019, richiamata come Cass. sez. lav. 1111/2019.")
    assert allucinazione.allowed is True, allucinazione
    assert riferimenti.allowed is True, riferimenti


def test_estremi_di_norme_non_sono_pronunce():
    from lex.guards.hallucination_guard import extract_legal_references

    for testo in ("L. 107/2015", "D.Lgs. 165/2001", "La Cassazione, applicando la legge 107/2015, ha deciso",
                  "secondo la Cassazione il CCNL 2016/2018 prevede", "Cass. civ., 12/03/2021"):
        assert not [r for r in extract_legal_references(testo) if r.kind == "case_law"], testo


def test_forme_brevi_estratte_con_organo_numero_anno():
    from lex.guards.hallucination_guard import extract_legal_references

    attese = {
        "Cass. 22222/2023": "cassazione:22222:2023",
        "Corte cost. 77/2018": "corte costituzionale:77:2018",
        "Cons. Stato, sez. IV, 1234/2020": "consiglio di stato:1234:2020",
        "Cass. SS.UU. n. 9999/2021": "cassazione:9999:2021",
        "Cass. pen. SS.UU. 12345/2022": "cassazione:12345:2022",
    }
    for testo, chiave in attese.items():
        assert chiave in [r.key for r in extract_legal_references(testo)], testo
