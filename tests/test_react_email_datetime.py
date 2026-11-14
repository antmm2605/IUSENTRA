from web.services.react_email_bridge import _parse_datetime


def test_saved_html_status_describes_available_content_without_claiming_original_mime():
    from types import SimpleNamespace
    from pct.email_client import EmailRicevuta
    from web.services.react_email_bridge import _email_body_payload

    message = EmailRicevuta(id='controlled', oggetto='Email ordinaria', corpo_testo='Attività.', corpo_html='<p>Attività.</p>')
    manager = SimpleNamespace(leggi_eml_originale=lambda _message: b'')
    payload = _email_body_payload(message, manager)
    assert payload['bodyText'] == 'Attività.'
    assert payload['bodyCompleteness'] == 'testo_disponibile'
    assert 'versione grafica' in payload['bodyCompletenessLabel']
    assert 'MIME originale non è ancora acquisito' in payload['bodyCompletenessLabel']
    assert 'PEC' not in payload['bodyCompletenessLabel']


def test_pec_preview_prefers_readable_html_and_audit_reads_without_row_context(tmp_path):
    from pct.email_client import EmailRicevuta
    from web.services.react_email_bridge import _email_row, _pec_audit_summaries

    message = EmailRicevuta(id='controlled', oggetto='Prova', corpo_testo='Versione ridotta', corpo_html='<p>È stato inviato: attività.</p>')
    row = _email_row(message, include_telematic=True, include_provisional_audit=False)
    assert row['preview'] == 'È stato inviato: attività.'
    assert _pec_audit_summaries(str(tmp_path / 'studio.db'), [message]) == {}


def test_mime_alternatives_are_not_concatenated():
    from email.message import EmailMessage
    from web.services.react_email_bridge import _iter_message_display_parts

    message = EmailMessage()
    message.set_content('Versione solo testo')
    message.add_alternative('<p>Attività: è stato inviato.</p>', subtype='html')
    parts = _iter_message_display_parts(message)
    assert len(parts) == 1
    assert parts[0].get_content_type() == 'text/html'
    assert 'Attività' in parts[0].get_content()


def test_react_email_bridge_converte_arrivo_utc_in_ora_italiana():
    parsed = _parse_datetime("2026-06-28T19:30:19Z")

    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d %H:%M:%S") == "2026-06-28 21:30:19"


def test_pec_cestino_ricerca_rg_presente_solo_nell_esito_xml(tmp_path, monkeypatch):
    from email.message import EmailMessage

    from pct.email_client import EmailRicevuta, GestioneEmailRicevute
    from pct.pec_pipeline import PecAuditRepository
    from web.services.react_email_bridge import build_react_email_payload

    db_path = str(tmp_path / "casella.json")
    mailbox = GestioneEmailRicevute(db_path=db_path)
    monkeypatch.setattr("web.services.react_email_bridge.create_email_mailbox", lambda **kwargs: mailbox)
    repo = PecAuditRepository(tmp_path / "pec_audit.sqlite")
    for number in (1831, 11831, 1830):
        header = f"<esito-{number}@example.test>"
        mime = EmailMessage()
        mime["From"] = "tribunale.vicenza@civile.ptel.giustiziacert.it"
        mime["To"] = "studio@example.test"
        mime["Subject"] = "POSTA CERTIFICATA: ACCETTAZIONE DEPOSITO TELEMATICO: Ricorso.pdf"
        mime["Message-ID"] = header
        mime.set_content("Deposito accettato.")
        mime.add_attachment(
            f"<EsitoAtto><NumeroRuolo>{number}/2026</NumeroRuolo><CodiceEsito>2</CodiceEsito></EsitoAtto>".encode(),
            maintype="application", subtype="xml", filename="EsitoAtto.xml",
        )
        row = repo.ingest_mime(mime.as_bytes(), account_email="studio@example.test", folder="CESTINO", imap_uid=str(number))
        repo.parse_and_store(row["id"])
        if number == 1830:
            audit_only_id = row["id"]
            continue
        mailbox.aggiungi(EmailRicevuta(
            id=str(number), cartella="CESTINO", message_id=header,
            oggetto=str(mime["Subject"]), corpo_testo="Deposito accettato.",
        ))

    result = build_react_email_payload(db_path=db_path, folder="CESTINO", query="1831/2026")
    assert [item["id"] for item in result["items"]] == ["1831"]
    assert result["summary"]["filtered"] == 1
    assert build_react_email_payload(db_path=db_path, folder="INBOX", query="1831/2026")["items"] == []
    formatted = build_react_email_payload(db_path=db_path, folder="TUTTE", query="R.G. 001831 / 2026")
    assert [item["id"] for item in formatted["items"]] == ["1831"]
    audit_only = build_react_email_payload(db_path=db_path, folder="CESTINO", query="1830/2026")
    assert [item["id"] for item in audit_only["items"]] == [f"pec-audit:{audit_only_id}"]
