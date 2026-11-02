"""Messaggi in errore e stati PCT: l'avvocato legge un motivo in italiano, mai un codice o un'eccezione."""

from __future__ import annotations

from web.services.react_email_bridge import _pct_status_label
from web.services.react_messaggi_bridge import _readable_error


def test_eccezione_python_diventa_motivo_operativo():
    raw = "('a float is required', <object object at 0x7010a2c886a0>, <class 'object'>)"
    testo = _readable_error(raw, "FALLITO", "EMAIL")

    assert "object" not in testo
    assert testo.startswith("Invio non riuscito")
    assert "Email" in testo


def test_configurazione_mancante_indica_le_impostazioni():
    testo = _readable_error("'NoneType' object has no attribute 'email'", "FALLITO", "EMAIL")

    assert "NoneType" not in testo
    assert "configurazione del canale Email" in testo


def test_motivo_italiano_resta_e_motivo_assente_e_dichiarato():
    assert _readable_error("Casella del destinatario piena.", "FALLITO", "EMAIL") == "Casella del destinatario piena."
    assert _readable_error("", "FALLITO", "SMS").startswith("Motivo non registrato")
    assert _readable_error("", "INVIATO", "EMAIL") == ""


def test_stati_pct_in_italiano():
    assert _pct_status_label("ACCETTATO_PEC") == "Accettazione PEC"
    assert _pct_status_label("RIFIUTATO_CANCELLERIA") == "Rifiutato dalla cancelleria"
    assert _pct_status_label("NUOVO_STATO") == "Nuovo stato"
