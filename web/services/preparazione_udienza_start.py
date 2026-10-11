"""Avvio SQL puntuale con checklist nativa e ricevuta ripetibile."""
from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from pct.agenda import Appuntamento, StatoAppuntamento, TipoAppuntamento
from pct import agenda_sql_writer
from pct.fascicoli import GestioneFascicoli
from pct.udienze.delivery import _AgendaSnapshot, _FascicoloSnapshot, _rows
from pct.udienze.repository import PreparazioneConflict, PreparazioneRejected
from pct.wizard_pro import SessioneWizardPro


class _InitialSession:
    """Il costruttore nativo consegna la sessione senza scrivere un archivio."""
    def lista(self):
        return []

    def lista_per_fascicolo(self, key):
        return []

    def salva(self, session):
        self.session = session


def start_command(repository, *, fascicolo_id, appuntamento_id, command_key, avvocato, titolo=""):
    if not isinstance(fascicolo_id, str) or not fascicolo_id.strip():
        raise ValueError("Scegli il fascicolo dell'udienza.")
    if not isinstance(appuntamento_id, str) or not isinstance(avvocato, str):
        raise ValueError("Contesto dell'avvio non valido.")
    intent = {"id_fascicolo": fascicolo_id, "id_appuntamento": appuntamento_id}
    if titolo:
        if not isinstance(titolo, str) or len(titolo) > 300:
            raise ValueError("Titolo della preparazione non valido o troppo lungo.")
        intent["titolo"] = titolo
    # La risposta persa deve riaprire la stessa ricevuta anche dopo eliminazione.
    prior = repository.db.conn.execute(
        "SELECT session_key FROM preparazioni_commands WHERE tenant_key=? AND command_key=?",
        (repository.tenant, command_key)).fetchone()
    existing = [item for item in repository.list() if
        (item["record"]["id_appuntamento"] == appuntamento_id if appuntamento_id else
         item["record"]["id_fascicolo"] == fascicolo_id and not item["record"]["id_appuntamento"]
         and item["record"]["stato"] == "in_corso")]
    if len(existing) > 1:
        raise PreparazioneConflict("Più preparazioni corrispondenti: nessuna copia eliminata.")
    key = (prior[0] if prior else existing[0]["record"]["id"] if existing else
           str(uuid5(NAMESPACE_URL, f"iusentra:preparazione:{repository.tenant}:{command_key}")))
    initial = SessioneWizardPro.nuova(fascicolo_id, "Preparazione udienza", id_appuntamento=appuntamento_id,
                                     avvocato=avvocato)
    initial.id = key

    def prepare(conn, session, values):
        from web.services.preparazione_udienza_elenco import avvia
        row = conn.execute("SELECT * FROM fascicoli WHERE id=?", (fascicolo_id,)).fetchone()
        if row is None:
            raise ValueError("Fascicolo della preparazione non presente nello studio.")
        fascicolo = GestioneFascicoli._row_to_fascicolo(dict(row))
        if fascicolo is None or fascicolo.id != fascicolo_id:
            raise ValueError("Identità SQL del fascicolo discordante.")
        _, _, appointments = _rows(conn, "appuntamenti", agenda_sql_writer, "id=?", (appuntamento_id,), Appuntamento)
        appointment = appointments.get(appuntamento_id)
        if appuntamento_id and (appointment is None or appointment.tipo != TipoAppuntamento.UDIENZA
                or appointment.stato in {StatoAppuntamento.ANNULLATO, StatoAppuntamento.RINVIATO}):
            raise ValueError("Udienza mancante, annullata o rinviata: avvio non confermato.")
        if appointment:
            from web.services.preparazione_udienza_associazione import verifica_collegamento_esplicito
            verifica_collegamento_esplicito(appointment, fascicolo)
        prepared = avvia(agenda=_AgendaSnapshot(appointments), fascicoli=_FascicoloSnapshot(fascicolo),
            preparazioni=_InitialSession(), id_appuntamento=appuntamento_id, id_fascicolo=fascicolo_id, avvocato=avvocato)
        prepared.id = session.id
        if titolo:
            prepared.titolo = titolo
        session.__dict__.update(prepared.__dict__)
        return {"kind": "avvio", "status": "confirmed"}

    try:
        return repository.execute(key, "avvio", intent, command_key=command_key, expected_revision=0,
                                  initial_record=initial.to_dict(), apply=prepare)
    except PreparazioneRejected:
        raise
    except (PreparazioneConflict, ValueError) as exc:
        receipt = repository.reject(key, "avvio", intent, command_key=command_key, expected_revision=0,
            code="conflict" if isinstance(exc, PreparazioneConflict) else "validation", message=str(exc))
        if receipt.get("status") != "rejected":
            return receipt
        raise PreparazioneRejected(receipt) from exc
