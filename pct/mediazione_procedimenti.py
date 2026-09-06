"""Procedimenti dello studio: SQL tenant-aware, separati dal registro pubblico.

Nessun invio esterno, nessuna attestazione automatica di deposito o conciliazione.
Il calendario deriva dagli artt. 6 e 8 D.Lgs. 28/2010, correttivo 216/2024.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

REGIMI = {"volontaria", "obbligatoria", "demandata", "clausola"}
STATI = {"bozza", "pronta", "depositata", "in_corso", "accordo", "mancato_accordo", "ritirata"}
MODALITA = {"presenza", "remoto", "telematica"}
FONTI = [
    {"titolo": "D.Lgs. 28/2010: procedimento di mediazione", "url": "https://www.gazzettaufficiale.it/eli/id/2010/03/05/010G0050/sg"},
    {"titolo": "D.Lgs. 216/2024: durata, delega e modalità telematiche", "url": "https://www.gazzettaufficiale.it/eli/id/2025/01/10/25G00003/SG"},
    {"titolo": "D.M. 150/2023: organismi e indennità", "url": "https://www.gazzettaufficiale.it/eli/id/2023/10/31/23G00163/sg"},
    {"titolo": "Regolamento UE 2016/679: protezione dei dati personali", "url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj?locale=it"},
]
TEXT_FIELDS = {
    "titolo": 250, "organismo_numero": 30, "sede_id": 300,
    "oggetto": 2000, "ragioni": 18000, "competenza": 1500,
    "valore": 60, "protocollo": 150, "mediatore": 300,
    "note_riservate": 18000, "esito_note": 8000,
}
DATE_FIELDS = {"data_deposito", "data_ordinanza", "data_chiusura"}
BOOL_FIELDS = {"valore_indeterminabile", "informativa_avvocato", "riservatezza_verificata",
               "assistenza_verificata", "competenza_verificata", "patrocinio_richiesto", "modulo_verificato"}
DOC_FIELDS = {"istanza_documento", "ricevuta_documento", "verbale_documento", "accordo_documento",
              "ordinanza_documento", "delega_documento", "pagamento_documento", "modulo_ufficiale_documento",
              "bozza_documento", "modulo_compilato_documento"}


def _text(value, limit=2000):
    if not isinstance(value, (str, int, float)):
        raise ValueError("Campo testuale non valido.")
    value = str(value).strip()
    if len(value) > limit or "\x00" in value:
        raise ValueError(f"Testo non valido o superiore a {limit} caratteri.")
    return value


def _date(value):
    value = _text(value, 10)
    if value and date.fromisoformat(value).isoformat() != value:
        raise ValueError("Data non valida.")
    return value


def add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year, month = value.year + month // 12, month % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def calendario(payload):
    judicial = payload.get("regime") == "demandata" or bool(payload.get("data_ordinanza"))
    start = payload.get("data_ordinanza") if judicial else payload.get("data_deposito")
    result = {"decorrenza": start or "", "scadenza": "", "sospensione_feriale": False,
              "fonte": "Art. 6 D.Lgs. 28/2010, come modificato dal D.Lgs. 216/2024"}
    if start:
        deadline = add_months(date.fromisoformat(start), 6)
        for extension in payload.get("proroghe", []):
            deadline = date.fromisoformat(extension["scadenza"])
        result["scadenza"] = deadline.isoformat()
    if payload.get("data_deposito"):
        deposited = date.fromisoformat(payload["data_deposito"])
        result["primo_incontro_da"] = (deposited + timedelta(days=20)).isoformat()
        result["primo_incontro_entro"] = (deposited + timedelta(days=40)).isoformat()
    return result


def verifica(payload):
    checks = [
        ("organismo", bool(payload.get("organismo_numero") and payload.get("sede_id")), "Seleziona organismo e sede."),
        ("oggetto", bool(payload.get("oggetto") and payload.get("ragioni")), "Completa oggetto e ragioni della pretesa."),
        ("parti", all(any(p["ruolo"] == role for p in payload.get("parti", [])) for role in ("istante", "invitata")), "Indica parte istante e parte invitata."),
        ("valore", bool(payload.get("valore") or payload.get("valore_indeterminabile")), "Indica il valore o se è indeterminabile."),
        ("competenza", bool(payload.get("competenza_verificata") and payload.get("competenza")), "Verifica la competenza territoriale o l'accordo derogatorio."),
        ("informativa", bool(payload.get("informativa_avvocato")), "Verifica l'informativa dell'avvocato sulla mediazione."),
        ("riservatezza", bool(payload.get("riservatezza_verificata")), "Verifica riservatezza e documenti da comunicare all'organismo."),
        ("modulo", bool(payload.get("modulo_verificato")), "Verifica il modulo e le istruzioni dell'organismo scelto."),
        ("assistenza", payload.get("regime") not in {"obbligatoria", "demandata"} or bool(payload.get("assistenza_verificata")), "Verifica l'assistenza degli avvocati richiesta per il procedimento."),
    ]
    if payload.get("regime") == "demandata":
        checks.append(("ordinanza", bool(payload.get("data_ordinanza") and payload.get("ordinanza_documento")), "Collega l'ordinanza e la sua data di deposito."))
    return [{"id": key, "ok": bool(ok), "messaggio": message} for key, ok, message in checks]


def normalizza(body, document_ids):
    if not isinstance(body, dict):
        raise ValueError("Dati del procedimento non validi.")
    result = {key: _text(body.get(key, ""), size) for key, size in TEXT_FIELDS.items()}
    result.update({key: _date(body.get(key, "")) for key in DATE_FIELDS})
    if result["valore"]:
        if not re.fullmatch(r"\d+(?:\.\d{3})*(?:,\d{1,2})?", result["valore"]):
            raise ValueError("Indica il valore in euro, per esempio 1.234,56.")
        try:
            amount = Decimal(result["valore"].replace(".", "").replace(",", "."))
            if not amount.is_finite() or amount < 0:
                raise ValueError("Valore economico non valido.")
        except InvalidOperation as exc:
            raise ValueError("Valore economico non valido.") from exc
    for key in BOOL_FIELDS:
        if not isinstance(body.get(key, False), bool):
            raise ValueError("Valore di verifica non valido.")
        result[key] = body.get(key, False)
    for key in DOC_FIELDS:
        value = _text(body.get(key, ""), 64)
        if value and value not in document_ids:
            raise ValueError("Il documento collegato non appartiene al fascicolo corrente.")
        result[key] = value
    attachments = body.get("allegati_documenti", [])
    if not isinstance(attachments, list) or any(not isinstance(i, str) or i not in document_ids for i in attachments):
        raise ValueError("Uno degli allegati non appartiene al fascicolo corrente.")
    result["allegati_documenti"] = list(dict.fromkeys(attachments))
    for key, allowed, default in (("regime", REGIMI, "volontaria"), ("stato", STATI, "bozza"),
                                  ("modalita", MODALITA, "presenza")):
        result[key] = body.get(key, default)
        if result[key] not in allowed:
            raise ValueError(f"Valore non valido: {key}.")
    for key, fields, limit in (
        ("parti", {"nome", "ruolo", "codice_fiscale", "indirizzo", "pec", "email", "difensore", "rappresentante"}, 50),
        ("incontri", {"data_ora", "luogo", "presenze", "note", "verbale_documento"}, 100),
        ("proroghe", {"data_accordo", "scadenza", "documento", "comunicazione_giudice_documento"}, 30),
    ):
        rows = body.get(key, [])
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError(f"Elenco non valido: {key}.")
        result[key] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Riga non valida: {key}.")
            clean = {field: _text(row.get(field, ""), 2000) for field in fields}
            for field in fields:
                if field.endswith("documento") and clean[field] and clean[field] not in document_ids:
                    raise ValueError("Documento di prova esterno al fascicolo.")
            if key == "parti" and (not clean["nome"] or clean["ruolo"] not in {"istante", "invitata", "aderente"}):
                raise ValueError("Completa nome e ruolo di ciascuna parte.")
            if key == "incontri":
                meeting = datetime.fromisoformat(clean["data_ora"])
                if meeting.tzinfo:
                    meeting = meeting.astimezone(ZoneInfo("Europe/Rome"))
                clean["data_ora"] = meeting.replace(tzinfo=ZoneInfo("Europe/Rome")).isoformat()
            if key == "proroghe":
                _date(clean["data_accordo"])
                _date(clean["scadenza"])
                if not clean["documento"] or not clean["data_accordo"] or not clean["scadenza"]:
                    raise ValueError("La proroga richiede accordo scritto, data e nuova scadenza.")
            result[key].append(clean)
    if result["parti"] and not any(p["ruolo"] == "istante" for p in result["parti"]):
        raise ValueError("Indica almeno una parte istante.")
    judicial = result["regime"] == "demandata" or bool(result["data_ordinanza"])
    start = result["data_ordinanza"] if judicial else result["data_deposito"]
    if result["proroghe"]:
        if not start or (judicial and len(result["proroghe"]) > 1):
            raise ValueError("Proroga non compatibile con decorrenza e regime del procedimento.")
        previous = add_months(date.fromisoformat(start), 6)
        for extension in result["proroghe"]:
            signed = date.fromisoformat(extension["data_accordo"])
            end = date.fromisoformat(extension["scadenza"])
            if not date.fromisoformat(start) <= signed < previous or not previous < end <= add_months(previous, 3):
                raise ValueError("Proroga fuori termine o superiore a tre mesi.")
            previous = end
    if result["stato"] != "bozza":
        missing = [row["messaggio"] for row in verifica(result) if not row["ok"]]
        if missing:
            raise ValueError(" ".join(missing))
    if result["stato"] in {"depositata", "in_corso", "accordo", "mancato_accordo"}:
        if not all(result[key] for key in ("data_deposito", "istanza_documento", "ricevuta_documento")):
            raise ValueError("Per registrare il deposito occorrono istanza, ricevuta e data effettiva.")
    if result["stato"] in {"accordo", "mancato_accordo"}:
        if not result["verbale_documento"] or not result["data_chiusura"]:
            raise ValueError("La conclusione richiede verbale e data effettiva.")
        if result["stato"] == "accordo" and not result["accordo_documento"]:
            raise ValueError("Collega l'accordo sottoscritto prima di registrare l'esito.")
    if result["data_deposito"] and result["data_chiusura"] and result["data_chiusura"] < result["data_deposito"]:
        raise ValueError("La chiusura non può precedere il deposito della domanda.")
    return result


class MediazioneProcedimentiRepository:
    def __init__(self, studio_db):
        if studio_db is None:
            raise RuntimeError("Archivio SQL dello studio non disponibile: nessun salvataggio su JSON storico.")
        self.db = studio_db
        if not getattr(studio_db, "_mediazione_schema_ready", False):
            schema = (Path(__file__).with_name("sql") / "20260905_mediazione_procedimenti.sql").read_text(encoding="utf-8")
            studio_db.conn.execute("BEGIN")
            for statement in schema.split(";"):
                if statement.strip():
                    studio_db.conn.execute(statement)
            studio_db.conn.execute("COMMIT")
            studio_db._mediazione_schema_ready = True

    @property
    def source_of_truth(self):
        return getattr(self.db, "backend_kind", "sqlite")

    def lista(self, fascicolo_id):
        rows = self.db.conn.execute("SELECT * FROM mediazione_procedimenti WHERE fascicolo_id=? ORDER BY creato_il", (fascicolo_id,)).fetchall()
        return [dict(json.loads(row["dati_json"]), id=row["id"], versione=row["versione"],
                     creato_il=row["creato_il"], modificato_il=row["modificato_il"]) for row in rows]

    def salva(self, fascicolo_id, identifier, versione, payload, actor):
        identifier = identifier or uuid4().hex
        now = datetime.now(ZoneInfo("Europe/Rome")).isoformat()
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        conn = self.db.conn
        conn.execute("BEGIN")
        try:
            if versione == 0:
                conn.execute("INSERT INTO mediazione_procedimenti VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (identifier, fascicolo_id, 1, payload["stato"], raw, now, now))
            else:
                updated = conn.execute(
                    "UPDATE mediazione_procedimenti SET versione=versione+1, stato=?, dati_json=?, modificato_il=? "
                    "WHERE id=? AND fascicolo_id=? AND versione=? RETURNING versione",
                    (payload["stato"], raw, now, identifier, fascicolo_id, versione),
                ).fetchone()
                if not updated:
                    raise ValueError("Il procedimento è stato aggiornato altrove: ricarica prima di salvare.")
            conn.execute("INSERT INTO mediazione_procedimenti_audit VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (uuid4().hex, identifier, versione + 1, actor, "salvataggio", now, hashlib.sha256(raw.encode()).hexdigest()))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return identifier

    def audit(self, fascicolo_id):
        rows = self.db.conn.execute(
            "SELECT a.* FROM mediazione_procedimenti_audit a JOIN mediazione_procedimenti p "
            "ON a.procedimento_id=p.id WHERE p.fascicolo_id=? ORDER BY a.timestamp DESC LIMIT 100",
            (fascicolo_id,),
        ).fetchall()
        return [dict(row) for row in rows]
