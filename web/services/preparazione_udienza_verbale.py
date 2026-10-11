"""Collegamento del verbale alla preparazione, nei documenti SQL del fascicolo."""
from urllib.parse import quote


def marker(session_id):
    return "preparazione-verbale:" + session_id


def source(session_id, fascicolo_id):
    from uuid import UUID
    from web.helpers import get_wizard_pro
    try:
        key = str(UUID(session_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Preparazione non valida.") from exc
    manager = get_wizard_pro()
    if not getattr(manager, "write_protocol", {}).get("persistentCommands"):
        raise ValueError("La preparazione richiede l’archivio SQL confermato.")
    session = manager.carica(key)
    if session is None or session.id_fascicolo != fascicolo_id or getattr(session, "reference_issue", ""):
        raise ValueError("Preparazione non disponibile in questo fascicolo.")
    return session


def linked_document(session_id, fascicolo_id, documents):
    linked = [doc for doc in documents if marker(session_id) in (doc.tags or [])]
    if len(linked) > 1:
        return {"href": "", "message": "Più verbali collegati: verifica i documenti del fascicolo prima di proseguire."}
    if not linked:
        return {"href": "", "message": ""}
    doc = linked[0]
    return {"documentId": doc.id, "href": f"/fascicoli/{quote(fascicolo_id)}/documenti/{quote(doc.id)}/editor", "message": ""}


def validate_content(session, matter, title, html):
    from pct.controllo_studio.fonti import rif_fascicolo
    from web.helpers import get_agenda
    def escape(text):
        replacements = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}
        return ''.join(replacements.get(char, char) for char in str(text or ''))
    text = str(session.verbale_preparazione or '')
    if not text.strip():
        raise ValueError("Salva la bozza del verbale prima di creare il documento.")
    court = str(getattr(matter, 'tribunale', '') or '')
    if not court and session.id_appuntamento:
        appointment = get_agenda().get(session.id_appuntamento)
        court = str(getattr(appointment, 'tribunale', '') or '')
    expected = '<h1>Preparazione del verbale di udienza</h1>'
    expected += f'<p>{escape(rif_fascicolo(matter).get("etichetta", ""))}</p><p>{escape(court)}</p>'
    expected += ''.join(f'<p>{escape(line) or "<br>"}</p>' for line in text.replace('\r\n', '\n').split('\n'))
    if title != f'Preparazione verbale udienza {session.id}'[:100] or html != expected:
        raise ValueError("La bozza salvata è cambiata. Riapri la preparazione prima di creare il documento.")
