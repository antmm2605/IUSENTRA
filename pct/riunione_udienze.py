"""Rettifica atomica di proiezioni automatiche, con prova e confronto versione.

Il piano proviene dal verificatore: nessuna equivalenza per il solo giorno.
Ogni riga sorgente resta nell'archivio e l'operazione registra prima/dopo.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from .eventi_unici_repository import EventiUniciRepository, canonical_json


def impronta_riga(payload):
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verifica_piano_archivio(registro, tenant_id, piano):
    from pct.archivio_letture import fatti_canonici

    if registro is None:
        raise ValueError("Archivio delle prove obbligatorio per riunire le udienze.")
    fid = piano["fascicolo_id"]
    current = []
    inventory = {}
    for fact in registro.fatti(tenant_id, fid, verifiche=None):
        key = (fact.tipo, fact.oggetto_id)
        if key not in inventory:
            inventory[key] = registro.oggetto(tenant_id, fid, *key)
        obj = inventory[key]
        if obj and obj.presente and fact.fascicolo_id == fid and fact.sha256 and fact.sha256 == obj.sha256 and fact.verifica in {"verificata", "corretta", "plausibile"}:
            current.append(fact)
    source = next((f for f in current if f.id == piano["fatto_id"]), None)
    if not source or source.verifica not in {"verificata", "corretta"} or source.tipo != "documento" or source.oggetto_id != piano["documento_id"] or source.sha256 != piano["prova_sha256"] or source.campo != "udienza":
        raise ValueError("Il piano non coincide con una prova corrente e verificata nell'archivio.")
    normalize = lambda value: " ".join(str(value or "").split()).casefold()
    if normalize(piano["estratto"]) not in normalize(source.contesto):
        raise ValueError("L'estratto del piano non coincide con la prova registrata.")
    expected = datetime.fromisoformat(piano["data_ora"])
    actual = datetime.fromisoformat(source.valore)
    if expected != actual:
        raise ValueError("Il piano indica un orario diverso dalla prova registrata.")
    canonical = next((f for f in fatti_canonici(current) if f.id == piano["canonico_fatto_id"]), None)
    if canonical is None or canonical.campo != "udienza" or datetime.fromisoformat(canonical.valore) != actual:
        raise ValueError("Il piano non coincide con l'evento canonico corrente.")
    members = [f for p in canonical.prove if p.get("codice") == "fonti_unite" for f in p.get("fonti", [])]
    if canonical.id != source.id and not any(f.get("fatto_id") == source.id and f.get("sha256") == source.sha256 for f in members):
        raise ValueError("La prova non è tra le fonti dell'evento canonico.")


def riunisci_udienza(database, tenant_id, piano, *, attore, registro):
    required = {"fascicolo_id", "documento_id", "prova_sha256", "fatto_id", "estratto", "data_ora",
                "canonico_id", "canonico_fatto_id", "duplicato_id", "canonico_impronta", "duplicato_impronta"}
    if not isinstance(piano, dict) or not required <= piano.keys() or any(not piano[k] for k in required) or not attore:
        raise ValueError("Piano di riunione incompleto.")
    if piano["canonico_id"] == piano["duplicato_id"]:
        raise ValueError("Le due registrazioni sono già la stessa udienza.")
    dt = datetime.fromisoformat(piano["data_ora"])
    if dt.tzinfo is not None:
        dt = dt.astimezone(ZoneInfo("Europe/Rome")).replace(tzinfo=None)
    expected_date = dt.isoformat(timespec="seconds")
    repo = EventiUniciRepository(database, tenant_id)
    repo.crea_schema()
    operation = "eventi-unici-" + uuid.uuid4().hex
    timestamp = datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds")
    result = {}

    def write(conn, _):
        verifica_piano_archivio(registro, tenant_id, piano)
        lock = " FOR UPDATE" if getattr(database, "backend_kind", "") == "postgresql" else ""
        source = conn.execute("SELECT documenti_json,attivita_json,numero_rg,anno_rg,nome_cliente,tribunale FROM fascicoli WHERE id=?" + lock, (piano["fascicolo_id"],)).fetchone()
        if not source:
            raise ValueError("Fascicolo non più disponibile.")
        documents = json.loads(source["documenti_json"] or "[]")
        document = next((d for d in documents if d.get("id") == piano["documento_id"] and not d.get("eliminato_il")), None)
        if not document or piano["prova_sha256"] not in {document.get("hash_sha256"), document.get("hash_contenuto_sha256")}:
            raise ValueError("La versione della fonte è cambiata. Nessuna riunione eseguita.")
        rows = conn.execute("SELECT * FROM appuntamenti WHERE id IN (?,?) ORDER BY id" + lock,
                            (piano["canonico_id"], piano["duplicato_id"])).fetchall()
        payloads = {row["id"]: json.loads(row["dati_json"] or "{}") for row in rows}
        if set(payloads) != {piano["canonico_id"], piano["duplicato_id"]}:
            raise ValueError("Una delle udienze non è più disponibile.")
        primary, duplicate = payloads[piano["canonico_id"]], payloads[piano["duplicato_id"]]
        previous_uid = str(duplicate.get("external_uid") or "")
        if duplicate.get("stato") == "ANNULLATO" and previous_uid:
            previous = repo.risolvi_verificato("agenda", previous_uid, fascicolo_id=piano["fascicolo_id"])
            if previous is not None:
                binding, _ = previous
                if binding["canonico_id"] != primary["id"] or json.loads(binding["evidenza_json"]) != piano:
                    raise ValueError("La precedente riunione non coincide con questo piano.")
                result.update(operazione_id=binding["operazione_id"], canonico_id=primary["id"],
                              duplicato_id=duplicate["id"], already_applied=True)
                return
        for row in rows:
            payload = payloads[row["id"]]
            for field in ("id", "stato", "data_ora", "note"):
                if str(row[field] or "") != str(payload.get(field) or ""):
                    raise ValueError("Colonne SQL e registrazione non concordano. Nessuna riunione eseguita.")
            expected_rg = f"RG {str(source['numero_rg'] or '').strip()}/{str(source['anno_rg'] or '').strip()}"
            if not source["numero_rg"] or not source["anno_rg"] or payload.get("procedimento") != expected_rg:
                raise ValueError("Le udienze non coincidono con il ruolo del fascicolo.")
            normalized = lambda value: " ".join(str(value or "").split()).casefold()
            if not source["nome_cliente"] or normalized(payload.get("cliente")) != normalized(source["nome_cliente"]):
                raise ValueError("Il cliente dell'udienza non coincide con il fascicolo.")
            if payload.get("tribunale") and source["tribunale"] and normalized(payload["tribunale"]) != normalized(source["tribunale"]):
                raise ValueError("L'ufficio dell'udienza non coincide con il fascicolo.")
        if impronta_riga(primary) != piano["canonico_impronta"] or impronta_riga(duplicate) != piano["duplicato_impronta"]:
            raise ValueError("Le registrazioni sono cambiate. Nessuna riunione eseguita.")
        if primary.get("data_ora") != expected_date or primary.get("stato") not in {"PROGRAMMATO", "CONFERMATO"}:
            raise ValueError("L'udienza principale non coincide con la fonte verificata.")
        if "ARCHIVIO_FATTO:" + piano["canonico_fatto_id"] not in str(primary.get("note") or "").splitlines():
            raise ValueError("Manca il collegamento all'evento canonico verificato.")
        uid = str(duplicate.get("external_uid") or "")
        marker = uid.removesuffix(":deadline")
        doc_prefix = f"PEC_AUDIT:docpresidio:{piano['fascicolo_id']}:{piano['documento_id']}:udienza:"
        if duplicate.get("stato") != "PROGRAMMATO" or duplicate.get("external_provider") != "pec_audit" or duplicate.get("external_profile_id") != "pec_scadenziario" or not uid.startswith(doc_prefix):
            raise ValueError("La registrazione sorgente non è una proposta automatica riconoscibile.")
        terms = conn.execute("SELECT * FROM scadenze WHERE id_appuntamento=?" + lock, (duplicate["id"],)).fetchall()
        term_payloads = []
        for row in terms:
            payload = json.loads(row["dati_json"] or "{}")
            for field in ("id", "stato", "id_fascicolo", "id_appuntamento", "note"):
                if str(row[field] or "") != str(payload.get(field) or ""):
                    raise ValueError("Colonne SQL e scadenza non concordano. Nessuna modifica parziale.")
            if row["id_fascicolo"] != piano["fascicolo_id"] or marker not in str(row["note"] or "") or row["stato"] not in {"APERTO", "SCADUTO"}:
                raise ValueError("Una scadenza collegata richiede verifica: nessuna modifica parziale.")
            term_payloads.append((row, payload))
        activities = json.loads(source["attivita_json"] or "[]")
        for item in activities:
            if item.get("id_appuntamento") == duplicate["id"] and (item.get("esito") != "IN_ATTESA" or item.get("id_documento") != piano["documento_id"] or item.get("avvocato")):
                raise ValueError("Un'attività collegata è già stata lavorata: nessuna modifica parziale.")
        evidence = {"piano": piano, "prima": payloads, "scadenze": [dict(r) for r, _ in term_payloads]}
        repo.collega(conn, area="agenda", origine_id=uid, canonico_id=primary["id"], fascicolo_id=piano["fascicolo_id"], prova_sha256=piano["prova_sha256"], evidenza=piano, operazione_id=operation, timestamp=timestamp)
        duplicate.update(stato="ANNULLATO", modificato_il=timestamp,
                         note=(str(duplicate.get("note") or "") + f"\nRegistrazione riunita all’udienza {primary['id']} sulla fonte verificata. Operazione {operation}.").strip())
        conn.execute("UPDATE appuntamenti SET stato=?,note=?,dati_json=? WHERE id=?", (duplicate["stato"], duplicate["note"], canonical_json(duplicate), duplicate["id"]))
        for row, payload in term_payloads:
            payload.update(id_appuntamento=primary["id"], hearing_time=dt.strftime("%H:%M"), operational_due_at=expected_date,
                           note=(str(row["note"] or "") + f"\nOrario rettificato dalla fonte verificata; udienza collegata {primary['id']}. Operazione {operation}.").strip())
            conn.execute("UPDATE scadenze SET id_appuntamento=?,note=?,dati_json=? WHERE id=?", (primary["id"], payload["note"], canonical_json(payload), row["id"]))
            repo.collega(conn, area="scadenze", origine_id=marker, canonico_id=row["id"], fascicolo_id=piano["fascicolo_id"], prova_sha256=piano["prova_sha256"], evidenza=piano, operazione_id=operation, timestamp=timestamp)
        for item in activities:
            if item.get("id_appuntamento") == duplicate["id"]:
                item.update(id_appuntamento=primary["id"], note=(str(item.get("note") or "") + f"\nUdienza riunita con orario verificato {dt.strftime('%H:%M')}. Operazione {operation}.").strip())
        conn.execute("UPDATE fascicoli SET attivita_json=? WHERE id=?", (canonical_json(activities), piano["fascicolo_id"]))
        evidence["dopo"] = {"duplicato": duplicate, "canonico_id": primary["id"], "scadenze": [p for _, p in term_payloads], "attivita": activities}
        repo.audit(conn, operazione_id=operation, fascicolo_id=piano["fascicolo_id"], attore=attore, evidenza=evidence, timestamp=timestamp)
        result.update(operazione_id=operation, canonico_id=primary["id"], duplicato_id=duplicate["id"], scadenze=len(terms))

    database.salva_tabella("eventi_unici_correlazioni", [None], write, delete_all=False)
    return result
