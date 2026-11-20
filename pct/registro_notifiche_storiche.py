"""Registro formale delle notifiche: le notifiche PEC storiche provate dalle ricevute del gestore.

Le notifiche eseguite fuori dal registro (inviate da un altro programma, poi importate nel fascicolo) entrano
qui come casi provati, con la stessa catena probatoria che il registro esige per le notifiche nate nel
software (``pct/notification_proof_matrix.validate_notification_proof_bundle``): atto notificato, relata,
PEC inviata, ricevuta di accettazione e di avvenuta consegna per ogni destinatario, tutte con impronta
SHA-256, ricevute VERIFIED e CORRELATED. Il caso è legato all'atto elencato nella relata e presente nel
fascicolo con la stessa impronta del file consegnato (``pct/notifica_atto_l53.py``).

Le tabelle sono quelle del registro (``pct/sql/20260602_notification_proof_matrix.sql``) nel database dello
studio, dove le legge ``web/services/ragionamento_raccolta._consegne_verificate``. Un caso prima provato che
non lo è più (ricevuta tolta, documento cambiato) non resta «verificato»: torna da rivedere con il motivo.

Base normativa: art. 3-bis L. 53/1994; D.P.R. 68/2005, artt. 6 e 9; art. 196-octies disp. att. c.p.c. per
l'attestazione di conformità della copia notificata.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pct.notification_proof_matrix import REQUIRED_NOTIFICATION_EVIDENCE, validate_notification_proof_bundle
from pct.notifiche_pec_storiche_prova import EsitoSpedizione

_SQL = Path(__file__).with_name("sql")
_TABELLE_BASE = ("notification_events", "evidence_documents", "procedure_audit_log")
PREFISSO_CASO = "pec-storica"
SORGENTE = "ricevute_pec_gestore"

_SCHEMA_ESITI = """
CREATE TABLE IF NOT EXISTS notification_historic_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    ambito TEXT NOT NULL,
    riferimento TEXT NOT NULL,
    impronta TEXT NOT NULL DEFAULT '',
    esito TEXT NOT NULL,
    codice TEXT NOT NULL DEFAULT '',
    motivo TEXT NOT NULL DEFAULT '',
    dettagli_json TEXT NOT NULL DEFAULT '{}',
    versione TEXT NOT NULL DEFAULT '',
    verificato_il TEXT NOT NULL,
    UNIQUE (tenant_id, fascicolo_id, ambito, riferimento)
);
CREATE INDEX IF NOT EXISTS idx_nhc_fascicolo ON notification_historic_checks (tenant_id, fascicolo_id);
"""


def _json(valore: Any) -> str:
    return json.dumps(valore, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _statement_tabella(sql: str, tabella: str) -> list[str]:
    """CREATE TABLE e CREATE INDEX di una tabella dallo schema della pipeline procedurale."""
    trovate = re.findall(rf"CREATE TABLE IF NOT EXISTS {tabella} \(.*?\n\);", sql, re.DOTALL)
    trovate += re.findall(rf"CREATE INDEX IF NOT EXISTS \w+ ON {tabella} \([^)]*\);", sql)
    return trovate


def assicura_schema(conn: sqlite3.Connection) -> None:
    """Crea, se mancano, le tabelle del registro delle notifiche e degli esiti della verifica."""
    presenti = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if {"notification_cases", "notification_historic_checks"} <= presenti:
        return
    base = (_SQL / "20260520_xsd_procedure_lifecycle_knowledge.sql").read_text(encoding="utf-8")
    script = [s for tabella in _TABELLE_BASE for s in _statement_tabella(base, tabella)]
    script.append((_SQL / "20260602_notification_proof_matrix.sql").read_text(encoding="utf-8"))
    script.append(_SCHEMA_ESITI)
    conn.executescript("\n".join(script))


def _uid(fascicolo_id: str, esito: EsitoSpedizione, atto: dict) -> str:
    return f"{PREFISSO_CASO}:{fascicolo_id}:{esito.identificativo}:{atto['documento_id']}"


def _impronta_prova(esito: EsitoSpedizione, atto: dict) -> str:
    parti = [atto["documento_id"], atto["sha256"], esito.relata.get("sha256", ""), esito.invio.get("sha256", ""),
             esito.accettazione.get("sha256", ""), *sorted(c["sha256"] for c in esito.consegne)]
    return hashlib.sha256("|".join(parti).encode()).hexdigest()[:32]


def _audit(conn, tenant: str, entita: str, entita_id: Any, azione: str, dopo: dict) -> None:
    corpo = _json(dopo)
    conn.execute(
        """INSERT INTO procedure_audit_log (tenant_id, entity_type, entity_id, action, actor, source, after_json, event_hash)
           VALUES (?, ?, ?, ?, 'scheduler', ?, ?, ?)""",
        (tenant, entita, str(entita_id), azione, SORGENTE, corpo, hashlib.sha256(corpo.encode()).hexdigest()),
    )


def _elimina_caso(conn, caso_id: int) -> None:
    prove = [r[0] for r in conn.execute("SELECT evidence_document_id FROM notification_evidence_links WHERE notification_case_id=?", (caso_id,))]
    for tabella in ("notification_evidence_links", "notification_receipts", "notification_messages", "notification_relata",
                    "conformity_attestations", "notification_proof_bundles", "notification_recipients"):
        conn.execute(f"DELETE FROM {tabella} WHERE notification_case_id=?", (caso_id,))
    conn.executemany("DELETE FROM evidence_documents WHERE id=?", [(p,) for p in prove])
    conn.execute("DELETE FROM notification_cases WHERE id=?", (caso_id,))


def _prova_documento(conn, tenant, fascicolo_id, ruolo, documento_id, impronta, nome="") -> int:
    return int(conn.execute(
        """INSERT INTO evidence_documents (tenant_id, fascicolo_id, evidence_type, document_id, hash, filename_original, legal_relevance)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tenant, fascicolo_id, ruolo, documento_id, impronta, nome, "prova della notificazione (art. 3-bis L. 53/1994)"),
    ).lastrowid)


def _collega(conn, tenant, fascicolo_id, bundle_id, caso_id, prova_id, ruolo, impronta, destinatario_id=None) -> None:
    conn.execute(
        """INSERT INTO notification_evidence_links (tenant_id, fascicolo_id, bundle_id, notification_case_id, recipient_id,
               evidence_document_id, evidence_role, document_hash, validation_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED')""",
        (tenant, fascicolo_id, bundle_id, caso_id, destinatario_id, prova_id, ruolo, impronta),
    )


def _scrivi_caso(conn, tenant: str, fascicolo_id: str, esito: EsitoSpedizione, atto: dict, uid: str, bundle_id: str,
                 ricevute: dict[str, dict]) -> int:
    caso_id = int(conn.execute(
        """INSERT INTO notification_cases (tenant_id, fascicolo_id, notification_event_id, case_uid, case_type, status,
               act_document_id, proof_bundle_id, updated_at)
           VALUES (?, ?, NULL, ?, 'NOTIFICA_AVVOCATO_PEC', 'PROOF_COMPLETE', ?, ?, CURRENT_TIMESTAMP)""",
        (tenant, fascicolo_id, uid, atto["documento_id"], bundle_id),
    ).lastrowid)
    invio, rac, relata = esito.invio, esito.accettazione, esito.relata
    relata_id = relata.get("documento_id") or f"{invio['riferimento']}#{relata['file']}"
    conn.execute(
        """INSERT INTO notification_proof_bundles (tenant_id, fascicolo_id, notification_case_id, bundle_id, bundle_type,
               required_evidence_json, collected_evidence_json, missing_evidence_json, validation_status, updated_at)
           VALUES (?, ?, ?, ?, 'NOTIFICA_AVVOCATO_PEC', ?, '[]', ?, 'DRAFT', CURRENT_TIMESTAMP)""",
        (tenant, fascicolo_id, caso_id, bundle_id, _json(sorted(REQUIRED_NOTIFICATION_EVIDENCE)), _json(sorted(REQUIRED_NOTIFICATION_EVIDENCE))),
    )
    conn.execute(
        """INSERT INTO notification_messages (tenant_id, fascicolo_id, notification_case_id, direction, channel, message_id,
               sender, recipients_to, subject, raw_eml_document_id, body_hash, parsed_payload_json, parse_status,
               verification_status, updated_at)
           VALUES (?, ?, ?, 'OUTBOUND', 'PEC', ?, ?, ?, ?, ?, ?, ?, 'PARSED', 'VERIFIED', CURRENT_TIMESTAMP)""",
        (tenant, fascicolo_id, caso_id, invio["message_id"], ricevute["casella"], _json(invio["destinatari"]), invio["oggetto"],
         invio["riferimento"], invio["sha256"], _json({"fonte": invio["fonte"]})),
    )
    for ruolo, documento, impronta, nome in (
        ("ATTO_NOTIFICATO", atto["documento_id"], atto["sha256"], atto["file"]),
        ("RELATA", relata_id, relata["sha256"], relata["file"]),
        ("PEC_INVIATA", invio["riferimento"], invio["sha256"], ""),
    ):
        _collega(conn, tenant, fascicolo_id, bundle_id, caso_id, _prova_documento(conn, tenant, fascicolo_id, ruolo, documento, impronta, nome),
                 ruolo, impronta)
    for consegna in esito.consegne:
        destinatario_id = int(conn.execute(
            """INSERT INTO notification_recipients (tenant_id, notification_case_id, fascicolo_id, recipient_name, recipient_address,
                   recipient_address_source, recipient_type, status, updated_at)
               VALUES (?, ?, ?, ?, ?, 'relata di notifica', ?, 'DELIVERY_RECEIVED', CURRENT_TIMESTAMP)""",
            (tenant, caso_id, fascicolo_id, consegna.get("voce_relata", ""), consegna["destinatario"],
             f"RELATA_{str(consegna.get('ruolo') or 'altro').upper()}"),
        ).lastrowid)
        for tipo, ruolo, voce, completezza in (("ACCETTAZIONE", "RICEVUTA_ACCETTAZIONE", rac, "UNKNOWN"),
                                               ("AVVENUTA_CONSEGNA", "RICEVUTA_AVVENUTA_CONSEGNA", consegna, "COMPLETA")):
            conn.execute(
                """INSERT INTO notification_receipts (tenant_id, fascicolo_id, notification_case_id, recipient_id,
                       original_message_id, receipt_type, receipt_completeness, sender, recipient, event_time, provider,
                       raw_eml_document_id, daticert_xml_document_id, parsed_payload_json, hash, verification_status,
                       correlation_status, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED', 'CORRELATED', CURRENT_TIMESTAMP)""",
                (tenant, fascicolo_id, caso_id, destinatario_id, invio["message_id"], tipo, completezza, ricevute["casella"],
                 consegna["destinatario"], voce["data"], voce.get("gestore", ""), voce["riferimento"], f"{voce['riferimento']}#daticert.xml",
                 _json(ricevute.get(voce["riferimento"], {})), voce["sha256"]),
            )
            _collega(conn, tenant, fascicolo_id, bundle_id, caso_id,
                     _prova_documento(conn, tenant, fascicolo_id, ruolo, voce["riferimento"], voce["sha256"]),
                     ruolo, voce["sha256"], destinatario_id)
    conn.execute(
        """INSERT INTO notification_relata (tenant_id, fascicolo_id, notification_case_id, relata_type, document_id,
               signed_file_document_id, signer_tax_code, signature_status, contains_conformity_attestation,
               related_act_document_id, verified_at, validation_status, updated_at)
           VALUES (?, ?, ?, 'AVVOCATO_PEC', ?, ?, ?, 'FIRMA_INTEGRA', ?, ?, ?, 'VERIFIED', CURRENT_TIMESTAMP)""",
        (tenant, fascicolo_id, caso_id, relata_id, relata_id, relata["codice_fiscale"], int(bool(atto["copia_attestata"])),
         atto["documento_id"], _adesso()),
    )
    if atto["copia_attestata"]:
        # La relata attesta che il file notificato è copia conforme estratta dal fascicolo informatico.
        conn.execute(
            """INSERT INTO conformity_attestations (tenant_id, fascicolo_id, notification_case_id, document_attested_id,
                   attestation_document_id, attestation_mode, description, attested_filename, document_hash, signer,
                   signature_status, destination, validation_status, updated_at)
               VALUES (?, ?, ?, ?, ?, 'RELATA_NOTIFICA', ?, ?, ?, ?, 'FIRMA_INTEGRA', 'NOTIFICA', 'VERIFIED', CURRENT_TIMESTAMP)""",
            (tenant, fascicolo_id, caso_id, atto["documento_id"], relata_id, atto["titolo"], atto["file"], atto["sha256"],
             relata["codice_fiscale"]),
        )
    raccolte = sorted({r[0] for r in conn.execute(
        "SELECT evidence_role FROM notification_evidence_links WHERE bundle_id=? AND validation_status='VERIFIED'", (bundle_id,))})
    mancanti = sorted(REQUIRED_NOTIFICATION_EVIDENCE - set(raccolte))
    conn.execute(
        "UPDATE notification_proof_bundles SET collected_evidence_json=?, missing_evidence_json=?, validation_status=? WHERE bundle_id=?",
        (_json(raccolte), _json(mancanti), "PARTIAL" if mancanti else "VERIFIED", bundle_id),
    )
    return caso_id


def registra_spedizioni(conn: sqlite3.Connection, *, tenant: str, fascicolo_id: str, casella: str,
                        spedizioni: Iterable[EsitoSpedizione], ricevute: dict[str, dict] | None = None) -> dict[str, int]:
    """Crea o aggiorna i casi provati; un caso storico non più provato torna da rivedere. Una transazione."""
    assicura_schema(conn)
    conteggio = {"creati": 0, "invariati": 0, "da_rivedere": 0, "respinti": 0}
    dati_ricevute = {**(ricevute or {}), "casella": casella}
    attesi: set[str] = set()
    conn.execute("SAVEPOINT registro_notifiche_storiche")
    try:
        for esito in spedizioni:
            if not esito.provata:
                continue
            for atto in esito.atti:
                uid = _uid(fascicolo_id, esito, atto)
                bundle_id = f"{PREFISSO_CASO}-{_impronta_prova(esito, atto)}"
                attesi.add(uid)
                presente = conn.execute(
                    """SELECT c.id, b.bundle_id, b.validation_status FROM notification_cases c
                       LEFT JOIN notification_proof_bundles b ON b.notification_case_id=c.id WHERE c.case_uid=?""", (uid,)).fetchone()
                if presente and presente[1] == bundle_id and presente[2] == "VERIFIED":
                    conteggio["invariati"] += 1
                    continue
                if presente:
                    _elimina_caso(conn, int(presente[0]))
                conn.execute("SAVEPOINT caso_storico")
                caso_id = _scrivi_caso(conn, tenant, fascicolo_id, esito, atto, uid, bundle_id, dati_ricevute)
                fabbrica, conn.row_factory = conn.row_factory, sqlite3.Row
                try:
                    validate_notification_proof_bundle(conn, fascicolo_id=fascicolo_id, proof_bundle_id=bundle_id)
                    errore = ""
                except ValueError as exc:
                    errore = str(exc)
                finally:
                    conn.row_factory = fabbrica
                if errore:
                    conn.execute("ROLLBACK TO caso_storico")
                    conn.execute("RELEASE caso_storico")
                    esito.provata, esito.motivo = False, errore
                    attesi.discard(uid)
                    conteggio["respinti"] += 1
                    continue
                conn.execute("RELEASE caso_storico")
                _audit(conn, tenant, "notification_cases", caso_id, "notifica_storica_provata",
                       {"case_uid": uid, "bundle_id": bundle_id, "data_consegna": esito.data_consegna, "atto": atto["documento_id"]})
                conteggio["creati"] += 1
        for caso_id, uid in conn.execute(
                "SELECT id, case_uid FROM notification_cases WHERE tenant_id=? AND fascicolo_id=? AND case_uid LIKE ? AND status<>'NEEDS_REVIEW'",
                (tenant, fascicolo_id, f"{PREFISSO_CASO}:{fascicolo_id}:%")).fetchall():
            if uid in attesi:
                continue
            conn.execute("UPDATE notification_cases SET status='NEEDS_REVIEW', updated_at=CURRENT_TIMESTAMP WHERE id=?", (caso_id,))
            conn.execute("UPDATE notification_proof_bundles SET validation_status='NEEDS_REVIEW', updated_at=CURRENT_TIMESTAMP WHERE notification_case_id=?", (caso_id,))
            _audit(conn, tenant, "notification_cases", caso_id, "notifica_storica_non_piu_provata", {"case_uid": uid})
            conteggio["da_rivedere"] += 1
        conn.execute("RELEASE registro_notifiche_storiche")
    except Exception:
        conn.execute("ROLLBACK TO registro_notifiche_storiche")
        conn.execute("RELEASE registro_notifiche_storiche")
        raise
    return conteggio


def registra_esiti(conn: sqlite3.Connection, *, tenant: str, fascicolo_id: str, versione: str,
                   ricevute: Iterable[dict], spedizioni: Iterable[EsitoSpedizione]) -> None:
    """Gli esiti della verifica, con il motivo del dubbio: ricevute una per una e spedizioni."""
    assicura_schema(conn)
    adesso = _adesso()
    righe = [("ricevuta", r["riferimento"], r["impronta"], "verificata" if r["verificata"] else "non_verificata",
              r["codice"], r["motivo"], _json(r)) for r in ricevute]
    righe += [("spedizione", s.msgid, s.identificativo, "provata" if s.provata else "dubbio", "", s.motivo,
               _json(s.come_dizionario())) for s in spedizioni]
    conn.execute("DELETE FROM notification_historic_checks WHERE tenant_id=? AND fascicolo_id=?", (tenant, fascicolo_id))
    conn.executemany(
        """INSERT INTO notification_historic_checks (tenant_id, fascicolo_id, ambito, riferimento, impronta, esito, codice,
               motivo, dettagli_json, versione, verificato_il) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(tenant, fascicolo_id, *riga, versione, adesso) for riga in righe],
    )


def esiti_salvati(conn: sqlite3.Connection, *, tenant: str, fascicolo_id: str) -> dict[str, dict]:
    """Le ricevute già verificate per impronta: una ricevuta invariata non si riverifica."""
    try:
        righe = conn.execute(
            "SELECT impronta, dettagli_json, versione FROM notification_historic_checks WHERE tenant_id=? AND fascicolo_id=? AND ambito='ricevuta'",
            (tenant, fascicolo_id)).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {r[0]: {**json.loads(r[1] or "{}"), "_versione": r[2]} for r in righe}


__all__ = ["PREFISSO_CASO", "assicura_schema", "esiti_salvati", "registra_esiti", "registra_spedizioni"]
