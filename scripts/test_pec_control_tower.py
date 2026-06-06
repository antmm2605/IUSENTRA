#!/usr/bin/env python
"""Genera PEC sintetiche, alimenta PEC Control Tower e interroga Lex.

Lo script non invia PEC e non usa dati di produzione: crea un runtime locale,
ingesta MIME RFC 822 realistici, conferma una scadenza e verifica le risposte
operative richieste per Lex AI.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from lex.operational_knowledge.service import OperationalKnowledgeService
from lex.operational_knowledge.settings import OperationalKnowledgeSettings
from lex.operational_knowledge.tools import OperationalKnowledgeTools
from pct.pec_control_tower import PecControlTowerRepository, build_synthetic_pec_eml


QUESTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Quali PEC ricevute oggi generano scadenze?", ("PEC ricevute oggi", "Scadenza")),
    ("Quali notifiche verso enti o controparti devo fare?", ("Notifiche", "Bozza")),
    ("Quali PEC inviate non hanno ancora ricevuta di consegna?", ("senza consegna", "accettazione")),
    ("Quali termini sono stati calcolati ma non confermati?", ("Termini calcolati", "da confermare")),
    ("Quali atti sono arrivati da cancelleria?", ("cancelleria", "Provvedimento")),
    ("Quali comunicazioni PA richiedono risposta?", ("Comunicazioni PA", "riscontro")),
    ("Quali notifiche sono fallite?", ("fallite", "mancata consegna")),
    ("Qual è la prova completa di questa notifica?", ("Prova: completa", "accettazione")),
    ("Chi ha confermato la scadenza e con quale regola?", ("Conferma", "Avvocato Rossi")),
    ("Quale fascicolo rischia una decadenza?", ("rischio operativo", "FASC-2026-001")),
)


class _User:
    id = "avv-rossi"
    username = "Avvocato Rossi"
    tenant_slug = "tenant-test"

    @property
    def permessi_effettivi(self):
        return ["ai.usa", "messaggi.leggi", "fascicoli.leggi", "scadenziario.leggi"]

    def ha_permesso(self, permission: str) -> bool:
        return permission in set(self.permessi_effettivi)


def _fascicoli_rows() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id="FASC-2026-001",
            numero="RG 1234/2026",
            titolo="Rossi c. Comune di Milano",
            oggetto="Impugnazione provvedimento amministrativo e comunicazioni di cancelleria",
            procedimento="RG 1234/2026",
            tribunale="Tribunale di Milano",
            nome_cliente="Mario Rossi",
            controparte="Comune di Milano",
            documenti=[
                {"id": "doc-ricorso", "nome": "ricorso introduttivo.pdf", "data_documento": "2026-05-20"},
                {"id": "doc-procura", "nome": "procura alle liti.pdf", "data_documento": "2026-05-20"},
            ],
        )
    ]


def _daticert(tipo: str, msgid: str, destinatario: str) -> str:
    now = datetime.now(timezone.utc)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<postacert>
  <dati>
    <tipo>{tipo}</tipo>
    <msgid>{msgid}</msgid>
    <mittente>studio@example.pec.it</mittente>
    <destinatario>{destinatario}</destinatario>
    <giorno>{now.strftime('%d/%m/%Y')}</giorno>
    <ora>{now.strftime('%H:%M:%S')}</ora>
    <oggetto>Notifica atto RG 1234/2026</oggetto>
  </dati>
</postacert>
"""


def _messages() -> list[tuple[str, bytes]]:
    now = datetime.now(timezone.utc)
    return [
        (
            "cancelleria",
            build_synthetic_pec_eml(
                subject="Comunicazione di cancelleria RG 1234/2026 - deposito provvedimento",
                body=(
                    "Si comunica il deposito del provvedimento nel fascicolo RG 1234/2026. "
                    "Valutare termini e documenti collegati."
                ),
                sender="cancelleria@giustiziacert.it",
                dt=now,
                attachments={"provvedimento.pdf.txt": "Ordinanza del Tribunale di Milano nel procedimento RG 1234/2026."},
            ),
        ),
        (
            "pa",
            build_synthetic_pec_eml(
                subject="Comune di Milano - richiesta documenti protocollo PA entro 10 giorni",
                body=(
                    "Il Comune di Milano richiede integrazione documentale entro 10 giorni "
                    "per il procedimento collegato a Mario Rossi RG 1234/2026."
                ),
                sender="protocollo@comune.milano.pec.it",
                dt=now,
                attachments={"richiesta-pa.pdf.txt": "Richiesta di integrazione documentale con termine espresso."},
            ),
        ),
        (
            "notifica_da_fare",
            build_synthetic_pec_eml(
                subject="Ricorso da notificare a controparte RG 1234/2026",
                body="Preparare notifica verso controparte@example.pec.it con relata e atto allegato.",
                sender="studio@example.pec.it",
                to="studio@example.pec.it",
                dt=now,
                attachments={"ricorso.pdf.txt": "Ricorso da notificare.", "relata-bozza.txt": "Bozza relata."},
            ),
        ),
        (
            "accettazione_senza_consegna",
            build_synthetic_pec_eml(
                subject="Ricevuta di accettazione PEC - notifica RG 1234/2026",
                body="Ricevuta di accettazione del messaggio PEC.",
                sender="postmaster@pec.it",
                dt=now,
                headers={"X-Ricevuta": "accettazione", "X-Riferimento-Message-ID": "<notifica-nodelivery@iusentra.test>"},
                attachments={"daticert.xml": _daticert("accettazione", "notifica-nodelivery@iusentra.test", "controparte@example.pec.it")},
            ),
        ),
        (
            "accettazione_completa",
            build_synthetic_pec_eml(
                subject="Ricevuta di accettazione PEC - notifica completa",
                body="Ricevuta di accettazione del messaggio PEC completo.",
                sender="postmaster@pec.it",
                dt=now,
                headers={"X-Ricevuta": "accettazione", "X-Riferimento-Message-ID": "<notifica-completa@iusentra.test>"},
                attachments={"daticert.xml": _daticert("accettazione", "notifica-completa@iusentra.test", "ente@example.pec.it")},
            ),
        ),
        (
            "consegna_completa",
            build_synthetic_pec_eml(
                subject="Ricevuta di avvenuta consegna PEC - notifica completa",
                body="Ricevuta di avvenuta consegna completa del messaggio PEC.",
                sender="postmaster@pec.it",
                dt=now,
                headers={"X-Ricevuta": "avvenuta-consegna", "X-TipoRicevuta": "completa", "X-Riferimento-Message-ID": "<notifica-completa@iusentra.test>"},
                attachments={"daticert.xml": _daticert("avvenuta-consegna", "notifica-completa@iusentra.test", "ente@example.pec.it")},
            ),
        ),
        (
            "mancata_consegna",
            build_synthetic_pec_eml(
                subject="Avviso di mancata consegna PEC - notifica fallita",
                body="Mancata consegna della notifica verso destinatario errato.",
                sender="postmaster@pec.it",
                dt=now,
                headers={"X-Ricevuta": "mancata-consegna", "X-Riferimento-Message-ID": "<notifica-fallita@iusentra.test>"},
                attachments={"daticert.xml": _daticert("mancata-consegna", "notifica-fallita@iusentra.test", "errata@example.pec.it")},
            ),
        ),
    ]


def _service(repo: PecControlTowerRepository) -> OperationalKnowledgeService:
    tools = OperationalKnowledgeTools(repositories={"pec_control_tower": repo})
    return OperationalKnowledgeService(
        settings=OperationalKnowledgeSettings(enabled=True, audit_enabled=False, strict_mode_enabled=True),
        tools=tools,
    )


def run(runtime_root: Path) -> dict:
    runtime_root.mkdir(parents=True, exist_ok=True)
    repo = PecControlTowerRepository(
        runtime_root / "pec_control_tower.sqlite",
        tenant_id="tenant-test",
        fascicoli_rows=_fascicoli_rows(),
    )
    ingested = []
    for label, raw in _messages():
        result = repo.ingest_eml(raw, account_email="studio@example.pec.it", folder="INBOX", actor="script-test")
        ingested.append({"label": label, "id": result["data"]["id"], "category": result["data"]["legal_category"]})
    deadlines = repo.list_deadlines(limit=50)
    if deadlines:
        repo.confirm_deadline(
            deadlines[0]["id"],
            actor="Avvocato Rossi",
            confirmation_rule="Conferma manuale test: termine operativo verificato su comunicazione e fascicolo.",
        )
    service = _service(repo)
    user = _User()
    answers: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for question, expected_tokens in QUESTIONS:
        answer = service.answer(question=question, user=user, tenant_id="tenant-test")
        text = answer.answer if answer is not None else ""
        answers.append({"question": question, "answer": text})
        missing = [token for token in expected_tokens if token.lower() not in text.lower()]
        if missing:
            failures.append({"question": question, "missing": ", ".join(missing), "answer": text})
    audit = repo.verify_audit_chain()
    if not audit.get("ok"):
        failures.append({"question": "audit", "missing": "catena audit valida", "answer": json.dumps(audit, ensure_ascii=False)})
    return {
        "ok": not failures,
        "runtime_root": str(runtime_root),
        "ingested": ingested,
        "deadline_count": len(repo.list_deadlines(limit=100)),
        "notification_count": len(repo.list_notifications(limit=100)),
        "audit": audit,
        "answers": answers,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", default="", help="Cartella runtime temporanea per database e report.")
    args = parser.parse_args(argv)
    runtime_root = Path(args.runtime_root) if args.runtime_root else Path.cwd() / ".tmp" / "pec-control-tower-script"
    result = run(runtime_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
