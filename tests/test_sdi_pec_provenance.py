from email.message import EmailMessage
from email import policy
import hashlib

import pytest

from pct.sdi_pec_provenance import _attested_content
from pct.sdi_pec_trust import PecTrustError


def certified_content(*, original_id="pec-id@gestore.invalid", certified_id="pec-id@gestore.invalid", client_id="client-id@client.invalid", sender="sdi24@pec.fatturapa.it", recipient="studio@studio.invalid"):
    original = EmailMessage()
    original["From"] = sender
    original["To"] = recipient
    original["Message-ID"] = f"<{original_id}>"
    original.set_content("Ricevuta di prova")
    receipt = b'<RicevutaConsegna xmlns="http://www.fatturapa.gov.it/sdi/messaggi/v1.0" />'
    original.add_attachment(receipt, maintype="application", subtype="xml", filename="receipt.xml")
    outer = EmailMessage()
    outer.set_content("Contenuto certificato di prova")
    xml = f'''<postacert tipo="posta-certificata" errore="nessuno"><intestazione><mittente>{sender}</mittente><destinatari tipo="certificato">{recipient}</destinatari></intestazione><dati><identificativo>{certified_id}</identificativo><msgid>{client_id}</msgid></dati></postacert>'''.encode()
    outer.add_attachment(xml, maintype="application", subtype="xml", filename="daticert.xml")
    outer.add_attachment(original, filename="postacert.eml")
    return outer.as_bytes(policy=policy.SMTP), receipt


def test_pec_identifier_matches_after_provider_replaces_client_message_id():
    content, receipt = certified_content()
    result = _attested_content(content, "studio@studio.invalid")
    assert result["original_message_id"] == "pec-id@gestore.invalid"
    assert result["certified_message_id"] == "pec-id@gestore.invalid"
    assert result["receipt_hashes"] == [hashlib.sha256(receipt).hexdigest()]


@pytest.mark.parametrize("values", [
    {"original_id": "different@gestore.invalid"},
    {"certified_id": ""},
    {"original_id": "client-id@client.invalid"},
])
def test_client_message_id_cannot_replace_certified_identity(values):
    content, _ = certified_content(**values)
    with pytest.raises(PecTrustError) as exc:
        _attested_content(content, "studio@studio.invalid")
    assert exc.value.code == "original_message_mismatch"


@pytest.mark.parametrize("values,code", [
    ({"sender": "sdi24@pec.fatturapa.it.attacker.invalid"}, "sdi_sender_mismatch"),
    ({"recipient": "other@studio.invalid"}, "sdi_recipient_mismatch"),
])
def test_same_identifier_does_not_bypass_sender_or_recipient(values, code):
    content, _ = certified_content(**values)
    with pytest.raises(PecTrustError) as exc:
        _attested_content(content, "studio@studio.invalid")
    assert exc.value.code == code
