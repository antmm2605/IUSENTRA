from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest
from lex.providers.deterministic_provider import DeterministicProvider


def _request(query: str) -> LexRequest:
    return LexRequest(
        tenant_id="tenant-coverage",
        user_id="utente-test",
        session_id="sessione-test",
        query=query,
    )


def _evidence(title: str = "Evidenza principale", content: str = "Contenuto verificato"):
    return {
        "items": [
            EvidenceItem(
                source_type="fascicolo",
                source_id="fonte-1",
                title=title,
                content=content,
                score=0.91,
            )
        ]
    }


def test_provider_fascicolo_usa_inventario_completo_delle_sezioni():
    provider = DeterministicProvider()
    rows = [
        {"titolo": f"Documento {index}", "data_documento": f"2026-04-{index:02d}", "stato": "depositato"}
        for index in range(1, 13)
    ]
    context = {
        "structured_context": {
            "fascicolo": {
                "numero": "1025/2024",
                "titolo": "Montagnese / Stillitano",
                "oggetto": "Azione risarcitoria",
                "cliente": "Montagnese Elisabetta",
                "controparte": "Stillitano Antonella",
                "tribunale": "Tribunale di Palmi",
                "stato": "attivo",
                "data_prossima_udienza": "2026-05-04T09:00:00",
            },
            "documenti": rows[:2],
            "fascicolo_sezioni": {
                "counts": {
                    "attivita": 6,
                    "documenti": 12,
                    "udienze_scadenze": 4,
                    "comunicazioni": 3,
                    "istanze": 2,
                },
                "attivita_processuali": [
                    {"titolo": "Iscrizione a ruolo", "data": "2024-09-05", "stato": "ok"}
                ],
                "documenti_fascicolo": rows,
                "udienze_scadenze": [
                    {"titolo": "Udienza istruttoria", "data_ora": "2026-05-04T09:00:00", "esito": "fissata"}
                ],
                "comunicazioni_cancelleria": [
                    {"titolo": "Comunicazione cancelleria", "timestamp": "2026-04-10T12:30:00"}
                ],
                "istanze": [
                    {"titolo": "Istanza trattazione scritta", "data": "2026-03-02"}
                ],
            },
            "fascicolo_intelligence": {
                "presidio": {"summary": "Documenti e scadenze presidiati"},
                "giurisprudenza": [{"id": "cass-1"}],
                "next_actions": ["verificare ultimo provvedimento e note d'udienza"],
            },
            "conformita_fascicolo": {
                "readiness_label": "Da completare",
                "general": {"label": "Attenzione", "blocking_count": 1, "warning_count": 2},
            },
            "agenda": [
                {"titolo": "Riunione cliente", "data_ora": "2026-04-28T15:00:00"}
            ],
            "scadenziario": [
                {"titolo": "Deposito note", "data": "2026-04-30"}
            ],
        }
    }

    draft = provider.generate(
        _request("quali documenti e udienze ha il fascicolo"),
        context,
        _evidence(),
        "fascicolo",
    )

    assert "fascicolo 1025/2024" in draft.text
    assert "Documenti fascicolo: 12 voci" in draft.text
    assert "+ 7 altre voci censite" in draft.text
    assert "Comunicazioni di cancelleria: 3 voci" in draft.text
    assert "Istanze: 2 voci" in draft.text
    assert "04/05/2026 alle 09:00" in draft.text
    assert draft.metadata["provider"] == "deterministic"
    assert draft.metadata["evidence_count"] == 1


def test_provider_fascicolo_senza_pratica_chiede_riferimento_corretto():
    draft = DeterministicProvider().generate(
        _request("riepilogo fascicolo"),
        {},
        _evidence(),
        "fascicolo",
    )

    assert "ho bisogno del riferimento corretto della pratica" in draft.text


def test_provider_economico_con_summary_presidia_preventivi_conferimenti_e_parcelle():
    context = {
        "structured_context": {
            "economico": {
                "scope": "fascicolo",
                "fascicolo": {"numero": "1025/2024", "titolo": "Montagnese / Stillitano"},
                "summary": {
                    "preventivi_count": 1,
                    "conferimenti_count": 1,
                    "parcelle_count": 1,
                    "totale_preventivato": 1200,
                    "totale_conferito": 1000,
                    "totale_fatturato": 800,
                    "totale_incassato": 500,
                    "saldo_aperto": 300,
                    "parcelle_scadute": 1,
                },
                "preventivi": [{"oggetto": "Preventivo giudizio civile", "stato": "approvato", "totale": 1200}],
                "conferimenti": [{"oggetto": "Incarico civile", "stato": "firmato", "compenso_pattuito": 1000}],
                "parcelle": [{"numero": "P-1", "stato": "emessa", "totale": 800}],
                "best_practice": {"label": "Percorso economico completo"},
            }
        }
    }

    draft = DeterministicProvider().generate(
        _request("controlla preventivo parcella e saldo"),
        context,
        _evidence("Preventivo", "Saldo aperto"),
        "economico",
    )

    assert "Presidio economico del fascicolo 1025/2024" in draft.text
    assert "saldo aperto EUR 300,00" in draft.text
    assert "sollecitare gli incassi scaduti" in draft.text


def test_provider_economico_senza_summary_risponde_sui_flussi_specifici():
    provider = DeterministicProvider()

    preventivo = provider.generate(_request("devo fare un preventivo"), {}, _evidence(), "economico")
    tariffario = provider.generate(_request("calcolo tariffario e compenso"), {}, _evidence(), "economico")
    fattura = provider.generate(_request("stato parcella e incasso"), {}, _evidence(), "economico")
    generico = provider.generate(_request("presidio economico"), {}, _evidence(), "economico")

    assert "preventivo guidato" in preventivo.text
    assert "partire dal tariffario" in tariffario.text
    assert "fatturazione o incasso" in fattura.text
    assert "preventivo, tariffario, parcella o pagamento" in generico.text


def test_provider_operational_copre_cabina_fascicolo_e_studio():
    provider = DeterministicProvider()
    fascicolo_context = {
        "structured_context": {
            "fascicolo": {"numero": "466/2023"},
            "fascicolo_intelligence": {
                "presidio": {"summary": "Udienza da preparare"},
                "scadenze": [{"titolo": "Deposito note", "data": "2026-06-01"}],
                "appuntamenti": [{"titolo": "Udienza", "data_ora": "2026-06-10T09:30:00"}],
                "next_actions": ["preparare note e fascicolo telematico"],
            },
        }
    }
    studio_context = {
        "structured_context": {
            "studio_operativo": {
                "summary": {
                    "scadenze_urgenti": 2,
                    "appuntamenti_orizzonte": 3,
                    "fascicoli_attenzionati": 4,
                },
                "domains": {
                    "clienti": {"total": 10},
                    "soggetti": {"total": 11},
                    "fascicoli": {"total": 12},
                    "preventivi": {"total": 13},
                    "parcelle": {"total": 14},
                },
                "actions": [{"title": "Verifica SIGP", "description": "controllare documenti GDP"}],
            }
        }
    }

    fascicolo = provider.generate(_request("cabina fascicolo"), fascicolo_context, _evidence(), "cabina")
    studio = provider.generate(_request("cabina studio"), studio_context, _evidence(), "next_action")

    assert "Cabina operativa del fascicolo 466/2023" in fascicolo.text
    assert "preparare note e fascicolo telematico" in fascicolo.text
    assert "Cabina operativa dello studio aggiornata" in studio.text
    assert "Verifica SIGP" in studio.text


def test_provider_compliance_legge_controlli_blocchi_warning_e_gate_deposito():
    context = {
        "structured_context": {
            "conformita_fascicolo": {
                "readiness_label": "Responsabile pronto con avvisi",
                "general": {"label": "Da verificare", "score": 72, "blocking_count": 1, "warning_count": 2},
                "sections": {
                    "processuale": {"label": "Processuale", "state": "ok"},
                    "documentale": {"label": "Documentale", "state": "warning"},
                    "tecnico_pst": {"label": "PST", "state": "blocco"},
                    "redazionale": {"label": "Redazionale", "state": "ok"},
                },
                "blocking_issues": [{"title": "Manca procura"}],
                "warning_issues": [{"title": "Controllare contributo"}],
                "missing_documents": [{"label": "Procura alle liti"}],
                "action_gates": {
                    "prepare_deposit": {
                        "applicable": True,
                        "allowed": False,
                        "reason": "Procura mancante",
                    }
                },
                "next_steps": ["caricare la procura firmata"],
            }
        }
    }

    draft = DeterministicProvider().generate(
        _request("controllo conformita deposito"),
        context,
        _evidence(),
        "compliance",
    )

    assert "Responsabile di conformita': Responsabile pronto con avvisi" in draft.text
    assert "punteggio 72/100" in draft.text
    assert "Blocchi principali: Manca procura" in draft.text
    assert "Pre-deposito: non pronto. Procura mancante" in draft.text
    assert "caricare la procura firmata" in draft.text

