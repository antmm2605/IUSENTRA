"""Esito governato: motori nativi su snapshot, nella transazione del comando.

Nessun costruttore apre un archivio o un file; la persistenza avviene soltanto
dopo che tutte le regole del comando primario hanno restituito il risultato.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date

from pct.agenda import Agenda, Appuntamento, StatoAppuntamento, TipoAppuntamento
from pct import agenda_sql_writer, scadenziario_sql_writer
from pct.fascicoli import GestioneFascicoli
from pct.scadenziario import GestioneScadenziario, Scadenza, StatoTermine, TipoTermine
from pct.udienze.repository import PreparazioneConflict


class _AgendaSnapshot(Agenda):
    def __init__(self, items):
        self._appuntamenti = items

    def _salva(self):
        # Il chiamante conferma tutti gli effetti insieme con lo scrittore SQL.
        pass


class _ScadenzeSnapshot(GestioneScadenziario):
    def __init__(self, items):
        self._scadenze = items

    def _salva(self):
        pass


class _FascicoloSnapshot(GestioneFascicoli):
    def __init__(self, item):
        self._fascicoli = {item.id: item}

    def get(self, key):
        return self._fascicoli.get(key)

    def aggiungi_attivita(self, *args, **kwargs):
        return super().aggiungi_attivita(*args, **kwargs, persist=False)

    def aggiorna(self, key, **fields):
        # Il comando esito modifica soltanto questa data; nessuna riconciliazione
        # documentale o modifica dei flussi deposito/firma viene richiamata.
        if set(fields) != {"data_prossima_udienza"}:
            raise ValueError("Campo del fascicolo non previsto nell'esito.")
        item = self._get_o_errore(key)
        item.data_prossima_udienza = fields["data_prossima_udienza"]
        return item


def _rows(conn, table, writer, condition, args, model):
    columns = writer.COLUMNS
    original, encoded, items = {}, {}, {}
    for row in conn.execute(f"SELECT {','.join(columns)} FROM {table} WHERE {condition}", args).fetchall():
        raw = dict(row) if hasattr(row, "keys") else dict(zip(columns, row, strict=True))
        payload = json.loads(raw["dati_json"])
        item = model.from_dict(payload)
        if item.id != raw["id"]:
            raise ValueError("Identità SQL del seguito dell'udienza discordante.")
        for column, expected in zip(columns, writer.row_values(item), strict=True):
            if column in {"dati_json", "descrizione"}:
                continue
            actual = raw[column]
            if column in {"giorni_preavviso", "avvisi_inviati"}:
                actual, expected = json.loads(actual or "[]"), json.loads(expected)
            if actual != expected and not (actual in (None, "") and expected in (None, "")):
                raise PreparazioneConflict("Colonne SQL e contenuto del seguito discordanti: nessuna decisione sovrascritta.")
        original[item.id], items[item.id] = raw, item
        encoded[item.id] = json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return original, encoded, items


def _validated_intent(intent):
    if not isinstance(intent, dict) or set(intent) - {"esito", "rinvioData", "rinvioOra", "noteVerbale", "azioni", "termini"}:
        raise ValueError("Campi dell'esito non previsti.")
    values = copy.deepcopy(intent)
    for key, limit in (("esito", 40), ("rinvioData", 10), ("rinvioOra", 5), ("noteVerbale", 4000), ("azioni", 4000)):
        value = values.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("Campo dell'esito non valido o troppo lungo.")
    if values.get("esito") == "rinvio":
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", values.get("rinvioData", "")):
            raise ValueError("Indica la data del rinvio.")
        if values.get("rinvioOra") and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", values["rinvioOra"]):
            raise ValueError("Orario del rinvio non valido.")
    terms = values.get("termini", [])
    if not isinstance(terms, list) or len(terms) > 10:
        raise ValueError("L'esito può contenere al massimo dieci termini: nessuna riga scartata.")
    for row in terms:
        if not isinstance(row, dict) or set(row) - {"descrizione", "data", "perentorio", "id_scadenza"}:
            raise ValueError("Campi del termine non previsti.")
        if (not isinstance(row.get("descrizione"), str) or not row["descrizione"].strip()
                or len(row["descrizione"]) > 200 or not isinstance(row.get("data"), str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["data"])
                or type(row.get("perentorio", False)) is not bool
                or not isinstance(row.get("id_scadenza", ""), str)):
            raise ValueError("Termine incompleto o non valido: nessuna riga scartata.")
        date.fromisoformat(row["data"])
        row["descrizione"] = row["descrizione"].strip()
        row.setdefault("perentorio", False)
    values["termini"] = terms
    return values


def _bind_terms(values, session, deadlines):
    """Riconosce il fatto solo nel seguito della stessa preparazione."""
    prior = session.termini_assegnati
    used = set()
    for row in values["termini"]:
        key = row.get("id_scadenza", "")
        matches = [p for p in prior if (p.get("id_scadenza") == key if key else
            (p.get("descrizione"), p.get("data"), bool(p.get("perentorio"))) ==
            (row["descrizione"], row["data"], row["perentorio"]))]
        if (key and len(matches) != 1) or len(matches) > 1:
            raise ValueError("Collegamento del termine ambiguo o estraneo alla preparazione.")
        if matches:
            previous = matches[0]
            key = previous.get("id_scadenza", "")
            item = deadlines.get(key)
            if (item is None or item.id_fascicolo != session.id_fascicolo or item.tipo != TipoTermine.ADEMPIMENTO
                    or (item.titolo, item.data_scadenza, bool(item.perentorio)) !=
                    (previous["descrizione"], previous["data"], bool(previous.get("perentorio")))):
                raise PreparazioneConflict("Termine modificato o mancante: decisione corrente preservata.")
            if (row["descrizione"], row["data"], row["perentorio"]) != (item.titolo, item.data_scadenza, bool(item.perentorio)):
                if item.stato not in {StatoTermine.BOZZA, StatoTermine.APERTO}:
                    raise PreparazioneConflict("Termine già lavorato: modificarlo nello Scadenziario.")
                _ScadenzeSnapshot(deadlines).aggiorna(key, titolo=row["descrizione"], data_scadenza=row["data"], perentorio=row["perentorio"])
            row["id_scadenza"] = key
        signature = key or (row["descrizione"], row["data"], row["perentorio"])
        if signature in used:
            raise ValueError("Lo stesso termine compare due volte nell'esito.")
        used.add(signature)
    if any(p.get("id_scadenza") and p["id_scadenza"] not in used for p in prior):
        raise ValueError("Un termine già registrato non può sparire: gestirne lo stato nello Scadenziario.")


def deliver_outcome(conn, session, intent, *, tenant, actor, today):
    """Callback del repository: conferma anche Agenda, termini e attività."""
    from web.services.preparazione_udienza_runtime import ESITI, _ESITO_ATTIVITA, registra_esito
    from pct.fascicoli import EsitoAttivita, TipoAttivita

    if not tenant or not actor or not isinstance(today, date):
        raise ValueError("Studio, operatore o data della consegna assenti.")
    values = _validated_intent(intent)
    columns = ("id", "stato", "attivita_json", "dati_json", "modificato_il")
    row = conn.execute(f"SELECT {','.join(columns)} FROM fascicoli WHERE id=?", (session.id_fascicolo,)).fetchone()
    if row is None:
        raise ValueError("Fascicolo della preparazione non presente nello studio.")
    raw = dict(row) if hasattr(row, "keys") else dict(zip(columns, row, strict=True))
    fascicolo = GestioneFascicoli._row_to_fascicolo(raw)
    if fascicolo is None or fascicolo.id != session.id_fascicolo or fascicolo.stato.value != raw["stato"]:
        raise ValueError("Identità o stato del fascicolo SQL discordante.")
    agenda_rows, agenda_models, appointments = _rows(conn, "appuntamenti", agenda_sql_writer,
        "id IN (?,?)", (session.id_appuntamento, session.id_appuntamento_rinvio), Appuntamento)
    if session.id_appuntamento and session.id_appuntamento not in appointments:
        raise ValueError("Udienza della preparazione mancante: nessun effetto registrato.")
    if session.id_appuntamento:
        from web.services.preparazione_udienza_associazione import verifica_collegamento_esplicito
        verifica_collegamento_esplicito(appointments[session.id_appuntamento], fascicolo)
    deadline_rows, deadline_models, deadlines = _rows(conn, "scadenze", scadenziario_sql_writer,
        "id_fascicolo=?", (session.id_fascicolo,), Scadenza)
    _bind_terms(values, session, deadlines)
    agenda, scadenze, fascicoli = _AgendaSnapshot(appointments), _ScadenzeSnapshot(deadlines), _FascicoloSnapshot(fascicolo)
    if session.id_appuntamento_rinvio:
        postponed = appointments.get(session.id_appuntamento_rinvio)
        previous_date = f"{session.esito_rinvio_data}T{session.esito_rinvio_ora or '09:00'}:00"
        if (postponed is None or postponed.tipo != TipoAppuntamento.UDIENZA or postponed.data_ora != previous_date
                or postponed.stato in {StatoAppuntamento.COMPLETATO, StatoAppuntamento.ANNULLATO}):
            raise PreparazioneConflict("Udienza di rinvio modificata o mancante: aggiornamento da verificare.")
        if values.get("esito") != "rinvio":
            raise PreparazioneConflict("Il rinvio già registrato va gestito in Agenda prima di cambiare la natura dell'esito.")
        from web.services.preparazione_udienza_associazione import verifica_collegamento_esplicito
        verifica_collegamento_esplicito(postponed, fascicolo)
        # Il seguito resta collegato anche quando si elimina la sola preparazione.
        postponed.id_fascicolo = fascicolo.id
        new_date = f"{values['rinvioData']}T{values.get('rinvioOra') or '09:00'}:00"
        if new_date != previous_date:
            if postponed.stato in {StatoAppuntamento.COMPLETATO, StatoAppuntamento.ANNULLATO}:
                raise PreparazioneConflict("Udienza di rinvio già lavorata: decisione corrente preservata.")
            agenda.modifica(postponed.id, data_ora=new_date)
    previous_activity = None
    if session.id_attivita_fascicolo:
        previous_activity = next((a for a in fascicolo.attivita if a.id == session.id_attivita_fascicolo), None)
        description = "\n".join(p for p in (f"Esito: {ESITI.get(session.esito, '')}.", session.esito_note_verbale, session.esito_azioni) if p)
        if (previous_activity is None or previous_activity.tipo != TipoAttivita.UDIENZA
                or previous_activity.id_appuntamento != session.id_appuntamento
                or previous_activity.note != f"[Preparazione udienza {session.id}]"
                or previous_activity.esito != EsitoAttivita(_ESITO_ATTIVITA.get(session.esito, "IN_ATTESA"))
                or previous_activity.descrizione != description):
            raise PreparazioneConflict("Nota d'udienza modificata o mancante: versione corrente preservata.")
    created = registra_esito(session, values, agenda=agenda, fascicoli=fascicoli, scadenziario=scadenze, utente=actor, oggi=today)
    if previous_activity is not None:
        description = "\n".join(p for p in (f"Esito: {ESITI[session.esito]}.", session.esito_note_verbale, session.esito_azioni) if p)
        professional = session.avvocato if previous_activity.avvocato == actor and session.avvocato else previous_activity.avvocato
        fascicoli.aggiorna_attivita(fascicolo.id, previous_activity.id, persist=False, descrizione=description,
            esito=EsitoAttivita(_ESITO_ATTIVITA.get(session.esito, "IN_ATTESA")), avvocato=professional)
    agenda_sql_writer.write_changes(conn, original_rows=agenda_rows, original_models=agenda_models, current=appointments)
    scadenziario_sql_writer.write_changes(conn, original_rows=deadline_rows, original_models=deadline_models, current=deadlines)
    payload = json.loads(raw["dati_json"])
    updated = fascicolo.to_dict()
    for key in ("stato", "avanzamento", "data_prima_udienza", "data_prossima_udienza", "modificato_il"):
        payload[key] = updated[key]
    condition = " AND ".join(f"{key} IS NOT DISTINCT FROM ?" for key in columns)
    result = conn.execute(f"UPDATE fascicoli SET stato=?,attivita_json=?,dati_json=?,modificato_il=? WHERE {condition} RETURNING id",
        (fascicolo.stato.value, json.dumps(updated["attivita"], ensure_ascii=False), json.dumps(payload, ensure_ascii=False),
         fascicolo.modificato_il, *(raw[key] for key in columns))).fetchone()
    if result is None:
        raise PreparazioneConflict("Fascicolo cambiato durante la consegna: nessun seguito confermato.")
    return {"kind": "esito", "created": created, "fascicolo_id": fascicolo.id,
            "rinvio_id": session.id_appuntamento_rinvio, "activity_id": session.id_attivita_fascicolo,
            "deadline_ids": [term["id_scadenza"] for term in session.termini_assegnati]}
