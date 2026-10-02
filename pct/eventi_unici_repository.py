"""Correlazioni persistenti: le fonti rimangono, l'evento operativo è unico.

Le correlazioni si scrivono nella transazione che rettifica le proiezioni.
La consultazione non crea tabelle, non modifica stati e non usa mirror JSON.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class EventiUniciRepository:
    def __init__(self, database, tenant_id):
        if database is None or not tenant_id:
            raise RuntimeError("Archivio SQL degli eventi non disponibile.")
        self.database, self.tenant_id = database, str(tenant_id)

    def crea_schema(self):
        suffix = "_postgres" if getattr(self.database, "backend_kind", "") == "postgresql" else ""
        sql = (Path(__file__).parent / "sql" / f"20261001_eventi_unici{suffix}.sql").read_text(encoding="utf-8")
        def create(conn, _):
            for statement in sql.split(";"):
                if statement.strip():
                    conn.execute(statement)
        self.database.salva_tabella("eventi_unici_correlazioni", [None], create, delete_all=False)

    def presente(self):
        if getattr(self.database, "backend_kind", "") == "postgresql":
            return bool(self.database.conn.execute("SELECT to_regclass(?) AS nome", ("eventi_unici_correlazioni",)).fetchone()["nome"])
        return bool(self.database.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", ("eventi_unici_correlazioni",)).fetchone())

    def risolvi(self, area, origine_id):
        if area not in {"agenda", "scadenze", "notifiche"} or not origine_id:
            raise ValueError("Riferimento all’evento non valido.")
        if not self.presente():
            return None
        row = self.database.conn.execute(
            "SELECT * FROM eventi_unici_correlazioni WHERE tenant_id=? AND area=? AND origine_id=?",
            (self.tenant_id, area, origine_id)).fetchone()
        return dict(row) if row else None

    def risolvi_verificato(self, area, origine_id, *, fascicolo_id=""):
        """Riusa soltanto una correlazione integra con fonte e destinazione correnti.

        Una correlazione non più valida richiede riconciliazione esplicita:
        non autorizza il vecchio produttore a ricreare l'evento precedente.
        """
        binding = self.risolvi(area, origine_id)
        if binding is None:
            return None
        fid = binding["fascicolo_id"]
        if fascicolo_id and fid != fascicolo_id:
            raise ValueError("La correlazione dell'evento appartiene a un altro fascicolo.")
        evidence = json.loads(binding["evidenza_json"])
        audit = self.database.conn.execute(
            "SELECT evidenza_json,evidenza_sha256 FROM eventi_unici_audit WHERE id=? AND tenant_id=? AND fascicolo_id=?",
            (binding["operazione_id"], self.tenant_id, fid)).fetchone()
        if not audit or hashlib.sha256(audit["evidenza_json"].encode("utf-8")).hexdigest() != audit["evidenza_sha256"]:
            raise ValueError("La prova della riunione non è integra: evento da verificare.")
        if json.loads(audit["evidenza_json"]).get("piano") != evidence:
            raise ValueError("La correlazione non coincide con il piano registrato nell'audit.")
        source = self.database.conn.execute(
            "SELECT documenti_json,numero_rg,anno_rg,nome_cliente FROM fascicoli WHERE id=?", (fid,)).fetchone()
        documents = json.loads(source["documenti_json"] or "[]") if source else []
        document = next((d for d in documents if d.get("id") == evidence.get("documento_id") and not d.get("eliminato_il")), None)
        if not document or binding["prova_sha256"] not in {document.get("hash_sha256"), document.get("hash_contenuto_sha256")}:
            raise ValueError("La fonte dell'evento riunito è cambiata: nuova verifica necessaria.")
        if area not in {"agenda", "scadenze"}:
            raise ValueError("Questo tipo di correlazione richiede il suo verificatore dedicato.")
        table = "appuntamenti" if area == "agenda" else "scadenze"
        target = self.database.conn.execute("SELECT * FROM " + table + " WHERE id=?", (binding["canonico_id"],)).fetchone()
        payload = json.loads(target["dati_json"] or "{}") if target else {}
        if not target or payload.get("id") != binding["canonico_id"] or payload.get("stato") != target["stato"]:
            raise ValueError("La destinazione dell'evento riunito non è disponibile o non concorda con SQL.")
        if area == "agenda":
            expected_rg = f"RG {str(source['numero_rg'] or '').strip()}/{str(source['anno_rg'] or '').strip()}"
            normalize = lambda value: " ".join(str(value or "").split()).casefold()
            if payload.get("stato") not in {"PROGRAMMATO", "CONFERMATO"} or payload.get("procedimento") != expected_rg or normalize(payload.get("cliente")) != normalize(source["nome_cliente"]):
                raise ValueError("L'udienza riunita ha cambiato stato o identità: verifica necessaria.")
            if payload.get("data_ora") != target["data_ora"]:
                raise ValueError("L'orario dell'udienza non concorda con SQL.")
            expected_time = datetime.fromisoformat(evidence["data_ora"])
            if expected_time.tzinfo is not None:
                expected_time = expected_time.astimezone(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
            if payload["data_ora"] != expected_time.isoformat(timespec="seconds"):
                raise ValueError("L'orario dell'udienza è cambiato dopo la riunione: verifica necessaria.")
        elif payload.get("id_fascicolo") != fid or target["id_fascicolo"] != fid or payload.get("stato") not in {"APERTO", "SCADUTO"}:
            raise ValueError("La scadenza riunita ha cambiato stato o fascicolo: verifica necessaria.")
        elif payload.get("id_appuntamento") != evidence.get("canonico_id") or target["id_appuntamento"] != payload.get("id_appuntamento"):
            raise ValueError("La scadenza non è più collegata all'udienza verificata.")
        elif self.risolvi_verificato("agenda", origine_id + ":deadline", fascicolo_id=fid) is None:
            raise ValueError("Manca la correlazione della scadenza con l'udienza verificata.")
        return binding, payload

    def destinazione_verificata(self, area, canonico_id):
        if not self.presente():
            return False
        bindings = self.database.conn.execute(
            "SELECT origine_id FROM eventi_unici_correlazioni WHERE tenant_id=? AND area=? AND canonico_id=?",
            (self.tenant_id, area, canonico_id)).fetchall()
        for binding in bindings:
            self.risolvi_verificato(area, binding["origine_id"])
        return bool(bindings)

    def risolvi_evento_documentale(self, area, origine_id, *, fascicolo_id="", data_ora=""):
        """Anche una nuova chiave della stessa lettura deve ritrovare la prova.

        La chiave variabile non basta: coincidono documento, fascicolo, giorno,
        ora esatta e versione della fonte. Udienze diverse restano distinte.
        """
        exact = self.risolvi_verificato(area, origine_id, fascicolo_id=fascicolo_id)
        if exact is not None or not self.presente() or area not in {"agenda", "scadenze"}:
            return exact
        match = re.match(r"^PEC_AUDIT:docpresidio:([A-Za-z0-9-]+):([A-Za-z0-9-]+):udienza:(\d{4}-\d{2}-\d{2})(?::|$)", origine_id)
        if not match or not data_ora or (fascicolo_id and match[1] != fascicolo_id):
            return None
        try:
            proposed = datetime.fromisoformat(data_ora)
        except ValueError:
            return None
        if proposed.tzinfo is not None:
            proposed = proposed.astimezone(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
        if proposed.date().isoformat() != match[3] or "T" not in data_ora:
            return None
        prefix = f"PEC_AUDIT:docpresidio:{match[1]}:{match[2]}:udienza:{match[3]}"
        bindings = self.database.conn.execute(
            "SELECT origine_id,evidenza_json FROM eventi_unici_correlazioni WHERE tenant_id=? AND fascicolo_id=? AND area=? AND origine_id LIKE ?",
            (self.tenant_id, match[1], area, prefix + "%")).fetchall()
        matches = []
        for binding in bindings:
            evidence = json.loads(binding["evidenza_json"])
            expected = datetime.fromisoformat(evidence["data_ora"])
            if expected.tzinfo is not None:
                expected = expected.astimezone(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
            if expected != proposed or evidence.get("documento_id") != match[2]:
                continue
            matches.append(self.risolvi_verificato(area, binding["origine_id"], fascicolo_id=match[1]))
        if len({m[0]["canonico_id"] for m in matches}) > 1:
            raise ValueError("Più eventi verificati coincidono con la lettura: riconciliazione necessaria.")
        return matches[0] if matches else None

    def collega(self, conn, *, area, origine_id, canonico_id, fascicolo_id, prova_sha256, evidenza, operazione_id, timestamp):
        if area not in {"agenda", "scadenze", "notifiche"} or not all((origine_id, canonico_id, fascicolo_id, operazione_id, timestamp)):
            raise ValueError("Correlazione incompleta: nessuna modifica eseguita.")
        if not re.fullmatch(r"[0-9a-f]{64}", prova_sha256 or "") or not isinstance(evidenza, dict):
            raise ValueError("Prova documentale della correlazione non valida.")
        existing = conn.execute("SELECT canonico_id,prova_sha256,fascicolo_id,evidenza_json FROM eventi_unici_correlazioni WHERE tenant_id=? AND area=? AND origine_id=?",
                                (self.tenant_id, area, origine_id)).fetchone()
        if existing and (existing["canonico_id"] != canonico_id or existing["prova_sha256"] != prova_sha256 or existing["fascicolo_id"] != fascicolo_id or existing["evidenza_json"] != canonical_json(evidenza)):
            raise ValueError("La fonte ha già una correlazione differente da verificare.")
        conn.execute("INSERT INTO eventi_unici_correlazioni (tenant_id,area,origine_id,canonico_id,fascicolo_id,prova_sha256,evidenza_json,operazione_id,creato_il) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,area,origine_id) DO NOTHING",
                     (self.tenant_id, area, origine_id, canonico_id, fascicolo_id, prova_sha256, canonical_json(evidenza), operazione_id, timestamp))

    def audit(self, conn, *, operazione_id, fascicolo_id, attore, evidenza, timestamp):
        text = canonical_json(evidenza)
        conn.execute("INSERT INTO eventi_unici_audit (id,tenant_id,fascicolo_id,attore,evidenza_json,evidenza_sha256,creato_il) VALUES (?,?,?,?,?,?,?)",
                     (operazione_id, self.tenant_id, fascicolo_id, attore, text, hashlib.sha256(text.encode("utf-8")).hexdigest(), timestamp))
