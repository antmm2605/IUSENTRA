"""PEC → documenti del fascicolo (richiesta dell'avvocato del 02/11/2026).

Una PEC collegata con certezza al fascicolo porta tra i documenti i provvedimenti allegati e, per le notifiche
in proprio, l'.eml della notifica e delle ricevute (L. 53/1994 art. 3-bis; art. 19-bis Provv. DGSIA 16/04/2014).
Dati di prova sintetici: nessun dato reale di clienti.
"""

from __future__ import annotations

import json
import uuid
from email import policy
from email.message import EmailMessage
from pathlib import Path

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.pec_fascicolo_documenti import conferma_collegamento, processa_messaggio, recupera_storico, stato_flusso
from pct.pec_fascicolo_documenti.classificazione import NOTIFICA, RICEVUTA_DEPOSITO, genere_messaggio, scegli_allegati
from pct.pec_pipeline import PecAuditRepository, canonical_json, iso_now

PDF_DECRETO = b"%PDF-1.4\n% decreto di fissazione udienza\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PDF_ORDINANZA = b"%PDF-1.4\n% ordinanza istruttoria\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _ambiente(tmp_path: Path, tenant: str = "studio-prova"):
    gestione = GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"), documents_dir=str(tmp_path / "docs"))
    fascicolo = gestione.nuovo(titolo="Rossi / Bianchi", tipo=TipoFascicolo.CIVILE, nome_cliente="Mario Rossi",
                               tribunale="Tribunale di Vicenza", numero_rg="523", anno_rg="2026")
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id=tenant, fascicoli_db_path=str(tmp_path / "fascicoli.json"),
                              fascicoli_docs_path=str(tmp_path / "docs"))
    return repo, fascicolo


def _documenti(tmp_path: Path, fascicolo_id: str):
    return GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"), documents_dir=str(tmp_path / "docs")).get(fascicolo_id).documenti


def _comunicazione(tag: str = "decreto", *, allegati: tuple[tuple[str, bytes], ...] = (("Decreto_153768904.pdf", PDF_DECRETO),)) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Per conto di: tribunale.vicenza@civile.ptel.giustiziacert.it <posta-certificata@giustiziacert.it>"
    msg["To"] = "studio@pec.example.test"
    msg["Subject"] = "POSTA CERTIFICATA: COMUNICAZIONE RG 523/2026"
    msg["Date"] = "Mon, 02 Nov 2026 00:30:00 +0100"
    msg["Message-ID"] = f"<comunicazione-{tag}@example.test>"
    msg.set_content("Comunicazione di cancelleria: decreto di fissazione dell'udienza.")
    for nome, dati in allegati:
        msg.add_attachment(dati, maintype="application", subtype="pdf", filename=nome)
    msg.add_attachment(b"<postacert tipo=\"posta-certificata\"/>", maintype="application", subtype="xml", filename="daticert.xml")
    msg.add_attachment(b"firma", maintype="application", subtype="pkcs7-signature", filename="smime.p7s")
    return msg.as_bytes(policy=policy.SMTP)


def _ingesta(repo: PecAuditRepository, mime: bytes, uid: str) -> str:
    esito = repo.ingest_mime(mime, account_email="studio@pec.example.test", folder="INBOX", imap_uid=uid, actor="pytest")
    repo.run_pending_jobs(limit=40)
    return str(esito["id"])


def _certifica(repo: PecAuditRepository, message_id: str, fascicolo_id: str, stato: str = "ruolo_certificato_ufficio") -> None:
    """Come la lettura del fascicolo quando l'ufficio cita il ruolo (web/services/fascicolo_lettura_verifiche)."""
    with repo.connect() as conn:
        versione = repo.latest_parsed_row(conn, message_id)
        conn.execute(
            "INSERT INTO pec_fascicolo_links (id, message_id, parsed_version_id, fascicolo_id, score, status, seeds_json, candidates_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, message_id, versione["id"], fascicolo_id, 1.0, stato, canonical_json({}), canonical_json([]), iso_now()),
        )
        conn.execute("UPDATE pec_messages SET linked_fascicolo_id=?, status='linked' WHERE id=?", (fascicolo_id, message_id))


def _eventi():
    ricevuti: list[tuple[str, int, bool]] = []
    return ricevuti, lambda fascicolo_id, nuovi, pec_nuova: ricevuti.append((fascicolo_id, nuovi, pec_nuova))


def test_pec_collegata_con_decreto_entra_nel_fascicolo_con_provenienza_ed_evento(tmp_path):
    repo, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _comunicazione(), "INBOX:UID:1")
    _certifica(repo, message_id, fascicolo.id)
    ricevuti, eventi = _eventi()

    esito = processa_messaggio(repo, message_id, eventi=eventi)

    assert esito["ok"] and esito["stato"] == "completato" and esito["salvati"] == 1 and esito["eml_salvati"] == 0
    [documento] = [doc for doc in _documenti(tmp_path, fascicolo.id) if doc.fonte_documento == "PEC_CANCELLERIA"]
    assert documento.nome_originale == "Decreto_153768904.pdf"
    assert documento.tipo == TipoDocumento.DECRETO  # catalogato dal nome e dalla comunicazione
    assert f"iusentra:pec:{message_id}" in documento.tags and "iusentra:pec-data:2026-11-02" in documento.tags
    assert "copia-informativa" in documento.tags and "Da PEC del 02/11/2026 (00:30, ora italiana)" in documento.note
    assert documento.data_documento == "2026-11-02"  # consegna alle 00:30 ora italiana: non il giorno UTC prima
    assert ricevuti == [(fascicolo.id, 1, True)]  # registro delle letture: inventario e lettura dei soli nuovi
    with repo.connect() as conn:
        motivi = {r["nome_originale"]: r["motivo"] for r in conn.execute("SELECT * FROM pec_fascicolo_documenti WHERE esito='scartato'")}
        audit = conn.execute("SELECT payload_json FROM pec_audit_log WHERE action='pec.fascicolo_documenti.salvati'").fetchall()
    assert motivi == {"daticert.xml": "daticert", "smime.p7s": "firma_gestore"}
    [prova] = [json.loads(row[0]) for row in audit]
    assert prova["documenti"][0]["sha256"] == documento.hash_contenuto_sha256 and prova["documenti"][0]["consegnata_il"] == "2026-11-02T00:30"


def test_stessa_pec_due_volte_e_documento_gia_scaricato_non_creano_doppioni(tmp_path):
    repo, fascicolo = _ambiente(tmp_path)
    # L'avvocato ha già caricato l'ordinanza dal portale: stessa impronta, nessun secondo documento.
    GestioneFascicoli(db_path=str(tmp_path / "fascicoli.json"), documents_dir=str(tmp_path / "docs")).aggiungi_documento(
        fascicolo.id, "ordinanza_dal_portale.pdf", TipoDocumento.ORDINANZA, PDF_ORDINANZA)
    message_id = _ingesta(repo, _comunicazione("doppia", allegati=(("Decreto.pdf", PDF_DECRETO), ("Ordinanza.pdf", PDF_ORDINANZA),
                                                                    ("Decreto copia.pdf", PDF_DECRETO))), "INBOX:UID:2")
    _certifica(repo, message_id, fascicolo.id)
    primo = processa_messaggio(repo, message_id, eventi=lambda *a: None)
    assert (primo["salvati"], primo["gia_presenti"]) == (1, 1)
    # Seconda elaborazione: già elaborata; anche forzando con la conferma nulla si duplica.
    assert processa_messaggio(repo, message_id, eventi=lambda *a: None)["stato"] == "gia_elaborato"
    terzo = processa_messaggio(repo, message_id, conferma_avvocato=True, eventi=lambda *a: None)
    assert (terzo["salvati"], terzo["gia_presenti"]) == (0, 2)
    impronte = [doc.hash_contenuto_sha256 or doc.hash_sha256 for doc in _documenti(tmp_path, fascicolo.id)]
    assert len(impronte) == len(set(impronte)) == 2


def test_collegamento_proposto_non_salva_nulla_fino_alla_conferma(tmp_path):
    repo, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _comunicazione("proposta"), "INBOX:UID:3")
    _certifica(repo, message_id, fascicolo.id, stato="automatico")  # collegamento non certificato
    esito = processa_messaggio(repo, message_id, eventi=lambda *a: None)
    assert esito["stato"] == "in_attesa_conferma" and not _documenti(tmp_path, fascicolo.id)
    assert stato_flusso(repo)["in_attesa_conferma"] == 1
    # Il recupero non lo riprende finché il linker non scrive un esito nuovo.
    assert recupera_storico(repo, limite=10, eventi=lambda *a: None)["esaminati"] == 0

    confermato = conferma_collegamento(repo, message_id, fascicolo.id, actor="avvocato", eventi=lambda *a: None)
    assert confermato["stato"] == "completato" and confermato["salvati"] == 1
    with repo.connect() as conn:
        stati = [r[0] for r in conn.execute("SELECT status FROM pec_fascicolo_links WHERE message_id=? ORDER BY rowid", (message_id,))]
    assert stati[-1] == "manuale"
    assert stato_flusso(repo)["in_attesa_conferma"] == 0


def test_collegamento_certificato_ad_altro_fascicolo_non_si_sovrascrive(tmp_path):
    repo, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _comunicazione("altro"), "INBOX:UID:4")
    _certifica(repo, message_id, fascicolo.id)
    assert conferma_collegamento(repo, message_id, "ALTRO", eventi=lambda *a: None)["stato"] == "collegamento_certificato_ad_altro_fascicolo"


def test_link_fascicolo_porta_i_documenti_quando_il_collegamento_e_certificato(tmp_path):
    repo, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _comunicazione("linker"), "INBOX:UID:5")
    _certifica(repo, message_id, fascicolo.id)
    risultato = repo.link_fascicolo(message_id, actor="pytest")  # il linker conserva il certificato e chiude il flusso
    assert risultato["fascicolo_documents"]["stato"] == "completato"
    assert [doc.nome_originale for doc in _documenti(tmp_path, fascicolo.id) if f"iusentra:pec:{message_id}" in doc.tags] == ["Decreto_153768904.pdf"]


def test_recupero_storico_limitato_e_riprendibile(tmp_path):
    repo, fascicolo = _ambiente(tmp_path)
    ids = []
    for indice in range(5):
        pdf = PDF_DECRETO.replace(b"decreto", f"decreto {indice}".encode())
        ids.append(_ingesta(repo, _comunicazione(f"storico-{indice}", allegati=((f"Decreto_{indice}.pdf", pdf),)), f"INBOX:UID:1{indice}"))
        _certifica(repo, ids[-1], fascicolo.id)
    primo = recupera_storico(repo, limite=2, eventi=lambda *a: None)
    assert (primo["esaminati"], primo["salvati"], primo["restano"], primo["ok"]) == (2, 2, 3, True)
    secondo = recupera_storico(repo, limite=2, eventi=lambda *a: None)
    terzo = recupera_storico(repo, limite=2, eventi=lambda *a: None)
    assert (secondo["restano"], terzo["esaminati"], terzo["restano"]) == (1, 1, 0)
    assert recupera_storico(repo, limite=2, eventi=lambda *a: None)["esaminati"] == 0
    stato = stato_flusso(repo)
    assert (stato["pec_collegate"], stato["messaggi_completati"], stato["documenti_salvati"], stato["da_elaborare"]) == (5, 5, 5, 0)
    assert stato["ultimo_giro"]["origine"] == "recupero" and stato["ultimo_giro"]["esito"]["restano"] == 0
    assert stato["scartati_per_motivo"]["daticert"] == 5


def test_isolamento_tra_studi(tmp_path):
    repo_a, fascicolo_a = _ambiente(tmp_path / "a", tenant="studio-a")
    repo_b, _fascicolo_b = _ambiente(tmp_path / "b", tenant="studio-b")
    message_id = _ingesta(repo_a, _comunicazione("isolamento"), "INBOX:UID:20")
    _certifica(repo_a, message_id, fascicolo_a.id)
    assert recupera_storico(repo_b, limite=10, eventi=lambda *a: None)["esaminati"] == 0
    assert processa_messaggio(repo_b, message_id, eventi=lambda *a: None)["stato"] == "messaggio_non_trovato"
    assert recupera_storico(repo_a, limite=10, eventi=lambda *a: None)["salvati"] == 1
    assert stato_flusso(repo_b)["documenti_salvati"] == 0 and not _documenti(tmp_path / "b", _fascicolo_b.id)
    # Stesso database condiviso da due studi: ciascuno vede solo le proprie PEC.
    repo_c = PecAuditRepository(tmp_path / "a" / "pec_audit.sqlite", tenant_id="studio-c", fascicoli_db_path=str(tmp_path / "a" / "fascicoli.json"),
                                fascicoli_docs_path=str(tmp_path / "a" / "docs"))
    assert stato_flusso(repo_c)["pec_collegate"] == 0 and recupera_storico(repo_c, limite=10, eventi=lambda *a: None)["esaminati"] == 0


def test_daticert_involucro_e_ricevute_di_deposito_restano_fuori_con_il_motivo():
    salvare, scarti = scegli_allegati([("daticert.xml", b"<x/>"), ("smime.p7s", b"f"), ("Comunicazione.xml", b"<c/>"),
                                       ("postacert.eml", b"From: a"), ("logo.png", b"img"), ("Sentenza.pdf.p7m", b"firmata")],
                                      genere=NOTIFICA)
    assert [a.nome for a in salvare] == ["Sentenza.pdf.p7m"]  # originale firmato conservato
    assert {s.nome: s.motivo for s in scarti} == {"daticert.xml": "daticert", "smime.p7s": "firma_gestore", "Comunicazione.xml": "xml_tecnico",
                                                  "postacert.eml": "involucro_postacert", "logo.png": "formato_non_documentale"}
    assert genere_messaggio("ACCETTAZIONE: DEPOSITO TELEMATICO - Memoria - RG 1/2026", [], "rac") == RICEVUTA_DEPOSITO
    assert genere_messaggio("POSTA CERTIFICATA: Notificazione ai sensi della legge n. 53 del 1994", [], "") == NOTIFICA


def _notifica_con_rdac(tmp_path: Path):
    """Presidio notifiche dello studio con l'invio registrato e la RdAC completa (con postacert.eml) in arrivo."""
    from pct.pec_notification_presidio import NotificationPresidioRepository, NotificationPresidioService, NotificationReceiptEnvelope, PecNotificationReconciler, ReceiptKind

    repo, fascicolo = _ambiente(tmp_path, tenant="tenant-notifiche-test")
    presidi = NotificationPresidioRepository(tmp_path / "pec_audit.sqlite", tenant_id="tenant-notifiche-test")
    destinatario = {"name": "Controparte di prova", "role": "controparte", "pec_address": "controparte@pec.example.test", "fiscal_id": "00000000000"}
    presidio_id = str(NotificationPresidioService(presidi).create_candidate({
        "fascicolo_id": fascicolo.id, "source_message_id": "atto-da-notificare", "source_effective_at": "2026-10-30T10:00:00+01:00",
        "trigger_type": "EXPLICIT_NOTIFICATION_ORDER", "notification_case": "notifica_l53", "rulepack_version": "pytest", "priority": "P1",
        "confidence": 1, "detection_reason": "Notifica L. 53/1994 preparata dallo studio.",
        "documents": [{"content_sha256": "b" * 64, "original_filename": "atto.pdf"}], "recipients": [destinatario],
    })["id"])
    inviato = "<notifica-inviata@example.test>"
    PecNotificationReconciler(presidi).process(NotificationReceiptEnvelope(
        kind=ReceiptKind.SENT, message_id=inviato, presidio_id=presidio_id, recipient_address=destinatario["pec_address"],
        recipient_name=destinatario["name"], recipient_fiscal_id=destinatario["fiscal_id"], occurred_at="2026-10-30T10:30:00+01:00"))
    originale = EmailMessage()
    originale["Subject"] = "Notificazione ai sensi della legge n. 53 del 1994 [Notifica_ID:ProvaRdac]"
    originale["Message-ID"] = inviato
    originale.set_content("Notificazione in proprio.")
    originale.add_attachment(PDF_DECRETO, maintype="application", subtype="pdf", filename="atto_notificato.pdf")
    rdac = EmailMessage()
    rdac["Subject"] = "CONSEGNA: Notificazione ai sensi della legge n. 53 - 1994 e succ. mod. [Notifica_ID:ProvaRdac]"
    rdac["From"] = "posta-certificata@pec.example.test"
    rdac["To"] = "studio@pec.example.test"
    rdac["Date"] = "Fri, 30 Oct 2026 10:31:00 +0100"
    rdac["Message-ID"] = "<rdac-prova@example.test>"
    rdac["X-Riferimento-Message-ID"] = inviato
    rdac.set_content("Ricevuta completa di avvenuta consegna.")
    rdac.add_attachment(("<postacert><tipo>avvenuta-consegna</tipo><msgid>notifica-inviata@example.test</msgid>"
                         "<destinatario>controparte@pec.example.test</destinatario></postacert>"), subtype="xml", filename="daticert.xml")
    rdac.add_attachment(originale.as_bytes(policy=policy.SMTP), maintype="message", subtype="rfc822", filename="postacert.eml")
    return repo, fascicolo, presidi, presidio_id, rdac.as_bytes(policy=policy.SMTP)


def test_rdac_completa_eml_nel_fascicolo_e_prova_visibile_al_presidio(tmp_path):
    repo, fascicolo, presidi, presidio_id, mime = _notifica_con_rdac(tmp_path)
    message_id = _ingesta(repo, mime, "INBOX:UID:30")
    _certifica(repo, message_id, fascicolo.id, stato="ricevuta_identificativi_verificati")
    esito = processa_messaggio(repo, message_id, eventi=lambda *a: None)
    assert esito["stato"] == "completato" and esito["genere"] == "ricevuta_notifica"
    eml = [doc for doc in _documenti(tmp_path, fascicolo.id) if doc.nome.endswith(".eml")]
    assert len(eml) == 1 and eml[0].tipo == TipoDocumento.NOTIFICA and "receipt_kind: RdAC" in eml[0].note
    assert eml[0].hash_contenuto_sha256  # impronta dell'.eml originale, prova della consegna
    # L'atto dentro la ricevuta non diventa un documento nuovo: la prova è l'.eml.
    assert not [doc for doc in _documenti(tmp_path, fascicolo.id) if doc.nome_originale == "atto_notificato.pdf"]
    with presidi.connection() as conn:
        ruoli = {r["document_role"]: r["fascicolo_document_id"] for r in conn.execute(
            "SELECT document_role, fascicolo_document_id FROM pec_legal_notification_documents WHERE presidio_id=?", (presidio_id,))}
    assert ruoli.get("rdac") == eml[0].id
    # Rielaborazione: nessun secondo .eml.
    processa_messaggio(repo, message_id, conferma_avvocato=True, eventi=lambda *a: None)
    assert len([doc for doc in _documenti(tmp_path, fascicolo.id) if doc.nome.endswith(".eml")]) == 1


def test_ricevuta_di_notifica_senza_presidio_conserva_l_eml_con_il_marcatore_del_presidio(tmp_path):
    repo, fascicolo, _presidi, _presidio_id, mime = _notifica_con_rdac(tmp_path)
    mime = mime.replace(b"ProvaRdac", b"AltraNotifica").replace(b"notifica-inviata@example.test", b"notifica-esterna@example.test")
    message_id = _ingesta(repo, mime, "INBOX:UID:31")
    _certifica(repo, message_id, fascicolo.id, stato="manuale")
    assert processa_messaggio(repo, message_id, eventi=lambda *a: None)["eml_salvati"] == 1
    [eml] = [doc for doc in _documenti(tmp_path, fascicolo.id) if doc.nome.endswith(".eml")]
    # Lo stesso marcatore della riconciliazione: se la notifica si abbina più tardi, il documento si riusa.
    assert f"IUSENTRA_LEGAL_NOTIFICATION_RECEIPT:{message_id}" in eml.note and "receipt_kind: RdAC" in eml.note
    assert {"notifica-legale", "rdac"} <= set(eml.tags) and eml.fonte_documento == "PEC_AUDIT_NOTIFICATION_RECEIPT"


def test_origine_da_pec_nella_scheda_documenti(tmp_path):
    from types import SimpleNamespace

    from web.services.pec_origine_documento import origine_pec

    repo, fascicolo = _ambiente(tmp_path)
    message_id = _ingesta(repo, _comunicazione("origine"), "INBOX:UID:40")
    _certifica(repo, message_id, fascicolo.id)
    processa_messaggio(repo, message_id, eventi=lambda *a: None)
    [documento] = _documenti(tmp_path, fascicolo.id)
    assert origine_pec(documento) == {"label": "da PEC del 02/11/2026", "href": f"/email/?audit_id={message_id}"}
    # Documenti salvati prima del flusso: fonte PEC e riferimento interno del messaggio.
    vecchio = SimpleNamespace(tags=[], fonte_documento="PEC_CANCELLERIA", msg_id_portale="abc123#ffff", data_documento="2026-10-29")
    assert origine_pec(vecchio) == {"label": "da PEC del 29/10/2026", "href": "/email/?audit_id=abc123"}
    assert origine_pec(SimpleNamespace(tags=["contratto"], fonte_documento="CARICAMENTO_STUDIO", msg_id_portale="")) is None


def test_esito_della_pianificazione_notturna_solo_conteggi(tmp_path):
    from web.services.pec_fascicolo_documenti_runtime import recupero_per_studi, stato_per_studi

    repo, fascicolo = _ambiente(tmp_path, tenant="studio-notte")
    message_id = _ingesta(repo, _comunicazione("notte"), "INBOX:UID:50")
    _certifica(repo, message_id, fascicolo.id)
    percorsi = {"EMAIL_CASELLA_DB": str(tmp_path / "casella.json"), "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
                "FASCICOLI_DOCS": str(tmp_path / "docs")}
    report = recupero_per_studi([("studio-notte", percorsi)], limite=10)
    assert report["ok"] is True and report["job"] == "pec_fascicolo_documenti_recupero"
    assert (report["totals"]["salvati"], report["totals"]["restano"], report["totals"]["errori"]) == (1, 0, 0)
    [stato] = stato_per_studi([("studio-notte", percorsi)])
    assert stato["documenti_salvati"] == 1 and stato["ultimo_giro"]["esito"]["salvati"] == 1
    # Solo numeri e date tecniche: nessun nome di file, cliente o indirizzo nel testo dell'esito.
    testo = json.dumps([report, stato])
    assert "Decreto" not in testo and "@" not in testo and "Rossi" not in testo
