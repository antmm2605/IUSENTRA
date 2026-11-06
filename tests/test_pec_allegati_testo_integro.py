"""Testo degli allegati PEC non tagliato (06/11/2026): il dispositivo e la data in calce delle sentenze lunghe stanno
oltre i 20.000 caratteri (sentenza Alessi, Tribunale di Velletri, 35.000 caratteri)."""

from __future__ import annotations

from email.message import EmailMessage

from pct.pec_pipeline import PecAuditRepository, _attachment_ocr_text, tagliato_dal_vecchio_limite

CODA = " P.Q.M. condanna la parte convenuta al pagamento delle spese processuali. Velletri, 7 ottobre 2026 Il giudice"


def _mime(corpo_allegato: str) -> bytes:
    messaggio = EmailMessage()
    messaggio["From"] = "tribunale.velletri@civile.ptel.giustiziacert.it"
    messaggio["To"] = "studio@example.test"
    messaggio["Subject"] = "POSTA CERTIFICATA: COMUNICAZIONE 2539/2025/LAV"
    messaggio["Message-ID"] = "<sentenza-lunga@example.test>"
    messaggio["Date"] = "Thu, 08 Oct 2026 15:19:56 +0200"
    messaggio.set_content("Comunicazione di cancelleria")
    messaggio.add_attachment(corpo_allegato.encode(), maintype="text", subtype="plain", filename="sentenza.txt")
    return messaggio.as_bytes()


def test_il_testo_lungo_resta_intero_fino_al_dispositivo():
    testo = "motivazione " * 3000 + CODA  # oltre 36.000 caratteri
    assert _attachment_ocr_text({"ocr_text": testo}).endswith("Il giudice")


def test_gli_allegati_tagliati_dal_vecchio_limite_si_rileggono_e_gli_integri_no(tmp_path):
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="default")
    lungo = "motivazione " * 3000 + CODA
    messaggio = repo.ingest_mime(_mime(lungo), account_email="studio@example.test", folder="INBOX", imap_uid="1")
    repo.run_pending_jobs(limit=10, actor="pytest")
    with repo.connect() as conn:
        conn.execute("UPDATE pec_attachments SET ocr_text=? WHERE message_id=? AND filename='sentenza.txt'",
                     (lungo[:19999] + "…", messaggio["id"]))
    assert repo.rileggi_allegati_tagliati(prova=True)["messaggi"] == 1
    esito = repo.rileggi_allegati_tagliati(actor="pytest")
    assert esito["riletti"] == 1 and not esito["errori"]
    with repo.connect() as conn:
        testo = conn.execute("SELECT ocr_text FROM pec_attachments WHERE message_id=? AND filename='sentenza.txt'",
                             (messaggio["id"],)).fetchone()[0]
    assert testo.endswith("Il giudice") and not tagliato_dal_vecchio_limite(testo)
    assert repo.rileggi_allegati_tagliati(prova=True)["messaggi"] == 0
