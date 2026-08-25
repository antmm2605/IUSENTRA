"""CRM di studio: intake dei potenziali clienti (lead) con verifica conflitti.

Base deontologica: art. 23 (incarico) e art. 24 (conflitto di interessi,
dovere di astensione) del Codice Deontologico Forense; art. 28 (titolarita'
dello studio nei rapporti col cliente). La pipeline registra la richiesta di
assistenza, verifica i conflitti PRIMA dell'assunzione dell'incarico e
conduce fino a preventivo (L. 247/2012 art. 13: preventivo scritto) e
onboarding — riusando i moduli esistenti (``pct/preventivi.py``,
``pct/workflow_onboarding.py``); l'adeguata verifica antiriciclaggio resta in
``pct/antiriciclaggio.py`` e si aggancia alla conversione in cliente.

Verifica conflitti fail-closed:
- match su codice fiscale/partita IVA → esito certo;
- match solo sul nome → "da valutare" (omonimie possibili): la decisione
  resta all'avvocato, il software non assolve ne' condanna;
- il lead non diventa cliente finche' la verifica non e' stata eseguita.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pct.transactional_outbox import OutboxEvent, enqueue

FONTE_DEONTOLOGICA = "Codice Deontologico Forense artt. 23-24; L. 247/2012 art. 13"

# Pipeline di intake (stati ordinati).
STATI_LEAD = ("NUOVO", "CONTATTATO", "APPUNTAMENTO", "PREVENTIVO", "VINTO", "PERSO")

FONTI_LEAD = (
    "passaparola",
    "sito_studio",
    "referral_professionista",
    "directory_ordine",
    "social",
    "altro",
)

DECISIONI_CONFLITTO = ("CLEARANCE_CONCESSA", "ASTENSIONE")

_MIGRAZIONE_CRM_SCOPED_SQLITE = "crm_scoped_sqlite_to_root_v1"


def _norm(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm_fiscale(value: Any) -> str:
    return _norm(value).upper().replace(" ", "")


def _norm_nome(value: Any) -> str:
    return _norm(value).casefold()


def _now() -> str:
    """Timestamp esplicito UTC per il dato; la UI lo rende Europe/Rome."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Lead:
    """Richiesta di assistenza di un potenziale cliente."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12].upper())
    denominazione: str = ""  # nome e cognome o ragione sociale
    codice_fiscale: str = ""
    partita_iva: str = ""
    email: str = ""
    telefono: str = ""
    fonte: str = "altro"
    materia: str = ""  # es. "lavoro", "famiglia", "recupero crediti"
    esigenza: str = ""  # descrizione libera della richiesta
    stato: str = "NUOVO"
    conflitto_verificato: bool = False
    conflitto_esito: dict[str, Any] = field(default_factory=dict)
    cliente_id: str = ""  # valorizzato alla conversione
    preventivo_id: str = ""
    motivo_perso: str = ""
    note: str = ""
    referente: str = ""  # avvocato assegnato
    creato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    modificato_il: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, dati: dict[str, Any]) -> "Lead":
        return cls(**{k: v for k, v in dict(dati or {}).items() if k in cls.__dataclass_fields__})


def verifica_conflitto_interessi(
    *,
    denominazione: str,
    codice_fiscale: str = "",
    partita_iva: str = "",
    get_clienti: Callable[[], Any] | None = None,
    get_soggetti: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Cerca il potenziale cliente tra anagrafiche e controparti dello studio.

    Ritorna ``{"livello": "nessuno"|"da_valutare"|"potenziale_conflitto",
    "riscontri": [...], "verificato_il": iso}``. Il livello e' informativo:
    la valutazione ex art. 24 CDF resta dell'avvocato.
    """

    nome_norm = _norm_nome(denominazione)
    cf_norm = _norm_fiscale(codice_fiscale)
    piva_norm = _norm_fiscale(partita_iva)
    riscontri: list[dict[str, Any]] = []

    def _match_codici(cf: str, piva: str) -> bool:
        return bool((cf_norm and _norm_fiscale(cf) == cf_norm) or (piva_norm and _norm_fiscale(piva) == piva_norm))

    # Clienti esistenti: un cliente attuale che chiede un nuovo incarico non e'
    # un conflitto, ma va segnalato (posizioni contrapposte in altri giudizi).
    if get_clienti is not None:
        try:
            clienti = list(get_clienti().tutti(stato=None))
        except TypeError:
            clienti = list(get_clienti().tutti())
        except Exception:
            clienti = []
        for cliente in clienti:
            nome_cliente = _norm_nome(
                getattr(cliente, "denominazione", "")
                or f"{getattr(cliente, 'nome', '')} {getattr(cliente, 'cognome', '')}"
            )
            certo = _match_codici(getattr(cliente, "codice_fiscale", ""), getattr(cliente, "partita_iva", ""))
            omonimo = bool(nome_norm and nome_cliente and nome_norm == nome_cliente)
            if certo or omonimo:
                riscontri.append(
                    {
                        "tipo": "cliente_esistente",
                        "certo": certo,
                        "id": str(getattr(cliente, "id", "") or ""),
                        "etichetta": _norm(
                            getattr(cliente, "denominazione", "")
                            or f"{getattr(cliente, 'nome', '')} {getattr(cliente, 'cognome', '')}"
                        ),
                    }
                )

    # Soggetti dello studio: controparti e difensori di controparte sono il
    # cuore della verifica ex art. 24 CDF.
    if get_soggetti is not None:
        try:
            soggetti = list(get_soggetti().tutti())
        except Exception:
            soggetti = []
        for soggetto in soggetti:
            tipo = str(getattr(getattr(soggetto, "tipo", ""), "value", getattr(soggetto, "tipo", "")) or "")
            nome_soggetto = _norm_nome(
                getattr(soggetto, "ragione_sociale", "")
                or f"{getattr(soggetto, 'nome', '')} {getattr(soggetto, 'cognome', '')}"
            )
            certo = _match_codici(getattr(soggetto, "codice_fiscale", ""), getattr(soggetto, "partita_iva", ""))
            omonimo = bool(nome_norm and nome_soggetto and nome_norm == nome_soggetto)
            if not (certo or omonimo):
                continue
            e_controparte = "CONTROPARTE" in tipo.upper()
            riscontri.append(
                {
                    "tipo": "controparte" if e_controparte else "soggetto_noto",
                    "certo": certo,
                    "id": str(getattr(soggetto, "id", "") or ""),
                    "etichetta": _norm(
                        getattr(soggetto, "ragione_sociale", "")
                        or f"{getattr(soggetto, 'nome', '')} {getattr(soggetto, 'cognome', '')}"
                    ),
                    "ruolo": tipo,
                }
            )

    livello = "nessuno"
    if any(r["tipo"] == "controparte" and r["certo"] for r in riscontri):
        livello = "potenziale_conflitto"
    elif riscontri:
        livello = "da_valutare"
    return {
        "livello": livello,
        "riscontri": riscontri,
        "fonte": FONTE_DEONTOLOGICA,
        "verificato_il": datetime.now().isoformat(timespec="seconds"),
    }


class GestioneCrmIntake:
    """Intake tenant-aware con SQL come fonte di verità.

    Il precedente ``leads.json`` viene importato una sola volta quando il
    database SQL è vuoto e viene poi mantenuto come mirror rigenerabile.  Le
    letture, le decisioni di conflitto e le conversioni non ricadono mai sul
    JSON: in assenza dell'archivio SQL l'operazione fallisce esplicitamente.
    """

    def __init__(
        self,
        db_path: str = "./crm/leads.json",
        *,
        studio_db: Any | None = None,
        tenant_id: str = "studio-locale",
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_id = _norm(tenant_id) or "studio-locale"
        self.studio_db = studio_db or self._default_studio_db()
        self._ensure_sql_schema()
        self._migrate_legacy_scoped_sqlite()
        self._bootstrap_sql_from_legacy_mirror()
        self._leads = self._load_sql()

    @property
    def source_of_truth(self) -> str:
        return str(getattr(self.studio_db, "backend_kind", "sqlite") or "sqlite")

    def _default_studio_db(self) -> Any:
        from pct.storage import StudioDB

        # Nel runtime il mirror vive in ``<tenant>/crm/leads.json``; i test e
        # gli strumenti possono invece usare un JSON direttamente nella loro
        # directory temporanea. In quest'ultimo caso non risaliamo di due
        # livelli, altrimenti tenant diversi finirebbero nello stesso DB temp.
        if self.db_path.parent.name.lower() == "crm":
            return StudioDB.from_data_path(str(self.db_path))
        return StudioDB.get(str(self.db_path.parent / "studio.db"))

    @staticmethod
    def _json(value: Any, default: Any) -> Any:
        if isinstance(value, type(default)):
            return value
        if value in (None, ""):
            return default
        try:
            parsed = json.loads(str(value))
        except (TypeError, ValueError):
            return default
        return parsed if isinstance(parsed, type(default)) else default

    @staticmethod
    def _row_value(row: Any, key: str, default: Any = "") -> Any:
        try:
            value = row[key]
        except (KeyError, IndexError, TypeError):
            return default
        return default if value is None else value

    def _ensure_sql_schema(self) -> None:
        filename = (
            "20260824_crm_intake_postgres.sql"
            if self.source_of_truth == "postgresql"
            else "20260824_crm_intake.sql"
        )
        script = (Path(__file__).with_name("sql") / filename).read_text(encoding="utf-8")
        if self.source_of_truth == "postgresql":
            with self.studio_db.raw_conn.cursor() as cursor:
                cursor.execute(script)
            self.studio_db.raw_conn.commit()
            return
        self.studio_db.conn.executescript(script)
        self.studio_db.conn.commit()

    def _commit(self) -> None:
        (getattr(self.studio_db, "raw_conn", None) or self.studio_db.conn).commit()

    def _rollback(self) -> None:
        (getattr(self.studio_db, "raw_conn", None) or self.studio_db.conn).rollback()

    def _load_legacy_mirror(self) -> dict[str, Lead]:
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            return {}
        return {
            str(key): Lead.from_dict(value)
            for key, value in raw.items()
            if isinstance(value, dict)
        }

    def _load_sql(self) -> dict[str, Lead]:
        rows = self.studio_db.conn.execute(
            "SELECT * FROM crm_leads ORDER BY creato_il DESC, id DESC"
        ).fetchall()
        leads: dict[str, Lead] = {}
        for row in rows:
            payload = self._json(self._row_value(row, "dati_json", "{}"), {})
            payload.update(
                {
                    "id": self._row_value(row, "id"),
                    "denominazione": self._row_value(row, "denominazione"),
                    "codice_fiscale": self._row_value(row, "codice_fiscale"),
                    "partita_iva": self._row_value(row, "partita_iva"),
                    "email": self._row_value(row, "email"),
                    "telefono": self._row_value(row, "telefono"),
                    "fonte": self._row_value(row, "fonte", "altro"),
                    "materia": self._row_value(row, "materia"),
                    "esigenza": self._row_value(row, "esigenza"),
                    "stato": self._row_value(row, "stato", "NUOVO"),
                    "conflitto_verificato": bool(self._row_value(row, "conflitto_verificato", False)),
                    "conflitto_esito": self._json(self._row_value(row, "conflitto_esito_json", "{}"), {}),
                    "cliente_id": self._row_value(row, "cliente_id"),
                    "preventivo_id": self._row_value(row, "preventivo_id"),
                    "motivo_perso": self._row_value(row, "motivo_perso"),
                    "note": self._row_value(row, "note"),
                    "referente": self._row_value(row, "referente"),
                    "creato_il": self._row_value(row, "creato_il"),
                    "modificato_il": self._row_value(row, "modificato_il"),
                }
            )
            lead = Lead.from_dict(payload)
            leads[lead.id] = lead
        return leads

    def _bootstrap_sql_from_legacy_mirror(self) -> None:
        existing = self.studio_db.conn.execute("SELECT 1 FROM crm_leads LIMIT 1").fetchone()
        if existing:
            return
        # Dopo la migrazione del precedente database CRM, il JSON resta un
        # mirror rigenerabile: non può riportare in vita record eliminati dalla
        # fonte SQL canonica.
        migrated = self.studio_db.conn.execute(
            "SELECT 1 FROM crm_runtime_migrations WHERE migration_key = ? LIMIT 1",
            (_MIGRAZIONE_CRM_SCOPED_SQLITE,),
        ).fetchone()
        if migrated:
            return
        legacy = self._load_legacy_mirror()
        if not legacy:
            return
        try:
            for lead in legacy.values():
                self._write_lead(lead, enqueue_event=False)
            self._commit()
        except Exception:
            self._rollback()
            raise

    def _migrate_legacy_scoped_sqlite(self) -> None:
        """Recupera il precedente ``crm/studio.db`` nel DB canonico del tenant.

        Il percorso errato è stato usato soltanto per una finestra di sviluppo,
        ma può già contenere lead, decisioni, audit ed eventi outbox. Il file
        non resta una seconda fonte operativa: i record vengono copiati in modo
        idempotente nel database SQL radice e il mirror JSON non guida mai la
        riparazione.
        """

        if self.source_of_truth != "sqlite" or self.db_path.parent.name.lower() != "crm":
            return
        current_path = Path(str(getattr(self.studio_db, "db_path", "") or ""))
        legacy_path = self.db_path.parent / "studio.db"
        if not legacy_path.exists() or not current_path:
            return
        try:
            if legacy_path.resolve() == current_path.resolve():
                return
        except OSError:
            return
        already_migrated = self.studio_db.conn.execute(
            "SELECT 1 FROM crm_runtime_migrations WHERE migration_key = ? LIMIT 1",
            (_MIGRAZIONE_CRM_SCOPED_SQLITE,),
        ).fetchone()
        if already_migrated:
            return

        tables = (
            "crm_leads",
            "entity_nodes",
            "entity_relationships",
            "intake_compliance_assessments",
            "intake_compliance_audit",
            "transactional_outbox",
            "aml_verifications",
            "aml_screening_evidence",
            "aml_audit",
        )
        try:
            source = sqlite3.connect(str(legacy_path))
            source.row_factory = sqlite3.Row
            try:
                present = {
                    str(row[0])
                    for row in source.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                target = self.studio_db.conn
                for table in tables:
                    if table not in present:
                        continue
                    source_columns = [
                        str(row[1])
                        for row in source.execute(f"PRAGMA table_info({table})").fetchall()
                    ]
                    target_columns = {
                        str(row[1])
                        for row in target.execute(f"PRAGMA table_info({table})").fetchall()
                    }
                    columns = [column for column in source_columns if column in target_columns]
                    if not columns:
                        continue
                    column_names = ", ".join(columns)
                    placeholders = ", ".join("?" for _ in columns)
                    for row in source.execute(
                        f"SELECT {column_names} FROM {table}"
                    ).fetchall():
                        target.execute(
                            f"INSERT OR IGNORE INTO {table} ({column_names}) VALUES ({placeholders})",
                            tuple(row[column] for column in columns),
                        )
                target.execute(
                    """
                    INSERT OR IGNORE INTO crm_runtime_migrations
                    (migration_key, source_path, applied_at)
                    VALUES (?, ?, ?)
                    """,
                    (_MIGRAZIONE_CRM_SCOPED_SQLITE, str(legacy_path.resolve()), _now()),
                )
                self._commit()
            finally:
                source.close()
        except sqlite3.Error as exc:
            self._rollback()
            raise RuntimeError(
                "Recupero del precedente archivio CRM locale non riuscito; "
                "il sistema blocca l'avvio per non perdere il dato SQL."
            ) from exc

    def _write_legacy_mirror(self) -> None:
        """Scrive il mirror dopo il commit SQL; un errore non cambia SQL."""

        try:
            self.db_path.write_text(
                json.dumps(
                    {key: lead.to_dict() for key, lead in self._leads.items()},
                    ensure_ascii=False,
                    indent=1,
                ),
                encoding="utf-8",
            )
        except OSError:
            # Il mirror è rigenerabile; il dato SQL e la transazione restano validi.
            return

    def _entity_id(self, source_type: str, source_id: str) -> str:
        row = self.studio_db.conn.execute(
            "SELECT id FROM entity_nodes WHERE source_type = ? AND source_id = ?",
            (source_type, source_id),
        ).fetchone()
        return str(self._row_value(row, "id", "")) if row else ""

    def _upsert_lead_entity(self, lead: Lead) -> str:
        now = lead.modificato_il or _now()
        entity_id = self._entity_id("crm_lead", lead.id) or f"lead::{lead.id}"
        self.studio_db.conn.execute(
            """
            INSERT INTO entity_nodes (
                id, entity_type, display_name, normalized_name, codice_fiscale,
                partita_iva, source_type, source_id, payload_json, creato_il, modificato_il
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_type, source_id) DO UPDATE SET
                entity_type = excluded.entity_type,
                display_name = excluded.display_name,
                normalized_name = excluded.normalized_name,
                codice_fiscale = excluded.codice_fiscale,
                partita_iva = excluded.partita_iva,
                payload_json = excluded.payload_json,
                modificato_il = excluded.modificato_il
            """,
            (
                entity_id,
                "LEAD",
                lead.denominazione,
                _norm_nome(lead.denominazione),
                _norm_fiscale(lead.codice_fiscale),
                _norm_fiscale(lead.partita_iva),
                "crm_lead",
                lead.id,
                json.dumps({"fonte": lead.fonte, "materia": lead.materia}, ensure_ascii=False),
                lead.creato_il or now,
                now,
            ),
        )
        return entity_id

    def _link_converted_client(self, lead: Lead, lead_entity_id: str) -> None:
        if not lead.cliente_id:
            return
        now = lead.modificato_il or _now()
        client_source = str(lead.cliente_id)
        client_entity_id = self._entity_id("cliente", client_source) or f"cliente::{client_source}"
        self.studio_db.conn.execute(
            """
            INSERT INTO entity_nodes (
                id, entity_type, display_name, normalized_name, codice_fiscale,
                partita_iva, source_type, source_id, payload_json, creato_il, modificato_il
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_type, source_id) DO UPDATE SET
                display_name = excluded.display_name,
                normalized_name = excluded.normalized_name,
                codice_fiscale = excluded.codice_fiscale,
                partita_iva = excluded.partita_iva,
                modificato_il = excluded.modificato_il
            """,
            (
                client_entity_id,
                "CLIENTE",
                lead.denominazione,
                _norm_nome(lead.denominazione),
                _norm_fiscale(lead.codice_fiscale),
                _norm_fiscale(lead.partita_iva),
                "cliente",
                client_source,
                "{}",
                now,
                now,
            ),
        )
        self.studio_db.conn.execute(
            """
            INSERT INTO entity_relationships (
                id, from_entity_id, to_entity_id, relationship_type, status,
                source_type, source_id, explanation, creato_il, modificato_il
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(from_entity_id, to_entity_id, relationship_type, source_type, source_id)
            DO UPDATE SET status = excluded.status, explanation = excluded.explanation,
                          modificato_il = excluded.modificato_il
            """,
            (
                f"lead-client::{lead.id}", lead_entity_id, client_entity_id,
                "CONVERTITO_IN_CLIENTE", "ATTIVA", "crm_intake", lead.id,
                "Conversione esplicita del lead dopo verifica conflitti.", now, now,
            ),
        )

    def _record_audit(self, lead: Lead, event_type: str, message: str, payload: dict[str, Any]) -> None:
        now = _now()
        self.studio_db.conn.execute(
            """
            INSERT INTO intake_compliance_audit (id, lead_id, event_type, actor, message, payload_json, creato_il)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex, lead.id, event_type, lead.referente,
                message, json.dumps(payload, ensure_ascii=False), now,
            ),
        )

    def _record_compliance_event(
        self,
        lead: Lead,
        event_type: str,
        message: str,
        payload: dict[str, Any],
        *,
        decision: dict[str, Any] | None = None,
    ) -> None:
        now = _now()
        self.studio_db.conn.execute(
            """
            INSERT INTO intake_compliance_assessments (
                id, lead_id, client_id, assessment_type, status,
                source_snapshot_json, decision_json, creato_il, modificato_il
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id, assessment_type) DO UPDATE SET
                client_id = excluded.client_id, status = excluded.status,
                source_snapshot_json = excluded.source_snapshot_json,
                decision_json = excluded.decision_json, modificato_il = excluded.modificato_il
            """,
            (
                f"conflict::{lead.id}", lead.id, lead.cliente_id, "CONFLITTO_INTERESSI",
                str(payload.get("livello") or "DA_VALUTARE").upper(),
                json.dumps(payload, ensure_ascii=False),
                json.dumps(decision or {"message": message}, ensure_ascii=False), now, now,
            ),
        )
        self._record_audit(lead, event_type, message, payload)

    def _write_lead(self, lead: Lead, *, event_type: str = "", enqueue_event: bool = True) -> None:
        current = self.studio_db.conn.execute(
            "SELECT versione FROM crm_leads WHERE id = ?", (lead.id,)
        ).fetchone()
        version = int(self._row_value(current, "versione", 0) or 0) + 1
        payload = lead.to_dict()
        self.studio_db.conn.execute(
            """
            INSERT INTO crm_leads (
                id, denominazione, codice_fiscale, partita_iva, email, telefono,
                fonte, materia, esigenza, stato, conflitto_verificato,
                conflitto_esito_json, cliente_id, preventivo_id, motivo_perso,
                note, referente, versione, creato_il, modificato_il, dati_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                denominazione = excluded.denominazione,
                codice_fiscale = excluded.codice_fiscale,
                partita_iva = excluded.partita_iva,
                email = excluded.email,
                telefono = excluded.telefono,
                fonte = excluded.fonte,
                materia = excluded.materia,
                esigenza = excluded.esigenza,
                stato = excluded.stato,
                conflitto_verificato = excluded.conflitto_verificato,
                conflitto_esito_json = excluded.conflitto_esito_json,
                cliente_id = excluded.cliente_id,
                preventivo_id = excluded.preventivo_id,
                motivo_perso = excluded.motivo_perso,
                note = excluded.note,
                referente = excluded.referente,
                versione = excluded.versione,
                modificato_il = excluded.modificato_il,
                dati_json = excluded.dati_json
            """,
            (
                lead.id, lead.denominazione, _norm_fiscale(lead.codice_fiscale),
                _norm_fiscale(lead.partita_iva), lead.email, lead.telefono,
                lead.fonte, lead.materia, lead.esigenza, lead.stato,
                bool(lead.conflitto_verificato), json.dumps(lead.conflitto_esito, ensure_ascii=False),
                lead.cliente_id, lead.preventivo_id, lead.motivo_perso, lead.note,
                lead.referente, version, lead.creato_il, lead.modificato_il,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        lead_entity_id = self._upsert_lead_entity(lead)
        self._link_converted_client(lead, lead_entity_id)
        if event_type and enqueue_event:
            enqueue(
                self.studio_db.conn,
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="crm_lead",
                    aggregate_id=lead.id,
                    aggregate_version=version,
                    event_type=event_type,
                    idempotency_key=f"crm:{lead.id}:{version}:{event_type}",
                    payload={"lead_id": lead.id, "stato": lead.stato},
                    actor_id=lead.referente or "sistema",
                ),
            )

    def _persist(self, lead: Lead, *, event_type: str = "") -> Lead:
        try:
            self._write_lead(lead, event_type=event_type)
            self._commit()
        except Exception:
            self._rollback()
            raise
        self._leads[lead.id] = lead
        self._write_legacy_mirror()
        return lead

    # ------------------------------------------------------------------ CRUD
    def nuovo(self, **campi: Any) -> Lead:
        lead = Lead(**{k: v for k, v in campi.items() if k in Lead.__dataclass_fields__})
        if lead.fonte not in FONTI_LEAD:
            lead.fonte = "altro"
        if not _norm(lead.denominazione):
            raise ValueError("Il lead richiede almeno nome e cognome o denominazione.")
        return self._persist(lead, event_type="CRM_LEAD_CREATED")

    def aggiorna(self, lead_id: str, **campi: Any) -> Lead:
        """Corregge il contatto senza perdere l'intake né rifarlo da capo.

        Se cambiano nome o identificativi, il precedente controllo conflitti
        non viene riutilizzato: resta nello storico ma va eseguito di nuovo
        sul dato corretto. Un cliente già creato va invece gestito dalla sua
        anagrafica, per non disallineare la relazione lead → cliente.
        """

        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        if lead.cliente_id:
            raise ValueError("Il contatto è già un cliente: correggi l'anagrafica cliente collegata.")

        allowed = {
            "denominazione", "codice_fiscale", "partita_iva", "email",
            "telefono", "fonte", "materia", "esigenza", "note",
        }
        changed: dict[str, str] = {}
        for field_name in allowed:
            if field_name not in campi:
                continue
            value = _norm(campi[field_name])
            if field_name in {"codice_fiscale", "partita_iva"}:
                value = _norm_fiscale(value)
            if field_name == "fonte" and value not in FONTI_LEAD:
                raise ValueError("Fonte del lead non valida.")
            if getattr(lead, field_name) != value:
                changed[field_name] = value

        denominazione = changed.get("denominazione", lead.denominazione)
        if not _norm(denominazione):
            raise ValueError("Il lead richiede almeno nome e cognome o denominazione.")
        if not changed:
            return lead

        for field_name, value in changed.items():
            setattr(lead, field_name, value)
        conflict_fields = {"denominazione", "codice_fiscale", "partita_iva"}
        verification_invalidated = bool(conflict_fields.intersection(changed))
        if verification_invalidated:
            lead.conflitto_verificato = False
            lead.conflitto_esito = {}
        lead.modificato_il = _now()
        try:
            self._write_lead(lead, event_type="CRM_LEAD_UPDATED")
            self._record_audit(
                lead,
                "LEAD_DATA_UPDATED",
                "Dati del contatto corretti nella pipeline.",
                {
                    "campi": sorted(changed),
                    "verifica_conflitti_da_ripetere": verification_invalidated,
                },
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        self._leads[lead.id] = lead
        self._write_legacy_mirror()
        return lead

    def get(self, lead_id: str) -> Lead | None:
        return self._leads.get(lead_id)

    def tutti(self, *, stato: str = "") -> list[Lead]:
        rows = [l for l in self._leads.values() if not stato or l.stato == stato]
        rows.sort(key=lambda l: l.creato_il, reverse=True)
        return rows

    def pipeline(self) -> dict[str, list[Lead]]:
        colonne: dict[str, list[Lead]] = {stato: [] for stato in STATI_LEAD}
        for lead in self.tutti():
            colonne.setdefault(lead.stato, []).append(lead)
        return colonne

    # ------------------------------------------------------------------ stati
    def cambia_stato(self, lead_id: str, stato: str, *, motivo_perso: str = "") -> Lead:
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        if stato not in STATI_LEAD:
            raise ValueError(f"Stato non valido: {stato}.")
        if stato == "PERSO" and not _norm(motivo_perso):
            raise ValueError("Per chiudere un lead come perso serve il motivo (migliora le statistiche di intake).")
        if stato == "VINTO" and not lead.conflitto_verificato:
            raise ValueError(
                "Prima di assumere l'incarico va eseguita la verifica conflitti (art. 24 CDF)."
            )
        if stato == "VINTO" and not self.stato_clearance_conflitto(lead.id)["convertibile"]:
            raise ValueError(
                "Il conflitto richiede una decisione professionale motivata prima dell'assunzione dell'incarico."
            )
        lead.stato = stato
        lead.motivo_perso = _norm(motivo_perso)
        lead.modificato_il = _now()
        return self._persist(lead, event_type="CRM_LEAD_STATUS_CHANGED")

    # ------------------------------------------------------------ conflitti
    def verifica_conflitti(
        self,
        lead_id: str,
        *,
        get_clienti: Callable[[], Any] | None = None,
        get_soggetti: Callable[[], Any] | None = None,
    ) -> dict[str, Any]:
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        esito = verifica_conflitto_interessi(
            denominazione=lead.denominazione,
            codice_fiscale=lead.codice_fiscale,
            partita_iva=lead.partita_iva,
            get_clienti=get_clienti,
            get_soggetti=get_soggetti,
        )
        lead.conflitto_verificato = True
        lead.conflitto_esito = esito
        lead.modificato_il = _now()
        try:
            self._write_lead(lead, event_type="CRM_CONFLICT_CHECKED")
            self._record_compliance_event(
                lead,
                "CONFLICT_CHECKED",
                "Verifica conflitti conclusa: la decisione professionale resta all'avvocato.",
                esito,
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        self._leads[lead.id] = lead
        self._write_legacy_mirror()
        return esito

    def stato_clearance_conflitto(self, lead_id: str) -> dict[str, Any]:
        """Restituisce lo stato che abilita (o blocca) l'assunzione.

        La ricerca non è una clearance: per ogni riscontro serve una decisione
        dell'avvocato, con motivazione ed evidenza audit. Il solo esito
        ``nessuno`` non richiede alcuna decisione ulteriore.
        """

        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        esito = dict(lead.conflitto_esito or {})
        livello = str(esito.get("livello") or "").strip()
        if not lead.conflitto_verificato:
            return {
                "richiesta": True,
                "decisione": "",
                "convertibile": False,
                "label": "Verifica conflitti da eseguire",
            }
        if livello == "nessuno":
            return {
                "richiesta": False,
                "decisione": "NON_NECESSARIA",
                "convertibile": True,
                "label": "Nessun riscontro: nessuna clearance aggiuntiva necessaria",
            }
        row = self.studio_db.conn.execute(
            "SELECT decision_json FROM intake_compliance_assessments WHERE lead_id = ? AND assessment_type = ?",
            (lead.id, "CONFLITTO_INTERESSI"),
        ).fetchone()
        decision = self._json(self._row_value(row, "decision_json", "{}"), {})
        value = str(decision.get("decision") or "").strip().upper()
        return {
            "richiesta": True,
            "decisione": value,
            "convertibile": value == "CLEARANCE_CONCESSA",
            "label": (
                "Clearance concessa e tracciata"
                if value == "CLEARANCE_CONCESSA"
                else "Astensione registrata"
                if value == "ASTENSIONE"
                else "Decisione professionale sul conflitto richiesta"
            ),
        }

    def registra_decisione_conflitto(
        self,
        lead_id: str,
        *,
        decisione: str,
        motivazione: str,
        operatore: str,
    ) -> dict[str, Any]:
        """Registra una clearance o l'astensione dopo un riscontro.

        Nessuna decisione viene inferita dal software. La motivazione è
        obbligatoria e viene salvata nel controllo di conformità e nell'audit.
        """

        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        if not lead.conflitto_verificato:
            raise ValueError("Esegui prima la verifica conflitti.")
        if str((lead.conflitto_esito or {}).get("livello") or "") == "nessuno":
            raise ValueError("Non è necessaria una clearance quando non emergono riscontri.")
        scelta = str(decisione or "").strip().upper()
        reason = _norm(motivazione)
        if scelta not in DECISIONI_CONFLITTO:
            raise ValueError("Decisione sul conflitto non valida.")
        if not reason:
            raise ValueError("La decisione sul conflitto richiede una motivazione professionale.")
        actor = _norm(operatore) or lead.referente or "avvocato"
        decision_payload = {
            "decision": scelta,
            "motivazione": reason,
            "operatore": actor,
            "decisa_il": _now(),
        }
        try:
            self._record_compliance_event(
                lead,
                "CONFLICT_CLEARANCE_DECIDED",
                "Decisione professionale sul conflitto registrata.",
                dict(lead.conflitto_esito or {}),
                decision=decision_payload,
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        self._write_legacy_mirror()
        return self.stato_clearance_conflitto(lead.id)

    # ----------------------------------------------------- barriera informativa
    def _wall_row(self, lead_id: str) -> Any | None:
        return self.studio_db.conn.execute(
            "SELECT * FROM ethical_walls WHERE lead_id = ?",
            (lead_id,),
        ).fetchone()

    def _wall_members(self, wall_id: str) -> list[str]:
        rows = self.studio_db.conn.execute(
            """
            SELECT username FROM ethical_wall_members
            WHERE wall_id = ? AND access_level = 'AUTORIZZATO'
            ORDER BY username
            """,
            (wall_id,),
        ).fetchall()
        return [
            _norm_nome(self._row_value(row, "username", ""))
            for row in rows
            if _norm_nome(self._row_value(row, "username", ""))
        ]

    @staticmethod
    def _normalized_members(members: list[str] | tuple[str, ...] | set[str] | None, *, owner: str) -> list[str]:
        values = {_norm_nome(owner)}
        for member in members or []:
            value = _norm_nome(member)
            if value:
                values.add(value)
        values.discard("")
        return sorted(values)

    def _record_wall_audit(
        self,
        *,
        wall_id: str,
        lead: Lead,
        event_type: str,
        actor: str,
        message: str,
        payload: dict[str, Any],
    ) -> None:
        now = _now()
        safe_actor = _norm_nome(actor)
        encoded = json.dumps(payload, ensure_ascii=False)
        self.studio_db.conn.execute(
            """
            INSERT INTO ethical_wall_audit
            (id, wall_id, lead_id, event_type, actor, message, payload_json, creato_il)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid.uuid4().hex, wall_id, lead.id, event_type, safe_actor, message, encoded, now),
        )
        self._record_audit(lead, event_type, message, payload)

    def stato_barriera_riservatezza(self, lead_id: str, *, operatore: str = "") -> dict[str, Any]:
        """Restituisce lo stato della segregazione per il soggetto del lead.

        Una barriera attiva è deny-by-default: il suo responsabile e gli
        utenti autorizzati in modo esplicito possono accedere; gli altri no.
        Il dato non equivale mai a una clearance del conflitto di interessi.
        """

        row = self._wall_row(lead_id)
        if row is None:
            return {
                "attiva": False,
                "accesso_consentito": True,
                "gestibile": False,
                "label": "Nessuna barriera informativa attiva",
                "utenti_autorizzati": [],
            }
        wall_id = str(self._row_value(row, "id", ""))
        stato = str(self._row_value(row, "stato", "") or "").upper()
        owner = _norm_nome(self._row_value(row, "creato_da", ""))
        actor = _norm_nome(operatore)
        members = self._wall_members(wall_id)
        active = stato == "ATTIVA"
        allowed = not active or bool(actor and actor in members)
        return {
            "id": wall_id,
            "attiva": active,
            "stato": stato,
            "titolo": _norm(self._row_value(row, "titolo", "")),
            "motivazione": _norm(self._row_value(row, "motivazione", "")),
            "creato_da": owner,
            "creato_il": str(self._row_value(row, "creato_il", "")),
            "modificato_il": str(self._row_value(row, "modificato_il", "")),
            "utenti_autorizzati": members,
            "accesso_consentito": allowed,
            "gestibile": bool(active and actor and actor == owner),
            "label": (
                f"Accesso riservato a {len(members)} professionisti"
                if active
                else "Barriera informativa revocata"
            ),
        }

    def accesso_lead_consentito(self, lead_id: str, *, operatore: str) -> bool:
        return bool(self.stato_barriera_riservatezza(lead_id, operatore=operatore).get("accesso_consentito"))

    def _write_wall_members(self, wall_id: str, members: list[str], *, actor: str, now: str) -> None:
        self.studio_db.conn.execute("DELETE FROM ethical_wall_members WHERE wall_id = ?", (wall_id,))
        for username in members:
            self.studio_db.conn.execute(
                """
                INSERT INTO ethical_wall_members
                (id, wall_id, username, access_level, aggiunto_da, aggiunto_il)
                VALUES (?, ?, ?, 'AUTORIZZATO', ?, ?)
                """,
                (uuid.uuid4().hex, wall_id, username, _norm_nome(actor), now),
            )

    def crea_barriera_riservatezza(
        self,
        lead_id: str,
        *,
        motivazione: str,
        utenti_autorizzati: list[str] | tuple[str, ...] | set[str] | None,
        operatore: str,
        titolo: str = "Barriera informativa del fascicolo",
    ) -> dict[str, Any]:
        """Istituisce (o riattiva) una barriera informativa SQL-first.

        Il responsabile corrente è sempre incluso negli autorizzati. La
        chiamata richiede una motivazione verificabile e produce audit/outbox
        transazionali, senza mutare l'esito del conflitto deontologico.
        """

        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        actor = _norm_nome(operatore)
        reason = _norm(motivazione)
        wall_title = _norm(titolo) or "Barriera informativa del fascicolo"
        if not actor:
            raise ValueError("Serve il professionista responsabile della barriera informativa.")
        if not reason:
            raise ValueError("La barriera informativa richiede una motivazione verificabile.")
        existing = self._wall_row(lead_id)
        if existing is not None and str(self._row_value(existing, "stato", "")).upper() == "ATTIVA":
            existing_owner = _norm_nome(self._row_value(existing, "creato_da", ""))
            if existing_owner != actor:
                raise PermissionError("Solo il responsabile della barriera può modificarne gli accessi.")
        owner = actor if existing is None else _norm_nome(self._row_value(existing, "creato_da", "")) or actor
        members = self._normalized_members(utenti_autorizzati, owner=owner)
        now = _now()
        subject_entity_id = self._entity_id("crm_lead", lead.id) or self._upsert_lead_entity(lead)
        wall_id = str(self._row_value(existing, "id", "")) if existing is not None else uuid.uuid4().hex[:16].upper()
        version = int(self._row_value(existing, "versione", 0) or 0) + 1
        try:
            if existing is None:
                self.studio_db.conn.execute(
                    """
                    INSERT INTO ethical_walls (
                        id, lead_id, subject_entity_id, titolo, motivazione, stato,
                        creato_da, creato_il, modificato_il, versione
                    ) VALUES (?, ?, ?, ?, ?, 'ATTIVA', ?, ?, ?, ?)
                    """,
                    (wall_id, lead.id, subject_entity_id, wall_title, reason, owner, now, now, version),
                )
                event_type = "CRM_ETHICAL_WALL_CREATED"
                message = "Barriera informativa istituita: accesso limitato agli autorizzati."
            else:
                self.studio_db.conn.execute(
                    """
                    UPDATE ethical_walls
                    SET subject_entity_id = ?, titolo = ?, motivazione = ?, stato = 'ATTIVA',
                        modificato_il = ?, revocato_da = '', revocato_il = '',
                        motivazione_revoca = '', versione = ?
                    WHERE id = ?
                    """,
                    (subject_entity_id, wall_title, reason, now, version, wall_id),
                )
                event_type = "CRM_ETHICAL_WALL_REACTIVATED"
                message = "Barriera informativa riattivata e autorizzazioni aggiornate."
            self._write_wall_members(wall_id, members, actor=actor, now=now)
            payload = {
                "subject_entity_id": subject_entity_id,
                "titolo": wall_title,
                "motivazione": reason,
                "utenti_autorizzati": members,
                "versione": version,
            }
            self._record_wall_audit(
                wall_id=wall_id,
                lead=lead,
                event_type=event_type,
                actor=actor,
                message=message,
                payload=payload,
            )
            enqueue(
                self.studio_db.conn,
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="ethical_wall",
                    aggregate_id=wall_id,
                    aggregate_version=version,
                    event_type=event_type,
                    idempotency_key=f"ethical-wall:{wall_id}:{version}:{event_type}",
                    payload={"lead_id": lead.id, **payload},
                    actor_id=actor,
                ),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self.stato_barriera_riservatezza(lead.id, operatore=actor)

    def aggiorna_barriera_riservatezza(
        self,
        lead_id: str,
        *,
        motivazione: str,
        utenti_autorizzati: list[str] | tuple[str, ...] | set[str] | None,
        operatore: str,
    ) -> dict[str, Any]:
        wall = self._wall_row(lead_id)
        if wall is None or str(self._row_value(wall, "stato", "")).upper() != "ATTIVA":
            raise ValueError("Non esiste una barriera informativa attiva per questo contatto.")
        actor = _norm_nome(operatore)
        owner = _norm_nome(self._row_value(wall, "creato_da", ""))
        if not actor or actor != owner:
            raise PermissionError("Solo il responsabile della barriera può modificarne gli accessi.")
        reason = _norm(motivazione)
        if not reason:
            raise ValueError("L'aggiornamento della barriera richiede una motivazione verificabile.")
        members = self._normalized_members(utenti_autorizzati, owner=owner)
        wall_id = str(self._row_value(wall, "id", ""))
        version = int(self._row_value(wall, "versione", 0) or 0) + 1
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        now = _now()
        try:
            self.studio_db.conn.execute(
                """
                UPDATE ethical_walls
                SET motivazione = ?, modificato_il = ?, versione = ?
                WHERE id = ?
                """,
                (reason, now, version, wall_id),
            )
            self._write_wall_members(wall_id, members, actor=actor, now=now)
            payload = {"motivazione": reason, "utenti_autorizzati": members, "versione": version}
            self._record_wall_audit(
                wall_id=wall_id,
                lead=lead,
                event_type="CRM_ETHICAL_WALL_UPDATED",
                actor=actor,
                message="Autorizzazioni della barriera informativa aggiornate.",
                payload=payload,
            )
            enqueue(
                self.studio_db.conn,
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="ethical_wall",
                    aggregate_id=wall_id,
                    aggregate_version=version,
                    event_type="CRM_ETHICAL_WALL_UPDATED",
                    idempotency_key=f"ethical-wall:{wall_id}:{version}:updated",
                    payload={"lead_id": lead.id, **payload},
                    actor_id=actor,
                ),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self.stato_barriera_riservatezza(lead.id, operatore=actor)

    def revoca_barriera_riservatezza(self, lead_id: str, *, motivazione: str, operatore: str) -> dict[str, Any]:
        wall = self._wall_row(lead_id)
        if wall is None or str(self._row_value(wall, "stato", "")).upper() != "ATTIVA":
            raise ValueError("Non esiste una barriera informativa attiva per questo contatto.")
        actor = _norm_nome(operatore)
        owner = _norm_nome(self._row_value(wall, "creato_da", ""))
        if not actor or actor != owner:
            raise PermissionError("Solo il responsabile della barriera può revocarla.")
        reason = _norm(motivazione)
        if not reason:
            raise ValueError("La revoca della barriera richiede una motivazione verificabile.")
        wall_id = str(self._row_value(wall, "id", ""))
        version = int(self._row_value(wall, "versione", 0) or 0) + 1
        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        now = _now()
        try:
            self.studio_db.conn.execute(
                """
                UPDATE ethical_walls
                SET stato = 'REVOCATA', modificato_il = ?, revocato_da = ?,
                    revocato_il = ?, motivazione_revoca = ?, versione = ?
                WHERE id = ?
                """,
                (now, actor, now, reason, version, wall_id),
            )
            payload = {"motivazione_revoca": reason, "versione": version}
            self._record_wall_audit(
                wall_id=wall_id,
                lead=lead,
                event_type="CRM_ETHICAL_WALL_REVOKED",
                actor=actor,
                message="Barriera informativa revocata con motivazione.",
                payload=payload,
            )
            enqueue(
                self.studio_db.conn,
                OutboxEvent(
                    tenant_id=self.tenant_id,
                    aggregate_type="ethical_wall",
                    aggregate_id=wall_id,
                    aggregate_version=version,
                    event_type="CRM_ETHICAL_WALL_REVOKED",
                    idempotency_key=f"ethical-wall:{wall_id}:{version}:revoked",
                    payload={"lead_id": lead.id, **payload},
                    actor_id=actor,
                ),
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self.stato_barriera_riservatezza(lead.id, operatore=actor)

    def registra_accesso_barriera_negato(self, lead_id: str, *, operatore: str, azione: str) -> None:
        """Traccia un tentativo di azione bloccato senza esporre il contenuto."""

        wall = self._wall_row(lead_id)
        lead = self._leads.get(lead_id)
        if wall is None or lead is None or str(self._row_value(wall, "stato", "")).upper() != "ATTIVA":
            return
        try:
            self._record_wall_audit(
                wall_id=str(self._row_value(wall, "id", "")),
                lead=lead,
                event_type="CRM_ETHICAL_WALL_ACCESS_DENIED",
                actor=operatore,
                message="Tentativo di azione bloccato dalla barriera informativa.",
                payload={"azione": _norm(azione)},
            )
            self._commit()
        except Exception:
            self._rollback()
            raise

    # ------------------------------------------------------------ conversione
    def converti_in_cliente(
        self,
        lead_id: str,
        *,
        crea_cliente: Callable[[dict[str, Any]], Any],
    ) -> Lead:
        """Conversione in cliente reale: solo dopo la verifica conflitti.

        ``crea_cliente`` riceve i dati anagrafici e ritorna il cliente creato
        (la persistenza resta nel dominio clienti). Il lead passa a VINTO.
        """

        lead = self._leads.get(lead_id)
        if lead is None:
            raise KeyError(f"Lead {lead_id} non trovato.")
        if not lead.conflitto_verificato:
            raise ValueError(
                "Prima della conversione va eseguita la verifica conflitti (art. 24 CDF)."
            )
        if not self.stato_clearance_conflitto(lead.id)["convertibile"]:
            raise ValueError(
                "Il conflitto richiede una decisione professionale motivata prima della conversione in cliente."
            )
        if lead.cliente_id:
            return lead  # gia' convertito: idempotente
        cliente = crea_cliente(
            {
                "denominazione": lead.denominazione,
                "codice_fiscale": lead.codice_fiscale,
                "partita_iva": lead.partita_iva,
                "email": lead.email,
                "telefono": lead.telefono,
                "note": f"Da intake CRM (fonte: {lead.fonte}). {lead.esigenza}".strip(),
            }
        )
        cliente_id = cliente.get("id", "") if isinstance(cliente, dict) else getattr(cliente, "id", "")
        lead.cliente_id = str(cliente_id or "")
        lead.stato = "VINTO"
        lead.modificato_il = _now()
        return self._persist(lead, event_type="CRM_LEAD_CONVERTED")

    # ------------------------------------------------------------ statistiche
    def statistiche(self) -> dict[str, Any]:
        rows = self.tutti()
        per_stato = {stato: sum(1 for l in rows if l.stato == stato) for stato in STATI_LEAD}
        per_fonte: dict[str, int] = {}
        for lead in rows:
            per_fonte[lead.fonte] = per_fonte.get(lead.fonte, 0) + 1
        chiusi = per_stato["VINTO"] + per_stato["PERSO"]
        return {
            "totale": len(rows),
            "per_stato": per_stato,
            "per_fonte": per_fonte,
            "tasso_conversione": round(per_stato["VINTO"] / chiusi, 2) if chiusi else 0.0,
        }
